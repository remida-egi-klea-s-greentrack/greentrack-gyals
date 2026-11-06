from types import SimpleNamespace

import pytest

from data.run_pipeline import GLUE_IMAGE, build_steps, run_pipeline


class FakeRun:
    """Records every command instead of running it; can pretend one step fails."""

    def __init__(self, fail_on=None):
        self.commands = []
        self.fail_on = fail_on

    def __call__(self, command, cwd=None):
        self.commands.append(command)
        failed = self.fail_on is not None and any(self.fail_on in part for part in command)
        return SimpleNamespace(returncode=1 if failed else 0)


@pytest.fixture
def raw_file(tmp_path):
    path = tmp_path / "household_power_consumption.txt"
    path.write_text("Date;Time\n")
    return path


def test_steps_run_in_order_bronze_silver_gold(raw_file):
    fake = FakeRun()
    run_pipeline(raw_file, run=fake)

    scripts = [command[-1] for command in fake.commands]
    assert scripts[0] == str(raw_file)                     # bronze gets the raw file
    assert scripts[1].endswith("data/jobs/silver_clean.py")
    assert scripts[2].endswith("data/jobs/gold_aggregate.py")


def test_bronze_runs_locally_and_spark_jobs_run_in_glue_image(raw_file):
    steps = dict(build_steps(raw_file))
    assert "bronze_ingest.py" in steps["bronze"][1]
    for name in ("silver", "gold"):
        assert steps[name][:2] == ["docker", "run"]
        assert GLUE_IMAGE in steps[name]
        assert "spark-submit" in steps[name]


def test_pipeline_stops_at_first_failed_step(raw_file):
    fake = FakeRun(fail_on="silver_clean.py")

    with pytest.raises(RuntimeError, match="silver step failed"):
        run_pipeline(raw_file, run=fake)

    assert len(fake.commands) == 2  # bronze and silver ran, gold never started


def test_missing_raw_file_is_reported_before_anything_runs(tmp_path):
    fake = FakeRun()
    with pytest.raises(FileNotFoundError):
        run_pipeline(tmp_path / "does_not_exist.txt", run=fake)
    assert fake.commands == []
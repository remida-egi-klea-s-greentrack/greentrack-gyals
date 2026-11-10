"""DATA-05: Run the whole local pipeline (bronze -> silver -> gold) with one command.

Usage, from the repository root:
    python data/run_pipeline.py                                   (uses data/raw/household_power_consumption.txt)
    python data/run_pipeline.py data/raw/some_other_file.txt
"""
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GLUE_IMAGE = "public.ecr.aws/glue/aws-glue-libs:5"
DEFAULT_RAW_FILE = REPO / "data" / "raw" / "household_power_consumption.txt"


def glue_command(script_name: str) -> list[str]:
    """The docker command that runs one Spark job inside the AWS Glue 5 image."""
    return [
        "docker", "run", "--rm",
        "-v", f"{REPO}:/home/hadoop/workspace/",
        GLUE_IMAGE,
        "spark-submit", "--driver-memory", "2g",
        f"/home/hadoop/workspace/data/jobs/{script_name}",
    ]


def build_steps(raw_file: Path) -> list[tuple[str, list[str]]]:
    return [
        ("bronze", [sys.executable, str(REPO / "data" / "jobs" / "bronze_ingest.py"), str(raw_file)]),
        ("silver", glue_command("silver_clean.py")),
        ("gold", glue_command("gold_aggregate.py")),
    ]


def run_pipeline(raw_file: Path, run=subprocess.run) -> None:
    """Run bronze, silver and gold one after the other; stop at the first failure."""
    raw_file = Path(raw_file)
    if not raw_file.exists():
        raise FileNotFoundError(f"Raw file not found: {raw_file}")

    for name, command in build_steps(raw_file):
        print(f"\n===== {name.upper()} =====", flush=True)
        started = time.time()
        result = run(command, cwd=REPO)
        if result.returncode != 0:
            raise RuntimeError(f"Pipeline stopped: the {name} step failed (exit code {result.returncode})")
        print(f"{name} finished in {time.time() - started:.0f}s", flush=True)

    print("\n===== PIPELINE COMPLETE =====")
    print("Gold tables: data/lakehouse/warehouse/gold/  |  exports: data/lakehouse/exports/")


if __name__ == "__main__":
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RAW_FILE
    run_pipeline(raw)
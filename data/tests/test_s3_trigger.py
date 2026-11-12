"""Tests for the new-file trigger: event parsing, a fake S3 client, and moto's mock S3."""
import os

import pytest

from data.s3_trigger import handle_new_file_event, make_s3_event, parse_new_files

BUCKET = "greentrack-bronze-test"
REGION = "eu-central-1"


class FakeS3:
    """Pretends to be an S3 client: 'downloads' by writing a small file."""

    def __init__(self):
        self.downloads = []

    def download_file(self, bucket, key, filename):
        self.downloads.append((bucket, key))
        with open(filename, "w") as f:
            f.write("Date;Time\n")


class FakeRunner:
    def __init__(self):
        self.files = []

    def __call__(self, raw_file):
        self.files.append(raw_file)


# ---------- Event parsing ----------

def test_parses_s3_notification():
    event = make_s3_event(BUCKET, "incoming/household_power_consumption.txt")
    assert parse_new_files(event) == [(BUCKET, "incoming/household_power_consumption.txt")]


def test_parses_eventbridge_event():
    event = {
        "source": "aws.s3",
        "detail-type": "Object Created",
        "detail": {"bucket": {"name": BUCKET}, "object": {"key": "incoming/new.csv"}},
    }
    assert parse_new_files(event) == [(BUCKET, "incoming/new.csv")]


def test_decodes_spaces_in_keys():
    event = make_s3_event(BUCKET, "incoming/my+new+file.txt")
    assert parse_new_files(event) == [(BUCKET, "incoming/my new file.txt")]


@pytest.mark.parametrize("key", ["incoming/", "incoming/notes.json", "incoming/photo.png"])
def test_ignores_folders_and_non_data_files(key):
    assert parse_new_files(make_s3_event(BUCKET, key)) == []


def test_ignores_deletions():
    event = make_s3_event(BUCKET, "incoming/data.txt")
    event["Records"][0]["eventName"] = "ObjectRemoved:Delete"
    assert parse_new_files(event) == []


def test_rejects_events_that_are_not_from_s3():
    with pytest.raises(ValueError):
        parse_new_files({"hello": "world"})


# ---------- Handler with a simple fake S3 ----------

def test_handler_downloads_file_and_runs_pipeline(tmp_path):
    s3, runner = FakeS3(), FakeRunner()
    event = make_s3_event(BUCKET, "incoming/household_power_consumption.txt")

    result = handle_new_file_event(event, s3_client=s3, raw_dir=tmp_path, run=runner)

    expected = tmp_path / "household_power_consumption.txt"
    assert s3.downloads == [(BUCKET, "incoming/household_power_consumption.txt")]
    assert runner.files == [expected]
    assert expected.exists()
    assert result == {"processed": [str(expected)]}


def test_handler_cannot_write_outside_raw_dir(tmp_path):
    raw_dir = tmp_path / "raw"
    s3, runner = FakeS3(), FakeRunner()

    handle_new_file_event(make_s3_event(BUCKET, "../../evil.txt"), s3_client=s3, raw_dir=raw_dir, run=runner)

    assert runner.files == [raw_dir / "evil.txt"]


def test_handler_does_nothing_for_ignored_files(tmp_path):
    s3, runner = FakeS3(), FakeRunner()
    result = handle_new_file_event(make_s3_event(BUCKET, "incoming/readme.json"),
                                   s3_client=s3, raw_dir=tmp_path, run=runner)
    assert result == {"processed": []}
    assert s3.downloads == [] and runner.files == []


# ---------- Handler with moto's mock S3 (real boto3 calls, fake AWS) ----------

@pytest.fixture
def mock_s3():
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        os.environ[name] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION
    with moto.mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
        yield client


def test_handler_with_mock_s3_downloads_the_real_content(mock_s3, tmp_path):
    content = "Date;Time;Global_active_power\n16/12/2006;17:24:00;4.216\n"
    mock_s3.put_object(Bucket=BUCKET, Key="incoming/sample.txt", Body=content.encode())
    runner = FakeRunner()

    handle_new_file_event(make_s3_event(BUCKET, "incoming/sample.txt"),
                          s3_client=mock_s3, raw_dir=tmp_path, run=runner)

    assert (tmp_path / "sample.txt").read_text() == content
    assert runner.files == [tmp_path / "sample.txt"]


def test_handler_with_mock_s3_fails_clearly_for_missing_object(mock_s3, tmp_path):
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        handle_new_file_event(make_s3_event(BUCKET, "incoming/missing.txt"),
                              s3_client=mock_s3, raw_dir=tmp_path, run=FakeRunner())
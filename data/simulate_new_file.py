"""DATA-05: Simulate "a new CSV lands in the bronze bucket" end to end, without AWS.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

from data.s3_trigger import handle_new_file_event, make_s3_event  # noqa: E402

BUCKET = "greentrack-bronze-local"
REGION = "eu-central-1"
DEFAULT_RAW_FILE = REPO / "data" / "raw" / "household_power_consumption.txt"


def main():
    raw_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RAW_FILE
    if not raw_file.exists():
        raise FileNotFoundError(f"Raw file not found: {raw_file}")

    # Fake credentials: moto never talks to real AWS, but boto3 wants something to sign with.
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        os.environ[name] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION

    with mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})

        key = f"incoming/{raw_file.name}"
        s3.upload_file(str(raw_file), BUCKET, key)
        print(f"[fake S3] uploaded {raw_file.name} to s3://{BUCKET}/{key}")

        event = make_s3_event(BUCKET, key)
        print("[fake S3] new-file event sent to the handler")

        result = handle_new_file_event(event, s3_client=s3, raw_dir=REPO / "data" / "raw" / "from_s3")
        print(f"\nProcessed: {result['processed']}")


if __name__ == "__main__":
    main()
"""DATA-05: React to "a new file landed in the bronze bucket" and start the pipeline.

On AWS (DATA-07) the event will come from S3/EventBridge. Locally we build the same
event by hand and use a fake S3 (moto), so the logic is tested before the cloud exists.
"""
from pathlib import Path
from urllib.parse import unquote_plus

REPO = Path(__file__).resolve().parents[1]
RAW_DIR = REPO / "data" / "raw"
ALLOWED_SUFFIXES = (".txt", ".csv")


def make_s3_event(bucket: str, key: str) -> dict:
    """A minimal S3 'ObjectCreated' notification, shaped like the real one."""
    return {
        "Records": [{
            "eventSource": "aws:s3",
            "eventName": "ObjectCreated:Put",
            "s3": {"bucket": {"name": bucket}, "object": {"key": key}},
        }]
    }


def parse_new_files(event: dict) -> list[tuple[str, str]]:
    """Return (bucket, key) for every new data file in the event.

    Understands both formats AWS can send:
    - S3 event notifications:  {"Records": [{"s3": {...}}]}
    - EventBridge events:      {"source": "aws.s3", "detail": {"bucket": ..., "object": ...}}
    Folders and non-data files (e.g. .json, .png) are ignored.
    """
    candidates = []

    if event.get("source") == "aws.s3" and "detail" in event:
        if event.get("detail-type") == "Object Created":
            detail = event["detail"]
            candidates.append((detail["bucket"]["name"], detail["object"]["key"]))
    else:
        records = event.get("Records")
        if not records:
            raise ValueError("Not an S3 event: no 'Records' and no EventBridge 'detail'")
        for record in records:
            if record.get("eventSource") != "aws:s3":
                continue
            if not record.get("eventName", "").startswith("ObjectCreated"):
                continue
            candidates.append((record["s3"]["bucket"]["name"], record["s3"]["object"]["key"]))

    new_files = []
    for bucket, key in candidates:
        key = unquote_plus(key)  # S3 sends "my file.txt" as "my+file.txt"
        if key.endswith("/") or not key.lower().endswith(ALLOWED_SUFFIXES):
            continue
        new_files.append((bucket, key))
    return new_files


def handle_new_file_event(event: dict, s3_client=None, raw_dir: Path = RAW_DIR, run=None) -> dict:
    """Download each new file from S3 into raw_dir, then run the pipeline on it."""
    if s3_client is None:
        import boto3
        s3_client = boto3.client("s3")
    if run is None:
        from data.run_pipeline import run_pipeline as run

    processed = []
    for bucket, key in parse_new_files(event):
        raw_dir.mkdir(parents=True, exist_ok=True)
        # Keep only the file name, so a key like "../../x.txt" can't write outside raw_dir.
        local_file = raw_dir / Path(key).name
        s3_client.download_file(bucket, key, str(local_file))
        print(f"Downloaded s3://{bucket}/{key} -> {local_file}")
        run(local_file)
        processed.append(str(local_file))

    return {"processed": processed}
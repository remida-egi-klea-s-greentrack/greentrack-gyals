"""App configuration from SSM Parameter Store.

On AWS the Lambda gets only CONFIG_SSM_PATH (e.g. /g2-greentrack-production/api); every parameter under it
(HOUSEHOLD_ID, GOLD_BUCKET, DYNAMODB_TABLE_*, ...) is copied into os.environ once per container, so the
adapters keep reading os.environ. Locally CONFIG_SSM_PATH is unset and nothing happens.
Variables: path - SSM path; params - {name: value} read from SSM.
"""
import os


def read_parameters(client, path):
    """All parameters directly under `path` as {short name: value} (follows pagination)."""
    params, token = {}, None
    while True:
        kwargs = {"Path": path, "Recursive": False}
        if token:
            kwargs["NextToken"] = token
        page = client.get_parameters_by_path(**kwargs)
        for p in page.get("Parameters", []):
            params[p["Name"].rsplit("/", 1)[-1]] = p["Value"]
        token = page.get("NextToken")
        if not token:
            return params


def load_ssm_config(client=None):
    """Copy the SSM parameters into os.environ; returns how many were loaded (0 when not configured)."""
    path = os.environ.get("CONFIG_SSM_PATH")
    if not path:
        return 0
    try:
        if client is None:
            import boto3
            client = boto3.client("ssm")
        params = read_parameters(client, path)
    except Exception as e:  # the handlers fall back to fixtures when config is missing
        print(f"WARN could not read config from SSM {path}: {e}")
        return 0
    os.environ.update(params)
    print(f"Loaded {len(params)} config values from SSM {path}")
    return len(params)

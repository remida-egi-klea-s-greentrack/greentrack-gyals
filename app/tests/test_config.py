"""SSM Parameter Store configuration (app/adapters/config.py)."""
import os
import unittest
from unittest.mock import patch

from app.adapters.config import load_ssm_config, read_parameters


class FakeSsm:
    """Two pages of parameters, like get_parameters_by_path with NextToken."""

    def __init__(self):
        self.calls = []

    def get_parameters_by_path(self, **kwargs):
        self.calls.append(kwargs)
        if "NextToken" not in kwargs:
            return {"Parameters": [{"Name": "/p/api/HOUSEHOLD_ID", "Value": "household-1"}], "NextToken": "t"}
        return {"Parameters": [{"Name": "/p/api/DYNAMODB_TABLE_FORECASTS", "Value": "p-forecasts"}]}


class ConfigTest(unittest.TestCase):
    def test_reads_all_pages_with_short_names(self):
        ssm = FakeSsm()
        self.assertEqual(read_parameters(ssm, "/p/api"),
                         {"HOUSEHOLD_ID": "household-1", "DYNAMODB_TABLE_FORECASTS": "p-forecasts"})
        self.assertEqual(ssm.calls[0]["Path"], "/p/api")

    @patch.dict(os.environ, {"CONFIG_SSM_PATH": "/p/api"}, clear=False)
    def test_copies_parameters_into_environment(self):
        os.environ.pop("DYNAMODB_TABLE_FORECASTS", None)
        self.assertEqual(load_ssm_config(FakeSsm()), 2)
        self.assertEqual(os.environ["DYNAMODB_TABLE_FORECASTS"], "p-forecasts")

    @patch.dict(os.environ, {}, clear=False)
    def test_no_path_means_no_call(self):
        os.environ.pop("CONFIG_SSM_PATH", None)
        self.assertEqual(load_ssm_config(FakeSsm()), 0)

    @patch.dict(os.environ, {"CONFIG_SSM_PATH": "/p/api"}, clear=False)
    def test_ssm_error_is_reported_not_raised(self):
        class Broken:
            def get_parameters_by_path(self, **kwargs):
                raise RuntimeError("AccessDenied")
        self.assertEqual(load_ssm_config(Broken()), 0)


if __name__ == "__main__":
    unittest.main()

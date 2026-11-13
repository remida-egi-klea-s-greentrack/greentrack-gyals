"""Tests for gold layer integration."""
import json
import unittest
import unittest.mock
from unittest.mock import patch

import pandas as pd  # used by MLForecastTest (local-only adapter)


class GoldLoaderTest(unittest.TestCase):
    """Tests for gold_loader module."""
    
    HOURLY_CSV = (
        "timestamp,global_active_power_kwh,sub_metering_1_kwh,sub_metering_2_kwh,"
        "sub_metering_3_kwh,minutes_recorded,complete\n"
        "2024-01-01T00:00:00,1.5,0.5,0.3,0.2,60,true\n"
        "2024-01-01T01:00:00,6.5,0.6,0.4,0.3,60,true\n"
        "2024-01-01T02:00:00,,,,,12,false\n"
    )

    def setUp(self):
        from app.adapters import gold_loader
        gold_loader._cache.clear()

    @patch("app.adapters.gold_loader._read_csv_text_from_s3")
    def test_load_hourly_consumption_returns_records(self, mock_s3):
        """Test that hourly consumption is parsed from CSV and incomplete hours dropped."""
        from app.adapters.gold_loader import load_hourly_consumption

        mock_s3.return_value = self.HOURLY_CSV

        records = load_hourly_consumption(limit=10)

        mock_s3.assert_called_once_with("gold_hourly_consumption")
        self.assertIsInstance(records, list, "Should return a list")
        self.assertEqual(len(records), 2, "Should drop the incomplete hour")
        self.assertEqual(records[0]["timestamp"], "2024-01-01T00:00:00")
        self.assertEqual(records[0]["global_active_power_kwh"], 1.5)
        self.assertEqual(records[0]["minutes_recorded"], 60)
        self.assertTrue(records[0]["complete"], "Record should be marked as complete")

    @patch("app.adapters.gold_loader._read_csv_text_local")
    @patch("app.adapters.gold_loader._read_csv_text_from_s3")
    def test_falls_back_to_local_csv(self, mock_s3, mock_local):
        """If S3 fails, the local CSV export is used."""
        from app.adapters.gold_loader import load_hourly_consumption

        mock_s3.side_effect = RuntimeError("no creds")
        mock_local.return_value = self.HOURLY_CSV

        self.assertEqual(len(load_hourly_consumption()), 2)

    @patch("app.adapters.gold_loader._read_csv_text_from_s3")
    def test_detect_anomalies_finds_high_consumption(self, mock_s3):
        """Test that anomaly detection finds high consumption hours."""
        from app.adapters.gold_loader import detect_anomalies_simple

        mock_s3.return_value = self.HOURLY_CSV

        anomalies = detect_anomalies_simple(threshold_kwh=5.0)
        
        # Proper assertions
        self.assertIsInstance(anomalies, list, "Should return a list")
        self.assertEqual(len(anomalies), 1, "Should find exactly 1 anomaly")
        self.assertEqual(anomalies[0]["global_active_power_kwh"], 6.5, "Should detect the high consumption hour")
        self.assertIn("anomaly_score", anomalies[0], "Anomaly should have a score")
        self.assertIn("reason", anomalies[0], "Anomaly should have a reason")
        self.assertGreater(anomalies[0]["anomaly_score"], 0, "Anomaly score should be positive")


class MLForecastTest(unittest.TestCase):
    """Tests for ml_forecast module."""
    
    @patch("app.adapters.ml_forecast.get_consumption_series")
    def test_generate_forecast_returns_predictions(self, mock_get_series):
        """Test that forecast generation returns predictions."""
        from app.adapters.ml_forecast import generate_forecast
        
        # Mock consumption series with weekly data
        dates = pd.date_range("2024-01-01", periods=200, freq="h")
        mock_series = pd.Series([1.5] * 200, index=dates, name="global_active_power_kwh")
        mock_get_series.return_value = mock_series
        
        predictions = generate_forecast(horizon_hours=24)
        
        # Proper assertions
        self.assertIsInstance(predictions, list, "Should return a list")
        self.assertGreater(len(predictions), 0, "Should have at least one prediction")
        self.assertLessEqual(len(predictions), 24, "Should not exceed horizon")
        self.assertIn("timestamp", predictions[0], "Prediction should have timestamp")
        self.assertIn("predicted_kwh", predictions[0], "Prediction should have predicted_kwh")
        self.assertIsInstance(predictions[0]["predicted_kwh"], (int, float), "predicted_kwh should be numeric")
    
    @patch("app.adapters.ml_forecast.get_consumption_series")
    def test_get_forecast_metadata_returns_model_info(self, mock_get_series):
        """Test that metadata includes model information."""
        from app.adapters.ml_forecast import get_forecast_metadata
        
        dates = pd.date_range("2024-01-01", periods=200, freq="h")
        mock_series = pd.Series([1.5] * 200, index=dates, name="global_active_power_kwh")
        mock_get_series.return_value = mock_series
        
        metadata = get_forecast_metadata()
        
        # Proper assertions
        self.assertIsInstance(metadata, dict, "Should return a dictionary")
        self.assertIn("model", metadata, "Should include model name")
        self.assertIn("model_version", metadata, "Should include model version")
        self.assertIn("training_samples", metadata, "Should include training samples count")
        self.assertEqual(metadata["training_samples"], 200, "Should have correct training sample count")
        self.assertIsInstance(metadata["model"], str, "Model name should be a string")


class HandlerIntegrationTest(unittest.TestCase):
    """Tests for handler integration with gold data."""
    
    @patch("app.backend.consumption.default_loader")
    def test_consumption_handler_uses_gold_data(self, mock_loader):
        """Test that consumption handler can use gold loader."""
        from app.backend.consumption import handler
        
        mock_loader.return_value = {
            "unit": "kWh",
            "records": [{"timestamp": "2024-01-01T00:00:00", "global_active_power_kwh": 1.5}]
        }
        
        result = handler({}, None)
        
        # Proper assertions
        self.assertIsInstance(result, dict, "Handler should return a dict")
        self.assertEqual(result["statusCode"], 200, "Should return 200 status code")
        self.assertIn("body", result, "Response should have body")
        body = eval(result["body"])  # Simple eval for test
        self.assertIn("records", body, "Body should contain records")
        self.assertIsInstance(body["records"], list, "Records should be a list")
    
    @patch("app.backend.forecast.default_loader")
    def test_forecast_handler_uses_ml_model(self, mock_loader):
        """Test that forecast handler can use ML model."""
        from app.backend.forecast import handler
        
        mock_loader.return_value = {
            "unit": "kWh",
            "horizon_hours": 24,
            "predictions": [{"timestamp": "2024-01-02T00:00:00", "predicted_kwh": 1.8}],
            "model_info": {"model": "seasonal_naive"},
        }
        
        result = handler({}, None)
        
        # Proper assertions
        self.assertIsInstance(result, dict, "Handler should return a dict")
        self.assertEqual(result["statusCode"], 200, "Should return 200 status code")
        self.assertIn("body", result, "Response should have body")
        body = eval(result["body"])
        self.assertIn("predictions", body, "Body should contain predictions")
        self.assertIn("model_info", body, "Body should contain model_info")
        self.assertIsInstance(body["predictions"], list, "Predictions should be a list")
        self.assertIsInstance(body["model_info"], dict, "Model info should be a dict")


class MLResultsTest(unittest.TestCase):
    """Forecast/anomalies read from DynamoDB (ML loader output)."""

    def _patch_query(self, items):
        from decimal import Decimal  # noqa: F401
        table = unittest.mock.MagicMock()
        table.query.return_value = {"Items": items}
        resource = unittest.mock.MagicMock()
        resource.Table.return_value = table
        return patch("boto3.resource", return_value=resource), table

    @patch.dict("os.environ", {"DYNAMODB_TABLE_FORECASTS": "t-forecasts"})
    def test_forecast_converts_decimal_and_orders_oldest_first(self):
        from decimal import Decimal
        from app.adapters.ml_results import load_forecast

        items = [  # DynamoDB returns newest first (ScanIndexForward=False)
            {"household_id": "household-1", "timestamp": "2010-11-26T01:00:00",
             "predicted_kwh": Decimal("1.25"), "actual_kwh": Decimal("1.1")},
            {"household_id": "household-1", "timestamp": "2010-11-26T00:00:00",
             "predicted_kwh": Decimal("0.9"), "actual_kwh": Decimal("1")},
        ]
        p, table = self._patch_query(items)
        with p:
            data = load_forecast(24)

        self.assertEqual(table.query.call_args.kwargs["Limit"], 24)
        self.assertFalse(table.query.call_args.kwargs["ScanIndexForward"])
        self.assertEqual([x["timestamp"] for x in data["predictions"]],
                         ["2010-11-26T00:00:00", "2010-11-26T01:00:00"])
        self.assertEqual(data["predictions"][1]["predicted_kwh"], 1.25)
        self.assertIsInstance(data["predictions"][0]["actual_kwh"], int)
        json.dumps(data)  # must be serializable

    @patch.dict("os.environ", {"DYNAMODB_TABLE_ANOMALIES": "t-anomalies"})
    def test_anomalies_newest_first_with_detector(self):
        from decimal import Decimal
        from app.adapters.ml_results import load_anomalies

        items = [
            {"household_id": "household-1", "timestamp_detector": "2010-11-20T18:00:00#rcf_raw_24",
             "timestamp": "2010-11-20T18:00:00", "detector": "rcf_raw_24",
             "consumption_kwh": Decimal("5.6"), "anomaly_score": Decimal("0.97"), "severity": "high"},
            {"household_id": "household-1", "timestamp_detector": "2010-11-02T03:00:00#log_mad",
             "detector": "log_mad", "consumption_kwh": Decimal("3.1"),
             "anomaly_score": Decimal("0.7"), "severity": "medium"},
        ]
        p, _ = self._patch_query(items)
        with p:
            data = load_anomalies()

        self.assertEqual(data["anomalies"][0]["timestamp"], "2010-11-20T18:00:00")
        self.assertEqual(data["anomalies"][1]["timestamp"], "2010-11-02T03:00:00")  # from sort key
        self.assertEqual(data["anomalies"][0]["detector"], "rcf_raw_24")
        self.assertEqual(data["anomalies"][0]["anomaly_score"], 0.97)
        json.dumps(data)

    @patch.dict("os.environ", {"DYNAMODB_TABLE_CONSUMPTION": "t-consumption"})
    def test_consumption_reads_table_oldest_first_without_household_id(self):
        from decimal import Decimal
        from app.adapters.ml_results import load_consumption

        items = [
            {"household_id": "household-1", "timestamp": "2010-11-26T21:00:00",
             "global_active_power_kwh": Decimal("1.5"), "minutes_recorded": Decimal("60"), "complete": True},
            {"household_id": "household-1", "timestamp": "2010-11-26T20:00:00",
             "global_active_power_kwh": Decimal("2.25"), "minutes_recorded": Decimal("60"), "complete": True},
        ]
        p, table = self._patch_query(items)
        with p:
            data = load_consumption(100)

        self.assertEqual(table.query.call_args.kwargs["Limit"], 100)
        self.assertEqual([r["timestamp"] for r in data["records"]], ["2010-11-26T20:00:00", "2010-11-26T21:00:00"])
        self.assertNotIn("household_id", data["records"][0])
        self.assertEqual(data["records"][0]["minutes_recorded"], 60)
        json.dumps(data)

    def test_consumption_handler_prefers_table_then_gold_csv(self):
        from app.backend.consumption import default_loader

        table_data = {"unit": "kWh", "household_id": "household-1",
                      "records": [{"timestamp": "2010-11-26T21:00:00", "global_active_power_kwh": 1.5}]}
        with patch("app.adapters.ml_results.load_consumption", return_value=table_data):
            self.assertEqual(default_loader(), table_data)
        gold = [{"timestamp": "2010-11-26T20:00:00", "global_active_power_kwh": 2.0, "complete": True}]
        with patch("app.adapters.ml_results.load_consumption", return_value={"records": []}), \
             patch("app.adapters.gold_loader.load_hourly_consumption", return_value=gold):
            self.assertEqual(default_loader()["records"], gold)

    def test_loader_writes_only_complete_hours_as_decimal(self):
        from decimal import Decimal
        from app.data.load_consumption_table import complete_items

        rows = [
            {"timestamp": "2010-11-26T20:00:00", "global_active_power_kwh": "2.25", "sub_metering_1_kwh": "",
             "sub_metering_2_kwh": "0.1", "sub_metering_3_kwh": "0.5", "minutes_recorded": "60", "complete": "true"},
            {"timestamp": "2010-11-26T21:00:00", "global_active_power_kwh": "", "sub_metering_1_kwh": "",
             "sub_metering_2_kwh": "", "sub_metering_3_kwh": "", "minutes_recorded": "12", "complete": "false"},
        ]
        items = complete_items(rows, "household-1")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["household_id"], "household-1")
        self.assertEqual(items[0]["global_active_power_kwh"], Decimal("2.25"))
        self.assertNotIn("sub_metering_1_kwh", items[0])  # null dropped
        self.assertEqual(items[0]["minutes_recorded"], 60)

    def test_handlers_fall_back_to_fixtures_when_table_empty(self):
        from app.backend.anomalies import handler as anomalies_handler
        from app.backend.forecast import handler as forecast_handler

        with patch("app.adapters.ml_results._query_latest", return_value=[]):
            f = json.loads(forecast_handler({"queryStringParameters": {"horizon_hours": "24"}}, None)["body"])
            a = json.loads(anomalies_handler({}, None)["body"])
        self.assertTrue(f["predictions"])
        self.assertTrue(a["anomalies"])


if __name__ == "__main__":
    unittest.main()

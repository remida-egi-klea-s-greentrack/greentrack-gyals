"""Tests for gold layer integration."""
import unittest
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


if __name__ == "__main__":
    unittest.main()

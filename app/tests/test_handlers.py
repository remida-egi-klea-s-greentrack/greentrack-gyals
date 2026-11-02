import json
import unittest

from app.backend.anomalies import handler as anomalies_handler
from app.backend.chat import handler as chat_handler
from app.backend.consumption import handler as consumption_handler
from app.backend.forecast import handler as forecast_handler


def body_of(result):
    return json.loads(result["body"])


class GetEndpointsTest(unittest.TestCase):
    def test_consumption_returns_records(self):
        result = consumption_handler({}, None)
        self.assertEqual(result["statusCode"], 200)
        records = body_of(result)["records"]
        self.assertGreater(len(records), 0)
        self.assertIn("timestamp", records[0])
        self.assertIn("global_active_power_kwh", records[0])

    def test_anomalies_returns_list(self):
        result = anomalies_handler({}, None)
        self.assertEqual(result["statusCode"], 200)
        anomalies = body_of(result)["anomalies"]
        self.assertIn("anomaly_score", anomalies[0])

    def test_forecast_returns_predictions(self):
        result = forecast_handler({}, None)
        self.assertEqual(result["statusCode"], 200)
        body = body_of(result)
        self.assertEqual(body["unit"], "kWh")
        self.assertIn("predicted_kwh", body["predictions"][0])

    def test_responses_are_json(self):
        result = consumption_handler({}, None)
        self.assertEqual(result["headers"]["Content-Type"], "application/json")


class ChatEndpointTest(unittest.TestCase):
    def test_valid_message_returns_answer(self):
        event = {"body": json.dumps({"message": "hello", "session_id": "abc"})}
        result = chat_handler(event, None)
        self.assertEqual(result["statusCode"], 200)
        self.assertIn("answer", body_of(result))

    def test_missing_message_returns_400(self):
        result = chat_handler({"body": "{}"}, None)
        self.assertEqual(result["statusCode"], 400)

    def test_invalid_json_returns_400(self):
        result = chat_handler({"body": "not json"}, None)
        self.assertEqual(result["statusCode"], 400)


class InjectionTest(unittest.TestCase):
    def test_handler_uses_injected_data_source(self):
        fake = {"unit": "kWh", "records": [{"timestamp": "T", "global_active_power_kwh": 9.9}]}
        result = consumption_handler({}, None, loader=lambda name: fake)
        self.assertEqual(body_of(result)["records"][0]["global_active_power_kwh"], 9.9)


if __name__ == "__main__":
    unittest.main()

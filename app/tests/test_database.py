"""Teste për database access layer."""
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.adapters.dynamodb import AnomalyRepository, ConsumptionRepository


class ConsumptionRepositoryTest(unittest.TestCase):
    """Teste për ConsumptionRepository."""
    
    def setUp(self):
        """Setup mock DynamoDB resource."""
        self.mock_dynamodb = MagicMock()
        self.mock_table = MagicMock()
        self.mock_dynamodb.Table.return_value = self.mock_table
        self.repo = ConsumptionRepository(dynamodb=self.mock_dynamodb)
    
    def test_get_all_records_returns_items(self):
        """Teston që get_all_records kthen records."""
        self.mock_table.scan.return_value = {
            "Items": [
                {"timestamp": "2024-01-01T00:00:00Z", "global_active_power_kwh": Decimal("1.5")},
                {"timestamp": "2024-01-01T01:00:00Z", "global_active_power_kwh": Decimal("2.0")},
            ]
        }
        
        records = self.repo.get_all_records()
        
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["timestamp"], "2024-01-01T00:00:00Z")
        self.mock_table.scan.assert_called_once_with(Limit=100)
    
    def test_get_all_records_respects_limit(self):
        """Teston që limit parameter funksionon."""
        self.mock_table.scan.return_value = {"Items": []}
        
        self.repo.get_all_records(limit=50)
        
        self.mock_table.scan.assert_called_once_with(Limit=50)
    
    def test_put_record_calls_put_item(self):
        """Teston që put_record shkruan në DynamoDB."""
        record = {"timestamp": "2024-01-01T00:00:00Z", "global_active_power_kwh": 1.5}
        
        result = self.repo.put_record(record)
        
        self.mock_table.put_item.assert_called_once_with(Item=record)
        self.assertEqual(result, record)
    
    def test_get_all_records_returns_empty_when_no_items(self):
        """Teston që kthen listë boshe kur nuk ka të dhëna."""
        self.mock_table.scan.return_value = {}
        
        records = self.repo.get_all_records()
        
        self.assertEqual(records, [])


class AnomalyRepositoryTest(unittest.TestCase):
    """Teste për AnomalyRepository."""
    
    def setUp(self):
        """Setup mock DynamoDB resource."""
        self.mock_dynamodb = MagicMock()
        self.mock_table = MagicMock()
        self.mock_dynamodb.Table.return_value = self.mock_table
        self.repo = AnomalyRepository(dynamodb=self.mock_dynamodb)
    
    def test_get_all_anomalies_returns_items(self):
        """Teston që get_all_anomalies kthen anomalitë."""
        self.mock_table.scan.return_value = {
            "Items": [
                {"timestamp": "2024-01-01T10:00:00Z", "anomaly_score": Decimal("0.95")},
            ]
        }
        
        anomalies = self.repo.get_all_anomalies()
        
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["anomaly_score"], Decimal("0.95"))
        self.mock_table.scan.assert_called_once_with(Limit=50)
    
    def test_put_anomaly_calls_put_item(self):
        """Teston që put_anomaly shkruan në DynamoDB."""
        anomaly = {"timestamp": "2024-01-01T10:00:00Z", "anomaly_score": 0.95}
        
        result = self.repo.put_anomaly(anomaly)
        
        self.mock_table.put_item.assert_called_once_with(Item=anomaly)
        self.assertEqual(result, anomaly)


class DynamoDBConnectionTest(unittest.TestCase):
    """Teste për DynamoDB connection setup."""
    
    @patch("app.adapters.dynamodb.boto3.resource")
    def test_uses_local_endpoint_by_default(self, mock_boto3_resource):
        """Teston që default endpoint është localhost:8000."""
        from app.adapters.dynamodb import get_dynamodb_resource
        
        get_dynamodb_resource()
        
        mock_boto3_resource.assert_called_once_with(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-east-1",
            aws_access_key_id="dummy",
            aws_secret_access_key="dummy",
        )
    
    @patch.dict("os.environ", {"DYNAMODB_ENDPOINT": "http://custom:9000", "AWS_REGION": "eu-west-1"})
    @patch("app.adapters.dynamodb.boto3.resource")
    def test_uses_environment_variables(self, mock_boto3_resource):
        """Teston që environment variables ndryshojnë konfigurimin."""
        from app.adapters.dynamodb import get_dynamodb_resource
        
        get_dynamodb_resource()
        
        mock_boto3_resource.assert_called_once_with(
            "dynamodb",
            endpoint_url="http://custom:9000",
            region_name="eu-west-1",
            aws_access_key_id="dummy",
            aws_secret_access_key="dummy",
        )


if __name__ == "__main__":
    unittest.main()

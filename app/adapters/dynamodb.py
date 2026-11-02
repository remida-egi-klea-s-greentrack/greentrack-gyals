"""DynamoDB adapter për GreenTrack."""
import os
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key


def get_dynamodb_resource():
    """Krijon DynamoDB resource (local ose AWS)."""
    endpoint = os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8000")
    region = os.getenv("AWS_REGION", "us-east-1")
    
    return boto3.resource(
        "dynamodb",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id="dummy",  # DynamoDB Local nuk kërkon credentials të vërteta
        aws_secret_access_key="dummy",
    )


class ConsumptionRepository:
    """Repository për të dhënat e konsumit energjetik."""
    
    def __init__(self, dynamodb=None):
        self.dynamodb = dynamodb or get_dynamodb_resource()
        self.table = self.dynamodb.Table("greentrack-consumption")
    
    def get_all_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Merr të gjitha të dhënat e konsumit."""
        response = self.table.scan(Limit=limit)
        return response.get("Items", [])
    
    def get_by_date_range(
        self, 
        start_date: str, 
        end_date: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Merr të dhënat për një periudhë kohore."""
        response = self.table.scan(
            FilterExpression=Key("timestamp").between(start_date, end_date),
            Limit=limit
        )
        return response.get("Items", [])
    
    def put_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Shton një record të ri."""
        self.table.put_item(Item=record)
        return record


class AnomalyRepository:
    """Repository për anomalitë e konsumit."""
    
    def __init__(self, dynamodb=None):
        self.dynamodb = dynamodb or get_dynamodb_resource()
        self.table = self.dynamodb.Table("greentrack-anomalies")
    
    def get_all_anomalies(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Merr të gjitha anomalitë."""
        response = self.table.scan(Limit=limit)
        return response.get("Items", [])
    
    def put_anomaly(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        """Shton një anomali të re."""
        self.table.put_item(Item=anomaly)
        return anomaly

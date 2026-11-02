"""Script për krijimin e tabelave në DynamoDB Local."""
import sys
from pathlib import Path

# Shto root në Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.adapters.dynamodb import get_dynamodb_resource


def create_consumption_table(dynamodb):
    """Krijon tabelën e konsumit energjetik."""
    try:
        table = dynamodb.create_table(
            TableName="greentrack-consumption",
            KeySchema=[
                {"AttributeName": "timestamp", "KeyType": "HASH"},  # Partition key
            ],
            AttributeDefinitions=[
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",  # On-demand pricing (nuk kërkon provisioned capacity)
        )
        table.wait_until_exists()
        print(f"✅ Tabela '{table.table_name}' u krijua me sukses.")
        return table
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print(f"⚠️  Tabela 'greentrack-consumption' ekziston tashmë.")
        return dynamodb.Table("greentrack-consumption")


def create_anomaly_table(dynamodb):
    """Krijon tabelën e anomalive."""
    try:
        table = dynamodb.create_table(
            TableName="greentrack-anomalies",
            KeySchema=[
                {"AttributeName": "timestamp", "KeyType": "HASH"},  # Partition key
            ],
            AttributeDefinitions=[
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        print(f"✅ Tabela '{table.table_name}' u krijua me sukses.")
        return table
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print(f"⚠️  Tabela 'greentrack-anomalies' ekziston tashmë.")
        return dynamodb.Table("greentrack-anomalies")


def main():
    """Krijon të gjitha tabelat."""
    print("🚀 Duke krijuar tabelat në DynamoDB Local...")
    dynamodb = get_dynamodb_resource()
    
    create_consumption_table(dynamodb)
    create_anomaly_table(dynamodb)
    
    print("\n✅ Të gjitha tabelat janë gati!")
    print("💡 Mund të nisësh seeding me: python app/data/seed_tables.py")


if __name__ == "__main__":
    main()

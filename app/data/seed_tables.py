"""Script për mbushjen e tabelave me të dhëna fillestare."""
import json
import sys
from decimal import Decimal
from pathlib import Path

# Shto root në Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.adapters.dynamodb import AnomalyRepository, ConsumptionRepository


def load_fixture(filename: str):
    """Ngarkon një fixture file."""
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / filename
    with open(fixture_path, "r", encoding="utf-8") as f:
        # DynamoDB (boto3) nuk pranon float; numrat dhjetorë lexohen si Decimal.
        return json.load(f, parse_float=Decimal)


def seed_consumption_data():
    """Mbush tabelën e konsumit me të dhëna."""
    print("📊 Duke shtuar të dhëna në 'greentrack-consumption'...")
    repo = ConsumptionRepository()
    data = load_fixture("consumption.json")
    
    records = data.get("records", [])
    for record in records:
        repo.put_record(record)
    
    print(f"✅ U shtuan {len(records)} records në 'greentrack-consumption'.")


def seed_anomaly_data():
    """Mbush tabelën e anomalive me të dhëna."""
    print("🚨 Duke shtuar anomali në 'greentrack-anomalies'...")
    repo = AnomalyRepository()
    data = load_fixture("anomalies.json")
    
    anomalies = data.get("anomalies", [])
    for anomaly in anomalies:
        repo.put_anomaly(anomaly)
    
    print(f"✅ U shtuan {len(anomalies)} anomali në 'greentrack-anomalies'.")


def main():
    """Ekzekuton seeding për të gjitha tabelat."""
    print("🌱 Duke filluar seeding...")
    
    try:
        seed_consumption_data()
        seed_anomaly_data()
        print("\n✅ Seeding përfundoi me sukses!")
    except Exception as e:
        print(f"\n❌ Gabim gjatë seeding: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Integration test for Developer C's work - tests all endpoints."""
import json
from pathlib import Path


def test_gold_loader():
    """Test that gold data can be loaded."""
    print("\n🔍 Testing Gold Loader (Developer A integration)...")
    try:
        from app.adapters.gold_loader import (
            load_hourly_consumption,
            load_daily_consumption,
            get_gold_exports_dir
        )
        
        exports_dir = get_gold_exports_dir()
        print(f"   Export directory: {exports_dir}")
        
        if not exports_dir.exists():
            print("   ⚠️  Export directory does not exist")
            print(f"   📝 Please run: python data/jobs/gold_aggregate.py")
            return False
        
        hourly = load_hourly_consumption(limit=10)
        print(f"   ✅ Loaded {len(hourly)} hourly records")
        print(f"   📊 Sample: {hourly[0]['timestamp']} → {hourly[0]['global_active_power_kwh']} kWh")
        
        daily = load_daily_consumption()
        print(f"   ✅ Loaded {len(daily)} daily records")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_ml_forecast():
    """Test that ML forecasting works."""
    print("\n🔍 Testing ML Forecast (Developer B integration)...")
    try:
        from app.adapters.ml_forecast import generate_forecast, get_forecast_metadata
        
        predictions = generate_forecast(horizon_hours=24)
        metadata = get_forecast_metadata()
        
        print(f"   ✅ Generated forecast with {len(predictions)} predictions")
        print(f"   🔮 Model: {metadata.get('model', 'unknown')}")
        print(f"   📊 Training samples: {metadata.get('training_samples', 0)}")
        
        if predictions:
            sample = predictions[0]
            print(f"   📈 Sample: {sample['timestamp']} → {sample['predicted_kwh']} kWh")
            if 'lower_bound' in sample and 'upper_bound' in sample:
                print(f"      Confidence: [{sample['lower_bound']}, {sample['upper_bound']}]")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_ml_anomaly():
    """Test that ML anomaly detection works."""
    print("\n🔍 Testing ML Anomaly Detection (Developer B integration)...")
    try:
        from app.adapters.ml_anomaly import detect_anomalies
        
        result = detect_anomalies()
        anomalies = result.get('anomalies', [])
        print(f"   ✅ Detected {len(anomalies)} anomalies")
        print(f"   📊 Generated at: {result.get('generated_at')}")
        
        if anomalies:
            sample = anomalies[0]
            print(f"   🚨 Sample anomaly:")
            print(f"      Timestamp: {sample['timestamp']}")
            print(f"      Consumption: {sample['consumption_kwh']} kWh")
            print(f"      Score: {sample['anomaly_score']}")
            print(f"      Severity: {sample['severity']}")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_backend_endpoints():
    """Test that backend handlers work."""
    print("\n🔍 Testing Backend Endpoints...")
    
    tests_passed = 0
    tests_total = 4
    
    # Test consumption endpoint
    try:
        from app.backend.consumption import handler as consumption_handler
        event = {"httpMethod": "GET", "path": "/consumption", "body": None}
        result = consumption_handler(event, None)
        
        if result["statusCode"] == 200:
            data = json.loads(result["body"])
            records = data.get("records", [])
            print(f"   ✅ GET /consumption → {len(records)} records")
            tests_passed += 1
        else:
            print(f"   ❌ GET /consumption → Status {result['statusCode']}")
    except Exception as e:
        print(f"   ❌ GET /consumption → Error: {e}")
    
    # Test forecast endpoint
    try:
        from app.backend.forecast import handler as forecast_handler
        event = {"httpMethod": "GET", "path": "/forecast", "body": None}
        result = forecast_handler(event, None)
        
        if result["statusCode"] == 200:
            data = json.loads(result["body"])
            predictions = data.get("predictions", [])
            print(f"   ✅ GET /forecast → {len(predictions)} predictions")
            tests_passed += 1
        else:
            print(f"   ❌ GET /forecast → Status {result['statusCode']}")
    except Exception as e:
        print(f"   ❌ GET /forecast → Error: {e}")
    
    # Test anomalies endpoint
    try:
        from app.backend.anomalies import handler as anomalies_handler
        event = {"httpMethod": "GET", "path": "/anomalies", "body": None}
        result = anomalies_handler(event, None)
        
        if result["statusCode"] == 200:
            data = json.loads(result["body"])
            anomalies = data.get("anomalies", [])
            print(f"   ✅ GET /anomalies → {len(anomalies)} anomalies")
            tests_passed += 1
        else:
            print(f"   ❌ GET /anomalies → Status {result['statusCode']}")
    except Exception as e:
        print(f"   ❌ GET /anomalies → Error: {e}")
    
    # Test chat endpoint
    try:
        from app.backend.chat import handler as chat_handler
        event = {
            "httpMethod": "POST",
            "path": "/chat",
            "body": json.dumps({"message": "Test", "session_id": "test123"})
        }
        result = chat_handler(event, None)
        
        if result["statusCode"] == 200:
            data = json.loads(result["body"])
            print(f"   ✅ POST /chat → Response: {data.get('answer', 'N/A')[:50]}...")
            tests_passed += 1
        else:
            print(f"   ❌ POST /chat → Status {result['statusCode']}")
    except Exception as e:
        print(f"   ❌ POST /chat → Error: {e}")
    
    print(f"\n   📊 Backend tests: {tests_passed}/{tests_total} passed")
    return tests_passed == tests_total


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("🧪 GreenTrack Integration Tests - Developer C")
    print("=" * 60)
    
    results = {
        "Gold Loader (A)": test_gold_loader(),
        "ML Forecast (B)": test_ml_forecast(),
        "ML Anomaly (B)": test_ml_anomaly(),
        "Backend Endpoints (C)": test_backend_endpoints(),
    }
    
    print("\n" + "=" * 60)
    print("📋 Summary")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\n🎯 Overall: {total_passed}/{total_tests} components working")
    
    if total_passed == total_tests:
        print("\n✨ All integrations working! Ready for M2/M3.")
    else:
        print("\n⚠️  Some integrations need attention.")
        print("\n📝 Next steps:")
        if not results["Gold Loader (A)"]:
            print("   1. Run: python data/jobs/gold_aggregate.py")
        print("   2. Check the error messages above")
        print("   3. Fix any issues and re-run this test")


if __name__ == "__main__":
    main()

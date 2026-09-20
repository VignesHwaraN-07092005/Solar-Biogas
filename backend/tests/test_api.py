import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

from backend.app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["system_mode"] == "DEMO"

def test_favicon_endpoint():
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/x-icon"
    assert len(response.content) > 0


def test_devices_endpoints():
    # Register device
    res = client.post("/api/devices", json={
        "id": "DIGESTER_API_TEST",
        "name": "API Test Unit",
        "location": "Testing Bay",
        "mode": "DEMO"
    })
    assert res.status_code == 200
    assert res.json()["id"] == "DIGESTER_API_TEST"
    
    # List devices
    res_list = client.get("/api/devices")
    assert res_list.status_code == 200
    device_ids = [d["id"] for d in res_list.json()]
    assert "DIGESTER_API_TEST" in device_ids
    
    # Latest device status
    res_latest = client.get("/api/devices/DIGESTER_API_TEST/latest")
    assert res_latest.status_code == 200
    assert res_latest.json()["device"]["id"] == "DIGESTER_API_TEST"

def test_readings_ingestion_and_query():
    payload = {
        "device_id": "DIGESTER_API_TEST",
        "temperature_c": 35.8,
        "ph": 7.3,
        "pressure_bar": 1.15,
        "gas_flow_m3_day": 3.4,
        "biogas_production_m3_day": 3.4,
        "methane_percent": 62.0,
        "source": "synthetic"
    }
    res = client.post("/api/readings", json=payload)
    assert res.status_code == 200
    assert res.json()["temperature_c"] == 35.8
    assert res.json()["ph"] == 7.3
    
    # Query readings
    query_res = client.get("/api/readings?device_id=DIGESTER_API_TEST&limit=10")
    assert query_res.status_code == 200
    assert len(query_res.json()) >= 1

def test_alert_generation_on_abnormal_ph():
    # Ingest reading with critical low pH (5.9 < 6.5 threshold)
    low_ph_payload = {
        "device_id": "DIGESTER_API_TEST",
        "ph": 5.9,
        "temperature_c": 35.0,
        "source": "synthetic"
    }
    res = client.post("/api/readings", json=low_ph_payload)
    assert res.status_code == 200
    
    # Check alerts endpoint
    alerts_res = client.get("/api/alerts?device_id=DIGESTER_API_TEST")
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) >= 1
    assert any(a["parameter"] == "ph" and a["triggered_value"] == 5.9 for a in alerts)

def test_forecast_endpoints():
    target = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    fc_payload = {
        "device_id": "DIGESTER_API_TEST",
        "target_date": target,
        "predicted_biogas_m3_day": 3.65,
        "lower_bound_m3_day": 3.30,
        "upper_bound_m3_day": 4.00,
        "model_name": "Test_Model",
        "model_version": "v1.0.0",
        "top_feature_1": "temperature_c",
        "recommendation": "Conditions optimal."
    }
    res = client.post("/api/forecast", json=fc_payload)
    assert res.status_code == 200
    assert res.json()["predicted_biogas_m3_day"] == 3.65
    
    # Fetch latest forecast
    latest = client.get("/api/forecast?device_id=DIGESTER_API_TEST")
    assert latest.status_code == 200
    assert latest.json()["predicted_biogas_m3_day"] == 3.65

def test_solar_endpoints():
    solar_payload = {
        "device_id": "DIGESTER_API_TEST",
        "solar_voltage_v": 19.5,
        "solar_current_a": 2.2,
        "solar_power_w": 42.9,
        "battery_voltage_v": 12.6,
        "battery_soc_percent": 88.0,
        "solar_status": "CHARGING"
    }
    res = client.post("/api/solar", json=solar_payload)
    assert res.status_code == 200
    assert res.json()["battery_soc_percent"] == 88.0
    
    # Get latest solar
    latest_solar = client.get("/api/solar/latest?device_id=DIGESTER_API_TEST")
    assert latest_solar.status_code == 200
    assert latest_solar.json()["solar_power_w"] == 42.9

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_energy_config_endpoint():
    resp = client.get("/api/energy/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "generator" in data
    assert "community_demand" in data
    assert "conversion_factors" in data
    assert data["generator"]["status"] == "NOT CONNECTED"
    assert data["generator"]["runtime_hours"] == "N/A"
    assert data["generator"]["default_electrical_efficiency"] == 0.30
    assert data["community_demand"]["daily_demand_kwh"] == 5.20
    assert data["community_demand"]["is_configurable_illustrative_default"] is True
    assert data["conversion_factors"]["pure_ch4_lhv_kwh_per_nm3"] == 9.94

def test_energy_calculate_dynamic_math():
    # 3.4 m3/day biogas @ 60% CH4, 30% efficiency
    # LHV = 3.4 * 0.60 * 9.94 = 20.2776 kWh
    # E = 20.2776 * 0.30 = 6.08328 kWh
    # P_avg = 6.08328 / 24 = 0.25347 kW
    payload = {
        "biogas_volume_m3": 3.4,
        "methane_percent": 60.0,
        "efficiency": 0.30
    }
    resp = client.post("/api/energy/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["biogas_volume_m3"] == 3.4
    assert data["methane_percent"] == 60.0
    assert data["efficiency_used"] == 0.30
    assert abs(data["electricity_potential_kwh"] - 6.083) < 0.01
    assert abs(data["continuous_power_kw"] - 0.253) < 0.01
    assert data["provenance"] == "[CALCULATED]"
    assert data["continuous_power_label"] == "24-h Average Equivalent Power"

def test_energy_calculate_efficiency_slider_effect():
    # Vary efficiency between 20% and 45%
    base_payload = {"biogas_volume_m3": 10.0, "methane_percent": 60.0}
    
    resp_20 = client.post("/api/energy/calculate", json={**base_payload, "efficiency": 0.20})
    resp_30 = client.post("/api/energy/calculate", json={**base_payload, "efficiency": 0.30})
    resp_45 = client.post("/api/energy/calculate", json={**base_payload, "efficiency": 0.45})
    
    e20 = resp_20.json()["electricity_potential_kwh"]
    e30 = resp_30.json()["electricity_potential_kwh"]
    e45 = resp_45.json()["electricity_potential_kwh"]
    
    assert e20 < e30 < e45
    assert abs(e30 / e20 - 1.5) < 0.01

def test_energy_generation_current_endpoint():
    resp = client.get("/api/energy/generation/current")
    assert resp.status_code == 200
    data = resp.json()
    assert "generator_specification" in data
    assert data["generator_specification"]["status"] == "NOT CONNECTED"
    assert data["generator_specification"]["runtime_hours"] == "N/A"
    assert data["continuous_power_label"] == "24-h Average Equivalent Power"

def test_community_energy_balance_endpoint():
    resp = client.get("/api/energy/community/balance?daily_demand_kwh=5.20&biogas_volume_m3=3.4&methane_percent=60.0&efficiency=0.30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["daily_demand_kwh"] == 5.20
    assert abs(data["electricity_potential_kwh"] - 6.083) < 0.01
    assert data["coverage_percent"] > 0.0
    assert len(data["hourly_balance"]) == 24
    assert data["hardware_status"] == "NOT CONNECTED"
    assert data["continuous_power_label"] == "24-h Average Equivalent Power"
    assert "demand_label" in data

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.simulator_service import simulator_service, SimulatorService
from backend.app.schemas.forecast import ProvenanceEnum

client = TestClient(app)

def test_1_simulator_starts_with_valid_demo_synthetic_history():
    """1. Simulator starts with valid DEMO_SYNTHETIC history."""
    timeline = simulator_service.get_simulator_timeline(days=30, warmup_days=14)
    assert len(timeline) == 30
    for item in timeline:
        assert item["data_source"] == ProvenanceEnum.DEMO_SYNTHETIC.value

def test_2_simulator_provides_14_continuous_timesteps():
    """2. Simulator provides 14 continuous timesteps for warm-up."""
    timeline = simulator_service.get_simulator_timeline(days=20, warmup_days=14)
    warmup_slice = timeline[:14]
    assert len(warmup_slice) == 14
    for i, item in enumerate(warmup_slice):
        assert item["history_length"] == i + 1
        assert "features" in item
        assert "biogas_today_nm3" in item["features"]

def test_3_gru_forecast_succeeds_once_history_ge_14():
    """3. GRU forecast succeeds once history >= 14."""
    timeline = simulator_service.get_simulator_timeline(days=20, warmup_days=14)
    # Day index 13 is the 14th day (0-indexed)
    day_14 = timeline[13]
    assert day_14["history_length"] == 14
    assert day_14["status"] == "SUCCESS"
    assert day_14["predicted_next_day_nm3"] is not None
    assert day_14["predicted_next_day_nm3"] > 0.0
    assert day_14["model_name"] == "GRU-14d Residual"

def test_4_gru_warmup_state_below_14():
    """4. GRU returns warming up state below 14 timesteps."""
    timeline = simulator_service.get_simulator_timeline(days=20, warmup_days=14)
    for i in range(13):
        item = timeline[i]
        assert item["history_length"] == i + 1
        assert item["status"] == "Warming up forecast model"
        assert item["predicted_next_day_nm3"] is None

def test_5_timestamps_strictly_increase_24h():
    """5. Timestamps strictly increase with 24h interval."""
    timeline = simulator_service.get_simulator_timeline(days=30, warmup_days=14)
    for i in range(1, len(timeline)):
        t_prev = datetime.fromisoformat(timeline[i-1]["timestamp"])
        t_curr = datetime.fromisoformat(timeline[i]["timestamp"])
        assert (t_curr - t_prev) == timedelta(days=1), f"Non-24h gap at step {i}: {t_prev} -> {t_curr}"

def test_6_forecast_target_is_strictly_t_plus_1():
    """6. Forecast target is strictly t+1."""
    timeline = simulator_service.get_simulator_timeline(days=25, warmup_days=14)
    for item in timeline:
        t_now = datetime.fromisoformat(item["timestamp"])
        t_target = datetime.fromisoformat(item["target_date"])
        assert (t_target - t_now) == timedelta(days=1), f"Target date is not t+1: {t_now} -> {t_target}"

def test_7_provenance_remains_demo_synthetic():
    """7. Provenance remains DEMO_SYNTHETIC throughout timeline and predictions."""
    timeline = simulator_service.get_simulator_timeline(days=25, warmup_days=14)
    for item in timeline:
        assert item["data_source"] == "DEMO_SYNTHETIC"

def test_8_no_spark_records_mixed_into_demo():
    """8. No Spark records mixed into DEMO mode."""
    timeline = simulator_service.get_simulator_timeline(days=30, warmup_days=14)
    for item in timeline:
        # Simulator community scale biogas is around 2.5 - 6.0 Nm3/day
        # Spark industrial plant biogas is around 2000 - 8000 Nm3/day
        assert item["biogas_today_nm3"] < 200.0, f"Suspiciously high biogas value for community demo: {item['biogas_today_nm3']}"
        assert "Spark" not in item["data_source"]

def test_9_deterministic_output_fixed_seed():
    """9. Deterministic output for fixed seed."""
    sim1 = SimulatorService(seed=42)
    t1 = sim1.get_simulator_timeline(days=20, warmup_days=14)

    sim2 = SimulatorService(seed=42)
    t2 = sim2.get_simulator_timeline(days=20, warmup_days=14)

    for i in range(len(t1)):
        assert t1[i]["biogas_today_nm3"] == t2[i]["biogas_today_nm3"]
        assert t1[i]["predicted_next_day_nm3"] == t2[i]["predicted_next_day_nm3"]

def test_10_simulator_api_endpoints_and_continuity_log():
    """10. Simulator API endpoints respond with valid schemas and continuity verification."""
    # Test timeline endpoint
    res = client.get("/api/simulator/timeline?days=30&warmup_days=14")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 30
    assert data[13]["status"] == "SUCCESS"
    assert data[13]["predicted_next_day_nm3"] is not None

    # Test continuity verification endpoint
    res_log = client.get("/api/simulator/continuity-log")
    assert res_log.status_code == 200
    log_data = res_log.json()
    assert log_data["continuity_result"] is True
    assert log_data["provenance"] == "DEMO_SYNTHETIC"
    assert log_data["required_lookback"] == 14

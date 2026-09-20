import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_predict_invalid_model_returns_400():
    """PART A: Invalid model name must return controlled HTTP 400 without default substitution."""
    res = client.post("/api/forecast/predict", json={
        "device_id": "DIGESTER_001",
        "model_name": "NonExistentModel",
        "data_source": "DEMO_SYNTHETIC"
    })
    assert res.status_code == 400
    assert "Invalid model 'NonExistentModel'" in res.json()["detail"]
    assert "Valid models are" in res.json()["detail"]

def test_predict_agstar_data_source_returns_400():
    """PART A: AGSTAR time-series forecasting attempt must return controlled HTTP 400, not 500."""
    res = client.post("/api/forecast/predict", json={
        "device_id": "DIGESTER_001",
        "model_name": "GRU-14d Residual",
        "data_source": "AGSTAR_REGISTRY"
    })
    assert res.status_code == 400
    assert "AgSTAR is an external static benchmark" in res.json()["detail"]

def test_interpretation_invalid_model_returns_400():
    """PART A: Forecast interpretation with invalid model returns controlled HTTP 400."""
    res = client.post("/api/forecast/interpretation", json={
        "device_id": "DIGESTER_001",
        "model_name": "BogusModel",
        "data_source": "DEMO_SYNTHETIC"
    })
    assert res.status_code == 400
    assert "Invalid model 'BogusModel'" in res.json()["detail"]

def test_interpretation_agstar_returns_400():
    """PART A: Forecast interpretation with AGSTAR returns controlled HTTP 400."""
    res = client.post("/api/forecast/interpretation", json={
        "device_id": "DIGESTER_001",
        "model_name": "GRU-14d Residual",
        "data_source": "AGSTAR_REGISTRY"
    })
    assert res.status_code == 400
    assert "AgSTAR is an external static benchmark" in res.json()["detail"]

def test_spark_replay_invalid_mode_returns_400():
    """PART A: Spark replay with invalid mode returns controlled HTTP 400, no silent fallback."""
    res = client.get("/api/forecast/spark-replay?mode=non_existent_mode")
    assert res.status_code == 400
    assert "Invalid replay mode 'non_existent_mode'" in res.json()["detail"]

def test_spark_replay_invalid_model_returns_400():
    """PART A: Spark replay with invalid model returns controlled HTTP 400."""
    res = client.get("/api/forecast/spark-replay", params={"mode": "held_out_test", "model_name": "InvalidModel"})
    assert res.status_code == 400
    assert "Invalid model 'InvalidModel'" in res.json()["detail"]

def test_spark_replay_agstar_returns_400():
    """PART A: Spark replay with AGSTAR returns controlled HTTP 400."""
    res = client.get("/api/forecast/spark-replay", params={"mode": "held_out_test", "model_name": "AGSTAR"})
    assert res.status_code == 400
    assert "AgSTAR is an external static macro benchmark" in res.json()["detail"]

def test_ingestion_analyze_integer_scalars_serialization():
    """PART F: Ingestion analyze must serialize numpy integer scalars without 500 error."""
    res = client.post("/api/ingestion/analyze", json={
        "filename": "test_integers.xlsx",
        "rows": [
            {"day": 1, "biogas": 100, "temp": 36},
            {"day": 2, "biogas": 120, "temp": 37}
        ]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["total_records"] == 2
    assert len(data["standardized_rows"]) == 2
    assert data["standardized_rows"][0]["biogas"] == 100
    assert data["standardized_rows"][0]["biogas_today_nm3"] == 100.0

def test_api_matrix_valid_endpoints():
    """PART F: Comprehensive check that primary API routes respond with valid status codes."""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/devices").status_code == 200
    assert client.get("/api/readings/live-status").status_code == 200
    assert client.get("/api/alerts/thresholds").status_code == 200
    assert client.get("/api/forecast/benchmarks").status_code == 200
    assert client.get("/api/forecast/models-metadata").status_code == 200
    assert client.get("/api/forecast/xconet-research").status_code == 200
    assert client.get("/api/forecast/spark-replay", params={"mode": "held_out_test"}).status_code == 200
    assert client.get("/api/forecast/spark-replay", params={"mode": "full_historical"}).status_code == 200
    assert client.post("/api/alerts/evaluate", json={"pressure_bar": 1.15}).status_code == 200

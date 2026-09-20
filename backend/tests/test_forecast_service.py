import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import json

from backend.app.main import app
from backend.app.services.forecast_service import forecast_service
from backend.app.schemas.forecast import ProvenanceEnum, ForecastStatusEnum

client = TestClient(app)

def test_frozen_scaler_metadata_loading():
    """Verify that GRU scaler metadata is frozen and matches v1.0.0-frozen-train."""
    meta = forecast_service._gru_scaler_meta
    assert meta is not None
    assert meta["preprocessing_version"] == "v1.0.0-frozen-train"
    assert meta["lookback"] == 14
    assert len(meta["feature_cols"]) == 9
    assert len(meta["feature_mean"]) == 9
    assert len(meta["feature_scale"]) == 9
    assert meta["y_std"] > 0.0
    assert meta["train_date_range"] == ["2025-11-01", "2026-02-14"]


def test_insufficient_history_handling():
    """Verify safe fallback when input history is below required lookback."""
    # 1. GRU requires 14 rows; provide only 5
    short_history = [
        {"biogas_today_nm3": 15.0 + i, "temp_outlet_d1_c": 36.5, "ph_outlet_d1": 7.2}
        for i in range(5)
    ]
    res_gru = forecast_service.predict(
        device_id="TEST_DEV",
        model_name="GRU-14d Residual",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=short_history
    )
    assert res_gru.status == ForecastStatusEnum.INSUFFICIENT_HISTORY.value
    assert res_gru.predicted_biogas_m3_day == 0.0

    # 2. EMA requires 3 rows; provide only 2
    res_ema = forecast_service.predict(
        device_id="TEST_DEV",
        model_name="EMA-0.90",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=short_history[:2]
    )
    assert res_ema.status == ForecastStatusEnum.INSUFFICIENT_HISTORY.value

    # 3. Persistence requires at least 1 row; provide 0
    res_pers = forecast_service.predict(
        device_id="TEST_DEV",
        model_name="Persistence",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=[]
    )
    assert res_pers.status == ForecastStatusEnum.INSUFFICIENT_HISTORY.value

    # 4. XCO-Net requires 7 rows; provide only 6
    res_xco = forecast_service.predict(
        device_id="TEST_DEV",
        model_name="XCO-Net",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=short_history + [{"biogas_today_nm3": 20.0}]
    )
    assert res_xco.status == ForecastStatusEnum.INSUFFICIENT_HISTORY.value


def test_deterministic_gru_inference():
    """Verify that identical input history produces strictly identical predictions."""
    history_14d = [
        {
            "biogas_today_nm3": 5000.0 + np.sin(i) * 500.0,
            "total_incoming_mt": 130.0,
            "total_processed_mt": 100.0,
            "feed_total_m3": 180.0,
            "temp_outlet_d1_c": 36.5,
            "ph_outlet_d1": 7.3,
            "recycle_water_m3": 30.0,
            "feed_total_m3_was_missing": 0,
            "ph_outlet_d1_was_missing": 0
        }
        for i in range(14)
    ]
    
    pred1 = forecast_service.predict(
        device_id="TEST_DEV",
        model_name="GRU-14d Residual",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=history_14d
    )
    pred2 = forecast_service.predict(
        device_id="TEST_DEV",
        model_name="GRU-14d Residual",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=history_14d
    )
    
    assert pred1.status == ForecastStatusEnum.SUCCESS.value
    assert pred1.predicted_biogas_m3_day == pred2.predicted_biogas_m3_day
    assert pred1.predicted_biogas_m3_day > 0.0


def test_provenance_and_version_recording_in_database():
    """Verify model version, preprocessing version, and provenance are persisted to database."""
    history_14d = [
        {"biogas_today_nm3": 5000.0, "total_incoming_mt": 130.0, "total_processed_mt": 100.0,
         "feed_total_m3": 180.0, "temp_outlet_d1_c": 36.5, "ph_outlet_d1": 7.3,
         "recycle_water_m3": 30.0, "feed_total_m3_was_missing": 0, "ph_outlet_d1_was_missing": 0}
        for _ in range(14)
    ]
    
    payload = {
        "device_id": "TEST_PROVENANCE_DEV",
        "model_name": "GRU-14d Residual",
        "data_source": "REAL_SPARK_HISTORICAL",
        "history_window": history_14d
    }
    
    res = client.post("/api/forecast/predict", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["model_name"] == "GRU-14d Residual"
    assert data["model_version"] == "v1.0.0"
    assert data["preprocessing_version"] == "v1.0.0-frozen-train"
    assert data["data_source"] == "REAL_SPARK_HISTORICAL"
    assert data["status"] == "SUCCESS"
    assert data["input_biogas_m3_day"] == 5000.0
    assert "input_timestamp" in data
    assert data["input_timestamp"] is not None

    # Verify queryable from both /api/forecast and /api/forecast/latest
    latest1 = client.get("/api/forecast?device_id=TEST_PROVENANCE_DEV")
    assert latest1.status_code == 200
    lat_data1 = latest1.json()
    assert lat_data1["data_source"] == "REAL_SPARK_HISTORICAL"
    assert lat_data1["preprocessing_version"] == "v1.0.0-frozen-train"
    assert lat_data1["input_timestamp"] is not None

    latest2 = client.get("/api/forecast/latest?device_id=TEST_PROVENANCE_DEV")
    assert latest2.status_code == 200
    lat_data2 = latest2.json()
    assert lat_data2["id"] == lat_data1["id"]
    assert lat_data2["data_source"] == "REAL_SPARK_HISTORICAL"


def test_invalid_provenance_enum_rejected():
    """Verify that arbitrary provenance strings fail Pydantic validation."""
    payload = {
        "device_id": "TEST_DEV",
        "model_name": "GRU-14d Residual",
        "data_source": "FABRICATED_MEASURED",  # Invalid enum value
        "history_window": []
    }
    res = client.post("/api/forecast/predict", json=payload)
    assert res.status_code == 422


def test_causality_of_spark_replay():
    """Verify that Spark historical replay strictly enforces causality without lookahead."""
    res = client.get("/api/forecast/spark-replay?model_name=GRU-14d Residual&limit=15")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0

    for item in items:
        # Prediction is for target_date (t+1), while input date is date (t)
        dt_today = datetime.strptime(item["date"], "%Y-%m-%d")
        dt_target = datetime.strptime(item["target_date"], "%Y-%m-%d")
        assert (dt_target - dt_today).days == 1
        assert item["data_source"] == "REAL_SPARK_HISTORICAL"
        assert item["predicted_next_day_nm3"] > 0.0


def test_benchmarks_metrics_strict_separation():
    """Verify that held-out test metrics and cross-window metrics are strictly separated."""
    res = client.get("/api/forecast/benchmarks")
    assert res.status_code == 200
    data = res.json()
    assert len(data["models"]) == 4

    model_map = {m["model_id"]: m for m in data["models"]}
    
    # Check GRU-14d Residual
    gru = model_map["gru_14d_residual"]
    assert gru["role"] == "Default Forecasting Model"
    assert gru["held_out_test_metrics"]["mae"] == 766.61
    assert gru["held_out_test_metrics"]["rmse"] == 959.40
    assert gru["cross_window_mean_metrics"]["mae"] == 907.32
    assert gru["cross_window_mean_metrics"]["rmse"] == 1148.76

    # Check EMA-0.90
    ema = model_map["ema_090"]
    assert ema["role"] == "Statistical Benchmark"
    assert ema["held_out_test_metrics"]["rmse"] == 984.48
    assert ema["cross_window_mean_metrics"]["rmse"] == 1230.70

    # Check XCO-Net
    xco = model_map["xco_net"]
    assert xco["role"] == "Proposed Research Architecture"
    assert xco["category"] == "Research"
    assert xco["cross_window_mean_metrics"]["rmse"] == 1250.13


def test_xconet_research_endpoint():
    """Verify XCO-Net research endpoint exposes architecture, shock limits, and ablations."""
    res = client.get("/api/forecast/xconet-research")
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "Proposed Research Architecture"
    assert data["total_trainable_parameters"] == 2706
    assert data["delta_max_nm3_day"] == 4152.0
    assert "without_cross_channel" in data["ablation_findings"]
    assert len(data["feature_attributions"]) > 0


def test_xconet_exact_7_day_lookback_runtime():
    """Verify XCO-Net succeeds with exactly 7 days of history and fails with 6."""
    history_7d = [
        {
            "biogas_today_nm3": 5200.0 + i * 50.0,
            "total_incoming_mt": 130.0,
            "total_processed_mt": 100.0,
            "feed_total_m3": 180.0,
            "temp_outlet_d1_c": 36.5,
            "ph_outlet_d1": 7.3,
            "recycle_water_m3": 30.0,
            "feed_total_m3_was_missing": 0,
            "ph_outlet_d1_was_missing": 0
        }
        for i in range(7)
    ]
    # Exactly 7 steps on industrial Spark data -> SUCCESS
    res_7 = forecast_service.predict(
        device_id="DIGESTER_001",
        model_name="XCO-Net",
        data_source=ProvenanceEnum.REAL_SPARK_HISTORICAL,
        history_window=history_7d
    )
    assert res_7.status == ForecastStatusEnum.SUCCESS.value
    assert res_7.predicted_biogas_m3_day > 0.0
    assert res_7.domain_valid is True

    # 6 steps on industrial Spark data -> INSUFFICIENT_HISTORY
    res_6 = forecast_service.predict(
        device_id="DIGESTER_001",
        model_name="XCO-Net",
        data_source=ProvenanceEnum.REAL_SPARK_HISTORICAL,
        history_window=history_7d[:6]
    )
    assert res_6.status == ForecastStatusEnum.INSUFFICIENT_HISTORY.value
    assert res_6.predicted_biogas_m3_day == 0.0


def test_xconet_spark_replay_execution():
    """Verify Spark replay with XCO-Net generates valid causal predictions."""
    timeline = forecast_service.get_spark_replay_timeline(
        model_name="XCO-Net",
        mode="held_out_test"
    )
    assert len(timeline) == 24
    for item in timeline:
        assert item.status == "SUCCESS"
        assert item.predicted_next_day_nm3 is not None
        assert item.predicted_next_day_nm3 > 0.0
        assert item.history_length == 7


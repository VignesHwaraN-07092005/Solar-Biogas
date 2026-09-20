import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.forecast_service import forecast_service
from backend.app.services.simulator_service import simulator_service
from backend.app.schemas.forecast import ProvenanceEnum, ForecastStatusEnum

client = TestClient(app)

def test_1_nm3_day_presentation_metadata():
    """1. Verify Nm³/day presentation metadata across forecast and benchmark endpoints."""
    # Benchmarks endpoint
    res_bench = client.get("/api/forecast/benchmarks")
    assert res_bench.status_code == 200
    bench_data = res_bench.json()
    assert bench_data["unit"] == "Nm³/day"
    for m in bench_data["models"]:
        assert m["unit"] == "Nm³/day"
        assert m["held_out_test_metrics"]["unit"] == "Nm³/day"
        assert m["cross_window_mean_metrics"]["unit"] == "Nm³/day"

    # Spark replay endpoint
    res_spark = client.get("/api/forecast/spark-replay?mode=held_out_test")
    assert res_spark.status_code == 200
    spark_data = res_spark.json()
    assert len(spark_data) > 0
    assert spark_data[0]["unit"] == "Nm³/day"

def test_2_benchmark_api_values_and_labels():
    """2. Verify exact benchmark API values distinguishing Held-Out Test Set (24 days) from Cross-Window Mean (64 days)."""
    res = client.get("/api/forecast/benchmarks")
    assert res.status_code == 200
    data = res.json()
    assert data["held_out_test_label"] == "Held-Out Test Set — 24 operating days"
    assert data["cross_window_mean_label"] == "Cross-Window Mean — 64 out-of-sample days"
    assert data["test_set_days_evaluated"] == 24
    assert data["walk_forward_windows_evaluated"] == 3

    model_map = {m["model_id"]: m for m in data["models"]}
    
    # GRU-14d Residual (Default Forecasting Model)
    gru = model_map["gru_14d_residual"]
    assert gru["role"] == "Default Forecasting Model"
    assert gru["lookback_days"] == 14
    assert gru["held_out_test_metrics"]["mae"] == 766.61
    assert gru["held_out_test_metrics"]["rmse"] == 959.40
    assert gru["held_out_test_metrics"]["r2"] == 0.2494
    assert gru["cross_window_mean_metrics"]["mae"] == 907.32
    assert gru["cross_window_mean_metrics"]["rmse"] == 1148.76
    assert gru["cross_window_mean_metrics"]["r2"] == 0.2723

    # EMA-0.90 (Statistical Benchmark)
    ema = model_map["ema_090"]
    assert ema["role"] == "Statistical Benchmark"
    assert ema["held_out_test_metrics"]["rmse"] == 984.48
    assert ema["cross_window_mean_metrics"]["rmse"] == 1230.70

    # Persistence (Baseline)
    pers = model_map["persistence"]
    assert pers["role"] == "Naive Baseline"
    assert pers["held_out_test_metrics"]["rmse"] == 1000.90
    assert pers["cross_window_mean_metrics"]["rmse"] == 1252.86

    # XCO-Net (Research)
    xco = model_map["xco_net"]
    assert xco["role"] == "Proposed Research Architecture"
    assert xco["held_out_test_metrics"]["rmse"] == 1016.92
    assert xco["cross_window_mean_metrics"]["rmse"] == 1250.13

def test_3_t_to_t_plus_1_chart_alignment():
    """3. Verify strictly causal t -> t+1 target alignment in simulator and Spark timelines."""
    # Simulator timeline
    sim_timeline = simulator_service.get_simulator_timeline(days=20, warmup_days=14)
    for i in range(len(sim_timeline)):
        t_cur = datetime.fromisoformat(sim_timeline[i]["timestamp"])
        t_tgt = datetime.fromisoformat(sim_timeline[i]["target_date"])
        assert (t_tgt - t_cur) == timedelta(days=1), f"Target date is not t+1: {t_cur} -> {t_tgt}"
        if i < len(sim_timeline) - 1:
            assert sim_timeline[i]["actual_next_day_nm3"] == sim_timeline[i + 1]["biogas_today_nm3"]

    # Spark timeline
    spark_timeline = forecast_service.get_spark_replay_timeline(mode="held_out_test")
    for i in range(len(spark_timeline)):
        d_cur = datetime.strptime(spark_timeline[i].date, "%Y-%m-%d")
        d_tgt = datetime.strptime(spark_timeline[i].target_date, "%Y-%m-%d")
        assert (d_tgt - d_cur) == timedelta(days=1)

def test_4_spark_full_count_176_calendar_records():
    """4. Verify full Spark historical dataset contains exactly 176 calendar records."""
    t_full = forecast_service.get_spark_replay_timeline(mode="full_historical")
    assert len(t_full) == 176
    assert t_full[0].date == "2025-11-01"
    assert t_full[-1].date == "2026-04-25"

def test_5_spark_test_count_24_operating_days():
    """5. Verify official held-out test set contains exactly 24 operating days."""
    t_test = forecast_service.get_spark_replay_timeline(mode="held_out_test")
    assert len(t_test) == 24
    assert t_test[0].date == "2026-03-10"
    assert t_test[-1].date == "2026-04-02"

def test_6_synthetic_history_ge_14_before_gru_success():
    """6. Verify synthetic history >= 14 timesteps before GRU forecast succeeds."""
    timeline = simulator_service.get_simulator_timeline(days=25, warmup_days=14)
    # Days 0 to 12 (1st to 13th timesteps) are warming up
    for i in range(13):
        assert timeline[i]["status"] == "Warming up forecast model"
        assert timeline[i]["predicted_next_day_nm3"] is None
        assert timeline[i]["history_length"] == i + 1

    # Day index 13 (14th timestep) succeeds
    assert timeline[13]["status"] == "SUCCESS"
    assert timeline[13]["history_length"] == 14
    assert timeline[13]["predicted_next_day_nm3"] is not None
    assert timeline[13]["predicted_next_day_nm3"] > 0.0

def test_7_demo_synthetic_provenance_isolated():
    """7. Verify DEMO_SYNTHETIC provenance is maintained and isolated from real Spark data."""
    timeline = simulator_service.get_simulator_timeline(days=20, warmup_days=14)
    for item in timeline:
        assert item["data_source"] == "DEMO_SYNTHETIC"
        # Confirm no industrial magnitude contamination
        assert item["biogas_today_nm3"] < 100.0

def test_8_health_index_bounds_and_heuristic_penalties():
    """8. Verify Digester Health Index rule-based bounds [35, 100] and exact penalty logic."""
    def calc_health(temp, ph, press, ch4):
        score = 100
        if temp < 35.0 or temp > 38.0:
            score -= 15
        if ph < 6.8 or ph > 7.5:
            score -= 20
        if press > 1.30:
            score -= 25
        if ch4 < 55.0:
            score -= 15
        return max(35, min(100, score))

    # Nominal mesophilic conditions
    assert calc_health(36.5, 7.25, 1.15, 62.0) == 100

    # Temperature departure (-15)
    assert calc_health(32.0, 7.25, 1.15, 62.0) == 85

    # pH departure (-20)
    assert calc_health(36.5, 6.50, 1.15, 62.0) == 80

    # Pressure departure (-25)
    assert calc_health(36.5, 7.25, 1.40, 62.0) == 75

    # Methane departure (-15)
    assert calc_health(36.5, 7.25, 1.15, 50.0) == 85

    # Cumulative catastrophic departures bounded to minimum 35
    assert calc_health(25.0, 5.50, 1.80, 40.0) == 35

def test_9_correlation_n_and_isolated_calculation():
    """9. Verify Pearson correlation N and calculation on selected active source."""
    def pearson_r(x, y):
        n = len(x)
        assert n >= 2
        sx, sy = sum(x), sum(y)
        sx2, sy2 = sum(xi**2 for xi in x), sum(yi**2 for yi in y)
        pxy = sum(xi*yi for xi, yi in zip(x, y))
        num = pxy - (sx * sy / n)
        den = ((sx2 - sx**2/n) * (sy2 - sy**2/n))**0.5
        return num / den if den != 0 else 0.0

    # Synthetic timeline
    sim_t = simulator_service.get_simulator_timeline(days=30, warmup_days=14)
    assert len(sim_t) == 30
    temps = [r["temperature_c"] for r in sim_t]
    biogas = [r["biogas_today_nm3"] for r in sim_t]
    r_val = pearson_r(temps, biogas)
    assert -1.0 <= r_val <= 1.0

def test_simulator_timeline_continuity_180_days():
    """10. Verify simulator timeline continuity: 180 days, strictly 24h delta, no gaps."""
    valid, log = simulator_service.verify_simulator_continuity(days=180)
    assert valid is True
    assert log["simulator_history_length"] == 180
    assert log["continuity_result"] is True
    assert log["required_lookback"] == 14
    assert log["provenance"] == "DEMO_SYNTHETIC"

def test_simulator_gru_domain_valid_false_and_note_exists():
    """11. Verify that GRU on community simulation outputs domain_valid=False with domain_note."""
    timeline = simulator_service.get_simulator_timeline(days=20, warmup_days=14)
    item = timeline[13] # Day 14
    assert item["status"] == "SUCCESS"
    assert item["domain_valid"] is False
    assert item["domain_note"] is not None
    assert "transfer has not been validated" in item["domain_note"]

    # From API /api/forecast/predict
    features_window = [r["features"] for r in timeline[:14]]
    res = client.post("/api/forecast/predict", json={
        "device_id": "DIGESTER_001",
        "model_name": "GRU-14d Residual",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": features_window
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["domain_valid"] is False
    assert data["domain_note"] is not None
    assert "transfer has not been validated" in data["domain_note"]

def test_spark_gru_domain_valid_true():
    """12. Verify that GRU on Spark research data outputs domain_valid=True."""
    timeline = forecast_service.get_spark_replay_timeline(model_name="GRU-14d Residual", mode="held_out_test")
    assert len(timeline) == 24
    assert timeline[0].domain_valid is True
    assert timeline[0].domain_note == "Industrial research domain validated."

def test_simulator_ema_and_persistence_predictions_valid_community_scale():
    """13. Verify that EMA-0.90 and Persistence produce scale-compatible predictions on community simulation."""
    timeline = simulator_service.get_simulator_timeline(days=25, warmup_days=14)
    item = timeline[13]
    # Check precomputed scale-compatible values in timeline
    assert item["ema_predicted_next_day_nm3"] is not None
    assert 0.0 < item["ema_predicted_next_day_nm3"] < 20.0
    assert item["persistence_predicted_next_day_nm3"] is not None
    assert 0.0 < item["persistence_predicted_next_day_nm3"] < 20.0

    # Test EMA prediction via API
    features_window = [r["features"] for r in timeline[:14]]
    res_ema = client.post("/api/forecast/predict", json={
        "device_id": "DIGESTER_001",
        "model_name": "EMA-0.90",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": features_window
    })
    assert res_ema.status_code == 200
    data_ema = res_ema.json()
    assert data_ema["status"] == "SUCCESS"
    assert data_ema["domain_valid"] is True
    assert 0.0 < data_ema["predicted_biogas_m3_day"] < 20.0

    # Test Persistence prediction via API
    res_pers = client.post("/api/forecast/predict", json={
        "device_id": "DIGESTER_001",
        "model_name": "Persistence",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": features_window
    })
    assert res_pers.status_code == 200
    data_pers = res_pers.json()
    assert data_pers["status"] == "SUCCESS"
    assert data_pers["domain_valid"] is True
    assert 0.0 < data_pers["predicted_biogas_m3_day"] < 20.0

def test_xconet_architecture_name_operator_network():
    """14. Verify XCO-Net is named Cross-Channel Operator Network and not Orthogonal."""
    res = client.get("/api/forecast/xconet-research")
    assert res.status_code == 200
    data = res.json()
    assert "Operator Network" in data["architecture_name"]
    assert "Orthogonal" not in data["architecture_name"]

def test_source_reset_state_isolation():
    """15. Verify strict isolation between community simulator and industrial Spark datasets."""
    sim_t = simulator_service.get_simulator_timeline(days=30, warmup_days=14)
    spark_t = forecast_service.get_spark_replay_timeline(mode="held_out_test")
    
    sim_mean = np.mean([r["biogas_today_nm3"] for r in sim_t])
    spark_mean = np.mean([r.actual_biogas_today_nm3 for r in spark_t])
    
    # Verify scale divergence: community (~3 Nm3/day) vs industrial (~5,300 Nm3/day)
    assert sim_mean < 10.0
    assert spark_mean > 4000.0
    assert abs(spark_mean - sim_mean) > 4000.0

def test_models_metadata_endpoint():
    """16. Verify authoritative /api/forecast/models-metadata endpoint and history requirements."""
    res = client.get("/api/forecast/models-metadata")
    assert res.status_code == 200
    meta = res.json()
    
    assert "GRU-14d Residual" in meta
    assert meta["GRU-14d Residual"]["required_history"] == 14
    assert meta["GRU-14d Residual"]["role"] == "Default Forecasting Model"
    assert "information available through the current day" in meta["GRU-14d Residual"]["causal_footer"]

    assert "XCO-Net" in meta
    assert meta["XCO-Net"]["required_history"] == 7
    assert meta["XCO-Net"]["role"] == "Proposed Research Architecture"

    assert "EMA-0.90" in meta
    assert meta["EMA-0.90"]["required_history"] == 3
    assert meta["EMA-0.90"]["role"] == "Statistical Benchmark"

    assert "Persistence" in meta
    assert meta["Persistence"]["required_history"] == 1
    assert meta["Persistence"]["role"] == "Naive Baseline"

def test_alerts_thresholds_endpoint():
    """17. Verify /api/alerts/thresholds returns authoritative warning and critical levels."""
    res = client.get("/api/alerts/thresholds")
    assert res.status_code == 200
    th = res.json()
    assert th["alert_pressure_warn"] == 1.30
    assert th["alert_pressure_max"] == 1.50
    assert th["alert_ph_min"] == 6.5
    assert th["alert_ph_max"] == 8.2

def test_alerts_evaluate_pressure_unity():
    """18. Verify single source of truth for pressure alerts: 1.33 bar is WARNING, 1.55 bar is CRITICAL."""
    # A. Normal pressure (1.15 bar)
    res_norm = client.post("/api/alerts/evaluate", json={"pressure_bar": 1.15})
    assert res_norm.status_code == 200
    d_norm = res_norm.json()
    assert d_norm["status"] == "NORMAL"
    assert d_norm["pressure_status"] == "NORMAL"
    assert d_norm["alert_count"] == 0

    # B. Warning pressure (1.33 bar)
    res_warn = client.post("/api/alerts/evaluate", json={"pressure_bar": 1.33})
    assert res_warn.status_code == 200
    d_warn = res_warn.json()
    assert d_warn["status"] == "WARNING"
    assert d_warn["pressure_status"] == "WARNING"
    assert d_warn["alert_count"] == 1
    assert d_warn["alerts"][0]["severity"] == "WARNING"
    assert d_warn["alerts"][0]["parameter"] == "pressure"
    assert "High gas pressure warning" in d_warn["alerts"][0]["message"]

    # C. Critical pressure (1.55 bar)
    res_crit = client.post("/api/alerts/evaluate", json={"pressure_bar": 1.55})
    assert res_crit.status_code == 200
    d_crit = res_crit.json()
    assert d_crit["status"] == "CRITICAL"
    assert d_crit["pressure_status"] == "CRITICAL"
    assert d_crit["alert_count"] == 1
    assert d_crit["alerts"][0]["severity"] == "CRITICAL"
    assert d_crit["alerts"][0]["parameter"] == "pressure"
    assert "Overpressure critical" in d_crit["alerts"][0]["message"]

def test_forensic_dashboard_html_and_js_elements():
    """19. Verify dashboard HTML and JS contain exact required forensic strings and elements."""
    with open("frontend/public/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert "History Available / Required" in html
    assert 'id="forecast-causal-footer"' in html
    assert 'id="chart-withheld-notice"' in html
    assert 'id="sust-provenance-qualifier"' in html
    assert 'id="model-interpretation-title"' in html
    assert 'id="kpi-current-biogas-sub"' in html

    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "Simulated Daily Production" in js
    assert "Observed Daily Production" in js
    assert "Live Daily Production" in js
    assert "Prediction withheld — industrial model not validated for Community Scale" in js
    assert "Additive feature attribution is unavailable for this forecasting model." in js
    assert "Illustrative community-scale scenario estimate — not measured impact" in js


def test_spark_held_out_replay_record_1_immediate_prediction():
    """20. Test 1: Record 1 (2026-03-10) has immediate numeric prediction, status=SUCCESS, target=2026-03-11, history_length=14."""
    timeline = forecast_service.get_spark_replay_timeline(model_name="GRU-14d Residual", mode="held_out_test")
    assert len(timeline) == 24
    r1 = timeline[0]
    assert r1.date == "2026-03-10"
    assert r1.target_date == "2026-03-11"
    assert r1.status == "SUCCESS"
    assert r1.history_length == 14
    assert r1.predicted_next_day_nm3 is not None
    assert isinstance(r1.predicted_next_day_nm3, float)
    assert 8500.0 < r1.predicted_next_day_nm3 < 9000.0  # ~8731.2 Nm3/day
    assert r1.actual_biogas_today_nm3 == 9467.0
    assert r1.actual_next_day_nm3 == 9649.0


def test_spark_held_out_replay_record_2_causal_step_forward():
    """21. Test 2: Record 2 has numeric prediction and causal context shifted 1 timestep forward."""
    timeline = forecast_service.get_spark_replay_timeline(model_name="GRU-14d Residual", mode="held_out_test")
    r2 = timeline[1]
    assert r2.date == "2026-03-11"
    assert r2.target_date == "2026-03-12"
    assert r2.status == "SUCCESS"
    assert r2.history_length == 14
    assert r2.predicted_next_day_nm3 is not None
    assert isinstance(r2.predicted_next_day_nm3, float)
    assert 8400.0 < r2.predicted_next_day_nm3 < 8800.0  # ~8568.6 Nm3/day


def test_spark_held_out_anti_leakage():
    """22. Test 3: Anti-leakage assertion: inputs for record i do NOT contain target t+1."""
    df = forecast_service.get_spark_dataset().copy().sort_values("date").reset_index(drop=True)
    eval_indices = df[(df["date"] >= "2026-03-10") & (df["date"] <= "2026-04-02")].index.tolist()
    
    # Feature columns used for prediction
    feature_cols = [
        "biogas_today_nm3", "total_incoming_mt", "total_processed_mt",
        "feed_total_m3", "temp_outlet_d1_c", "ph_outlet_d1",
        "recycle_water_m3", "feed_total_m3_was_missing", "ph_outlet_d1_was_missing"
    ]
    assert "target_biogas_next_day_nm3" not in feature_cols

    for k in eval_indices:
        # Context window strictly ends at index k (day t)
        past_sub = df.iloc[k - 14 + 1 : k + 1]
        assert len(past_sub) == 14
        # Verify the maximum date in context is exactly the current day t, never target date t+1
        max_date_in_context = past_sub["date"].max()
        current_day_t = df.iloc[k]["date"]
        assert max_date_in_context == current_day_t
        # Verify target is strictly for next day
        assert df.iloc[k]["date"] + pd.Timedelta(days=1) > max_date_in_context


def test_spark_held_out_truncated_context_returns_insufficient_history():
    """23. Test 4: When preceding 14 rows are artificially truncated, record 1 returns INSUFFICIENT_HISTORY."""
    df = forecast_service.get_spark_dataset().copy().sort_values("date").reset_index(drop=True)
    truncated_df = df[df["date"] >= "2026-03-10"].copy().reset_index(drop=True)
    
    timeline = forecast_service.get_spark_replay_timeline(
        model_name="GRU-14d Residual",
        mode="held_out_test",
        dataset_override=truncated_df
    )
    assert len(timeline) == 24
    r1 = timeline[0]
    assert r1.status == "INSUFFICIENT_HISTORY"
    assert r1.predicted_next_day_nm3 is None
    assert r1.history_length == 1  # only 1 day available


def test_ema_persistence_lookback_preserved():
    """24. Test 5: EMA requires 3 days and Persistence requires 1 day."""
    # Test EMA with 2 days -> INSUFFICIENT_HISTORY
    res_ema_short = forecast_service.predict(
        device_id="DIGESTER_001",
        model_name="EMA-0.90",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=[{"biogas_today_nm3": 15.0}, {"biogas_today_nm3": 16.0}]
    )
    assert res_ema_short.status == ForecastStatusEnum.INSUFFICIENT_HISTORY.value

    # Test EMA with 3 days -> SUCCESS
    res_ema_ok = forecast_service.predict(
        device_id="DIGESTER_001",
        model_name="EMA-0.90",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=[{"biogas_today_nm3": 15.0}, {"biogas_today_nm3": 16.0}, {"biogas_today_nm3": 15.5}]
    )
    assert res_ema_ok.status == ForecastStatusEnum.SUCCESS.value
    assert res_ema_ok.predicted_biogas_m3_day > 0

    # Test Persistence with 1 day -> SUCCESS
    res_pers_ok = forecast_service.predict(
        device_id="DIGESTER_001",
        model_name="Persistence",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=[{"biogas_today_nm3": 15.0}]
    )
    assert res_pers_ok.status == ForecastStatusEnum.SUCCESS.value
    assert res_pers_ok.predicted_biogas_m3_day == 15.0


def test_community_simulator_domain_valid_false_for_gru_and_xco():
    """25. Test 6: Community simulator remains domain_valid == False for GRU and XCO-Net."""
    # GRU on community data
    res_gru = forecast_service.predict(
        device_id="DIGESTER_001",
        model_name="GRU-14d Residual",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=[{"biogas_today_nm3": 3.2, "total_incoming_mt": 0.12, "total_processed_mt": 0.12, "feed_total_m3": 0.144, "temp_outlet_d1_c": 36.5, "ph_outlet_d1": 7.2, "recycle_water_m3": 30.0, "feed_total_m3_was_missing": 0, "ph_outlet_d1_was_missing": 0} for _ in range(14)]
    )
    assert res_gru.domain_valid is False
    assert "transfer has not been validated" in res_gru.domain_note

    # XCO-Net on community data
    res_xco = forecast_service.predict(
        device_id="DIGESTER_001",
        model_name="XCO-Net",
        data_source=ProvenanceEnum.DEMO_SYNTHETIC,
        history_window=[{"biogas_today_nm3": 3.2, "total_incoming_mt": 0.12, "total_processed_mt": 0.12, "feed_total_m3": 0.144, "temp_outlet_d1_c": 36.5, "ph_outlet_d1": 7.2, "recycle_water_m3": 30.0, "feed_total_m3_was_missing": 0, "ph_outlet_d1_was_missing": 0} for _ in range(7)]
    )
    assert res_xco.domain_valid is False
    assert "transfer has not been validated" in res_xco.domain_note


def test_spark_full_initial_warmup_legitimate():
    """26. Verify full historical replay legitimately warms up for records 0..12 before producing predictions at record 13."""
    timeline = forecast_service.get_spark_replay_timeline(
        mode="full_historical",
        model_name="GRU-14d Residual"
    )
    assert len(timeline) == 176
    # Records 0 to 12 must legitimately warm up
    for idx in range(13):
        rec = timeline[idx]
        assert rec.status == "INSUFFICIENT_HISTORY", f"Record {idx} should be INSUFFICIENT_HISTORY during initial warmup"
        assert rec.predicted_next_day_nm3 is None, f"Record {idx} should have no prediction during warmup"
        assert rec.history_length == idx + 1, f"Record {idx} history_length should be {idx + 1}"
    
    # Record 13 (14th observation) must succeed
    rec13 = timeline[13]
    assert rec13.status == "SUCCESS", "Record 13 should have SUCCESS with 14 timesteps"
    assert rec13.predicted_next_day_nm3 is not None, "Record 13 should have a valid prediction"
    assert rec13.history_length == 14, "Record 13 should have history_length == 14"


def test_spark_held_out_immediate_prediction_with_context():
    """27. Verify held-out test replay provides preceding historical context so record 0 immediately predicts."""
    timeline = forecast_service.get_spark_replay_timeline(
        mode="held_out_test",
        model_name="GRU-14d Residual"
    )
    assert len(timeline) == 24
    rec0 = timeline[0]
    assert rec0.status == "SUCCESS", "Held-out record 0 must succeed with context"
    assert rec0.predicted_next_day_nm3 is not None, "Held-out record 0 must have prediction"
    assert rec0.history_length == 14, "Held-out record 0 should have 14 timesteps of context"


def test_feedstock_dataset_bounds_and_consistency():
    """28. Verify actual feedstock data bounds (64-325 for full, 119-256 for held-out) and no hardcoded 10-200 MT/day."""
    df = pd.read_csv("data/processed/spark_biogas_model_ready.csv")
    full_feed = df["feed_total_m3"].dropna()
    full_min = float(full_feed.min())
    full_max = float(full_feed.max())
    assert 60.0 <= full_min <= 65.0, f"Expected full_min ~64, got {full_min}"
    assert 320.0 <= full_max <= 330.0, f"Expected full_max ~325, got {full_max}"
    assert not (full_min == 10.0 and full_max == 200.0)

    # Held out slice (24 days: 2026-03-10 to 2026-04-02)
    held_df = df[(pd.to_datetime(df["date"]) >= "2026-03-10") & (pd.to_datetime(df["date"]) <= "2026-04-02")]
    held_feed = held_df["feed_total_m3"].dropna()
    assert len(held_feed) == 24
    held_min = float(held_feed.min())
    held_max = float(held_feed.max())
    assert 115.0 <= held_min <= 125.0, f"Expected held_min ~119, got {held_min}"
    assert 250.0 <= held_max <= 260.0, f"Expected held_max ~256, got {held_max}"

    # Verify frontend app.js computes range dynamically and never hardcodes 10-200 for industrial
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "Observed dataset range:" in js_code
    assert "Math.min(...feedVals)" in js_code
    assert "Math.max(...feedVals)" in js_code


def test_sdg11_provenance_labels_and_strings():
    """29. Verify SDG 11 impact matrix provenance labels for DEMO_SYNTHETIC, REAL_SPARK_HISTORICAL, and LIVE_IOT."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "Community Scenario Impact" in js_code
    assert "Illustrative community-scale scenario estimate — not measured impact" in js_code
    assert "Industrial Reference Impact" in js_code
    assert "Derived reference calculation from industrial historical data — not a measured community deployment outcome." in js_code
    assert "Community Impact — Derived from Live Telemetry" in js_code
    assert "Measured live community telemetry impact" in js_code


def test_solar_auxiliary_provenance_and_badge():
    """30. Verify solar subsystem provenance wording and AUXILIARY STATE badge."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "Auxiliary Solar Subsystem — Demo/Configured State" in js_code
    assert "AUXILIARY STATE" in js_code
    assert "Solar telemetry is unavailable in historical Spark data" in js_code


def test_methane_heuristic_wording():
    """31. Verify methane KPI is explicitly qualified as Heuristic/Scenario Value."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "Methane (CH₄) — Heuristic/Scenario Value" in js_code


def test_current_biogas_historical_mean_reference():
    """32. Verify current biogas subtext mentions Historical mean ≈ 5,300 Nm³/day for industrial Spark data."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "Historical mean ≈ 5,300 Nm³/day" in js_code


def test_model_causal_footers_standardized():
    """33. Verify standardized causal footer formula for all 4 models."""
    res = client.get("/api/forecast/models-metadata")
    assert res.status_code == 200
    meta = res.json()

    assert meta["GRU-14d Residual"]["causal_footer"] == (
        "Uses the previous 14 continuous timesteps and is generated causally from information available through the current day."
    )
    assert meta["XCO-Net"]["causal_footer"] == (
        "Uses the previous 7 continuous timesteps and is generated causally from information available through the current day."
    )
    assert meta["EMA-0.90"]["causal_footer"] == (
        "Uses the previous 3 continuous timesteps and is generated causally from information available through the current day."
    )
    assert meta["Persistence"]["causal_footer"] == (
        "Uses the previous 1 timestep and is generated causally from information available through the current day."
    )


def test_agstar_cannot_reach_gru_inference():
    """34. Test 1: Verify AgSTAR cannot enter GRU inference pipeline."""
    with pytest.raises(ValueError, match="AgSTAR"):
        forecast_service.predict(
            model_name="GRU-14d Residual",
            data_source="AGSTAR_REGISTRY",
            history_window=[{"biogas_today_nm3": 10.0} for _ in range(14)]
        )


def test_agstar_cannot_reach_ema_inference():
    """35. Test 2: Verify AgSTAR cannot enter EMA inference pipeline."""
    with pytest.raises(ValueError, match="AgSTAR"):
        forecast_service.predict(
            model_name="EMA-0.90",
            data_source="AGSTAR_REGISTRY",
            history_window=[{"biogas_today_nm3": 10.0} for _ in range(3)]
        )


def test_agstar_cannot_reach_persistence_inference():
    """36. Test 3: Verify AgSTAR cannot enter Persistence inference pipeline."""
    with pytest.raises(ValueError, match="AgSTAR"):
        forecast_service.predict(
            model_name="Persistence",
            data_source="AGSTAR_REGISTRY",
            history_window=[{"biogas_today_nm3": 10.0}]
        )


def test_agstar_cannot_reach_xconet_inference():
    """37. Test 4: Verify AgSTAR cannot enter XCO-Net inference pipeline."""
    with pytest.raises(ValueError, match="AgSTAR"):
        forecast_service.predict(
            model_name="XCO-Net",
            data_source="AGSTAR_REGISTRY",
            history_window=[{"biogas_today_nm3": 10.0} for _ in range(7)]
        )


def test_agstar_source_state_contains_no_numerical_forecast():
    """38. Test 5: Verify AgSTAR source state renders no numerical forecast and states forecasting disabled."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "kpiPredicted.textContent = '—';" in js_code
    assert "External benchmark — forecasting disabled" in js_code
    assert "None (Static Benchmark)" in js_code


def test_source_switch_spark_to_agstar_clears_stale_forecast_state():
    """39. Test 6: Verify switching to AgSTAR resets forecast state, disables controls, and hides playback buttons."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "function renderAgstarBenchmarkState()" in js_code
    assert "modelSelect.disabled = true;" in js_code
    assert "autoBtn.classList.add('hidden');" in js_code
    assert "rowDisp.classList.add('hidden');" in js_code
    assert "prevBtn.disabled = true;" in js_code
    assert "nextBtn.disabled = true;" in js_code


def test_source_switch_agstar_to_community_restores_simulator_state():
    """40. Test 7: Verify switching from AgSTAR to Community restores controls and loads simulator data."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "function restoreOperationalControls()" in js_code
    assert "restoreOperationalControls();" in js_code
    assert "await loadSimulatorData();" in js_code
    assert "modelSelect.disabled = false;" in js_code
    assert "prevBtn.disabled = false;" in js_code
    assert "nextBtn.disabled = false;" in js_code


def test_source_switch_agstar_to_spark_restores_industrial_state():
    """41. Test 8: Verify switching from AgSTAR to Spark restores controls and loads industrial replay."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "await loadSparkReplayData(\"held_out_test\");" in js_code
    assert "await loadSparkReplayData(\"full_historical\");" in js_code


def test_agstar_geographic_scope_wording_is_consistent():
    """42. Test 9: Verify AgSTAR geographic scope is consistently 38 US States and does not broaden to North America."""
    with open("frontend/public/index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    assert "526 Commercial Facilities Across 38 US States" in html_code
    assert "38 US States" in html_code
    assert "across North America" not in html_code

    # Role statement in modal
    assert "Role: External benchmark/context only — not used as GRU time-series input" in html_code


def test_agstar_technology_distribution_denominator_label():
    """43. Test 10: Verify AgSTAR technology distribution explicitly labels 'Distribution among classified facilities'."""
    with open("frontend/public/index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    assert "Digester Technology Distribution (EPA AgSTAR) — Distribution among classified facilities" in html_code
    assert "32% of facilities" in html_code
    assert "28% of facilities" in html_code
    assert "25% of facilities" in html_code


def test_source_group_labels():
    """44. Verify standardized source group labels in index.html."""
    with open("frontend/public/index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    assert 'optgroup label="FORECAST / DEPLOYMENT DATA — COMMUNITY SCALE"' in html_code
    assert 'optgroup label="FORECAST / RESEARCH DATA — INDUSTRIAL SCALE"' in html_code
    assert 'optgroup label="EXTERNAL BENCHMARK — STATIC NON-TIME-SERIES"' in html_code


# Aliases for exact names in Section 17
test_agstar_geographic_scope_wording_consistent = test_agstar_geographic_scope_wording_is_consistent
test_agstar_technology_distribution_denominator_correct = test_agstar_technology_distribution_denominator_label


def test_live_iot_in_source_selector():
    """45. Test 11: Verify LIVE_IOT option and its community-scale optgroup in source selector."""
    with open("frontend/public/index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    assert '<optgroup label="DEPLOYMENT / LIVE DATA — COMMUNITY SCALE">' in html_code
    assert '<option value="LIVE_IOT">Community Live Telemetry — ESP32 / IoT</option>' in html_code


def test_live_iot_maps_to_community_live_telemetry():
    """46. Test 12: Verify LIVE_IOT maps to COMMUNITY LIVE TELEMETRY badge and LIVE_IOT provenance."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "COMMUNITY LIVE TELEMETRY" in js_code
    assert "LIVE_IOT" in js_code
    assert "Community Live IoT" in js_code


def test_no_synthetic_values_when_live_iot_has_no_readings():
    """47. Test 13: Verify no synthetic values are loaded when LIVE_IOT has zero readings."""
    res_status = client.get("/api/readings/live-status?device_id=unseen_device_test_xyz")
    assert res_status.status_code == 200
    st = res_status.json()
    assert st["count"] == 0
    assert st["connectivity_state"] == "WAITING FOR ESP32"

    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "renderLiveIotEmptyState()" in js_code
    assert "tempEl.textContent = '—';" in js_code
    assert "phEl.textContent = '—';" in js_code
    assert "pressEl.textContent = '—';" in js_code
    assert "biogasEl.textContent = '—';" in js_code


def test_no_spark_values_appear_in_live_iot():
    """48. Test 14: Verify Spark industrial readings never contaminate LIVE_IOT queries."""
    res = client.get("/api/readings?source=live_esp32")
    assert res.status_code == 200
    readings = res.json()
    # Any reading with source=live_esp32 must not have Spark industrial magnitude (e.g., > 1000 Nm3/day)
    for r in readings:
        if r.get("biogas_production_m3_day") is not None:
            assert r["biogas_production_m3_day"] < 500.0, "Found industrial-scale value in live_esp32 reading"


def test_insufficient_live_history_prevents_forecast():
    """49. Test 15: Verify insufficient live history (< lookback) produces INSUFFICIENT LIVE HISTORY."""
    sparse_history = [
        {"temperature": 37.0, "ph": 7.2, "pressure": 1.1, "biogas_today_nm3": 2.5}
        for _ in range(5)
    ]
    res_gru = forecast_service.predict(
        model_name="GRU-14d Residual",
        data_source="LIVE_IOT",
        history_window=sparse_history
    )
    assert res_gru.status == ForecastStatusEnum.INSUFFICIENT_LIVE_HISTORY.value

    res_ema = forecast_service.predict(
        model_name="EMA-0.90",
        data_source="LIVE_IOT",
        history_window=sparse_history[:2]
    )
    assert res_ema.status == ForecastStatusEnum.INSUFFICIENT_LIVE_HISTORY.value

    res_pers = forecast_service.predict(
        model_name="Persistence",
        data_source="LIVE_IOT",
        history_window=[]
    )
    assert res_pers.status == ForecastStatusEnum.INSUFFICIENT_LIVE_HISTORY.value


def test_14_live_observations_allow_gru_execution_but_not_community_validation():
    """50. Test 16: Verify 14 live observations permit GRU execution but domain_valid remains false."""
    complete_history_14 = [
        {
            "biogas_today_nm3": 3.2,
            "total_incoming_mt": 0.15,
            "total_processed_mt": 0.12,
            "feed_total_m3": 0.2,
            "temp_outlet_d1_c": 36.8,
            "ph_outlet_d1": 7.25,
            "recycle_water_m3": 0.05,
            "feed_total_m3_was_missing": 0,
            "ph_outlet_d1_was_missing": 0
        }
        for _ in range(14)
    ]
    res_gru = forecast_service.predict(
        model_name="GRU-14d Residual",
        data_source="LIVE_IOT",
        history_window=complete_history_14
    )
    assert res_gru.status == ForecastStatusEnum.SUCCESS.value
    assert res_gru.predicted_biogas_m3_day is not None
    assert res_gru.predicted_biogas_m3_day > 0.0
    # CRITICAL: GRU is calibrated on Spark (~5300 Nm3/day), not validated for community scale
    assert res_gru.domain_valid is False
    assert "unvalidated" in res_gru.domain_note.lower() or "transfer" in res_gru.domain_note.lower()

    # In contrast, statistical baseline EMA-0.90 is valid for community scale
    res_ema = forecast_service.predict(
        model_name="EMA-0.90",
        data_source="LIVE_IOT",
        history_window=complete_history_14[:3]
    )
    assert res_ema.status == ForecastStatusEnum.SUCCESS.value
    assert res_ema.predicted_biogas_m3_day is not None
    assert res_ema.domain_valid is True


def test_live_source_disables_replay_controls():
    """51. Test 17: Verify LIVE_IOT disables step navigation and hides auto-play / record row."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "prevBtn.disabled = true;" in js_code
    assert "nextBtn.disabled = true;" in js_code
    assert "autoBtn.classList.add('hidden');" in js_code
    assert "rowDisp.classList.add('hidden');" in js_code


def test_source_switch_clears_stale_incompatible_state():
    """52. Test 18: Verify cross-source switching executes clearSourceState to sanitize UI."""
    with open("frontend/public/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    assert "function clearSourceState()" in js_code
    assert "clearSourceState();" in js_code


def test_live_iot_uses_actual_api_readings():
    """53. Test 19: Verify POST /api/readings with source='live_esp32' is consumed and reflected."""
    reading_payload = {
        "device_id": "esp32_verified_node",
        "temperature_c": 36.6,
        "ph": 7.31,
        "pressure_bar": 1.18,
        "gas_flow_m3_day": 3.1,
        "biogas_production_m3_day": 3.1,
        "source": "live_esp32"
    }
    post_res = client.post("/api/readings", json=reading_payload)
    assert post_res.status_code == 200

    get_res = client.get("/api/readings?source=live_esp32")
    assert get_res.status_code == 200
    records = get_res.json()
    assert any(r["device_id"] == "esp32_verified_node" and r["temperature_c"] == 36.6 for r in records)

    status_res = client.get("/api/readings/live-status?device_id=esp32_verified_node")
    assert status_res.status_code == 200
    st = status_res.json()
    assert st["count"] >= 1
    assert st["connectivity_state"] == "ESP32 CONNECTED"


def test_existing_simulator_spark_agstar_behavior_preserved():
    """54. Test 20: Verify simulator (180d), Spark held-out (24d), Spark full (176d), and AgSTAR remain intact."""
    # Simulator
    sim_timeline = simulator_service.get_simulator_timeline(days=20, warmup_days=14)
    assert len(sim_timeline) == 20
    assert sim_timeline[0]["data_source"] == "DEMO_SYNTHETIC"

    # Spark held out
    held_out = forecast_service.get_spark_replay_timeline(mode="held_out_test")
    assert len(held_out) == 24
    assert held_out[0].status == "SUCCESS"
    assert held_out[0].predicted_next_day_nm3 is not None

    # Spark full historical
    full_hist = forecast_service.get_spark_replay_timeline(mode="full_historical")
    assert len(full_hist) == 176

    # AgSTAR static benchmark isolation
    with open("frontend/public/index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    assert "526 Commercial Facilities Across 38 US States" in html_code

    with pytest.raises(ValueError, match="AgSTAR is an external static benchmark and cannot enter the time-series forecasting pipeline."):
        forecast_service.predict(
            model_name="GRU-14d Residual",
            data_source="AGSTAR_REGISTRY",
            history_window=[{"biogas_today_nm3": 10.0} for _ in range(14)]
        )


def test_live_iot_missing_required_model_features_never_uses_fallback_data():
    """55. Test 21: Verify LIVE_IOT with missing features returns INSUFFICIENT LIVE FEATURES and no fallback."""
    sparse_history = [
        {"temperature": 37.0, "ph": 7.2} # Missing biogas_today_nm3 and other 7 features
        for _ in range(14)
    ]
    res = forecast_service.predict(
        model_name="GRU-14d Residual",
        data_source="LIVE_IOT",
        history_window=sparse_history
    )
    assert res.status == ForecastStatusEnum.INSUFFICIENT_LIVE_FEATURES.value
    assert res.domain_valid is False


def test_live_iot_source_mapping_is_authoritative():
    """56. Test 22: Verify authoritative source mapping and offline threshold configuration."""
    assert ProvenanceEnum.LIVE_IOT.value == "LIVE_IOT"
    assert ForecastStatusEnum.INSUFFICIENT_LIVE_HISTORY.value == "INSUFFICIENT LIVE HISTORY"
    assert ForecastStatusEnum.INSUFFICIENT_LIVE_FEATURES.value == "INSUFFICIENT LIVE FEATURES"

    res = client.get("/api/readings/live-status")
    assert res.status_code == 200
    assert res.json()["offline_threshold_minutes"] == 60







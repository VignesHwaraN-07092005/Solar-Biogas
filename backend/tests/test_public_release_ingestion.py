import pytest
import os
import re
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.services.forecast_service import forecast_service
from backend.app.services.ingestion_service import ingestion_service
from backend.app.schemas.forecast import ProvenanceEnum, ForecastStatusEnum
from backend.app.schemas.ingestion import IngestionAnalyzeRequest

client = TestClient(app)

# ================================================================
# GROUP 1: PUBLIC BRANDING REMOVAL & SANITIZATION
# ================================================================

def test_public_branding_removal_in_html():
    with open("frontend/public/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert "Biogas Intelligence Platform" in html
    assert "MULTI-SCALE BIOGAS ANALYTICS" in html
    assert "PRODUCTION READY" not in html
    assert "IEEE YESIST12" not in html
    assert "Team Espada" not in html
    assert "Sri Sairam" not in html
    assert "Academic Non-Hazardous Prototype" not in html
    assert "SDG 11" not in html

def test_public_branding_removal_in_main():
    assert "Biogas Intelligence Platform" in app.title
    assert "IEEE" not in app.title
    assert "Espada" not in app.title
    assert "SDG 11" not in app.description

def test_public_branding_removal_in_chat_service():
    with open("backend/app/services/chat_service.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert "YESIST" not in code
    assert "Espada" not in code
    assert "SDG 11" not in code

def test_public_branding_removal_in_scripts():
    with open("simulation/synthetic_data_generator/generate_dataset.py", "r", encoding="utf-8") as f:
        code = f.read()
    assert "YESIST" not in code
    assert "Espada" not in code

    with open("ml/xco_net/model.py", "r", encoding="utf-8") as f:
        xco_code = f.read()
    assert "YESIST" not in xco_code
    assert "Espada" not in xco_code

# ================================================================
# GROUP 2: MODEL INTERPRETATION ENDPOINTS & MATHEMATICS
# ================================================================

def test_interpretation_gru_sensitivity_and_is_shap_false():
    history = [
        {
            "biogas_today_nm3": 15.0 + i * 0.1,
            "total_incoming_mt": 0.12,
            "total_processed_mt": 0.12,
            "feed_total_m3": 0.144,
            "temp_outlet_d1_c": 36.5,
            "ph_outlet_d1": 7.25,
            "recycle_water_m3": 30.0,
            "feed_total_m3_was_missing": 0,
            "ph_outlet_d1_was_missing": 0
        }
        for i in range(14)
    ]
    payload = {
        "device_id": "DIGESTER_001",
        "model_name": "GRU-14d Residual",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": history
    }
    resp = client.post("/api/forecast/interpretation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["is_shap"] is False
    assert "Local input sensitivity" in data["method"]
    assert len(data["sensitivities"]) > 0
    assert len(data["features"]) > 0
    assert data["prediction_nm3_day"] is not None
    assert data["reference_nm3_day"] is not None

def test_interpretation_gru_insufficient_history():
    history = [
        {"biogas_today_nm3": 15.0, "total_incoming_mt": 0.12, "temp_outlet_d1_c": 36.5, "ph_outlet_d1": 7.25}
        for _ in range(5)
    ]
    payload = {
        "device_id": "DIGESTER_001",
        "model_name": "GRU-14d Residual",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": history
    }
    resp = client.post("/api/forecast/interpretation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["is_shap"] is False
    assert "insufficient" in data["reason"].lower()

def test_interpretation_ema_mathematical_weights():
    history = [
        {"biogas_today_nm3": 10.0},
        {"biogas_today_nm3": 12.0},
        {"biogas_today_nm3": 14.0}
    ]
    payload = {
        "device_id": "DIGESTER_001",
        "model_name": "EMA-0.90",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": history
    }
    resp = client.post("/api/forecast/interpretation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["is_shap"] is False
    assert "Exponential moving average" in data["method"]
    
    weights = {c["component"]: c["weight"] for c in data["contributions"]}
    assert "93.33%" in weights["Observation y_t (Current Day)"]
    assert "3.33%" in weights["Observation y_{t-1} (Previous Day)"]
    assert "3.33%" in weights["Observation y_{t-2} (Two Days Prior)"]

def test_interpretation_ema_insufficient_history():
    history = [{"biogas_today_nm3": 10.0}]
    payload = {
        "device_id": "DIGESTER_001",
        "model_name": "EMA-0.90",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": history
    }
    resp = client.post("/api/forecast/interpretation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert "insufficient" in data["reason"].lower()

def test_interpretation_persistence_identity():
    history = [{"biogas_today_nm3": 18.5}]
    payload = {
        "device_id": "DIGESTER_001",
        "model_name": "Persistence",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": history
    }
    resp = client.post("/api/forecast/interpretation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["is_shap"] is False
    assert data["prediction_nm3_day"] == 18.5
    assert data["reference_nm3_day"] == 18.5
    assert data["prediction_delta_nm3_day"] == 0.0

def test_interpretation_xconet_architecture_weights():
    history = [
        {
            "biogas_today_nm3": 15.0 + i,
            "total_incoming_mt": 0.12,
            "total_processed_mt": 0.12,
            "feed_total_m3": 0.144,
            "temp_outlet_d1_c": 36.5,
            "ph_outlet_d1": 7.25,
            "recycle_water_m3": 30.0,
            "feed_total_m3_was_missing": 0,
            "ph_outlet_d1_was_missing": 0
        }
        for i in range(14)
    ]
    payload = {
        "device_id": "DIGESTER_001",
        "model_name": "XCO-Net",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": history
    }
    resp = client.post("/api/forecast/interpretation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["is_shap"] is False
    weights = {c["component"]: c["weight"] for c in data["contributions"]}
    assert "48.5%" in weights["Pointwise Cross-Channel Interaction"]
    assert "18.2%" in weights["Cross-Channel Operator Feedstock"]
    assert "+-4,152 Nm3/day" in weights["Differentiable Tanh Bounded Delta"]

def test_interpretation_xconet_insufficient_history():
    history = [{"biogas_today_nm3": 15.0} for _ in range(6)]
    payload = {
        "device_id": "DIGESTER_001",
        "model_name": "XCO-Net",
        "data_source": "DEMO_SYNTHETIC",
        "history_window": history
    }
    resp = client.post("/api/forecast/interpretation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert "insufficient" in data["reason"].lower()

def test_interpretation_get_endpoint():
    resp = client.get("/api/forecast/interpretation?model_name=Persistence")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_shap" in data
    assert data["is_shap"] is False

def test_interpretation_spark_full_provenance_accepted():
    resp = client.post("/api/forecast/interpretation", json={
        "device_id": "DIGESTER_001",
        "model_name": "Persistence",
        "data_source": "SPARK_FULL",
        "history_window": [{"biogas_today_nm3": 5000.0}]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["is_shap"] is False


# ================================================================
# GROUP 3: INGESTION ENGINE & SEMANTIC MAPPING
# ================================================================

def test_ingestion_semantic_mapping_standard_headers():
    rows = [
        {"timestamp": "2024-01-01", "temperature_c": 36.5, "ph": 7.2, "pressure_bar": 1.15, "biogas_m3_day": 15.0, "feed_kg": 120.0},
        {"timestamp": "2024-01-02", "temperature_c": 36.6, "ph": 7.3, "pressure_bar": 1.16, "biogas_m3_day": 15.2, "feed_kg": 122.0}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "test.csv", "rows": rows})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_records"] == 2
    assert data["columns_recognized"] >= 4

def test_ingestion_semantic_mapping_arbitrary_aliases():
    rows = [
        {"date": "2024-01-01", "reactor_temp": 36.5, "acidity": 7.25, "gas_pressure_kpa": 115.0, "yield": 14.8, "organic_feed": 120.0},
        {"date": "2024-01-02", "reactor_temp": 36.7, "acidity": 7.20, "gas_pressure_kpa": 116.0, "yield": 15.1, "organic_feed": 125.0}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "scada_export.xlsx", "rows": rows})
    assert resp.status_code == 200
    data = resp.json()
    concept_map = {m["original_name"]: m["semantic_concept"] for m in data["column_mappings"]}
    assert concept_map["reactor_temp"] == "temperature"
    assert concept_map["acidity"] == "ph"
    assert concept_map["gas_pressure_kpa"] == "pressure"
    assert concept_map["yield"] == "biogas_production"
    assert concept_map["organic_feed"] == "feedstock"

def test_ingestion_unit_conversion_fahrenheit_to_celsius():
    rows = [
        {"date": "2024-01-01", "temp_f": 98.6, "ph": 7.2, "biogas": 15.0},
        {"date": "2024-01-02", "temp_f": 100.4, "ph": 7.3, "biogas": 15.5}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "plant_f.xlsx", "rows": rows})
    assert resp.status_code == 200
    data = resp.json()
    clean = data["clean_rows"]
    assert abs(clean[0]["temperature_c"] - 37.0) < 0.1
    assert abs(clean[1]["temperature_c"] - 38.0) < 0.1

def test_ingestion_unit_conversion_pressure_kpa_to_bar():
    rows = [
        {"date": "2024-01-01", "pressure_kpa": 115.0, "biogas": 15.0},
        {"date": "2024-01-02", "pressure_kpa": 120.0, "biogas": 15.2}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "kpa.csv", "rows": rows})
    assert resp.status_code == 200
    data = resp.json()
    clean = data["clean_rows"]
    assert abs(clean[0]["pressure_bar"] - 1.15) < 0.01
    assert abs(clean[1]["pressure_bar"] - 1.20) < 0.01

def test_ingestion_standalone_statistics_computed_for_all_numeric_columns():
    rows = [
        {"timestamp": "2024-01-01", "biogas": 10.0, "extra_sensor_voltage": 3.3, "unrelated_metric": 100},
        {"timestamp": "2024-01-02", "biogas": 20.0, "extra_sensor_voltage": 3.4, "unrelated_metric": 200},
        {"timestamp": "2024-01-03", "biogas": 30.0, "extra_sensor_voltage": 3.5, "unrelated_metric": 300}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "extra_cols.csv", "rows": rows})
    assert resp.status_code == 200
    data = resp.json()
    stats = {s["column_name"]: s for s in data["column_statistics"]}
    assert "extra_sensor_voltage" in stats
    assert stats["extra_sensor_voltage"]["mean"] == 3.4
    assert stats["unrelated_metric"]["min"] == 100.0
    assert stats["unrelated_metric"]["max"] == 300.0

def test_ingestion_preserves_unrecognized_columns():
    rows = [
        {"timestamp": "2024-01-01", "biogas": 10.0, "custom_operator_tag": "LineA-Shift1"},
        {"timestamp": "2024-01-02", "biogas": 12.0, "custom_operator_tag": "LineA-Shift2"}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "custom.csv", "rows": rows})
    assert resp.status_code == 200
    data = resp.json()
    clean = data["clean_rows"]
    assert clean[0]["custom_operator_tag"] == "LineA-Shift1"

def test_ingestion_timestamp_row_not_aliased():
    rows = [
        {"row": 1, "temp": 36.5, "biogas": 15.0},
        {"row": 2, "temp": 36.6, "biogas": 15.2}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "row_col.csv", "rows": rows})
    assert resp.status_code == 200
    data = resp.json()
    mapping_concepts = [m["semantic_concept"] for m in data["column_mappings"]]
    assert "timestamp" not in mapping_concepts

def test_ingestion_model_eligibility_separation():
    rows = [
        {"timestamp": "2024-01-01", "biogas": 10.0},
        {"timestamp": "2024-01-02", "biogas": 12.0}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "short.csv", "rows": rows})
    assert resp.status_code == 200
    elig = resp.json()["model_eligibility"]
    assert elig["Persistence"]["eligible"] is True
    assert elig["EMA-0.90"]["eligible"] is False
    assert elig["GRU-14d Residual"]["eligible"] is False
    assert elig["XCO-Net"]["eligible"] is False

def test_ingestion_zero_fallback_data():
    rows = [
        {"timestamp": "2024-01-01", "biogas": 10.0}
    ]
    resp = client.post("/api/ingestion/analyze", json={"filename": "no_fallbacks.csv", "rows": rows})
    assert resp.status_code == 200
    clean = resp.json()["clean_rows"][0]
    assert clean.get("temperature_c") is None
    assert clean.get("ph") is None

# ================================================================
# GROUP 4: USER_UPLOAD FORECASTING & DOMAIN ISOLATION
# ================================================================

def test_user_upload_predict_gru_domain_valid_false():
    history = [
        {
            "biogas_today_nm3": 15.0 + i,
            "total_incoming_mt": 0.12,
            "total_processed_mt": 0.12,
            "feed_total_m3": 0.144,
            "temp_outlet_d1_c": 36.5,
            "ph_outlet_d1": 7.25,
            "recycle_water_m3": 30.0,
            "feed_total_m3_was_missing": 0,
            "ph_outlet_d1_was_missing": 0
        }
        for i in range(14)
    ]
    payload = {
        "device_id": "USER_DIGESTER_01",
        "model_name": "GRU-14d Residual",
        "data_source": "USER_UPLOAD",
        "history_window": history
    }
    resp = client.post("/api/forecast/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain_valid"] is False
    assert data["status"] == "UNVALIDATED USER DATASET"
    assert "unvalidated" in data["domain_note"].lower()

def test_user_upload_predict_xco_domain_valid_false():
    history = [
        {
            "biogas_today_nm3": 15.0 + i,
            "total_incoming_mt": 0.12,
            "total_processed_mt": 0.12,
            "feed_total_m3": 0.144,
            "temp_outlet_d1_c": 36.5,
            "ph_outlet_d1": 7.25,
            "recycle_water_m3": 30.0,
            "feed_total_m3_was_missing": 0,
            "ph_outlet_d1_was_missing": 0
        }
        for i in range(14)
    ]
    payload = {
        "device_id": "USER_DIGESTER_01",
        "model_name": "XCO-Net",
        "data_source": "USER_UPLOAD",
        "history_window": history
    }
    resp = client.post("/api/forecast/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain_valid"] is False
    assert data["status"] == "UNVALIDATED USER DATASET"

def test_user_upload_predict_ema_permitted():
    history = [
        {"biogas_today_nm3": 10.0},
        {"biogas_today_nm3": 12.0},
        {"biogas_today_nm3": 14.0}
    ]
    payload = {
        "device_id": "USER_DIGESTER_01",
        "model_name": "EMA-0.90",
        "data_source": "USER_UPLOAD",
        "history_window": history
    }
    resp = client.post("/api/forecast/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain_valid"] is True
    assert data["predicted_biogas_m3_day"] is not None
    assert data["predicted_biogas_m3_day"] > 0

def test_user_upload_predict_persistence_permitted():
    history = [{"biogas_today_nm3": 22.4}]
    payload = {
        "device_id": "USER_DIGESTER_01",
        "model_name": "Persistence",
        "data_source": "USER_UPLOAD",
        "history_window": history
    }
    resp = client.post("/api/forecast/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain_valid"] is True
    assert data["predicted_biogas_m3_day"] == 22.4

def test_user_upload_insufficient_features_inhibits_forecast():
    history = [{"biogas_today_nm3": 15.0} for _ in range(14)]
    payload = {
        "device_id": "USER_DIGESTER_01",
        "model_name": "GRU-14d Residual",
        "data_source": "USER_UPLOAD",
        "history_window": history
    }
    resp = client.post("/api/forecast/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "INSUFFICIENT_FEATURES"
    assert data["predicted_biogas_m3_day"] == 0.0

# ================================================================
# GROUP 5: SECURITY, CORS & CONFIGURATION INTEGRITY
# ================================================================

def test_security_no_active_gemini_key_in_repo():
    with open(".env", "r", encoding="utf-8") as f:
        env_content = f.read()
    assert re.search(r"GEMINI_API_KEY\s*=\s*['\"\s]*$", env_content, re.MULTILINE) is not None

def test_security_cors_no_wildcard_when_debug_false():
    with open("backend/app/main.py", "r", encoding="utf-8") as f:
        main_code = f.read()
    assert "allow_origins=cors_origins" in main_code
    assert "settings.CORS_ORIGINS" in main_code

def test_xco_lookback_strictly_7_timesteps():
    meta = forecast_service.get_models_metadata()
    assert meta["models"]["XCO-Net"]["required_history_timesteps"] == 7

import os
import pytest
import pandas as pd
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.database import Base, get_db
from backend.app.models.sensor_reading import SensorReading
from backend.app.services.alert_service import classify_telemetry_safety, evaluate_reading_for_alerts
from backend.app.services.chat_service import (
    get_live_telemetry_from_db,
    format_telemetry_context,
    generate_smart_local_response,
    generate_chat_response
)
from backend.app.schemas.chat import ChatRequest
from backend.app.services.ingestion_service import ingestion_service

client = TestClient(app)

# Setup isolated test database session for DB-dependent tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

# ================================================================
# TEST 1: AUTHORITATIVE SAFETY THRESHOLDS CONFIGURATION & API
# ================================================================

def test_1_authoritative_safety_thresholds():
    """Verify backend settings and GET /api/alerts/thresholds expose authoritative thresholds."""
    assert settings.ALERT_PRESSURE_WARN == 1.30
    assert settings.ALERT_PRESSURE_MAX == 1.50
    assert settings.ALERT_PH_MIN == 6.5
    assert settings.ALERT_PH_MAX == 8.2
    assert settings.ALERT_TEMP_MIN == 28.0
    assert settings.ALERT_TEMP_MAX == 42.0

    res = client.get("/api/alerts/thresholds")
    assert res.status_code == 200
    data = res.json()
    assert data["alert_pressure_warn"] == 1.30
    assert data["alert_pressure_max"] == 1.50
    assert data["alert_ph_min"] == 6.5
    assert data["alert_ph_max"] == 8.2
    assert data["alert_temp_min"] == 28.0
    assert data["alert_temp_max"] == 42.0

# ================================================================
# TEST 2: NORMAL PRESSURE TELEMETRY EVALUATION
# ================================================================

def test_2_normal_pressure_evaluation():
    """Verify normal pressure (1.15 bar) produces NORMAL status and 0 alerts."""
    res = client.post("/api/alerts/evaluate", json={
        "pressure_bar": 1.15,
        "temperature_c": 36.5,
        "ph": 7.25
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "NORMAL"
    assert data["pressure_status"] == "NORMAL"
    assert data["alert_count"] == 0
    assert len(data["alerts"]) == 0

# ================================================================
# TEST 3: PRESSURE WARNING BOUNDARY EVALUATION (1.30 bar)
# ================================================================

def test_3_pressure_warning_boundary():
    """Verify pressure warning boundary at exactly 1.30 bar."""
    # 1.29 bar -> NORMAL
    res_sub = client.post("/api/alerts/evaluate", json={"pressure_bar": 1.29})
    assert res_sub.json()["pressure_status"] == "NORMAL"
    assert res_sub.json()["alert_count"] == 0

    # 1.30 bar -> WARNING
    res_warn = client.post("/api/alerts/evaluate", json={"pressure_bar": 1.30})
    data_warn = res_warn.json()
    assert data_warn["status"] == "WARNING"
    assert data_warn["pressure_status"] == "WARNING"
    assert data_warn["alert_count"] == 1
    assert data_warn["alerts"][0]["severity"] == "WARNING"
    assert data_warn["alerts"][0]["parameter"] == "pressure"
    assert data_warn["alerts"][0]["threshold_limit"] == 1.30
    assert "High gas pressure warning" in data_warn["alerts"][0]["message"]

    # 1.49 bar -> WARNING
    res_high_warn = client.post("/api/alerts/evaluate", json={"pressure_bar": 1.49})
    assert res_high_warn.json()["pressure_status"] == "WARNING"

# ================================================================
# TEST 4: PRESSURE CRITICAL BOUNDARY EVALUATION (1.50 bar)
# ================================================================

def test_4_pressure_critical_boundary():
    """Verify pressure critical boundary at exactly 1.50 bar triggering relief valve activation."""
    res = client.post("/api/alerts/evaluate", json={"pressure_bar": 1.50})
    data = res.json()
    assert data["status"] == "CRITICAL"
    assert data["pressure_status"] == "CRITICAL"
    assert data["alert_count"] == 1
    assert data["alerts"][0]["severity"] == "CRITICAL"
    assert data["alerts"][0]["parameter"] == "pressure"
    assert data["alerts"][0]["threshold_limit"] == 1.50
    assert "Overpressure critical" in data["alerts"][0]["message"]
    assert "Relief valve activation" in data["alerts"][0]["message"]

    # Higher pressure (1.65 bar) -> CRITICAL
    res_higher = client.post("/api/alerts/evaluate", json={"pressure_bar": 1.65})
    assert res_higher.json()["pressure_status"] == "CRITICAL"

# ================================================================
# TEST 5: TEMPERATURE SAFETY BOUNDARIES (28.0°C - 42.0°C)
# ================================================================

def test_5_temperature_safety_boundaries():
    """Verify temperature boundaries: < 28.0 WARNING, > 42.0 CRITICAL."""
    # Nominal temperature
    res_nom = client.post("/api/alerts/evaluate", json={"temperature_c": 37.0})
    assert res_nom.json()["temperature_status"] == "NORMAL"

    # Boundary exactly 28.0 -> NORMAL
    res_bound_low = client.post("/api/alerts/evaluate", json={"temperature_c": 28.0})
    assert res_bound_low.json()["temperature_status"] == "NORMAL"

    # Low temperature 27.5 -> WARNING
    res_low = client.post("/api/alerts/evaluate", json={"temperature_c": 27.5})
    data_low = res_low.json()
    assert data_low["temperature_status"] == "WARNING"
    assert data_low["alert_count"] == 1
    assert "Microbial kinetics inhibited" in data_low["alerts"][0]["message"]

    # Boundary exactly 42.0 -> NORMAL
    res_bound_high = client.post("/api/alerts/evaluate", json={"temperature_c": 42.0})
    assert res_bound_high.json()["temperature_status"] == "NORMAL"

    # High temperature 43.0 -> CRITICAL
    res_high = client.post("/api/alerts/evaluate", json={"temperature_c": 43.0})
    data_high = res_high.json()
    assert data_high["temperature_status"] == "CRITICAL"
    assert data_high["alert_count"] == 1
    assert "Risk of thermal kill" in data_high["alerts"][0]["message"]

# ================================================================
# TEST 6: PH SAFETY BOUNDARIES (6.5 - 8.2)
# ================================================================

def test_6_ph_safety_boundaries():
    """Verify pH boundaries: < 6.5 WARNING (< 6.2 CRITICAL), > 8.2 WARNING."""
    # Nominal pH
    res_nom = client.post("/api/alerts/evaluate", json={"ph": 7.20})
    assert res_nom.json()["ph_status"] == "NORMAL"

    # Boundaries exactly 6.5 and 8.2 -> NORMAL
    assert client.post("/api/alerts/evaluate", json={"ph": 6.50}).json()["ph_status"] == "NORMAL"
    assert client.post("/api/alerts/evaluate", json={"ph": 8.20}).json()["ph_status"] == "NORMAL"

    # Mildly low pH 6.4 -> WARNING
    res_low_warn = client.post("/api/alerts/evaluate", json={"ph": 6.40})
    assert res_low_warn.json()["ph_status"] == "WARNING"
    assert "Risk of digester acidification" in res_low_warn.json()["alerts"][0]["message"]

    # Critically low pH 6.1 -> CRITICAL
    res_crit = client.post("/api/alerts/evaluate", json={"ph": 6.10})
    assert res_crit.json()["ph_status"] == "CRITICAL"
    assert res_crit.json()["alerts"][0]["severity"] == "CRITICAL"

    # High pH 8.35 -> WARNING
    res_high_warn = client.post("/api/alerts/evaluate", json={"ph": 8.35})
    assert res_high_warn.json()["ph_status"] == "WARNING"
    assert "Check ammonia loading" in res_high_warn.json()["alerts"][0]["message"]

# ================================================================
# TEST 7: NULL PRESSURE PARAMETER HANDLING
# ================================================================

def test_7_null_pressure_handling():
    """Verify null/None pressure does not produce false alerts or crash."""
    res = client.post("/api/alerts/evaluate", json={
        "pressure_bar": None,
        "temperature_c": 36.5,
        "ph": 7.25
    })
    assert res.status_code == 200
    data = res.json()
    assert data["pressure_status"] == "NORMAL"
    assert data["status"] == "NORMAL"
    assert data["alert_count"] == 0

# ================================================================
# TEST 8: ALL-NULL TELEMETRY EVALUATION
# ================================================================

def test_8_all_null_telemetry():
    """Verify evaluating an empty telemetry packet produces NORMAL and 0 alerts without error."""
    result = classify_telemetry_safety(None, None, None, None)
    assert result["status"] == "NORMAL"
    assert result["pressure_status"] == "NORMAL"
    assert result["ph_status"] == "NORMAL"
    assert result["temperature_status"] == "NORMAL"
    assert result["alert_count"] == 0
    assert len(result["alerts"]) == 0

    # API equivalent
    res = client.post("/api/alerts/evaluate", json={})
    assert res.status_code == 200
    assert res.json()["status"] == "NORMAL"
    assert res.json()["alert_count"] == 0

# ================================================================
# TEST 9: DB SENSOR READING EVALUATION NULL-SAFETY
# ================================================================

def test_9_sensor_reading_evaluation_null_safety(db_session):
    """Verify evaluate_reading_for_alerts safely handles readings with None fields."""
    reading_null = SensorReading(
        device_id="esp32_test",
        timestamp=datetime.now(timezone.utc),
        temperature_c=None,
        ph=None,
        pressure_bar=None
    )
    alerts = evaluate_reading_for_alerts(db_session, reading_null)
    assert len(alerts) == 0

    reading_overpressure = SensorReading(
        device_id="esp32_test",
        timestamp=datetime.now(timezone.utc),
        temperature_c=36.0,
        ph=7.2,
        pressure_bar=1.52
    )
    alerts_op = evaluate_reading_for_alerts(db_session, reading_overpressure)
    assert len(alerts_op) == 1
    assert alerts_op[0].severity == "CRITICAL"
    assert alerts_op[0].parameter == "pressure"

# ================================================================
# TEST 10: ZERO SYNTHETIC LIVE_IOT FALLBACK IN DB SERVICE
# ================================================================

def test_10_no_synthetic_live_iot_db_fallback(db_session):
    """Verify get_live_telemetry_from_db returns None for fields when DB has no sensor readings."""
    # Ensure no readings in the test db
    db_session.query(SensorReading).delete()
    db_session.commit()

    live = get_live_telemetry_from_db(db_session)
    # Sensor values MUST be None, not fabricated numbers (36.5, 7.25, 1.15, 62.5, 120.0)
    assert live.get("temp") is None
    assert live.get("ph") is None
    assert live.get("pressure") is None
    assert live.get("methane") is None
    assert live.get("feed") is None
    assert live.get("flow") is None
    assert live.get("biogas") is None
    assert live.get("source") == "database_latest"

# ================================================================
# TEST 11: CHATBOT TELEMETRY GROUNDING & CLIENT NULL PRESERVATION
# ================================================================

def test_11_chatbot_telemetry_grounding_and_null_preservation(db_session):
    """Verify chatbot explicitly states 'Unavailable / Not Observed' for missing fields and preserves client nulls."""
    # 1. format_telemetry_context formatting
    partial_telemetry = {
        "source": "LIVE_IOT",
        "temp": None,
        "ph": 7.25,
        "pressure": None,
        "methane": None,
        "feed": None,
        "biogas": None
    }
    context_str = format_telemetry_context(partial_telemetry)
    assert "Unavailable / Not Observed" in context_str
    assert "7.25" in context_str

    # 2. Smart local response handling of missing metrics
    ans_pressure = generate_smart_local_response("What is the current pressure?", partial_telemetry)
    assert "Unavailable / Not Observed" in ans_pressure
    assert "1.15" not in ans_pressure

    ans_temp = generate_smart_local_response("What is the temperature?", partial_telemetry)
    assert "Unavailable / Not Observed" in ans_temp
    assert "36.5" not in ans_temp

    ans_methane = generate_smart_local_response("How is the methane level?", partial_telemetry)
    assert "Unavailable / Not Observed" in ans_methane
    assert "62.5" not in ans_methane

    # Observed metric (pH) should report value accurately
    ans_ph = generate_smart_local_response("What is the pH?", partial_telemetry)
    assert "7.25" in ans_ph

    # 3. HTTP API test: verify client nulls are preserved and not overwritten with DB values
    res = client.post("/api/chat", json={
        "message": "What is the pressure reading?",
        "telemetry": partial_telemetry
    })
    assert res.status_code == 200
    reply = res.json()["reply"]
    assert "Unavailable / Not Observed" in reply
    assert "1.15" not in reply

# ================================================================
# TEST 12: USER_UPLOAD INGESTION EXACT SCHEMA & ZERO FALLBACKS
# ================================================================

def test_12_user_upload_ingestion_exact_schema_zero_fallbacks():
    """Verify test_A_exact_schema.xlsx ingestion produces correct values without synthetic pressure/methane."""
    excel_path = os.path.join("scratch", "audit_test_files", "test_A_exact_schema.xlsx")
    assert os.path.exists(excel_path), f"File {excel_path} must exist"

    df = pd.read_excel(excel_path)
    report, clean_rows = ingestion_service.analyze_dataset("test_A_exact_schema.xlsx", df.to_dict(orient="records"))

    assert report.total_rows == 15
    assert len(clean_rows) == 15

    # Check last row (current telemetry state)
    last_row = clean_rows[-1]
    assert last_row["biogas_production_m3_day"] == 5410.0
    assert last_row["temperature_c"] == 36.7
    assert last_row["ph"] == 7.25

    # Pressure and methane are absent in test_A_exact_schema.xlsx and must NOT be fabricated
    assert last_row.get("pressure_bar") is None
    assert last_row.get("methane_pct") is None


import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health_endpoint_includes_gemini():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "gemini_configured" in data
    assert isinstance(data["gemini_configured"], bool)
    assert data["status"] == "healthy"

def test_chat_endpoint_basic_query():
    payload = {
        "message": "What is the slurry pH stability?",
        "telemetry": {
            "temp": 36.8,
            "ph": 7.22,
            "pressure": 1.10,
            "methane": 64.0,
            "feed": 125.0,
            "biogas": 16.4,
            "solar_power": 2.1,
            "battery_soc": 90.0
        }
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 20
    assert "model" in data
    assert data["source"] in ["gemini-api", "xco-local-engine", "fallback"]
    assert "timestamp" in data
    assert "suggestions" in data
    assert len(data["suggestions"]) > 0

def test_chat_endpoint_telemetry_grounding_acidosis():
    payload = {
        "message": "What is the pH status?",
        "telemetry": {
            "temp": 36.5,
            "ph": 6.35,  # Acidosis trigger
            "pressure": 1.05,
            "methane": 52.0,
            "feed": 130.0,
            "biogas": 9.2
        }
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    reply = data["reply"].lower()
    assert "6.35" in reply or "acid" in reply or "vfa" in reply or "buffer" in reply

def test_chat_endpoint_overpressure_warning():
    payload = {
        "message": "Check the gas pressure safety",
        "telemetry": {
            "temp": 36.5,
            "ph": 7.2,
            "pressure": 1.62,  # Over safe limit 1.50 bar
            "methane": 62.0,
            "feed": 120.0,
            "biogas": 15.0
        }
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    reply = data["reply"].lower()
    assert "1.62" in reply or "relief" in reply or "overpressure" in reply or "pressure" in reply

def test_chat_endpoint_health_audit():
    payload = {
        "message": "Run digester health audit",
        "telemetry": {
            "temp": 36.5,
            "ph": 7.3,
            "pressure": 1.12,
            "methane": 65.0,
            "feed": 120.0,
            "biogas": 15.5,
            "battery_soc": 88.0
        }
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    reply = data["reply"].lower()
    assert "health" in reply or "audit" in reply or "%" in reply

def test_chat_endpoint_empty_message_fails():
    payload = {
        "message": "   "
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 422

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.sensor_reading import SensorReading
from backend.app.schemas.sensor_reading import SensorReadingCreate, SensorReadingResponse
from backend.app.services.device_service import get_or_create_device
from backend.app.services.alert_service import evaluate_reading_for_alerts

router = APIRouter(prefix="/api/readings", tags=["Readings"])

@router.get("", response_model=List[SensorReadingResponse])
def get_readings(
    device_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    query = db.query(SensorReading)
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)
    if source:
        query = query.filter(SensorReading.source == source)
    return query.order_by(SensorReading.timestamp.desc()).limit(limit).all()

@router.get("/live-status")
def get_live_status(
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns the real connectivity/freshness status of physical ESP32 telemetry.
    Uses settings.DEVICE_OFFLINE_THRESHOLD_MINUTES as single source of truth.
    """
    query = db.query(SensorReading).filter(SensorReading.source == "live_esp32")
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)

    count = query.count()
    if count == 0:
        return {
            "count": 0,
            "latest_timestamp": None,
            "connectivity_state": "WAITING FOR ESP32",
            "device_id": device_id,
            "last_seen": None,
            "offline_threshold_minutes": settings.DEVICE_OFFLINE_THRESHOLD_MINUTES
        }

    latest_reading = query.order_by(SensorReading.timestamp.desc()).first()
    ts = latest_reading.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_seconds = (now - ts).total_seconds()
    age_minutes = max(0.0, age_seconds / 60.0)

    if age_minutes <= settings.DEVICE_OFFLINE_THRESHOLD_MINUTES:
        conn_state = "ESP32 CONNECTED"
    else:
        conn_state = "DATA STALE / DEVICE NOT RECENTLY SEEN"

    return {
        "count": count,
        "latest_timestamp": ts.isoformat(),
        "connectivity_state": conn_state,
        "device_id": latest_reading.device_id,
        "last_seen": ts.isoformat(),
        "reading_age_minutes": round(age_minutes, 1),
        "offline_threshold_minutes": settings.DEVICE_OFFLINE_THRESHOLD_MINUTES
    }

@router.post("", response_model=SensorReadingResponse)
def ingest_reading(reading_in: SensorReadingCreate, db: Session = Depends(get_db)):
    # Ensure device exists and update liveness
    get_or_create_device(db, reading_in.device_id, mode="LIVE" if reading_in.source == "live_esp32" else "DEMO")
    
    ts = reading_in.timestamp or datetime.now(timezone.utc)
    reading = SensorReading(
        device_id=reading_in.device_id,
        timestamp=ts,
        temperature_c=reading_in.temperature_c,
        ambient_temperature_c=reading_in.ambient_temperature_c,
        ph=reading_in.ph,
        inlet_ph=reading_in.inlet_ph,
        pressure_bar=reading_in.pressure_bar,
        gas_flow_m3_day=reading_in.gas_flow_m3_day,
        biogas_production_m3_day=reading_in.biogas_production_m3_day,
        methane_percent=reading_in.methane_percent,
        co2_percent=reading_in.co2_percent,
        h2s_ppm=reading_in.h2s_ppm,
        feedstock_mass_kg=reading_in.feedstock_mass_kg,
        feedstock_type=reading_in.feedstock_type,
        agitator_runtime_min=reading_in.agitator_runtime_min,
        source=reading_in.source
    )
    db.add(reading)
    evaluate_reading_for_alerts(db, reading)
    db.commit()
    db.refresh(reading)
    return reading

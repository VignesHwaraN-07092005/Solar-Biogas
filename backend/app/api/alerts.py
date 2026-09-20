from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.alert import Alert
from backend.app.schemas.alert import AlertResponse
from backend.app.services.alert_service import classify_telemetry_safety

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

class TelemetryEvaluateRequest(BaseModel):
    temperature_c: Optional[float] = None
    ph: Optional[float] = None
    pressure_bar: Optional[float] = None
    battery_soc_percent: Optional[float] = None
    solar_power_w: Optional[float] = None
    biogas_production_m3_day: Optional[float] = None
    h2s_ppm: Optional[float] = None
    methane_percent: Optional[float] = None
    predicted_energy_kwh: Optional[float] = None
    is_sensor_connected: Optional[bool] = None

@router.get("/thresholds")
def get_alert_thresholds():
    """Returns authoritative system safety thresholds."""
    return {
        "disclaimer": "Prototype configurable alert threshold; validate against actual equipment/process specifications.",
        "categories": {
            "DIGESTER": {
                "alert_ph_min": settings.ALERT_PH_MIN,
                "alert_ph_max": settings.ALERT_PH_MAX,
                "alert_temp_min": settings.ALERT_TEMP_MIN,
                "alert_temp_max": settings.ALERT_TEMP_MAX
            },
            "GAS": {
                "alert_pressure_warn": settings.ALERT_PRESSURE_WARN,
                "alert_pressure_max": settings.ALERT_PRESSURE_MAX,
                "alert_biogas_min": settings.ALERT_BIOGAS_MIN,
                "alert_h2s_max": settings.ALERT_H2S_MAX,
                "alert_methane_min": settings.ALERT_METHANE_MIN
            },
            "SENSOR": {
                "device_offline_threshold_minutes": settings.DEVICE_OFFLINE_THRESHOLD_MINUTES
            },
            "ENERGY": {
                "default_generator_efficiency": settings.DEFAULT_GENERATOR_EFFICIENCY,
                "methane_lhv_kwh": settings.METHANE_LHV_KWH,
                "alert_energy_potential_min": settings.ALERT_ENERGY_POTENTIAL_MIN,
                "community_demand_daily_kwh": settings.COMMUNITY_DEMAND_DAILY_KWH
            },
            "SOLAR": {
                "alert_battery_soc_min": settings.ALERT_BATTERY_SOC_MIN,
                "alert_solar_power_min": settings.ALERT_SOLAR_POWER_MIN
            }
        },
        "alert_pressure_warn": settings.ALERT_PRESSURE_WARN,
        "alert_pressure_max": settings.ALERT_PRESSURE_MAX,
        "alert_ph_min": settings.ALERT_PH_MIN,
        "alert_ph_max": settings.ALERT_PH_MAX,
        "alert_temp_min": settings.ALERT_TEMP_MIN,
        "alert_temp_max": settings.ALERT_TEMP_MAX
    }

@router.post("/evaluate")
def evaluate_telemetry(req: TelemetryEvaluateRequest):
    """
    Evaluates telemetry parameters against authoritative safety thresholds.
    Single source of truth for both KPI badges and active safety alerts.
    """
    return classify_telemetry_safety(
        temperature_c=req.temperature_c,
        ph=req.ph,
        pressure_bar=req.pressure_bar,
        battery_soc_percent=req.battery_soc_percent,
        solar_power_w=req.solar_power_w,
        biogas_production_m3_day=req.biogas_production_m3_day,
        h2s_ppm=req.h2s_ppm,
        methane_percent=req.methane_percent,
        predicted_energy_kwh=req.predicted_energy_kwh,
        is_sensor_connected=req.is_sensor_connected
    )


@router.get("", response_model=List[AlertResponse])
def get_alerts(
    device_id: Optional[str] = Query(None),
    unacknowledged_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(Alert)
    if device_id:
        query = query.filter(Alert.device_id == device_id)
    if unacknowledged_only:
        query = query.filter(Alert.is_acknowledged == False)
    return query.order_by(Alert.timestamp.desc()).limit(limit).all()

@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from backend.app.database import get_db
from backend.app.models.solar import SolarMetric
from backend.app.schemas.solar import SolarMetricCreate, SolarMetricResponse
from backend.app.services.solar_service import process_solar_metric

router = APIRouter(prefix="/api/solar", tags=["Solar"])

@router.get("/latest", response_model=Optional[SolarMetricResponse])
def get_latest_solar_telemetry(
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(SolarMetric)
    if device_id:
        query = query.filter(SolarMetric.device_id == device_id)
    return query.order_by(SolarMetric.timestamp.desc()).first()

@router.get("/history", response_model=List[SolarMetricResponse])
def get_solar_history(
    device_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(SolarMetric)
    if device_id:
        query = query.filter(SolarMetric.device_id == device_id)
    return query.order_by(SolarMetric.timestamp.desc()).limit(limit).all()

@router.post("", response_model=SolarMetricResponse)
def ingest_solar_metric(metric_in: SolarMetricCreate, db: Session = Depends(get_db)):
    return process_solar_metric(db, metric_in)

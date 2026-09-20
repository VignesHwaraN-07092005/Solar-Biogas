from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from backend.app.database import get_db
from backend.app.models.device import Device
from backend.app.models.sensor_reading import SensorReading
from backend.app.schemas.device import DeviceCreate, DeviceResponse
from backend.app.services.device_service import get_or_create_device

router = APIRouter(prefix="/api/devices", tags=["Devices"])

@router.get("", response_model=List[DeviceResponse])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()

@router.post("", response_model=DeviceResponse)
def register_device(device_in: DeviceCreate, db: Session = Depends(get_db)):
    existing = db.query(Device).filter(Device.id == device_in.id).first()
    if existing:
        existing.name = device_in.name
        existing.location = device_in.location
        existing.mode = device_in.mode
        db.commit()
        db.refresh(existing)
        return existing
        
    device = Device(
        id=device_in.id,
        name=device_in.name,
        location=device_in.location,
        mode=device_in.mode,
        status="ONLINE",
        last_seen=datetime.now(timezone.utc)
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device

@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.get("/{device_id}/latest")
def get_latest_device_status(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    latest_reading = (
        db.query(SensorReading)
        .filter(SensorReading.device_id == device_id)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )
    
    return {
        "device": {
            "id": device.id,
            "name": device.name,
            "location": device.location,
            "status": device.status,
            "mode": device.mode,
            "last_seen": device.last_seen
        },
        "latest_reading": latest_reading
    }

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.app.models.device import Device
from backend.app.schemas.device import DeviceCreate
from backend.app.config import settings

def get_or_create_device(db: Session, device_id: str, name: str = None, mode: str = "DEMO") -> Device:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        device = Device(
            id=device_id,
            name=name or f"Digester Node {device_id}",
            mode=mode,
            status="ONLINE",
            last_seen=datetime.now(timezone.utc)
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        device.last_seen = datetime.now(timezone.utc)
        device.status = "ONLINE"
        db.commit()
    return device

def update_device_statuses(db: Session, offline_threshold_minutes: int = settings.DEVICE_OFFLINE_THRESHOLD_MINUTES):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=offline_threshold_minutes)
    devices = db.query(Device).filter(Device.last_seen < cutoff).all()
    for d in devices:
        d.status = "OFFLINE"
    db.commit()

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from datetime import datetime, timezone
from backend.app.database import Base

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    
    severity = Column(String(16), nullable=False)  # INFO, WARNING, CRITICAL
    parameter = Column(String(32), nullable=False) # ph, temperature, pressure, battery
    triggered_value = Column(Float, nullable=False)
    threshold_limit = Column(Float, nullable=False)
    message = Column(String(256), nullable=False)
    
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)

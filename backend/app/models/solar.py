from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from datetime import datetime, timezone
from backend.app.database import Base

class SolarMetric(Base):
    __tablename__ = "solar_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    
    solar_voltage_v = Column(Float, nullable=True)
    solar_current_a = Column(Float, nullable=True)
    solar_power_w = Column(Float, nullable=True)
    
    battery_voltage_v = Column(Float, nullable=True)
    battery_soc_percent = Column(Float, nullable=True)
    
    system_load_current_ma = Column(Float, nullable=True)
    system_load_power_w = Column(Float, nullable=True)
    
    solar_status = Column(String(32), default="NORMAL") # NORMAL, CHARGING, LOW_BATTERY

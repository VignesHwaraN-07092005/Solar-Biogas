from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from datetime import datetime, timezone
from backend.app.database import Base

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Biokinetic / Process parameters
    temperature_c = Column(Float, nullable=True)
    ambient_temperature_c = Column(Float, nullable=True)
    ph = Column(Float, nullable=True)
    inlet_ph = Column(Float, nullable=True)
    pressure_bar = Column(Float, nullable=True)
    gas_flow_m3_day = Column(Float, nullable=True)
    biogas_production_m3_day = Column(Float, nullable=True)
    
    # Gas composition
    methane_percent = Column(Float, nullable=True)
    co2_percent = Column(Float, nullable=True)
    h2s_ppm = Column(Float, nullable=True)
    
    # Substrate & Feed
    feedstock_mass_kg = Column(Float, nullable=True)
    feedstock_type = Column(String(64), nullable=True)
    agitator_runtime_min = Column(Float, nullable=True)
    
    # Provenance tracking
    source = Column(String(32), default="synthetic")  # live_esp32, synthetic, research_spark
    
    __table_args__ = (
        Index("idx_device_timestamp", "device_id", "timestamp"),
    )

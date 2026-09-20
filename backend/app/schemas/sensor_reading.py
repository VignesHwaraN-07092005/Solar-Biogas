from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class SensorReadingBase(BaseModel):
    temperature_c: Optional[float] = Field(None, ge=0.0, le=70.0, description="Reactor temperature in C")
    ambient_temperature_c: Optional[float] = Field(None, ge=-10.0, le=60.0)
    ph: Optional[float] = Field(None, ge=0.0, le=14.0, description="Reactor pH")
    inlet_ph: Optional[float] = Field(None, ge=0.0, le=14.0)
    pressure_bar: Optional[float] = Field(None, ge=0.0, le=10.0, description="Biogas pressure in bar")
    gas_flow_m3_day: Optional[float] = Field(None, ge=0.0, description="Gas flow rate in m3/day")
    biogas_production_m3_day: Optional[float] = Field(None, ge=0.0, description="Total daily biogas in m3/day")
    methane_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    co2_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    h2s_ppm: Optional[float] = Field(None, ge=0.0)
    feedstock_mass_kg: Optional[float] = Field(None, ge=0.0)
    feedstock_type: Optional[str] = None
    agitator_runtime_min: Optional[float] = Field(None, ge=0.0, le=1440.0)
    source: str = Field("synthetic", description="live_esp32, synthetic, or research_spark")

class SensorReadingCreate(SensorReadingBase):
    device_id: str
    timestamp: Optional[datetime] = None

class SensorReadingBatch(BaseModel):
    device_id: str
    readings: List[SensorReadingBase]

class SensorReadingResponse(SensorReadingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: str
    timestamp: datetime

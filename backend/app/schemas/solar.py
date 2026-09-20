from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class SolarMetricBase(BaseModel):
    device_id: str
    solar_voltage_v: Optional[float] = Field(None, ge=0.0, le=50.0)
    solar_current_a: Optional[float] = Field(None, ge=0.0, le=20.0)
    solar_power_w: Optional[float] = Field(None, ge=0.0)
    battery_voltage_v: Optional[float] = Field(None, ge=0.0, le=30.0)
    battery_soc_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    system_load_current_ma: Optional[float] = Field(None, ge=0.0)
    system_load_power_w: Optional[float] = Field(None, ge=0.0)
    solar_status: str = "NORMAL"

class SolarMetricCreate(SolarMetricBase):
    timestamp: Optional[datetime] = None

class SolarMetricResponse(SolarMetricBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime

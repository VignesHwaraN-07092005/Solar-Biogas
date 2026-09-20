from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class AlertBase(BaseModel):
    device_id: str
    severity: str = Field(..., json_schema_extra={"example": "WARNING"})
    parameter: str = Field(..., json_schema_extra={"example": "ph"})
    triggered_value: float
    threshold_limit: float
    message: str

class AlertCreate(AlertBase):
    timestamp: Optional[datetime] = None

class AlertResponse(AlertBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    is_acknowledged: bool
    acknowledged_at: Optional[datetime] = None

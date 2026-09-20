from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class DeviceBase(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "DIGESTER_001"})
    name: str = Field(..., json_schema_extra={"example": "Community Digester Alpha"})
    location: Optional[str] = Field(None, json_schema_extra={"example": "Sholinganallur Center"})
    mode: str = Field("DEMO", json_schema_extra={"example": "DEMO"})

class DeviceCreate(DeviceBase):
    pass

class DeviceResponse(DeviceBase):
    model_config = ConfigDict(from_attributes=True)
    status: str
    is_active: bool
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None

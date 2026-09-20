from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ModelRunBase(BaseModel):
    model_name: str
    model_type: str
    version: str
    dataset_source: str
    mae: Optional[float] = None
    rmse: Optional[float] = None
    r2: Optional[float] = None
    nnse: Optional[float] = None
    hyperparameters: Optional[str] = None
    feature_list: Optional[str] = None
    model_path: Optional[str] = None

class ModelRunCreate(ModelRunBase):
    pass

class ModelRunResponse(ModelRunBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime

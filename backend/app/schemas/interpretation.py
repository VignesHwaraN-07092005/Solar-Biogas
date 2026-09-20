from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class InterpretationFeatureSignal(BaseModel):
    name: str
    label: str
    latest_value: Optional[float] = None
    unit: str = ""
    trend: str = "→"  # "↑", "↑", "→"

class InterpretationSensitivity(BaseModel):
    feature_name: str
    label: str
    delta_prediction_nm3: float

class InterpretationWeight(BaseModel):
    component: str
    weight: str
    influence_nm3: Optional[float] = None

class ForecastInterpretationResponse(BaseModel):
    model_name: str
    method: str
    is_shap: bool = False
    available: bool = True
    prediction_nm3_day: Optional[float] = None
    reference_nm3_day: Optional[float] = None
    reference_label: Optional[str] = None
    prediction_delta_nm3_day: Optional[float] = None
    features: List[InterpretationFeatureSignal] = []
    sensitivities: List[InterpretationSensitivity] = []
    contributions: List[InterpretationWeight] = []
    explanation_text: str = ""
    reason: Optional[str] = None

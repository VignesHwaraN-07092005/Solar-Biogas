from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ColumnMappingDetail(BaseModel):
    original_name: str
    normalized_name: str
    semantic_concept: Optional[str] = None
    detected_unit: Optional[str] = None
    conversion_applied: Optional[str] = None
    is_required_feature: bool = False
    confidence: float = 0.0

class ColumnStatistics(BaseModel):
    column_name: str
    semantic_concept: Optional[str] = None
    count: int = 0
    null_count: int = 0
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None

class ModelEligibility(BaseModel):
    model_name: str
    eligible: bool
    required_history: int
    available_history: int
    missing_features: List[str] = []
    reasons: List[str] = []

class IngestionAnalyzeRequest(BaseModel):
    filename: str = "uploaded_data.xlsx"
    rows: List[Dict[str, Any]]

class IngestionReportResponse(BaseModel):
    filename: str
    total_rows: int
    total_columns: int
    recognized_columns_count: int
    extra_columns_count: int
    unmapped_columns_count: int
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    sampling_interval: str = "Unknown"
    duplicate_timestamps: int = 0
    missing_timestamps: int = 0
    timestamp_status: str = "Valid"
    mappings: List[ColumnMappingDetail] = []
    statistics: List[ColumnStatistics] = []
    model_eligibility: Dict[str, ModelEligibility] = {}
    data_source: str = "USER_UPLOAD"
    domain_valid: bool = False
    domain_status: str = "UNVALIDATED USER DATASET"
    domain_note: str = "Uploaded dataset has not been validated against the operational training domain."

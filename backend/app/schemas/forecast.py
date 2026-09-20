from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ProvenanceEnum(str, Enum):
    DEMO_SYNTHETIC = "DEMO_SYNTHETIC"
    REAL_SPARK_HISTORICAL = "REAL_SPARK_HISTORICAL"
    SPARK_FULL = "SPARK_FULL"
    AGSTAR_REGISTRY = "AGSTAR_REGISTRY"
    LIVE_IOT = "LIVE_IOT"
    USER_UPLOAD = "USER_UPLOAD"
    UPLOADED_SCADA = "UPLOADED_SCADA"

class ForecastStatusEnum(str, Enum):
    SUCCESS = "SUCCESS"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INSUFFICIENT_LIVE_HISTORY = "INSUFFICIENT LIVE HISTORY"
    INSUFFICIENT_LIVE_FEATURES = "INSUFFICIENT LIVE FEATURES"
    INSUFFICIENT_FEATURES = "INSUFFICIENT_FEATURES"
    UNVALIDATED_USER_DATASET = "UNVALIDATED USER DATASET"

class ModelRoleEnum(str, Enum):
    DEFAULT = "Default Forecasting Model"
    BENCHMARK = "Statistical Benchmark"
    BASELINE = "Naive Baseline"
    EXPERIMENTAL = "Proposed Research Architecture"

class ForecastBase(BaseModel):
    device_id: str
    target_date: datetime
    predicted_biogas_m3_day: float = Field(..., ge=0.0)
    input_biogas_m3_day: Optional[float] = None
    input_timestamp: Optional[datetime] = None
    lower_bound_m3_day: Optional[float] = None
    upper_bound_m3_day: Optional[float] = None
    unit: str = "Nm³/day"
    model_name: str
    model_version: str = "v1.0.0"
    preprocessing_version: str = "v1.0.0-frozen-train"
    data_source: ProvenanceEnum = ProvenanceEnum.DEMO_SYNTHETIC
    status: ForecastStatusEnum = ForecastStatusEnum.SUCCESS
    domain_valid: bool = True
    domain_note: Optional[str] = None
    top_feature_1: Optional[str] = None
    top_feature_2: Optional[str] = None
    top_feature_3: Optional[str] = None
    recommendation: Optional[str] = None

class ForecastCreate(ForecastBase):
    pass

class ForecastResponse(ForecastBase):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    timestamp: datetime

class ForecastPredictRequest(BaseModel):
    device_id: str = "DIGESTER_001"
    model_name: str = "GRU-14d Residual"  # "GRU-14d Residual", "EMA-0.90", "Persistence", "XCO-Net"
    data_source: ProvenanceEnum = ProvenanceEnum.DEMO_SYNTHETIC
    history_window: Optional[List[Dict[str, Any]]] = None

class MetricScore(BaseModel):
    mae: float
    rmse: float
    mape_pct: float
    r2: float
    unit: str = "Nm³/day"

class ModelBenchmarkItem(BaseModel):
    model_id: Optional[str] = None
    model_name: str
    category: str
    role: str
    artifact_path: Optional[str] = None
    lookback_days: int
    held_out_test_metrics: MetricScore
    cross_window_mean_metrics: MetricScore
    description: str
    unit: str = "Nm³/day"

class ModelComparisonResponse(BaseModel):
    benchmark_timestamp: str
    models: List[ModelBenchmarkItem]
    walk_forward_windows_evaluated: int = 3
    test_set_days_evaluated: int = 24
    held_out_test_label: str = "Held-Out Test Set — 24 operating days"
    cross_window_mean_label: str = "Cross-Window Mean — 64 out-of-sample days"
    unit: str = "Nm³/day"

class SparkTimelineItem(BaseModel):
    date: str
    target_date: str
    actual_biogas_today_nm3: float
    actual_next_day_nm3: Optional[float] = None
    predicted_next_day_nm3: Optional[float] = None
    model_name: str
    data_source: ProvenanceEnum
    target_is_valid: bool
    temperature_c: float
    ph_d1: float
    feed_total_m3: float
    domain_valid: bool = True
    domain_note: Optional[str] = None
    unit: str = "Nm³/day"
    history_length: int = 14
    status: str = "SUCCESS"

class XCONetResearchResponse(BaseModel):
    architecture_name: str = "XCO-Net (Cross-Channel Operator Network)"
    role: ModelRoleEnum = ModelRoleEnum.EXPERIMENTAL
    total_trainable_parameters: int = 2706
    parameter_to_sample_ratio: float = 25.8
    delta_bounding_mechanism: str = "Differentiable tanh-bounded delta: delta_y = delta_max * tanh(raw_delta)"
    delta_max_nm3_day: float = 4152.0
    loss_function: str = "Physics-Guided Huber Loss with non-negativity barrier"
    cross_channel_mixing: str = "1x1 Conv pointwise projection + LayerNorm"
    ablation_findings: Dict[str, Any]
    feature_attributions: List[Dict[str, Any]]

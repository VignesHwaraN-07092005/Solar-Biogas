from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from datetime import datetime, timezone
from backend.app.database import Base

class ForecastResult(Base):
    __tablename__ = "forecast_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    target_date = Column(DateTime, nullable=False)
    
    predicted_biogas_m3_day = Column(Float, nullable=False)
    input_biogas_m3_day = Column(Float, nullable=True)
    input_timestamp = Column(DateTime, nullable=True)
    lower_bound_m3_day = Column(Float, nullable=True)
    upper_bound_m3_day = Column(Float, nullable=True)
    
    model_name = Column(String(64), nullable=False)
    model_version = Column(String(32), default="v1.0.0")
    preprocessing_version = Column(String(32), default="v1.0.0-frozen-train")
    data_source = Column(String(32), default="DEMO_SYNTHETIC")
    status = Column(String(32), default="SUCCESS")
    domain_valid = Column(Boolean, default=True)
    domain_note = Column(String(256), nullable=True)
    
    # Top SHAP attributions
    top_feature_1 = Column(String(64), nullable=True)
    top_feature_2 = Column(String(64), nullable=True)
    top_feature_3 = Column(String(64), nullable=True)
    recommendation = Column(String(512), nullable=True)

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime, timezone
from backend.app.database import Base

class ModelRun(Base):
    __tablename__ = "model_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_name = Column(String(64), nullable=False, index=True)
    model_type = Column(String(32), nullable=False)  # baseline, temporal, xco_net
    version = Column(String(32), nullable=False)
    dataset_source = Column(String(64), nullable=False)
    
    # Metrics
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    r2 = Column(Float, nullable=True)
    nnse = Column(Float, nullable=True)
    
    hyperparameters = Column(Text, nullable=True)
    feature_list = Column(Text, nullable=True)
    model_path = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

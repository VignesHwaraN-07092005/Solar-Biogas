from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.app.database import get_db
from backend.app.models.forecast import ForecastResult
from backend.app.schemas.forecast import (
    ForecastCreate,
    ForecastResponse,
    ForecastPredictRequest,
    ModelComparisonResponse,
    SparkTimelineItem,
    XCONetResearchResponse,
    ProvenanceEnum
)
from backend.app.schemas.interpretation import ForecastInterpretationResponse
from backend.app.services.forecast_service import forecast_service

router = APIRouter(prefix="/api/forecast", tags=["Forecast"])

@router.get("", response_model=Optional[ForecastResponse])
@router.get("/latest", response_model=Optional[ForecastResponse])
def get_latest_forecast(
    device_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(ForecastResult)
    if device_id:
        query = query.filter(ForecastResult.device_id == device_id)
    if model_name:
        query = query.filter(ForecastResult.model_name.ilike(f"%{model_name}%"))
    return query.order_by(ForecastResult.timestamp.desc()).first()

@router.get("/history", response_model=List[ForecastResponse])
def get_forecast_history(
    device_id: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(ForecastResult)
    if device_id:
        query = query.filter(ForecastResult.device_id == device_id)
    if model_name:
        query = query.filter(ForecastResult.model_name.ilike(f"%{model_name}%"))
    return query.order_by(ForecastResult.timestamp.desc()).limit(limit).all()

@router.post("/predict", response_model=ForecastResponse)
def predict_forecast(
    req: ForecastPredictRequest,
    db: Session = Depends(get_db)
):
    """
    Generate next-day forecast using the selected model.
    Enforces minimum history, strict causality, and records controlled provenance.
    """
    try:
        res = forecast_service.predict(
            device_id=req.device_id,
            model_name=req.model_name,
            data_source=req.data_source,
            history_window=req.history_window,
            db=db
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/interpretation", response_model=ForecastInterpretationResponse)
def get_forecast_interpretation_post(
    req: ForecastPredictRequest,
    db: Session = Depends(get_db)
):
    """
    Returns model-specific interpretation:
    - GRU: Local input sensitivity over current 14-step sequence (is_shap: False)
    - EMA: Exact mathematical decomposition
    - Persistence: Baseline identity explanation
    - XCO-Net: Architecture-level research attribution
    """
    try:
        return forecast_service.get_interpretation(
            device_id=req.device_id,
            model_name=req.model_name,
            data_source=req.data_source,
            history_window=req.history_window,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/interpretation", response_model=ForecastInterpretationResponse)
def get_forecast_interpretation_get(
    model_name: str = Query("GRU-14d Residual"),
    device_id: str = Query("DIGESTER_001"),
    data_source: ProvenanceEnum = Query(ProvenanceEnum.DEMO_SYNTHETIC),
    db: Session = Depends(get_db)
):
    """
    GET version of model-specific interpretation fetching latest observations from DB.
    """
    try:
        return forecast_service.get_interpretation(
            device_id=device_id,
            model_name=model_name,
            data_source=data_source,
            history_window=None,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/models-metadata", response_model=Dict[str, Any])
def get_models_metadata():
    """
    Returns authoritative model metadata mapping:
    required lookback history lengths, model roles, and causal footers.
    """
    return forecast_service.get_models_metadata()

@router.get("/benchmarks", response_model=ModelComparisonResponse)
def get_model_benchmarks():
    """
    Returns validated model comparison benchmarks with strict separation
    between held-out test-set metrics and cross-window mean metrics.
    """
    return forecast_service.get_benchmarks()

@router.get("/spark-replay", response_model=List[SparkTimelineItem])
def get_spark_replay(
    model_name: str = Query("GRU-14d Residual"),
    mode: str = Query("held_out_test", description="Replay mode: 'held_out_test' (24 days) or 'full_historical' (176 days)"),
    limit: Optional[int] = Query(None, ge=1, le=200)
):
    """
    Provides causally-strict historical replay timeline from the real Spark dataset.
    Prediction for t+1 uses strictly data through day t.
    """
    try:
        return forecast_service.get_spark_replay_timeline(model_name=model_name, mode=mode, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/xconet-research", response_model=XCONetResearchResponse)
def get_xconet_research():
    """
    Provides XCO-Net research architecture details, parameter counts,
    differentiable tanh training-derived bounded production correction, and ablation findings.
    """
    return forecast_service.get_xconet_research_details()

@router.post("", response_model=ForecastResponse)
def create_forecast(forecast_in: ForecastCreate, db: Session = Depends(get_db)):
    forecast = ForecastResult(
        device_id=forecast_in.device_id,
        timestamp=datetime.now(timezone.utc),
        target_date=forecast_in.target_date,
        predicted_biogas_m3_day=forecast_in.predicted_biogas_m3_day,
        input_biogas_m3_day=forecast_in.input_biogas_m3_day,
        input_timestamp=forecast_in.input_timestamp,
        lower_bound_m3_day=forecast_in.lower_bound_m3_day,
        upper_bound_m3_day=forecast_in.upper_bound_m3_day,
        model_name=forecast_in.model_name,
        model_version=forecast_in.model_version,
        preprocessing_version=forecast_in.preprocessing_version,
        data_source=forecast_in.data_source.value if hasattr(forecast_in.data_source, "value") else str(forecast_in.data_source),
        status=forecast_in.status.value if hasattr(forecast_in.status, "value") else str(forecast_in.status),
        top_feature_1=forecast_in.top_feature_1,
        top_feature_2=forecast_in.top_feature_2,
        top_feature_3=forecast_in.top_feature_3,
        domain_valid=forecast_in.domain_valid,
        domain_note=forecast_in.domain_note,
        recommendation=forecast_in.recommendation
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return forecast

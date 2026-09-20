from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.database import get_db
from backend.app.models.model_run import ModelRun
from backend.app.schemas.model import ModelRunCreate, ModelRunResponse

router = APIRouter(prefix="/api/models", tags=["Models"])

@router.get("", response_model=List[ModelRunResponse])
def list_models(db: Session = Depends(get_db)):
    return db.query(ModelRun).order_by(ModelRun.created_at.desc()).all()

@router.post("", response_model=ModelRunResponse)
def register_model_run(run_in: ModelRunCreate, db: Session = Depends(get_db)):
    run = ModelRun(
        model_name=run_in.model_name,
        model_type=run_in.model_type,
        version=run_in.version,
        dataset_source=run_in.dataset_source,
        mae=run_in.mae,
        rmse=run_in.rmse,
        r2=run_in.r2,
        nnse=run_in.nnse,
        hyperparameters=run_in.hyperparameters,
        feature_list=run_in.feature_list,
        model_path=run_in.model_path
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

@router.get("/{model_id}/metrics")
def get_model_metrics(model_id: int, db: Session = Depends(get_db)):
    model = db.query(ModelRun).filter(ModelRun.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model run not found")
    return {
        "id": model.id,
        "name": model.model_name,
        "type": model.model_type,
        "version": model.version,
        "dataset": model.dataset_source,
        "metrics": {
            "mae": model.mae,
            "rmse": model.rmse,
            "r2": model.r2,
            "nnse": model.nnse
        }
    }

from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any, Optional

from backend.app.services.simulator_service import simulator_service

router = APIRouter(prefix="/api/simulator", tags=["Simulator"])

@router.get("/timeline")
def get_simulator_timeline(
    days: int = Query(180, ge=14, le=365),
    warmup_days: int = Query(14, ge=1, le=30)
):
    """
    Returns synthetic community anaerobic digestion timeline with
    14-day warm-up buffer and causal next-day GRU predictions.
    """
    return simulator_service.get_simulator_timeline(days=days, warmup_days=warmup_days)

@router.get("/continuity-log")
def get_continuity_log(
    days: int = Query(180, ge=14, le=365)
):
    """
    Audit endpoint verifying that simulator timestamps strictly increase,
    interval is strictly 24 hours, no duplicates exist, and 14-day history is continuous.
    """
    success, log_data = simulator_service.verify_simulator_continuity(days=days)
    if not success:
        raise HTTPException(status_code=500, detail=log_data)
    return log_data

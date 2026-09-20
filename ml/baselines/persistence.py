"""
Persistence and Seasonal Persistence Baselines for Daily Biogas Forecasting.
- Standard Persistence: y_hat(t+1) = y(t)
- Seasonal Persistence: y_hat(t+1) = y(t-6) (7-day cyclical shift)
Zero training required; serves as the ground-truth benchmark for ML models.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate standard regression metrics: MAE, RMSE, MAPE, R2."""
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    yt = y_true[mask]
    yp = y_pred[mask]
    
    if len(yt) == 0:
        return {"mae": float("nan"), "rmse": float("nan"), "mape_pct": float("nan"), "r2": float("nan")}
    
    mae = float(np.mean(np.abs(yt - yp)))
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
    
    # Avoid division by zero for MAPE
    non_zero = yt != 0
    if np.sum(non_zero) > 0:
        mape = float(np.mean(np.abs((yt[non_zero] - yp[non_zero]) / yt[non_zero])) * 100)
    else:
        mape = float("nan")
        
    ss_res = np.sum((yt - yp) ** 2)
    ss_tot = np.sum((yt - np.mean(yt)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else float("nan")
    
    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape_pct": round(mape, 2),
        "r2": round(r2, 4)
    }


def run_persistence_baseline(test_df: pd.DataFrame) -> Dict[str, Any]:
    """Standard Persistence: predict tomorrow using today's observed production."""
    y_true = test_df["target_biogas_next_day_nm3"].values
    y_pred = test_df["biogas_today_nm3"].values
    metrics = evaluate_predictions(y_true, y_pred)
    return {
        "model": "Persistence (Lag-0)",
        "type": "Naive Benchmark",
        "description": "y_hat(t+1) = y(t)",
        **metrics
    }


def run_seasonal_persistence(test_df: pd.DataFrame) -> Dict[str, Any]:
    """Seasonal Persistence: predict tomorrow using production from 7 days ago."""
    y_true = test_df["target_biogas_next_day_nm3"].values
    y_pred = test_df["biogas_lag_7d"].values
    metrics = evaluate_predictions(y_true, y_pred)
    return {
        "model": "Seasonal Persistence (Lag-7)",
        "type": "Naive Benchmark",
        "description": "y_hat(t+1) = y(t-6)",
        **metrics
    }

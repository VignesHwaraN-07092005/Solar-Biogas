"""
Standardized Ridge Regression Baseline for Daily Biogas Forecasting.
Applies L2 regularization on standardized operational and environmental features.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from ml.baselines.persistence import evaluate_predictions


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """Extract strictly historical input features, excluding targets and identifiers."""
    exclude = [
        "date", "target_biogas_next_day_nm3", "target_is_valid",
        "raw_gas_d1_nm3", "raw_gas_d2_nm3", "raw_gas_total_nm3",
        "raw_gas_total_raw_nm3", "biogas_prod_feature_imputed"
    ]
    return [c for c in df.columns if c not in exclude]


def run_ridge_baseline(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, alpha: float = 1.0) -> Dict[str, Any]:
    """Train and evaluate Ridge Regression on test set."""
    features = get_feature_columns(train_df)
    
    # Filter rows with valid targets
    tr = train_df[train_df["target_is_valid"] == 1]
    te = test_df[test_df["target_is_valid"] == 1]
    
    X_train = tr[features].values
    y_train = tr["target_biogas_next_day_nm3"].values
    
    X_test = te[features].values
    y_test = te["target_biogas_next_day_nm3"].values
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    model = Ridge(alpha=alpha, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    y_pred = model.predict(X_test_scaled)
    metrics = evaluate_predictions(y_test, y_pred)
    
    return {
        "model": "Ridge Regression",
        "type": "Linear L2 Regularized",
        "description": f"Standardized linear model (alpha={alpha})",
        **metrics
    }

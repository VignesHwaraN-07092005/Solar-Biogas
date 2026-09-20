"""
Tree-Based Non-Linear Baselines: Random Forest & Gradient Boosted Trees.
Captures non-linear biological digester responses and feedstock interaction effects.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from ml.baselines.persistence import evaluate_predictions
from ml.baselines.ridge_regression import get_feature_columns


def run_random_forest_baseline(train_df: pd.DataFrame, test_df: pd.DataFrame) -> Dict[str, Any]:
    """Train and evaluate Random Forest Regressor on test set."""
    features = get_feature_columns(train_df)
    
    tr = train_df[train_df["target_is_valid"] == 1]
    te = test_df[test_df["target_is_valid"] == 1]
    
    X_train = tr[features].values
    y_train = tr["target_biogas_next_day_nm3"].values
    X_test = te[features].values
    y_test = te["target_biogas_next_day_nm3"].values
    
    rf = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    
    y_pred = rf.predict(X_test)
    metrics = evaluate_predictions(y_test, y_pred)
    
    return {
        "model": "Random Forest Regressor",
        "type": "Ensemble Bagging",
        "description": "100 trees, max_depth=6",
        **metrics
    }


def run_gradient_boosting_baseline(train_df: pd.DataFrame, test_df: pd.DataFrame) -> Dict[str, Any]:
    """Train and evaluate Gradient Boosted Trees (XGBoost equivalent) on test set."""
    features = get_feature_columns(train_df)
    
    tr = train_df[train_df["target_is_valid"] == 1]
    te = test_df[test_df["target_is_valid"] == 1]
    
    X_train = tr[features].values
    y_train = tr["target_biogas_next_day_nm3"].values
    X_test = te[features].values
    y_test = te["target_biogas_next_day_nm3"].values
    
    # Use xgboost if installed, otherwise GradientBoostingRegressor
    try:
        from xgboost import XGBRegressor
        model = XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model_name = "XGBoost Regressor"
    except ImportError:
        model = GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        model_name = "Gradient Boosting Regressor (XGBoost counterpart)"
        
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    metrics = evaluate_predictions(y_test, y_pred)
    
    return {
        "model": model_name,
        "type": "Gradient Boosted Trees",
        "description": "100 estimators, max_depth=4, lr=0.05",
        **metrics
    }

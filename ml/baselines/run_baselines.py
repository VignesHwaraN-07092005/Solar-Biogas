"""
Unified Baseline Execution and Experiment Tracker.
Runs all baseline models on the strictly chronological test split
and logs actual measured metrics to results/baseline_results.csv.
"""

import os
from datetime import datetime
import pandas as pd

from ml.preprocessing.temporal_split import temporal_split
from ml.baselines.persistence import run_persistence_baseline, run_seasonal_persistence
from ml.baselines.ridge_regression import run_ridge_baseline
from ml.baselines.tree_baselines import run_random_forest_baseline, run_gradient_boosting_baseline

RESULTS_CSV = "results/baseline_results.csv"


def run_all_baselines():
    print("Executing temporal chronological split...")
    train_df, val_df, test_df = temporal_split()
    
    print(f"Dataset splits: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")
    
    results = []
    
    # 1. Standard Persistence
    res_pers = run_persistence_baseline(test_df)
    results.append(res_pers)
    
    # 2. Seasonal Persistence (7-day lag)
    res_seas = run_seasonal_persistence(test_df)
    results.append(res_seas)
    
    # 3. Ridge Regression
    res_ridge = run_ridge_baseline(train_df, val_df, test_df)
    results.append(res_ridge)
    
    # 4. Random Forest
    res_rf = run_random_forest_baseline(train_df, test_df)
    results.append(res_rf)
    
    # 5. Gradient Boosting
    res_gb = run_gradient_boosting_baseline(train_df, test_df)
    results.append(res_gb)
    
    res_df = pd.DataFrame(results)
    res_df["evaluated_at"] = datetime.now().isoformat()
    res_df["test_samples"] = len(test_df[test_df["target_is_valid"] == 1])
    res_df["test_date_start"] = str(test_df["date"].min().date())
    res_df["test_date_end"] = str(test_df["date"].max().date())
    
    os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
    res_df.to_csv(RESULTS_CSV, index=False)
    
    print("=== BASELINE MODEL BENCHMARK RESULTS (TEST SET) ===")
    print(res_df[["model", "mae", "rmse", "mape_pct", "r2"]].to_string(index=False))
    print(f"Results recorded in: {RESULTS_CSV}")
    return res_df


if __name__ == "__main__":
    run_all_baselines()

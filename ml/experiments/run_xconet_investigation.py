"""
Master Execution Pipeline for Physics-Guided XCO-Net and SFOA Investigation.
Conducts:
1. SFOA hyperparameter optimization on train/val
2. Champion model training, weight freezing, and test-set evaluation
3. Mandatory Ablation study (A through E)
4. Comparative benchmark against Persistence, EMA-0.90, GRU, and Ridge
5. Integrated Gradients explainability
6. Multi-window walk-forward validation
7. Experiment logging across all result tables
"""

import os
import sys
sys.path.insert(0, ".")
import copy
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler

from ml.xco_net.model import XCONet
from ml.xco_net.losses import PhysicsGuidedHuberLoss
from ml.sfoa.optimizer import SunflowerHyperparameterOptimizer, set_seed
from ml.preprocessing.sequence_data import build_sliding_windows
from ml.baselines.persistence import evaluate_predictions
from ml.explainability.xconet_attribution import explain_test_sample


def run_complete_xconet_investigation():
    set_seed(42)
    print("=================================================================")
    print("STARTING PHYSICS-GUIDED XCO-NET & SFOA INVESTIGATION")
    print("=================================================================")
    
    full_df = pd.read_csv("data/processed/spark_biogas_model_ready.csv")
    full_df["date"] = pd.to_datetime(full_df["date"])
    
    # Core feature definition: 7 core process variables + 2 missingness flags = 9 variables
    feature_cols = [
        "biogas_today_nm3", "total_incoming_mt", "total_processed_mt",
        "feed_total_m3", "temp_outlet_d1_c", "ph_outlet_d1",
        "recycle_water_m3", "feed_total_m3_was_missing", "ph_outlet_d1_was_missing"
    ]
    
    train_dates = (pd.to_datetime("2025-11-01"), pd.to_datetime("2026-02-14")) # 105 days
    val_dates   = (pd.to_datetime("2026-02-15"), pd.to_datetime("2026-03-09")) # 22 days
    test_dates  = (pd.to_datetime("2026-03-10"), pd.to_datetime("2026-04-02")) # 24 days
    
    # Compute delta_max strictly on train.csv
    train_df = pd.read_csv("data/processed/train.csv")
    tr_valid = train_df[train_df["target_is_valid"] == 1]
    delta_max_train = float(np.max(np.abs(tr_valid["target_biogas_next_day_nm3"] - tr_valid["biogas_today_nm3"])))
    print(f"Computed delta_max strictly from training set: {delta_max_train:.2f} Nm3/day")
    
    # -------------------------------------------------------------
    # PHASE 1: SFOA Hyperparameter Optimization on Train / Val only
    # -------------------------------------------------------------
    print("[PHASE 1] Executing Sunflower Optimization Algorithm (SFOA)...")
    sfoa = SunflowerHyperparameterOptimizer(population_size=8, max_iterations=6, seed=42)
    best_params, sfoa_history, _ = sfoa.optimize(
        full_df, feature_cols, train_dates, val_dates
    )
    
    os.makedirs("results", exist_ok=True)
    sfoa_history.to_csv("results/sfoa_search_results.csv", index=False)
    print(f"SFOA history saved to results/sfoa_search_results.csv")
    print(f"SFOA Champion Parameters: {best_params}")
    
    # -------------------------------------------------------------
    # Helper to train a specific configuration with early stopping
    # -------------------------------------------------------------
    def fit_and_evaluate_xconet(
        lookback: int,
        hidden_dim: int,
        dropout: float,
        lr: float,
        weight_decay: float,
        gamma_phys: float,
        use_cross_channel: bool = True,
        use_temporal_attn: bool = True,
        epochs: int = 120,
        tr_dates = None,
        va_dates = None,
        te_dates = None,
    ):
        set_seed(42)
        cur_tr = tr_dates if tr_dates is not None else train_dates
        cur_va = va_dates if va_dates is not None else val_dates
        cur_te = te_dates if te_dates is not None else test_dates
        
        tr_slice = full_df[(full_df["date"] >= cur_tr[0]) & (full_df["date"] <= cur_tr[1]) & (full_df["target_is_valid"] == 1)]
        cur_delta_max = float(np.max(np.abs(tr_slice["target_biogas_next_day_nm3"] - tr_slice["biogas_today_nm3"]))) if len(tr_slice) > 0 else delta_max_train

        X_tr_raw, y_tr, y_anc_tr, _ = build_sliding_windows(full_df, feature_cols, lookback, cur_tr)
        X_va_raw, y_va, y_anc_va, _ = build_sliding_windows(full_df, feature_cols, lookback, cur_va)
        X_te_raw, y_te, y_anc_te, dates_te = build_sliding_windows(full_df, feature_cols, lookback, cur_te)
        
        N_tr, L, D = X_tr_raw.shape
        scaler = StandardScaler()
        X_tr_flat = scaler.fit_transform(X_tr_raw.reshape(-1, D))
        X_tr = X_tr_flat.reshape(N_tr, L, D)
        
        N_va = X_va_raw.shape[0]
        X_va = scaler.transform(X_va_raw.reshape(-1, D)).reshape(N_va, L, D)
        
        N_te = X_te_raw.shape[0]
        X_te = scaler.transform(X_te_raw.reshape(-1, D)).reshape(N_te, L, D)
        
        t_X_tr = torch.tensor(X_tr, dtype=torch.float32)
        t_y_tr = torch.tensor(y_tr, dtype=torch.float32).view(-1, 1)
        t_anc_tr = torch.tensor(y_anc_tr, dtype=torch.float32).view(-1, 1)
        
        t_X_va = torch.tensor(X_va, dtype=torch.float32)
        t_y_va = torch.tensor(y_va, dtype=torch.float32).view(-1, 1)
        t_anc_va = torch.tensor(y_anc_va, dtype=torch.float32).view(-1, 1)
        
        t_X_te = torch.tensor(X_te, dtype=torch.float32)
        t_anc_te = torch.tensor(y_anc_te, dtype=torch.float32).view(-1, 1)
        
        model = XCONet(
            input_dim=D,
            hidden_dim=hidden_dim,
            num_layers=1,
            dropout=dropout,
            delta_max=cur_delta_max,
            use_cross_channel=use_cross_channel,
            use_temporal_attn=use_temporal_attn
        )
        
        criterion = PhysicsGuidedHuberLoss(delta=500.0, gamma_phys=gamma_phys)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        
        best_val_loss = float("inf")
        best_weights = None
        
        model.train()
        for ep in range(epochs):
            optimizer.zero_grad()
            y_hat, delta_y = model(t_X_tr, t_anc_tr)
            loss = criterion(y_hat, t_y_tr)
            loss.backward()
            optimizer.step()
            
            # Evaluate validation
            model.eval()
            with torch.no_grad():
                pred_va, _ = model(t_X_va, t_anc_va)
                val_loss = float(criterion(pred_va, t_y_va).item())
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    best_weights = copy.deepcopy(model.state_dict())
            model.train()
            
        # Load best weights
        model.load_state_dict(best_weights)
        model.eval()
        
        with torch.no_grad():
            pred_va, _ = model(t_X_va, t_anc_va)
            p_va_np = pred_va.numpy().flatten()
            m_va = evaluate_predictions(y_va, p_va_np)
            
            pred_te, delta_te = model(t_X_te, t_anc_te)
            p_te_np = pred_te.numpy().flatten()
            m_te = evaluate_predictions(y_te, p_te_np)
            
        param_count = model.get_parameter_count()
        return model, best_weights, param_count, m_va, m_te, X_te, y_anc_te, dates_te
        
    # -------------------------------------------------------------
    # PHASE 2: Train & Freeze SFOA Champion XCO-Net
    # -------------------------------------------------------------
    print("[PHASE 2] Training and Freezing SFOA Champion XCO-Net...")
    best_model, best_weights, param_count, m_va_best, m_te_best, X_te_best, anc_te_best, dates_te = fit_and_evaluate_xconet(
        lookback=best_params["lookback"],
        hidden_dim=best_params["hidden_dim"],
        dropout=best_params["dropout"],
        lr=best_params["lr"],
        weight_decay=best_params["weight_decay"],
        gamma_phys=best_params["gamma_phys"],
        use_cross_channel=True,
        use_temporal_attn=True
    )
    
    os.makedirs("models", exist_ok=True)
    torch.save(best_weights, "models/xco_net_best.pt")
    print(f"Frozen champion weights saved to models/xco_net_best.pt (Total Parameters: {param_count:,})")
    print(f"Champion Test Evaluation: MAE={m_te_best['mae']}, RMSE={m_te_best['rmse']}, MAPE={m_te_best['mape_pct']}%, R2={m_te_best['r2']}")

    # -------------------------------------------------------------
    # PHASE 3: Mandatory Component Ablation Study (A through E)
    # -------------------------------------------------------------
    print("[PHASE 3] Running Mandatory Component Ablations (A through E)...")
    ablation_records = []
    
    # Ablation A: Persistence Anchor Only
    test_df = pd.read_csv("data/processed/test.csv")
    val_df = pd.read_csv("data/processed/val.csv")
    te_v = test_df[test_df["target_is_valid"] == 1]
    va_v = val_df[val_df["target_is_valid"] == 1]
    m_va_pers = evaluate_predictions(va_v["target_biogas_next_day_nm3"].values, va_v["biogas_today_nm3"].values)
    m_te_pers = evaluate_predictions(te_v["target_biogas_next_day_nm3"].values, te_v["biogas_today_nm3"].values)
    ablation_records.append({
        "ablation_id": "A",
        "description": "Persistence Anchor Only (y_t)",
        "use_temporal_branch": False,
        "use_cross_channel": False,
        "use_physics_penalty": False,
        "sfoa_optimized": False,
        "param_count": 0,
        "val_mae": m_va_pers["mae"],
        "val_rmse": m_va_pers["rmse"],
        "val_r2": m_va_pers["r2"],
        "test_mae": m_te_pers["mae"],
        "test_rmse": m_te_pers["rmse"],
        "test_mape_pct": m_te_pers["mape_pct"],
        "test_r2": m_te_pers["r2"]
    })
    
    # Ablation B: Temporal Branch Without Cross-Channel
    _, _, p_b, m_va_b, m_te_b, _, _, _ = fit_and_evaluate_xconet(
        lookback=14, hidden_dim=24, dropout=0.1, lr=0.005, weight_decay=1e-4, gamma_phys=0.0,
        use_cross_channel=False, use_temporal_attn=False
    )
    ablation_records.append({
        "ablation_id": "B",
        "description": "Temporal Branch (GRU) without Cross-Channel",
        "use_temporal_branch": True,
        "use_cross_channel": False,
        "use_physics_penalty": False,
        "sfoa_optimized": False,
        "param_count": p_b,
        "val_mae": m_va_b["mae"],
        "val_rmse": m_va_b["rmse"],
        "val_r2": m_va_b["r2"],
        "test_mae": m_te_b["mae"],
        "test_rmse": m_te_b["rmse"],
        "test_mape_pct": m_te_b["mape_pct"],
        "test_r2": m_te_b["r2"]
    })
    
    # Ablation C: Temporal + Cross-Channel (No Physics Loss)
    _, _, p_c, m_va_c, m_te_c, _, _, _ = fit_and_evaluate_xconet(
        lookback=14, hidden_dim=24, dropout=0.1, lr=0.005, weight_decay=1e-4, gamma_phys=0.0,
        use_cross_channel=True, use_temporal_attn=True
    )
    ablation_records.append({
        "ablation_id": "C",
        "description": "Temporal + Cross-Channel Mixing (No Physics Loss)",
        "use_temporal_branch": True,
        "use_cross_channel": True,
        "use_physics_penalty": False,
        "sfoa_optimized": False,
        "param_count": p_c,
        "val_mae": m_va_c["mae"],
        "val_rmse": m_va_c["rmse"],
        "val_r2": m_va_c["r2"],
        "test_mae": m_te_c["mae"],
        "test_rmse": m_te_c["rmse"],
        "test_mape_pct": m_te_c["mape_pct"],
        "test_r2": m_te_c["r2"]
    })
    
    # Ablation D: XCO-Net + Physics Penalty (Fixed Hand-Tuned)
    _, _, p_d, m_va_d, m_te_d, _, _, _ = fit_and_evaluate_xconet(
        lookback=14, hidden_dim=24, dropout=0.1, lr=0.005, weight_decay=1e-4, gamma_phys=0.01,
        use_cross_channel=True, use_temporal_attn=True
    )
    ablation_records.append({
        "ablation_id": "D",
        "description": "XCO-Net with Physics-Guided Penalty (Hand-Tuned)",
        "use_temporal_branch": True,
        "use_cross_channel": True,
        "use_physics_penalty": True,
        "sfoa_optimized": False,
        "param_count": p_d,
        "val_mae": m_va_d["mae"],
        "val_rmse": m_va_d["rmse"],
        "val_r2": m_va_d["r2"],
        "test_mae": m_te_d["mae"],
        "test_rmse": m_te_d["rmse"],
        "test_mape_pct": m_te_d["mape_pct"],
        "test_r2": m_te_d["r2"]
    })
    
    # Ablation E: XCO-Net + SFOA (Champion)
    ablation_records.append({
        "ablation_id": "E",
        "description": f"XCO-Net + SFOA Optimized (L={best_params['lookback']}, d_h={best_params['hidden_dim']}, gamma={best_params['gamma_phys']})",
        "use_temporal_branch": True,
        "use_cross_channel": True,
        "use_physics_penalty": best_params["gamma_phys"] > 0,
        "sfoa_optimized": True,
        "param_count": param_count,
        "val_mae": m_va_best["mae"],
        "val_rmse": m_va_best["rmse"],
        "val_r2": m_va_best["r2"],
        "test_mae": m_te_best["mae"],
        "test_rmse": m_te_best["rmse"],
        "test_mape_pct": m_te_best["mape_pct"],
        "test_r2": m_te_best["r2"]
    })
    
    ablation_df = pd.DataFrame(ablation_records)
    ablation_df.to_csv("results/xconet_ablation_results.csv", index=False)
    print("Ablation study saved to results/xconet_ablation_results.csv")
    print(ablation_df[["ablation_id", "description", "param_count", "test_mae", "test_rmse", "test_r2"]].to_string(index=False))

    # -------------------------------------------------------------
    # PHASE 4: Comparative Benchmark Table
    # -------------------------------------------------------------
    print("[PHASE 4] Building Comparative Benchmark Table...")
    benchmark_models = [
        {"model": "Persistence (Lag-0)", "mae": 798.83, "rmse": 1000.90, "mape": 11.15, "r2": 0.1830, "category": "Naive Benchmark"},
        {"model": "Tuned Ridge Regression", "mae": 947.08, "rmse": 1139.13, "mape": 12.14, "r2": -0.0582, "category": "Classical Linear"},
        {"model": "GRU (14-day Residual)", "mae": 766.61, "rmse": 959.40, "mape": 11.01, "r2": 0.2494, "category": "Temporal Neural Network"},
        {"model": "Exponential Moving Average (EMA-0.90)", "mae": 769.02, "rmse": 957.78, "mape": 10.74, "r2": 0.2519, "category": "Statistical Filter"},
        {"model": "XCO-Net (Proposed Project Model)", "mae": m_te_best["mae"], "rmse": m_te_best["rmse"], "mape": m_te_best["mape_pct"], "r2": m_te_best["r2"], "category": "Physics-Guided Dual-Stream"}
    ]
    
    # Reference anchors
    pers_mae, pers_rmse = 798.83, 1000.90
    best_pre_xco_rmse = 957.78 # EMA-0.90
    best_pre_xco_mae = 766.61  # GRU-14d
    
    bench_rows = []
    for m in benchmark_models:
        delta_pers_rmse = pers_rmse - m["rmse"]
        delta_pers_mae = pers_mae - m["mae"]
        pct_imp_pers = (delta_pers_rmse / pers_rmse) * 100.0
        
        delta_pre_rmse = best_pre_xco_rmse - m["rmse"]
        pct_imp_pre_rmse = (delta_pre_rmse / best_pre_xco_rmse) * 100.0
        
        bench_rows.append({
            "model": m["model"],
            "category": m["category"],
            "mae": m["mae"],
            "rmse": m["rmse"],
            "mape_pct": m["mape"],
            "r2": m["r2"],
            "delta_rmse_vs_pers": round(delta_pers_rmse, 2),
            "pct_imp_rmse_vs_pers": round(pct_imp_pers, 2),
            "delta_rmse_vs_best_pre_xco": round(delta_pre_rmse, 2),
            "pct_imp_vs_best_pre_xco": round(pct_imp_pre_rmse, 2)
        })
        
    bench_df = pd.DataFrame(bench_rows)
    bench_df.to_csv("results/xconet_results.csv", index=False)
    print("Benchmark results saved to results/xconet_results.csv")
    print(bench_df[["model", "mae", "rmse", "mape_pct", "r2", "pct_imp_rmse_vs_pers", "delta_rmse_vs_best_pre_xco"]].to_string(index=False))

    # -------------------------------------------------------------
    # PHASE 5: Explainability (Integrated Gradients)
    # -------------------------------------------------------------
    print("[PHASE 5] Computing Feature Attributions via Integrated Gradients...")
    # Find 3 representative test samples:
    # 1. Day with largest positive delta_y
    # 2. Day with largest negative delta_y
    # 3. Steady-state day (delta_y near 0)
    with torch.no_grad():
        t_X_te = torch.tensor(X_te_best, dtype=torch.float32)
        t_anc_te = torch.tensor(anc_te_best, dtype=torch.float32).view(-1, 1)
        _, deltas = best_model(t_X_te, t_anc_te)
        deltas_np = deltas.numpy().flatten()
        
    idx_max_pos = int(np.argmax(deltas_np))
    idx_max_neg = int(np.argmin(deltas_np))
    idx_steady  = int(np.argmin(np.abs(deltas_np)))
    
    rep_indices = [
        ("Largest Positive Correction Day", idx_max_pos),
        ("Largest Negative Correction Day", idx_max_neg),
        ("Steady-State Equilibrium Day", idx_steady)
    ]
    
    explanations = []
    for label, idx in rep_indices:
        x_samp = X_te_best[idx]
        anc_val = float(anc_te_best[idx])
        dt_str = str(dates_te[idx].strftime("%Y-%m-%d"))
        exp_res = explain_test_sample(best_model, x_samp, anc_val, feature_cols, steps=40)
        exp_res["date"] = dt_str
        exp_res["case_label"] = label
        explanations.append(exp_res)
        print(f"  {label} ({dt_str}): Anchor={exp_res['y_anchor']}, Pred_Delta={exp_res['predicted_delta']:+.1f}, Top Drivers={exp_res['top_positive_drivers'] + exp_res['top_negative_drivers']}")

    # -------------------------------------------------------------
    # PHASE 6: Walk-Forward Robustness Validation
    # -------------------------------------------------------------
    print("[PHASE 6] Running Multi-Window Walk-Forward Validation for XCO-Net...")
    windows = [
        {"window_id": 1, "train_idx": (0, 75), "val_idx": (76, 95), "test_idx": (96, 115), "name": "Mid-Winter Transition"},
        {"window_id": 2, "train_idx": (0, 95), "val_idx": (96, 115), "test_idx": (116, 135), "name": "Late-Winter Ramp"},
        {"window_id": 3, "train_idx": (0, 104), "val_idx": (105, 126), "test_idx": (127, 150), "name": "Official Held-Out Spring Test"}
    ]
    
    wf_results = []
    for win in windows:
        w_id = win["window_id"]
        w_name = win["name"]
        
        valid_df = full_df[full_df["target_is_valid"] == 1].reset_index(drop=True)
        w_tr_dates = (valid_df.loc[win["train_idx"][0], "date"], valid_df.loc[win["train_idx"][1], "date"])
        w_va_dates = (valid_df.loc[win["val_idx"][0], "date"], valid_df.loc[win["val_idx"][1], "date"])
        w_te_dates = (valid_df.loc[win["test_idx"][0], "date"], valid_df.loc[win["test_idx"][1], "date"])
        
        w_model, _, _, _, m_te_win, p_te_win, y_te_win, _ = fit_and_evaluate_xconet(
            lookback=best_params["lookback"],
            hidden_dim=best_params["hidden_dim"],
            dropout=best_params["dropout"],
            lr=best_params["lr"],
            weight_decay=best_params["weight_decay"],
            gamma_phys=best_params["gamma_phys"],
            use_cross_channel=True,
            use_temporal_attn=True,
            epochs=80,
            tr_dates=w_tr_dates,
            va_dates=w_va_dates,
            te_dates=w_te_dates,
        )
        
        wf_results.append({
            "window_id": w_id,
            "window_name": w_name,
            "test_range": f"{w_te_dates[0].strftime('%Y-%m-%d')} to {w_te_dates[1].strftime('%Y-%m-%d')}",
            "test_n": len(y_te_win),
            "test_mae": m_te_win["mae"],
            "test_rmse": m_te_win["rmse"],
            "test_mape_pct": m_te_win["mape_pct"],
            "test_r2": m_te_win["r2"],
            "actual_sample": str([round(float(x), 1) for x in y_te_win[:3]]),
            "pred_sample": str([round(float(x), 1) for x in p_te_win[:3]])
        })
        
    wf_xco_df = pd.DataFrame(wf_results)
    wf_xco_df.to_csv("results/walk_forward_xconet_results.csv", index=False)
    print("=== XCO-NET WALK-FORWARD WINDOW RESULTS ===")
    print(wf_xco_df[["window_id", "window_name", "test_mae", "test_rmse", "test_r2"]].to_string(index=False))

    # -------------------------------------------------------------
    # PHASE 7: Update EXPERIMENT_LOG.csv with XCO-Net trials
    # -------------------------------------------------------------
    exp_log_path = "results/EXPERIMENT_LOG.csv"
    if os.path.exists(exp_log_path):
        exp_log_df = pd.read_csv(exp_log_path)
        last_id = int(exp_log_df["experiment_id"].str.extract(r'(\d+)')[0].max())
    else:
        exp_log_df = pd.DataFrame()
        last_id = 0

    new_logs = []
    # Add Champion XCO-Net
    last_id += 1
    new_logs.append({
        "experiment_id": f"EXP_{last_id:03d}",
        "model_family": "Physics-Guided XCO-Net",
        "model_name": "XCO-Net (SFOA Champion)",
        "category": "Dual-Stream Physics-Guided",
        "feature_set": "Core Process Variables (9)",
        "lookback_days": best_params["lookback"],
        "hyperparameters": f"L={best_params['lookback']}, d_h={best_params['hidden_dim']}, lr={best_params['lr']}, gamma_phys={best_params['gamma_phys']}, params={param_count:,}",
        "train_dates": "2025-11-01 to 2026-02-14",
        "val_dates": "2026-02-15 to 2026-03-09",
        "test_dates": "2026-03-10 to 2026-04-02",
        "val_mae": m_va_best["mae"],
        "val_rmse": m_va_best["rmse"],
        "val_r2": m_va_best["r2"],
        "test_mae": m_te_best["mae"],
        "test_rmse": m_te_best["rmse"],
        "test_mape_pct": m_te_best["mape_pct"],
        "test_r2": m_te_best["r2"],
        "delta_mae_vs_pers": round(798.83 - m_te_best["mae"], 2),
        "delta_rmse_vs_pers": round(1000.90 - m_te_best["rmse"], 2),
        "pct_imp_rmse": round(((1000.90 - m_te_best["rmse"]) / 1000.90) * 100.0, 2),
        "beats_persistence": m_te_best["rmse"] < 1000.90,
        "random_seed": 42,
        "preprocessing_version": "v1.0-frozen"
    })
    
    updated_exp_df = pd.concat([exp_log_df, pd.DataFrame(new_logs)], ignore_index=True)
    updated_exp_df.to_csv(exp_log_path, index=False)
    print(f"Updated {exp_log_path} with XCO-Net champion experiment.")

    return best_params, param_count, bench_df, ablation_df, explanations, wf_xco_df


if __name__ == "__main__":
    run_complete_xconet_investigation()

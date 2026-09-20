"""
Sunflower Optimization Algorithm (SFOA) for Hyperparameter Optimization.
Simulates solar tracking orientation, radiation absorption, and pollination.
STRICT RESTRICTION: SFOA searches hyperparameters only (never neural weights).
Selection criterion: Validation RMSE on val.csv (train.csv used for fitting).
The test set is completely quarantined and untouched during SFOA execution.
"""

import copy
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from typing import Dict, Any, List, Tuple
from ml.xco_net.model import XCONet
from ml.xco_net.losses import PhysicsGuidedHuberLoss
from ml.baselines.persistence import evaluate_predictions
from sklearn.preprocessing import StandardScaler


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class SunflowerHyperparameterOptimizer:
    def __init__(
        self,
        population_size: int = 8,
        max_iterations: int = 6,
        seed: int = 42
    ):
        self.pop_size = population_size
        self.max_iter = max_iterations
        self.seed = seed
        
        # Bounded Hyperparameter Search Space
        self.lookback_options = [7, 14, 21]
        self.hidden_dim_options = [16, 24, 32]
        self.dropout_bounds = (0.05, 0.25)
        self.lr_bounds = (0.001, 0.008)
        self.weight_decay_bounds = (1e-5, 1e-2)
        self.gamma_phys_bounds = (0.0, 0.05)

    def _sample_random_sunflower(self) -> Dict[str, Any]:
        """Generate a random sunflower position in hyperparameter space."""
        return {
            "lookback": random.choice(self.lookback_options),
            "hidden_dim": random.choice(self.hidden_dim_options),
            "dropout": round(random.uniform(*self.dropout_bounds), 3),
            "lr": round(random.uniform(*self.lr_bounds), 4),
            "weight_decay": round(10 ** random.uniform(-5, -2), 6),
            "gamma_phys": round(random.uniform(*self.gamma_phys_bounds), 4)
        }

    def _evaluate_candidate(
        self,
        params: Dict[str, Any],
        full_df: pd.DataFrame,
        feature_cols: List[str],
        train_dates: Tuple[pd.Timestamp, pd.Timestamp],
        val_dates: Tuple[pd.Timestamp, pd.Timestamp],
        epochs: int = 80
    ) -> Tuple[float, Dict[str, Any], Any]:
        """Train candidate XCO-Net on train.csv and evaluate on val.csv."""
        set_seed(self.seed)
        L = params["lookback"]
        
        from ml.preprocessing.sequence_data import build_sliding_windows
        X_tr_raw, y_tr, y_anc_tr, _ = build_sliding_windows(full_df, feature_cols, L, train_dates)
        X_va_raw, y_va, y_anc_va, _ = build_sliding_windows(full_df, feature_cols, L, val_dates)
        
        # 2. Scale features strictly on train
        N_tr, _, D = X_tr_raw.shape
        scaler = StandardScaler()
        X_tr_flat = scaler.fit_transform(X_tr_raw.reshape(-1, D))
        X_tr = X_tr_flat.reshape(N_tr, L, D)
        
        N_va = X_va_raw.shape[0]
        X_va = scaler.transform(X_va_raw.reshape(-1, D)).reshape(N_va, L, D)
        
        t_X_tr = torch.tensor(X_tr, dtype=torch.float32)
        t_y_tr = torch.tensor(y_tr, dtype=torch.float32).view(-1, 1)
        t_anc_tr = torch.tensor(y_anc_tr, dtype=torch.float32).view(-1, 1)
        
        t_X_va = torch.tensor(X_va, dtype=torch.float32)
        t_anc_va = torch.tensor(y_anc_va, dtype=torch.float32).view(-1, 1)
        
        # Compute delta_max strictly on training data
        delta_max_train = float(np.max(np.abs(y_tr - y_anc_tr)))
        
        # Instantiate XCONet
        model = XCONet(
            input_dim=D,
            hidden_dim=params["hidden_dim"],
            num_layers=1,
            dropout=params["dropout"],
            delta_max=delta_max_train,
            use_cross_channel=True,
            use_temporal_attn=True
        )
        
        criterion = PhysicsGuidedHuberLoss(delta=500.0, gamma_phys=params["gamma_phys"])
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=params["lr"],
            weight_decay=params["weight_decay"]
        )
        
        best_val_rmse = float("inf")
        best_metrics = None
        best_weights = None
        
        model.train()
        for ep in range(epochs):
            optimizer.zero_grad()
            y_hat, delta_y = model(t_X_tr, t_anc_tr)
            loss = criterion(y_hat, t_y_tr)
            loss.backward()
            optimizer.step()
            
            # Periodic validation
            if (ep + 1) % 5 == 0 or ep == epochs - 1:
                model.eval()
                with torch.no_grad():
                    pred_va, _ = model(t_X_va, t_anc_va)
                    p_va_np = pred_va.numpy().flatten()
                    val_rmse = float(np.sqrt(np.mean((y_va - p_va_np)**2)))
                    if val_rmse < best_val_rmse:
                        best_val_rmse = val_rmse
                        best_metrics = evaluate_predictions(y_va, p_va_np)
                        best_weights = copy.deepcopy(model.state_dict())
                model.train()
                
        return best_val_rmse, best_metrics, best_weights

    def optimize(
        self,
        full_df: pd.DataFrame,
        feature_cols: List[str],
        train_dates: Tuple[pd.Timestamp, pd.Timestamp],
        val_dates: Tuple[pd.Timestamp, pd.Timestamp]
    ) -> Tuple[Dict[str, Any], pd.DataFrame, Any]:
        """Execute SFOA optimization loop."""
        set_seed(self.seed)
        print(f"Initializing SFOA population ({self.pop_size} sunflowers)...")
        
        population = [self._sample_random_sunflower() for _ in range(self.pop_size)]
        history = []
        
        sun_best_rmse = float("inf")
        sun_best_params = None
        sun_best_weights = None
        
        for iteration in range(1, self.max_iter + 1):
            print(f"\n--- SFOA Iteration {iteration}/{self.max_iter} (Solar Tracking Cycle) ---")
            
            for idx, flower in enumerate(population):
                val_rmse, metrics, weights = self._evaluate_candidate(
                    flower, full_df, feature_cols, train_dates, val_dates
                )
                
                is_new_sun = val_rmse < sun_best_rmse
                if is_new_sun:
                    sun_best_rmse = val_rmse
                    sun_best_params = copy.deepcopy(flower)
                    sun_best_weights = copy.deepcopy(weights)
                    
                record = {
                    "iteration": iteration,
                    "sunflower_id": idx + 1,
                    "val_rmse": round(val_rmse, 2),
                    "val_mae": metrics["mae"] if metrics else None,
                    "val_r2": metrics["r2"] if metrics else None,
                    "is_current_sun": is_new_sun,
                    **flower
                }
                history.append(record)
                print(f"  Sunflower {idx+1}: L={flower['lookback']}, d_h={flower['hidden_dim']}, lr={flower['lr']}, val_rmse={val_rmse:.2f} {'[NEW SUN BEST]' if is_new_sun else ''}")

            # SFOA Orientation Step: Sunflowers adjust orientation toward the Sun (best)
            new_pop = [copy.deepcopy(sun_best_params)] # Elitism: keep the Sun
            
            for idx in range(1, self.pop_size):
                curr = population[idx]
                # Step size towards Sun
                step_direction = random.choice([-1, 1])
                
                # Discrete lookback jump with 20% pollination mutation
                if random.random() < 0.3:
                    new_lookback = sun_best_params["lookback"]
                else:
                    new_lookback = random.choice(self.lookback_options)
                    
                if random.random() < 0.3:
                    new_dh = sun_best_params["hidden_dim"]
                else:
                    new_dh = random.choice(self.hidden_dim_options)
                    
                # Continuous parameters move toward Sun
                alpha_step = random.uniform(0.1, 0.4)
                new_lr = np.clip(
                    curr["lr"] + alpha_step * (sun_best_params["lr"] - curr["lr"]) + random.uniform(-0.0005, 0.0005),
                    *self.lr_bounds
                )
                new_dropout = np.clip(
                    curr["dropout"] + alpha_step * (sun_best_params["dropout"] - curr["dropout"]),
                    *self.dropout_bounds
                )
                new_wd = np.clip(
                    curr["weight_decay"] * (1.0 + random.uniform(-0.2, 0.2)),
                    *self.weight_decay_bounds
                )
                new_gamma = np.clip(
                    curr["gamma_phys"] + alpha_step * (sun_best_params["gamma_phys"] - curr["gamma_phys"]),
                    *self.gamma_phys_bounds
                )
                
                new_flower = {
                    "lookback": int(new_lookback),
                    "hidden_dim": int(new_dh),
                    "dropout": round(float(new_dropout), 3),
                    "lr": round(float(new_lr), 4),
                    "weight_decay": round(float(new_wd), 6),
                    "gamma_phys": round(float(new_gamma), 4)
                }
                new_pop.append(new_flower)
                
            population = new_pop

        history_df = pd.DataFrame(history)
        print(f"\nSFOA Search Complete. Best Validation RMSE: {sun_best_rmse:.2f}")
        print(f"Optimal Parameters: {sun_best_params}")
        return sun_best_params, history_df, sun_best_weights

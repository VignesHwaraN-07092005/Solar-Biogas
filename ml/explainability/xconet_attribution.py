"""
Explainability Module for XCO-Net using Integrated Gradients.
Computes feature attributions across process channels driving positive
vs negative daily production corrections delta_y(t+1).
"""

from typing import List, Dict, Any, Tuple
import numpy as np
import torch
import torch.nn as nn
import pandas as pd


def compute_integrated_gradients(
    model: nn.Module,
    input_tensor: torch.Tensor,
    y_anchor: torch.Tensor,
    baseline_tensor: torch.Tensor = None,
    steps: int = 50
) -> np.ndarray:
    """
    Compute Integrated Gradients attribution for the delta_y output.
    input_tensor shape: (1, lookback, input_dim)
    Returns: attribution array of shape (lookback, input_dim)
    """
    model.eval()
    if baseline_tensor is None:
        baseline_tensor = torch.zeros_like(input_tensor)
        
    grads = []
    for i in range(steps + 1):
        alpha = float(i) / steps
        scaled = (baseline_tensor + alpha * (input_tensor - baseline_tensor)).clone().detach().requires_grad_(True)
        _, delta_y = model(scaled, y_anchor)
        delta_y.backward()
        grads.append(scaled.grad.detach().cpu().numpy())
        
    grads = np.array(grads) # (steps+1, 1, lookback, input_dim)
    avg_grads = np.mean(grads[:-1], axis=0) # (1, lookback, input_dim)
    delta_X = (input_tensor - baseline_tensor).detach().cpu().numpy()
    attributions = delta_X * avg_grads # (1, lookback, input_dim)
    return attributions[0]


def explain_test_sample(
    model: nn.Module,
    x_sample: np.ndarray,
    y_anchor_val: float,
    feature_names: List[str],
    steps: int = 50
) -> Dict[str, Any]:
    """
    Generate feature attribution summary for a single operational test day.
    """
    t_x = torch.tensor(x_sample, dtype=torch.float32).unsqueeze(0)
    t_anc = torch.tensor([[y_anchor_val]], dtype=torch.float32)
    
    with torch.no_grad():
        y_hat, delta_y = model(t_x, t_anc)
        y_hat_val = float(y_hat.item())
        delta_val = float(delta_y.item())
        
    attr = compute_integrated_gradients(model, t_x, t_anc, steps=steps)
    # Sum attribution across timesteps per feature channel
    channel_importance = np.sum(attr, axis=0) # (input_dim,)
    
    feat_imp = {
        name: float(imp)
        for name, imp in zip(feature_names, channel_importance)
    }
    
    # Sort by absolute importance
    sorted_feats = sorted(feat_imp.items(), key=lambda kv: abs(kv[1]), reverse=True)
    
    return {
        "y_anchor": round(y_anchor_val, 1),
        "predicted_delta": round(delta_val, 1),
        "final_prediction": round(y_hat_val, 1),
        "top_positive_drivers": [f"{k}: {v:+.2f}" for k, v in sorted_feats if v > 0][:3],
        "top_negative_drivers": [f"{k}: {v:+.2f}" for k, v in sorted_feats if v < 0][:3],
        "all_attributions": feat_imp
    }

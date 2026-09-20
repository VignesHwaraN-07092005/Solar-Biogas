"""
Unit Tests for Physics-Guided XCO-Net Architecture.
Verifies output shapes, persistence anchor integrity, deterministic inference,
absence of NaNs, strict tanh delta bounds, and checkpoint serialization.
"""

import os
import torch
import numpy as np
import pytest

from ml.xco_net.model import XCONet
from ml.xco_net.losses import PhysicsGuidedHuberLoss


def test_xconet_output_shape_and_types():
    """Verify forward pass returns tuple of (y_hat, delta_y) with shape (B, 1)."""
    batch_size = 4
    lookback = 14
    input_dim = 9
    
    model = XCONet(input_dim=input_dim, hidden_dim=24, delta_max=4000.0)
    x = torch.randn(batch_size, lookback, input_dim)
    y_anchor = torch.tensor([5000.0, 6000.0, 7000.0, 8000.0]).view(batch_size, 1)
    
    y_hat, delta_y = model(x, y_anchor)
    
    assert y_hat.shape == (batch_size, 1), f"Expected (4, 1), got {y_hat.shape}"
    assert delta_y.shape == (batch_size, 1), f"Expected (4, 1), got {delta_y.shape}"
    assert isinstance(y_hat, torch.Tensor)
    assert isinstance(delta_y, torch.Tensor)


def test_persistence_anchor_exact_additive_composition():
    """Verify y_hat strictly equals y_anchor + delta_y in all cases."""
    model = XCONet(input_dim=9, hidden_dim=24, delta_max=4000.0)
    x = torch.randn(5, 14, 9)
    y_anchor = torch.tensor([4500.0, 5200.0, 6800.0, 7100.0, 8300.0]).view(5, 1)
    
    y_hat, delta_y = model(x, y_anchor)
    
    diff = torch.abs(y_hat - (y_anchor + delta_y))
    assert torch.max(diff) < 1e-5, "y_hat does not match y_anchor + delta_y!"


def test_differentiable_tanh_delta_bounding():
    """
    Verify strict mathematical bounding: |delta_y| <= delta_max
    even under extreme synthetic input activations (stress test).
    """
    delta_max = 3500.0
    model = XCONet(input_dim=9, hidden_dim=24, delta_max=delta_max)
    
    # Extreme magnitude inputs to force saturation of head
    extreme_x = torch.randn(10, 14, 9) * 1e5
    y_anchor = torch.full((10, 1), 6000.0)
    
    y_hat, delta_y = model(extreme_x, y_anchor)
    
    # Every delta must be strictly within (-delta_max, delta_max)
    assert torch.all(torch.abs(delta_y) <= delta_max + 1e-4), "delta_y exceeded delta_max!"
    assert not torch.isnan(delta_y).any(), "NaNs detected under extreme inputs"
    assert not torch.isnan(y_hat).any(), "NaNs detected in y_hat under extreme inputs"


def test_deterministic_inference():
    """Verify identical inputs yield identical outputs in eval mode."""
    model = XCONet(input_dim=9, hidden_dim=24, dropout=0.2)
    model.eval()
    
    x = torch.randn(2, 14, 9)
    y_anchor = torch.tensor([[6500.0], [7200.0]])
    
    with torch.no_grad():
        out1, delta1 = model(x, y_anchor)
        out2, delta2 = model(x, y_anchor)
        
    assert torch.allclose(out1, out2), "Inference is not deterministic in eval mode!"
    assert torch.allclose(delta1, delta2), "Delta output is not deterministic in eval mode!"


def test_checkpoint_save_and_load(tmp_path):
    """Verify model weights can be serialized, reloaded, and reproduce exact predictions."""
    model = XCONet(input_dim=9, hidden_dim=24, delta_max=4152.0)
    model.eval()
    
    x = torch.randn(3, 14, 9)
    y_anchor = torch.tensor([[5500.0], [6200.0], [7800.0]])
    
    with torch.no_grad():
        orig_pred, orig_delta = model(x, y_anchor)
        
    ckpt_path = tmp_path / "test_model.pt"
    torch.save(model.state_dict(), ckpt_path)
    
    # New instance
    loaded_model = XCONet(input_dim=9, hidden_dim=24, delta_max=4152.0)
    loaded_model.load_state_dict(torch.load(ckpt_path, weights_only=True))
    loaded_model.eval()
    
    with torch.no_grad():
        loaded_pred, loaded_delta = loaded_model(x, y_anchor)
        
    assert torch.allclose(orig_pred, loaded_pred), "Loaded model predictions diverge!"
    assert torch.allclose(orig_delta, loaded_delta), "Loaded model deltas diverge!"


def test_physics_guided_loss_non_negativity():
    """Verify loss penalizes negative predictions when ground truth is positive."""
    loss_fn = PhysicsGuidedHuberLoss(delta=500.0, gamma_phys=0.1)
    
    y_true = torch.tensor([[5000.0]])
    # Positive prediction vs negative prediction
    y_pred_pos = torch.tensor([[4800.0]])
    y_pred_neg = torch.tensor([[-500.0]])
    
    loss_pos = loss_fn(y_pred_pos, y_true)
    loss_neg = loss_fn(y_pred_neg, y_true)
    
    # Loss for negative prediction must be substantially higher due to gamma_phys * relu(-y)^2
    assert loss_neg > loss_pos, "Physics loss failed to heavily penalize negative prediction"

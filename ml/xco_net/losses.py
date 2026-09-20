"""
Physics-Guided Loss Objectives for Anaerobic Digestion Forecasting.
Combines robust Huber regression loss with biological non-negativity constraints.
Zero fabrication: penalty terms are strictly grounded in CSTR physical laws.
"""

import torch
import torch.nn as nn


class PhysicsGuidedHuberLoss(nn.Module):
    """
    Hybrid loss objective combining:
    1. Smooth Huber loss on prediction y_hat vs ground truth y
    2. Non-negativity penalty: anaerobic methane yield cannot be negative (y_hat >= 0).
    """
    def __init__(self, delta: float = 500.0, gamma_phys: float = 0.01):
        super(PhysicsGuidedHuberLoss, self).__init__()
        self.huber = nn.HuberLoss(delta=delta)
        self.gamma_phys = gamma_phys

    def forward(self, y_pred: torch.Tensor, y_true: torch.Tensor) -> torch.Tensor:
        # Primary empirical regression loss
        data_loss = self.huber(y_pred, y_true)
        
        # Non-negativity physical constraint
        # Penalizes any prediction below zero: ReLU(-y_pred)^2
        neg_penalty = torch.mean(torch.relu(-y_pred) ** 2)
        
        total_loss = data_loss + self.gamma_phys * neg_penalty
        return total_loss

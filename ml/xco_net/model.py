"""
XCO-Net: Dual-Stream Cross-Channel Operator Network for Industrial CBG Forecasting.
Proposed Research Architecture for Biogas Intelligence Platform.

Computational Streams:
Channel 1 — Temporal-Inertia / Persistence Inductive Bias:
    Explicit computational graph anchor passing current observed production y(t).
Channel 2 — Cross-Channel Temporal Operator:
    Compact neural sequence encoder with cross-channel feature mixing and learned
    temporal pooling predicting the bounded biological delta:
    delta_y(t+1) = delta_max * tanh(raw_delta)
    where delta_max is computed strictly from training data.

Final Prediction:
    y_hat(t+1) = y(t) + delta_y(t+1)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple


class CrossChannelMixing(nn.Module):
    """Pointwise feature mixing allowing process channels to interact non-linearly."""
    def __init__(self, hidden_dim: int, dropout: float = 0.1):
        super(CrossChannelMixing, self).__init__()
        self.mixing = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim)
        )
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (B, L, hidden_dim)
        res = x
        out = self.mixing(x)
        return self.norm(res + out)


class TemporalAttentionPooling(nn.Module):
    """Learned attention weights across lookback timesteps."""
    def __init__(self, hidden_dim: int):
        super(TemporalAttentionPooling, self).__init__()
        self.attn = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (B, L, hidden_dim)
        scores = self.attn(x) # (B, L, 1)
        weights = F.softmax(scores, dim=1) # (B, L, 1)
        pooled = torch.sum(x * weights, dim=1) # (B, hidden_dim)
        return pooled


class XCONet(nn.Module):
    def __init__(
        self,
        input_dim: int = 9,
        hidden_dim: int = 24,
        num_layers: int = 1,
        dropout: float = 0.1,
        delta_max: float = 4152.0,  # Computed strictly on train.csv max daily shift
        use_cross_channel: bool = True,
        use_temporal_attn: bool = True
    ):
        super(XCONet, self).__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.delta_max = float(delta_max)
        self.use_cross_channel = use_cross_channel
        self.use_temporal_attn = use_temporal_attn
        
        # 1. Feature Projection
        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim)
        )
        
        # 2. Compact Recurrent Backbone
        self.temporal_encoder = nn.GRU(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        
        # 3. Cross-Channel Interaction
        if use_cross_channel:
            self.channel_mixing = CrossChannelMixing(hidden_dim, dropout=dropout)
        else:
            self.channel_mixing = nn.Identity()
            
        # 4. Temporal Aggregation
        if use_temporal_attn:
            self.pool = TemporalAttentionPooling(hidden_dim)
        else:
            self.pool = None
            
        # 5. Residual Correction Head with Differentiable Tanh Bounding
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(16, 1)
        )

    def forward(self, x: torch.Tensor, y_anchor: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Historical context tensor of shape (batch, lookback, input_dim)
            y_anchor: Current observed production y(t) of shape (batch, 1) or (batch,)
        Returns:
            y_hat: Next-day forecast y_hat(t+1) = y(t) + delta_y(t+1)
            delta_y: Bounded biological correction delta
        """
        # Ensure y_anchor is (B, 1)
        if y_anchor.dim() == 1:
            y_anchor = y_anchor.view(-1, 1)
            
        # 1. Project input features
        h = self.input_proj(x) # (B, L, hidden_dim)
        
        # 2. Temporal sequential encoding
        out_seq, _ = self.temporal_encoder(h) # (B, L, hidden_dim)
        
        # 3. Cross-channel interaction
        out_mixed = self.channel_mixing(out_seq) # (B, L, hidden_dim)
        
        # 4. Temporal pooling
        if self.pool is not None:
            context = self.pool(out_mixed) # (B, hidden_dim)
        else:
            context = out_mixed[:, -1, :] # Last timestep
            
        # 5. Raw delta prediction
        raw_delta = self.head(context) # (B, 1)
        
        # 6. Differentiable Tanh Bounding
        # delta_y in (-delta_max, +delta_max)
        delta_y = self.delta_max * torch.tanh(raw_delta)
        
        # 7. Explicit Persistence Composition
        y_hat = y_anchor + delta_y
        
        return y_hat, delta_y

    def get_parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

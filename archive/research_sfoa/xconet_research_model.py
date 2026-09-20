"""
Research-Only Modular XCO-Net Architecture for SFOA Hyperparameter Optimization.
Supports flexible exploration of:
- lookback: [3, 7, 14, 21]
- convolution channels: [8, 16, 32]
- kernel size: [1, 3, 5]
- GRU hidden size: [16, 32, 64]
- GRU layers: [1, 2]
- attention dimension: [8, 16, 32]
- dropout: [0.0, 0.1, 0.2, 0.3]
"""

import math
from typing import Tuple, Optional
import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvCrossChannelMixing(nn.Module):
    """
    1D Convolutional Cross-Channel Operator.
    Applies Conv1d across the temporal sequence to extract cross-channel and temporal motifs.
    Padding is dynamically calculated to preserve temporal sequence length L.
    """
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, dropout: float = 0.1):
        super(ConvCrossChannelMixing, self).__init__()
        padding = (kernel_size - 1) // 2
        self.conv1 = nn.Conv1d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=kernel_size,
            padding=padding
        )
        self.act = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        self.conv2 = nn.Conv1d(
            in_channels=out_channels,
            out_channels=out_channels,
            kernel_size=1
        )
        self.norm = nn.LayerNorm(out_channels)
        self.residual_proj = nn.Linear(in_channels, out_channels) if in_channels != out_channels else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (B, L, C_in)
        residual = self.residual_proj(x)
        # Conv1d expects (B, C_in, L)
        x_trans = x.transpose(1, 2)
        out = self.conv1(x_trans)
        out = self.act(out)
        out = self.dropout(out)
        out = self.conv2(out)
        # Transpose back: (B, L, C_out)
        out = out.transpose(1, 2)
        return self.norm(residual + out)


class ParametricTemporalAttentionPooling(nn.Module):
    """
    Learned 2-layer Attention Pooling with configurable attention dimension.
    Projects hidden representations to attention_dim before computing softmax weights.
    """
    def __init__(self, hidden_dim: int, attention_dim: int = 16):
        super(ParametricTemporalAttentionPooling, self).__init__()
        self.attn = nn.Sequential(
            nn.Linear(hidden_dim, attention_dim),
            nn.Tanh(),
            nn.Linear(attention_dim, 1)
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # x shape: (B, L, hidden_dim)
        scores = self.attn(x)  # (B, L, 1)
        weights = F.softmax(scores, dim=1)  # (B, L, 1)
        pooled = torch.sum(x * weights, dim=1)  # (B, hidden_dim)
        return pooled, weights


class ResearchXCONet(nn.Module):
    """
    SFOA-Configurable Research XCO-Net Architecture.
    Dual-stream design:
    Stream 1: Persistence Inductive Bias Anchor y(t)
    Stream 2: 1D Conv Cross-Channel Mixing -> Deep Recurrent GRU -> Parametric Attention -> Bounded Tanh Head
    """
    def __init__(
        self,
        input_dim: int = 9,
        conv_channels: int = 16,
        kernel_size: int = 3,
        gru_hidden_dim: int = 32,
        gru_layers: int = 1,
        attention_dim: int = 16,
        dropout: float = 0.1,
        delta_max: float = 4152.0,  # Strict training set day-over-day production delta bound
    ):
        super(ResearchXCONet, self).__init__()
        self.input_dim = input_dim
        self.conv_channels = conv_channels
        self.kernel_size = kernel_size
        self.gru_hidden_dim = gru_hidden_dim
        self.gru_layers = gru_layers
        self.attention_dim = attention_dim
        self.delta_max = float(delta_max)
        
        # 1. Linear Input Projection
        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, conv_channels),
            nn.LayerNorm(conv_channels)
        )
        
        # 2. 1D Convolutional Cross-Channel Mixing
        self.conv_mixing = ConvCrossChannelMixing(
            in_channels=conv_channels,
            out_channels=conv_channels,
            kernel_size=kernel_size,
            dropout=dropout
        )
        
        # 3. Recurrent Temporal Backbone (GRU)
        self.gru = nn.GRU(
            input_size=conv_channels,
            hidden_size=gru_hidden_dim,
            num_layers=gru_layers,
            batch_first=True,
            dropout=dropout if gru_layers > 1 else 0.0
        )
        
        # 4. Parametric Temporal Attention Pooling
        self.pool = ParametricTemporalAttentionPooling(
            hidden_dim=gru_hidden_dim,
            attention_dim=attention_dim
        )
        
        # 5. Residual Delta Prediction Head
        self.head = nn.Sequential(
            nn.Linear(gru_hidden_dim, 16),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(16, 1)
        )

    def forward(self, x: torch.Tensor, y_anchor: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Context tensor of shape (B, L, input_dim)
            y_anchor: Current day production y(t) of shape (B, 1) or (B,)
        Returns:
            y_hat: Forecast next-day production (B, 1)
            delta_y: Bounded residual correction (B, 1)
            attn_weights: Attention weights over timesteps (B, L, 1)
        """
        if y_anchor.dim() == 1:
            y_anchor = y_anchor.view(-1, 1)
            
        # 1. Projection
        h_proj = self.input_proj(x)  # (B, L, conv_channels)
        
        # 2. Conv Cross-Channel Mixing
        h_conv = self.conv_mixing(h_proj)  # (B, L, conv_channels)
        
        # 3. Recurrent Sequence Encoding
        out_seq, _ = self.gru(h_conv)  # (B, L, gru_hidden_dim)
        
        # 4. Attention Pooling
        context, attn_weights = self.pool(out_seq)  # (B, gru_hidden_dim), (B, L, 1)
        
        # 5. Raw Delta Prediction & Tanh Bounding
        raw_delta = self.head(context)  # (B, 1)
        delta_y = self.delta_max * torch.tanh(raw_delta)  # Bounded strictly within (-delta_max, +delta_max)
        
        # 6. Anchor Composition
        y_hat = torch.clamp(y_anchor + delta_y, min=0.0)
        return y_hat, delta_y, attn_weights

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

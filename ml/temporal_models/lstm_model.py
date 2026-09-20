"""
Recurrent Neural Network Interfaces for Sequential Biogas Modeling.
Scaffold providing PyTorch LSTM and GRU architectures for multi-step temporal dependencies.
Zero fabrication: cleanly defines sliding window sequence dataset and network architecture.
"""

from typing import Tuple, List, Optional
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd


class BiogasSequenceDataset(Dataset):
    """
    Sliding window sequence dataset for temporal neural networks.
    Produces input tensors of shape (batch, seq_len, num_features)
    and target tensor of shape (batch, 1).
    """
    def __init__(self, df: pd.DataFrame, feature_cols: List[str], seq_len: int = 7):
        self.seq_len = seq_len
        self.feature_cols = feature_cols
        
        # Continuous sequence data
        X_raw = df[feature_cols].values.astype(np.float32)
        y_raw = df["target_biogas_next_day_nm3"].values.astype(np.float32)
        valid_mask = df["target_is_valid"].values
        
        self.sequences = []
        self.targets = []
        
        for i in range(seq_len - 1, len(df)):
            if valid_mask[i] == 1:
                window = X_raw[i - seq_len + 1 : i + 1]
                target = y_raw[i]
                self.sequences.append(window)
                self.targets.append(target)
                
        self.sequences = np.array(self.sequences, dtype=np.float32)
        self.targets = np.array(self.targets, dtype=np.float32).reshape(-1, 1)

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return torch.tensor(self.sequences[idx]), torch.tensor(self.targets[idx])


class BiogasLSTM(nn.Module):
    """Deep LSTM architecture with dropout for sequential biological process tracking."""
    def __init__(self, input_dim: int, hidden_dim: int = 64, num_layers: int = 2, dropout: float = 0.2):
        super(BiogasLSTM, self).__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch_size, seq_len, input_dim)
        out, (hn, cn) = self.lstm(x)
        # Use last timestep representation
        last_hidden = out[:, -1, :]
        pred = self.fc(last_hidden)
        return pred


class BiogasGRU(nn.Module):
    """Gated Recurrent Unit (GRU) architecture with reduced parameterization."""
    def __init__(self, input_dim: int, hidden_dim: int = 64, num_layers: int = 2, dropout: float = 0.2):
        super(BiogasGRU, self).__init__()
        self.gru = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, hn = self.gru(x)
        last_hidden = out[:, -1, :]
        pred = self.fc(last_hidden)
        return pred

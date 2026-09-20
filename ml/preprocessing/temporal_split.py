"""
Temporal Chronological Train / Validation / Test Split Engine.
Preserves strict temporal sequence to prevent future lookahead leakage.
"""

import os
from typing import Tuple
import pandas as pd

PROCESSED_CSV = "data/processed/spark_biogas_model_ready.csv"
TRAIN_CSV = "data/processed/train.csv"
VAL_CSV = "data/processed/val.csv"
TEST_CSV = "data/processed/test.csv"


def temporal_split(
    csv_path: str = PROCESSED_CSV,
    train_pct: float = 0.70,
    val_pct: float = 0.15
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split time-series dataset chronologically into Train (70%), Val (15%), Test (15%).
    Excludes the final row where target t+1 is unobserved.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Processed dataset not found at {csv_path}")

    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Exclude last row if target is NaN (since target is next day)
    valid_df = df[df["target_biogas_next_day_nm3"].notna()].copy().reset_index(drop=True)
    n = len(valid_df)

    n_train = int(n * train_pct)
    n_val = int(n * val_pct)

    train_df = valid_df.iloc[:n_train].copy()
    val_df = valid_df.iloc[n_train:n_train + n_val].copy()
    test_df = valid_df.iloc[n_train + n_val:].copy()

    # Save split files
    train_df.to_csv(TRAIN_CSV, index=False)
    val_df.to_csv(VAL_CSV, index=False)
    test_df.to_csv(TEST_CSV, index=False)

    return train_df, val_df, test_df


if __name__ == "__main__":
    train, val, test = temporal_split()
    print("=== CHRONOLOGICAL TEMPORAL SPLIT COMPLETE ===")
    print(f"Train Set: {len(train)} days ({train['date'].min().date()} to {train['date'].max().date()})")
    print(f"Val Set:   {len(val)} days ({val['date'].min().date()} to {val['date'].max().date()})")
    print(f"Test Set:  {len(test)} days ({test['date'].min().date()} to {test['date'].max().date()})")

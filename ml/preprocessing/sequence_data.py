"""
Sequence window generation utilities for temporal neural networks.
Preserves strict chronological ordering and isolates test/validation windows.
"""

from typing import Tuple, List
import numpy as np
import pandas as pd


def build_sliding_windows(
    full_df: pd.DataFrame,
    feature_cols: List[str],
    lookback: int,
    split_dates: Tuple[pd.Timestamp, pd.Timestamp]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[pd.Timestamp]]:
    """
    Construct strictly past-only sequences of length `lookback`.
    For a sample predicting day t+1:
    Sequence uses observations [t - lookback + 1, ..., t].
    """
    X_list = []
    y_list = []
    y_anchor_list = []
    date_list = []
    
    start_date, end_date = split_dates
    df = full_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    for i in range(lookback - 1, len(df)):
        cur_date = df.loc[i, "date"]
        # Check if current day t is within the desired split partition
        if start_date <= cur_date <= end_date:
            # Check target validity on day t+1
            if df.loc[i, "target_is_valid"] == 1:
                # Historical window [i - lookback + 1 : i + 1]
                window = df.loc[i - lookback + 1 : i, feature_cols].values
                target = df.loc[i, "target_biogas_next_day_nm3"]
                anchor = df.loc[i, "biogas_today_nm3"]
                
                X_list.append(window)
                y_list.append(target)
                y_anchor_list.append(anchor)
                date_list.append(cur_date)
                
    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_list, dtype=np.float32),
        np.array(y_anchor_list, dtype=np.float32),
        date_list
    )

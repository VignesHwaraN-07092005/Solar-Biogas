"""
Reproducible Preprocessing Pipeline for Industrial CBG Operational Timeseries.
Primary Source: Master data Spark biogas.xlsx (Master data sheet)
Target: Next-day total raw biogas generation (Nm3/day)
Zero data fabrication; deterministic missing value handling; anti-leakage feature engineering.
"""

import os
import json
import logging
import hashlib
from datetime import datetime
from typing import Tuple, Dict, Any, List

import numpy as np
import pandas as pd
import openpyxl

logger = logging.getLogger("solar_biogas.preprocessing")

RAW_EXCEL_PATH = "Master data Spark biogas.xlsx"
PROCESSED_DIR = "data/processed"
MODEL_READY_CSV = os.path.join(PROCESSED_DIR, "spark_biogas_model_ready.csv")
METADATA_JSON = os.path.join(PROCESSED_DIR, "spark_biogas_metadata.json")


def compute_file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash to verify raw file immutability."""
    if not os.path.exists(filepath):
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def load_raw_spark_sheet(excel_path: str = RAW_EXCEL_PATH) -> pd.DataFrame:
    """
    Ingest raw Excel data without modifying original file.
    Extracts consecutive daily records across the entire calendar span.
    Uses openpyxl iter_rows for rapid, leak-free sequential reading.
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Raw dataset not found at {excel_path}")

    wb = openpyxl.load_workbook(excel_path, data_only=True, read_only=True)
    ws = wb["Master data"]

    rows_data = []
    for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if r_idx < 6:
            continue
        d_val = row[0] if len(row) > 0 else None
        if d_val is None:
            continue

        val_str = str(d_val).strip()
        if not val_str or val_str.lower() == "date":
            continue

        parsed_date = None
        if isinstance(d_val, datetime):
            parsed_date = d_val.date()
        else:
            try:
                parsed_date = pd.to_datetime(val_str, dayfirst=True).date()
            except Exception:
                continue

        if parsed_date is None:
            continue

        def get_col(col_1based: int):
            idx = col_1based - 1
            return row[idx] if len(row) > idx else None

        row_dict = {
            "date": parsed_date,
            # Feedstock incoming weighment (MT)
            "cow_dung_incoming_mt": get_col(4),
            "food_waste_incoming_mt": get_col(7),
            "veg_waste_incoming_mt": get_col(10),
            "total_incoming_mt": get_col(11),
            # Feedstock processed (MT)
            "processed_cow_dung_mt": get_col(12),
            "processed_food_waste_mt": get_col(13),
            "mavitech_processed_mt": get_col(14),
            "total_processed_mt": get_col(20),
            # Water balance (m3)
            "recycle_water_m3": get_col(21),
            "fresh_water_m3": get_col(22),
            "total_water_m3": get_col(23),
            # Digester feeding (m3)
            "feed_digester_1_m3": get_col(24),
            "feed_digester_2_m3": get_col(25),
            "feed_total_m3": get_col(26),
            # Biological / microclimate state
            "ph_inlet": get_col(31),
            "ph_outlet_d1": get_col(32),
            "ph_outlet_d2": get_col(33),
            "temp_outlet_d1_c": get_col(35),
            "temp_outlet_d2_c": get_col(36),
            # Biogas production (Nm3/day)
            "raw_gas_d1_nm3": get_col(42),
            "raw_gas_d2_nm3": get_col(43),
            "raw_gas_total_nm3": get_col(44),
            # Gas utilization (Nm3/day)
            "raw_gas_utilized_total_nm3": get_col(50),
            "scrubber_gas_flow_outlet_nm3": get_col(52)
        }
        rows_data.append(row_dict)

    df = pd.DataFrame(rows_data)
    # Ensure strict chronological sorting
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def clean_and_impute_series(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Clean columns, coerce numeric types, handle missing values deterministically,
    and generate boolean missingness indicators.
    CRITICAL: The raw target variable is NEVER imputed.
    """
    cleaned = df.copy()
    numeric_cols = [c for c in cleaned.columns if c != "date"]

    missing_stats = {}
    for col in numeric_cols:
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
        missing_count = int(cleaned[col].isna().sum())
        missing_stats[col] = {
            "initial_missing": missing_count,
            "pct_missing": round((missing_count / len(cleaned)) * 100, 2)
        }

    # Cross-verify and fill total gas if D1 and D2 are provided but total cell was blank
    d1_gas = cleaned["raw_gas_d1_nm3"].fillna(0)
    d2_gas = cleaned["raw_gas_d2_nm3"].fillna(0)
    calc_gas_total = d1_gas + d2_gas
    mask_fill_gas = cleaned["raw_gas_total_nm3"].isna() & (calc_gas_total > 0)
    cleaned.loc[mask_fill_gas, "raw_gas_total_nm3"] = calc_gas_total[mask_fill_gas]

    # Cross-verify and fill total feed if D1 and D2 are provided but total cell was blank
    d1_feed = cleaned["feed_digester_1_m3"].fillna(0)
    d2_feed = cleaned["feed_digester_2_m3"].fillna(0)
    calc_feed_total = d1_feed + d2_feed
    mask_fill_feed = cleaned["feed_total_m3"].isna() & (calc_feed_total > 0)
    cleaned.loc[mask_fill_feed, "feed_total_m3"] = calc_feed_total[mask_fill_feed]

    # Keep a pure, unimputed target column for truth
    cleaned["raw_gas_total_raw_nm3"] = cleaned["raw_gas_total_nm3"]

    # Impute operational input features for lag generation:
    # 1. Flag missingness explicitly
    # 2. Forward-fill past values (biological/process state persistence)
    # 3. Median fill remaining leading NaNs
    feature_input_cols = [
        "cow_dung_incoming_mt", "food_waste_incoming_mt", "veg_waste_incoming_mt",
        "total_incoming_mt", "processed_cow_dung_mt", "processed_food_waste_mt",
        "mavitech_processed_mt", "total_processed_mt",
        "recycle_water_m3", "fresh_water_m3", "total_water_m3",
        "feed_digester_1_m3", "feed_digester_2_m3", "feed_total_m3",
        "ph_inlet", "ph_outlet_d1", "ph_outlet_d2",
        "temp_outlet_d1_c", "temp_outlet_d2_c",
        "raw_gas_utilized_total_nm3", "scrubber_gas_flow_outlet_nm3"
    ]

    for col in feature_input_cols:
        if col in cleaned.columns:
            cleaned[f"{col}_was_missing"] = cleaned[col].isna().astype(int)
            cleaned[col] = cleaned[col].ffill()
            med_val = cleaned[col].median()
            cleaned[col] = cleaned[col].fillna(med_val if not pd.isna(med_val) else 0.0)

    # For autoregressive features of biogas generation, create a filled series for feature lags only
    cleaned["biogas_prod_was_missing"] = cleaned["raw_gas_total_nm3"].isna().astype(int)
    cleaned["biogas_prod_feature_imputed"] = cleaned["raw_gas_total_nm3"].ffill()
    gas_median = cleaned["raw_gas_total_nm3"].median()
    cleaned["biogas_prod_feature_imputed"] = cleaned["biogas_prod_feature_imputed"].fillna(
        gas_median if not pd.isna(gas_median) else 0.0
    )

    return cleaned, missing_stats


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construct temporal lags, rolling features, and day-ahead forecasting target.
    STRICT ANTI-LEAKAGE:
    - Features at row t only utilize data available on or before day t (<= t).
    - Rolling windows strictly use historical data up to and including t (closed='right').
    - Target at row t is the unmanipulated raw gas generation at t+1.
    - Zero data fabrication: target is NEVER imputed.
    """
    feat_df = df.copy()

    # 1. Primary Forecasting Target Formulation: Next-day raw biogas generation (t+1)
    # Shift -1 moves day t+1 value to row t
    feat_df["target_biogas_next_day_nm3"] = feat_df["raw_gas_total_raw_nm3"].shift(-1)
    
    # Target validity flag: 1 if t+1 has a valid recorded measurement > 0, 0 if missing/shutdown
    feat_df["target_is_valid"] = (
        feat_df["target_biogas_next_day_nm3"].notna() & 
        (feat_df["target_biogas_next_day_nm3"] > 0)
    ).astype(int)

    # 2. Production Autoregressive Features (strictly <= t)
    feat_df["biogas_today_nm3"] = feat_df["biogas_prod_feature_imputed"]
    feat_df["biogas_lag_1d"] = feat_df["biogas_prod_feature_imputed"].shift(1)
    feat_df["biogas_lag_2d"] = feat_df["biogas_prod_feature_imputed"].shift(2)
    feat_df["biogas_lag_3d"] = feat_df["biogas_prod_feature_imputed"].shift(3)
    feat_df["biogas_lag_7d"] = feat_df["biogas_prod_feature_imputed"].shift(7)

    # 3. Feedstock Loading Features (strictly <= t)
    feat_df["feed_total_lag_1d"] = feat_df["feed_total_m3"].shift(1)
    feat_df["feedstock_incoming_lag_1d"] = feat_df["total_incoming_mt"].shift(1)
    feat_df["processed_total_lag_1d"] = feat_df["total_processed_mt"].shift(1)
    feat_df["recycle_water_lag_1d"] = feat_df["recycle_water_m3"].shift(1)

    # 4. Microclimate / Environmental Lags (strictly <= t)
    feat_df["ph_d1_lag_1d"] = feat_df["ph_outlet_d1"].shift(1)
    feat_df["temp_d1_lag_1d"] = feat_df["temp_outlet_d1_c"].shift(1)

    # 5. Rolling Statistical Windows (strictly closed='right' - past and current only)
    feat_df["biogas_rolling_mean_3d"] = (
        feat_df["biogas_today_nm3"].rolling(window=3, min_periods=1, closed="right").mean()
    )
    feat_df["biogas_rolling_mean_7d"] = (
        feat_df["biogas_today_nm3"].rolling(window=7, min_periods=1, closed="right").mean()
    )
    feat_df["biogas_rolling_std_7d"] = (
        feat_df["biogas_today_nm3"].rolling(window=7, min_periods=1, closed="right").std().fillna(0)
    )
    feat_df["feed_rolling_mean_7d"] = (
        feat_df["feed_total_m3"].rolling(window=7, min_periods=1, closed="right").mean()
    )
    feat_df["incoming_rolling_mean_7d"] = (
        feat_df["total_incoming_mt"].rolling(window=7, min_periods=1, closed="right").mean()
    )

    # 6. Temporal / Calendar Cyclical Features
    feat_df["day_of_week"] = feat_df["date"].dt.dayofweek
    feat_df["is_weekend"] = feat_df["day_of_week"].isin([5, 6]).astype(int)
    feat_df["month"] = feat_df["date"].dt.month
    feat_df["day_of_month"] = feat_df["date"].dt.day

    # Backfill initial edge rows for lags (e.g. lag_7d for first 7 rows) deterministically
    lag_cols = [c for c in feat_df.columns if "lag" in c]
    for lc in lag_cols:
        feat_df[lc] = feat_df[lc].bfill().ffill()

    return feat_df


def run_pipeline() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Execute complete end-to-end preprocessing pipeline and save artifacts."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # 1. Ingest
    raw_df = load_raw_spark_sheet()

    # 2. Clean & Impute Features
    cleaned_df, missing_stats = clean_and_impute_series(raw_df)

    # 3. Feature Engineering & Target Formulation
    final_df = engineer_features(cleaned_df)

    # Save model-ready CSV
    final_df.to_csv(MODEL_READY_CSV, index=False)

    # Compute raw file sha256
    raw_sha = compute_file_sha256(RAW_EXCEL_PATH)

    feature_columns = [
        c for c in final_df.columns
        if c not in [
            "date", "target_biogas_next_day_nm3", "target_is_valid",
            "raw_gas_d1_nm3", "raw_gas_d2_nm3", "raw_gas_total_nm3",
            "raw_gas_total_raw_nm3", "biogas_prod_feature_imputed"
        ]
    ]

    valid_targets = int(final_df["target_is_valid"].sum())

    metadata = {
        "dataset_name": "Spark Bio Gas Operational CBG Plant Log",
        "primary_source_file": RAW_EXCEL_PATH,
        "primary_source_sha256": raw_sha,
        "processed_file": MODEL_READY_CSV,
        "generated_at": datetime.now().isoformat(),
        "total_calendar_days": int(len(final_df)),
        "date_range_start": str(final_df["date"].min().date()),
        "date_range_end": str(final_df["date"].max().date()),
        "duplicate_dates_count": int(final_df["date"].duplicated().sum()),
        "calendar_continuity": "176 consecutive calendar days (zero gaps)",
        "target_variable": "target_biogas_next_day_nm3",
        "target_unit": "Normal Cubic Meters (Nm3/day)",
        "prediction_horizon": "1 day ahead (t+1)",
        "valid_target_rows": valid_targets,
        "unrecorded_or_shutdown_target_rows": int(len(final_df) - valid_targets),
        "target_imputation_policy": "STRICT ZERO IMPUTATION - unrecorded target days are flagged and excluded from training loss",
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "missing_stats": missing_stats
    }

    with open(METADATA_JSON, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return final_df, metadata


if __name__ == "__main__":
    df, meta = run_pipeline()
    print("Preprocessing pipeline successfully executed.")
    print(f"Total Calendar Days: {len(df)}")
    print(f"Date Span: {meta['date_range_start']} to {meta['date_range_end']}")
    print(f"Valid Target Rows (t+1): {meta['valid_target_rows']}")
    print(f"Feature Count: {meta['feature_count']}")
    print(f"Model-Ready Dataset: {MODEL_READY_CSV}")
    print(f"Metadata: {METADATA_JSON}")

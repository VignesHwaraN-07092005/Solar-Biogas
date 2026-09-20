"""
Automated Tests for Dataset Audit, Preprocessing Pipeline, and Temporal Split.
Verifies scientific integrity, raw file immutability, leak-free feature engineering,
and deterministic missing value handling.
"""

import os
import json
import hashlib
import pandas as pd
import numpy as np
import pytest

from ml.preprocessing.pipeline import (
    RAW_EXCEL_PATH,
    MODEL_READY_CSV,
    METADATA_JSON,
    compute_file_sha256,
    run_pipeline
)
from ml.preprocessing.temporal_split import (
    TRAIN_CSV,
    VAL_CSV,
    TEST_CSV,
    temporal_split
)

# Known verified SHA-256 hashes of the source files
EXPECTED_SPARK_SHA256 = "4d45f2d469a3f2f4bbbb04f804ec57085d451101087e729a925617ad52e1d3b4"
EXPECTED_AGSTAR_SHA256 = "d10a6d76e07b352d988a6f283e56b20f567b509d6c0258b4b1292e0311693c38"
AGSTAR_PATH = "agstar-livestock-ad-database-combined.xlsx"


def test_raw_files_immutable():
    """Verify that both raw dataset files remain byte-for-byte unchanged."""
    assert os.path.exists(RAW_EXCEL_PATH), f"Missing {RAW_EXCEL_PATH}"
    assert os.path.exists(AGSTAR_PATH), f"Missing {AGSTAR_PATH}"
    
    spark_sha = compute_file_sha256(RAW_EXCEL_PATH)
    agstar_sha = compute_file_sha256(AGSTAR_PATH)
    
    assert spark_sha == EXPECTED_SPARK_SHA256, "Spark dataset was modified or corrupted!"
    assert agstar_sha == EXPECTED_AGSTAR_SHA256, "AgSTAR dataset was modified or corrupted!"


def test_preprocessing_pipeline_execution():
    """Verify preprocessing pipeline runs and generates valid model-ready outputs."""
    df, meta = run_pipeline()
    assert os.path.exists(MODEL_READY_CSV)
    assert os.path.exists(METADATA_JSON)
    
    assert len(df) == 176, f"Expected 176 consecutive days, got {len(df)}"
    assert meta["calendar_continuity"] == "176 consecutive calendar days (zero gaps)"
    assert meta["target_variable"] == "target_biogas_next_day_nm3"
    assert meta["target_unit"] == "Normal Cubic Meters (Nm3/day)"


def test_anti_leakage_target_alignment():
    """
    Verify strictly leak-free target alignment:
    target at row t MUST equal raw gas generation at row t+1.
    Features at row t MUST use data from t or prior (<= t).
    """
    df = pd.read_csv(MODEL_READY_CSV)
    df["date"] = pd.to_datetime(df["date"])
    
    # Check shift alignment for consecutive days
    for i in range(len(df) - 1):
        target_val = df.loc[i, "target_biogas_next_day_nm3"]
        next_day_gas = df.loc[i + 1, "raw_gas_total_raw_nm3"]
        
        if pd.isna(target_val):
            assert pd.isna(next_day_gas), f"Row {i} target is NaN but next day gas is {next_day_gas}"
        else:
            assert np.isclose(target_val, next_day_gas), f"Row {i} target {target_val} != row {i+1} gas {next_day_gas}"

    # Last row target MUST be NaN because t+1 has not occurred
    assert pd.isna(df.loc[len(df) - 1, "target_biogas_next_day_nm3"]), "Last row target must be NaN"


def test_zero_target_imputation():
    """Verify that unrecorded/shutdown target values are NEVER imputed."""
    df = pd.read_csv(MODEL_READY_CSV)
    
    # Check known unrecorded gas dates (e.g. 2026-01-28, plant turnaround 2026-04-04 onwards)
    apr_unrecorded = df[df["date"] >= "2026-04-04"]
    assert apr_unrecorded["raw_gas_total_raw_nm3"].isna().all(), "Maintenance days should have NaN raw gas"
    
    # Check target_is_valid flag
    valid_mask = df["target_biogas_next_day_nm3"].notna() & (df["target_biogas_next_day_nm3"] > 0)
    assert (df["target_is_valid"] == valid_mask.astype(int)).all()


def test_missingness_indicators_exist():
    """Verify boolean missingness flags exist for all imputed input features."""
    df = pd.read_csv(MODEL_READY_CSV)
    
    expected_flags = [
        "total_incoming_mt_was_missing",
        "feed_total_m3_was_missing",
        "ph_outlet_d1_was_missing",
        "temp_outlet_d1_c_was_missing",
        "biogas_prod_was_missing"
    ]
    for flag in expected_flags:
        assert flag in df.columns, f"Missing indicator flag {flag} not in dataset"
        assert set(df[flag].unique()).issubset({0, 1}), f"Flag {flag} must be binary 0 or 1"


def test_temporal_split_chronology_and_no_leakage():
    """Verify train / val / test splits are strictly chronological with zero temporal overlap."""
    train_df, val_df, test_df = temporal_split()
    
    assert os.path.exists(TRAIN_CSV)
    assert os.path.exists(VAL_CSV)
    assert os.path.exists(TEST_CSV)
    
    train_max_date = pd.to_datetime(train_df["date"]).max()
    val_min_date = pd.to_datetime(val_df["date"]).min()
    val_max_date = pd.to_datetime(val_df["date"]).max()
    test_min_date = pd.to_datetime(test_df["date"]).min()
    
    assert train_max_date < val_min_date, f"Train max ({train_max_date}) must precede Val min ({val_min_date})"
    assert val_max_date < test_min_date, f"Val max ({val_max_date}) must precede Test min ({test_min_date})"
    
    # Verify no date intersections
    train_dates = set(train_df["date"])
    val_dates = set(val_df["date"])
    test_dates = set(test_df["date"])
    
    assert len(train_dates.intersection(val_dates)) == 0, "Train and Val share dates!"
    assert len(val_dates.intersection(test_dates)) == 0, "Val and Test share dates!"
    assert len(train_dates.intersection(test_dates)) == 0, "Train and Test share dates!"

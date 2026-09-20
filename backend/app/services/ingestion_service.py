import re
import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd

from backend.app.schemas.ingestion import (
    ColumnMappingDetail,
    ColumnStatistics,
    ModelEligibility,
    IngestionReportResponse
)

TIMESTAMP_ALIASES = [
    "timestamp", "date", "datetime", "reading_time", "recorded_at", "time", "record_time"
]

# NOTE: 'row' is explicitly excluded from timestamp aliases.

ALIAS_DICTIONARY = {
    "biogas_production": [
        "biogas", "gas", "gas_production", "biogas_production", "gas_output",
        "biogas_nm3", "methane_gas_flow", "yield", "daily_biogas_output",
        "biogas_today_nm3", "biogas_production_m3_day", "gas_flow", "daily_biogas"
    ],
    "temperature": [
        "temp", "temperature", "temp_c", "temp_f", "reactor_temp",
        "outlet_temperature", "digester_temperature", "temp_outlet_d1_c",
        "reactor_temperature", "outlet_temp", "digester_temp", "slurry_temp"
    ],
    "ph": [
        "ph", "ph_value", "acidity", "reactor_ph", "outlet_ph",
        "ph_outlet_d1", "digester_ph", "reactor_acidity"
    ],
    "pressure": [
        "pressure", "gas_pressure", "pressure_bar", "pressure_kpa",
        "pressure_psi", "digester_pressure", "biogas_pressure"
    ],
    "feedstock": [
        "feed", "feedstock", "feed_mt", "feed_kg", "organic_feed",
        "loading", "input_waste", "organic_waste_input", "feed_rate",
        "feedstock_mass_kg", "total_incoming_mt", "total_processed_mt", "feed_total_m3"
    ],
    "methane": [
        "methane", "methane_percent", "ch4", "methane_concentration", "methane_pct"
    ],
    "recycle_water": [
        "recycle_water_m3", "recycle_water", "water_recycle", "recycled_water"
    ],
    "feed_total_m3_was_missing": [
        "feed_total_m3_was_missing"
    ],
    "ph_outlet_d1_was_missing": [
        "ph_outlet_d1_was_missing"
    ]
}

NINE_GRU_FEATURES = [
    "biogas_today_nm3",
    "total_incoming_mt",
    "total_processed_mt",
    "feed_total_m3",
    "temp_outlet_d1_c",
    "ph_outlet_d1",
    "recycle_water_m3",
    "feed_total_m3_was_missing",
    "ph_outlet_d1_was_missing"
]

def normalize_column_name(col: str) -> str:
    s = str(col).strip().lower()
    s = s.replace("°c", "_deg_c").replace("°f", "_deg_f").replace("°", "_deg_")
    s = s.replace("³", "3").replace("/", "_per_").replace("%", "_pct_")
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s

class IngestionService:
    def analyze_dataset(self, filename: str, raw_rows: List[Dict[str, Any]]) -> Tuple[IngestionReportResponse, List[Dict[str, Any]]]:
        if not raw_rows:
            return IngestionReportResponse(
                filename=filename,
                total_rows=0,
                total_columns=0,
                recognized_columns_count=0,
                extra_columns_count=0,
                unmapped_columns_count=0,
                timestamp_status="Empty file provided"
            ), []

        df = pd.DataFrame(raw_rows)
        orig_cols = list(df.columns)
        total_rows = len(df)
        total_cols = len(orig_cols)

        # 1. Map columns and units
        mappings: List[ColumnMappingDetail] = []
        mapped_col_map: Dict[str, str] = {}  # orig_col -> semantic_concept
        applied_conversions: Dict[str, str] = {}  # orig_col -> conversion_note

        timestamp_col = None
        timestamp_status = "Valid"

        for col in orig_cols:
            norm = normalize_column_name(col)
            
            # Explicit rule: 'row' is NOT a timestamp
            if norm != "row" and any(norm == t or norm.startswith(t + "_") or norm.endswith("_" + t) for t in TIMESTAMP_ALIASES):
                if timestamp_col is None:
                    try:
                        sample_vals = df[col].dropna().head(10).astype(str)
                        if len(sample_vals) > 0 and all(pd.to_datetime(sample_vals, errors='coerce').notna()):
                            timestamp_col = col
                            mappings.append(ColumnMappingDetail(
                                original_name=col,
                                normalized_name=norm,
                                semantic_concept="TIMESTAMP",
                                confidence=0.95
                            ))
                            continue
                    except Exception:
                        pass

            concept = None
            detected_unit = None
            conversion = None
            conf = 0.0

            if norm in NINE_GRU_FEATURES:
                concept = norm
                conf = 1.0
            else:
                best_match = None
                best_len = 0
                best_exact = False
                for grp, aliases in ALIAS_DICTIONARY.items():
                    for a in aliases:
                        if norm == a:
                            best_match = (grp, 0.90)
                            best_len = len(a)
                            best_exact = True
                            break
                        elif not best_exact:
                            if norm.startswith(a + "_") or norm.endswith("_" + a) or f"_{a}_" in f"_{norm}_" or a in norm:
                                if len(a) > best_len:
                                    best_match = (grp, 0.80 if len(a) > 3 else 0.65)
                                    best_len = len(a)
                    if best_exact:
                        break
                if best_match:
                    concept, conf = best_match

            # Unit detection & explicit conversions
            if concept == "temperature":
                if "_deg_f" in norm or "temp_f" in norm:
                    detected_unit = "°F"
                    conversion = "Converted: °F -> °C"
                elif "_deg_c" in norm or "temp_c" in norm:
                    detected_unit = "°C"
                else:
                    detected_unit = "°C (inferred)"
            elif concept == "pressure":
                if "kpa" in norm:
                    detected_unit = "kPa"
                    conversion = "Converted: kPa -> bar"
                elif "psi" in norm:
                    detected_unit = "psi"
                    conversion = "Converted: psi -> bar"
                elif "bar" in norm:
                    detected_unit = "bar"
                else:
                    detected_unit = "bar (inferred)"
            elif concept == "feedstock":
                if "_kg" in norm:
                    detected_unit = "kg"
                    conversion = "Converted: kg -> MT"
                elif "_mt" in norm or "tonne" in norm:
                    detected_unit = "MT"
                elif "_m3" in norm:
                    detected_unit = "m³"
            elif concept == "biogas_production":
                if "nm3" in norm or "nm3_per_day" in norm:
                    detected_unit = "Nm³/day"
                elif "m3" in norm:
                    detected_unit = "m³/day"

            if concept == "ph":
                numeric_vals = pd.to_numeric(df[col], errors='coerce').dropna()
                if len(numeric_vals) > 0:
                    val_mean = numeric_vals.mean()
                    if val_mean < 0.0 or val_mean > 14.0:
                        detected_unit = "Unit ambiguous / Out of physical range"
                        conversion = "Flagged: pH outside [0, 14]"

            if concept:
                mapped_col_map[col] = concept
                if conversion:
                    applied_conversions[col] = conversion

            mappings.append(ColumnMappingDetail(
                original_name=col,
                normalized_name=norm,
                semantic_concept=concept,
                detected_unit=detected_unit,
                conversion_applied=conversion,
                confidence=conf
            ))

        # 2. Time series analysis
        time_range_start = None
        time_range_end = None
        sampling_interval = "Unknown"
        duplicate_timestamps = 0
        missing_timestamps = 0

        if timestamp_col:
            try:
                df['_parsed_ts'] = pd.to_datetime(df[timestamp_col], errors='coerce')
                valid_ts = df['_parsed_ts'].dropna()
                if len(valid_ts) > 0:
                    df = df.sort_values(by='_parsed_ts').reset_index(drop=True)
                    time_range_start = valid_ts.min().isoformat()
                    time_range_end = valid_ts.max().isoformat()
                    duplicate_timestamps = int(df['_parsed_ts'].duplicated().sum())

                    if len(valid_ts) >= 2:
                        diffs = df['_parsed_ts'].diff().dropna()
                        median_diff_sec = diffs.dt.total_seconds().median()
                        if 80000 <= median_diff_sec <= 90000:
                            sampling_interval = "Daily (1.0 days)"
                        elif 3500 <= median_diff_sec <= 3700:
                            sampling_interval = "Hourly (1.0 hours)"
                        else:
                            sampling_interval = f"Irregular ({round(median_diff_sec / 3600.0, 1)} hrs)"
            except Exception as e:
                timestamp_status = f"Timestamp column parsing error: {e}"
        else:
            timestamp_status = "Timestamp column ambiguous or not detected"

        # 3. Numeric statistics across ALL numeric columns (mapped and extra)
        statistics: List[ColumnStatistics] = []
        for col in orig_cols:
            num_series = pd.to_numeric(df[col], errors='coerce')
            valid_num = num_series.dropna()
            concept = mapped_col_map.get(col)
            if len(valid_num) > 0:
                statistics.append(ColumnStatistics(
                    column_name=col,
                    semantic_concept=concept,
                    count=int(len(valid_num)),
                    null_count=int(len(df) - len(valid_num)),
                    min=round(float(valid_num.min()), 3),
                    max=round(float(valid_num.max()), 3),
                    mean=round(float(valid_num.mean()), 3),
                    median=round(float(valid_num.median()), 3),
                    std=round(float(valid_num.std()), 3) if len(valid_num) > 1 else 0.0
                ))

        # 4. Standardized mapped dataset construction
        standardized_rows: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            std_row: Dict[str, Any] = {}
            for col in orig_cols:
                v = row[col]
                if pd.isna(v):
                    std_row[col] = None
                elif hasattr(v, "item"):
                    std_row[col] = v.item()
                else:
                    std_row[col] = v

            if timestamp_col and pd.notna(row.get('_parsed_ts')):
                std_row['timestamp'] = row['_parsed_ts'].isoformat()
            else:
                std_row['timestamp'] = str(row.get(timestamp_col, '')) if timestamp_col else ''

            for col, concept in mapped_col_map.items():
                val = pd.to_numeric(row.get(col), errors='coerce')
                if pd.isna(val):
                    continue
                c_note = applied_conversions.get(col, '')
                if "°F -> °C" in c_note:
                    val = (val - 32.0) * 5.0 / 9.0
                elif "kPa -> bar" in c_note:
                    val = val / 100.0
                elif "psi -> bar" in c_note:
                    val = val / 14.5038
                elif "kg -> MT" in c_note:
                    val = val / 1000.0

                if concept == "biogas_production" or concept == "biogas_today_nm3":
                    std_row['biogas_today_nm3'] = float(val)
                    std_row['biogas_production_m3_day'] = float(val)
                elif concept == "temperature" or concept == "temp_outlet_d1_c":
                    std_row['temp_outlet_d1_c'] = float(val)
                    std_row['temperature_c'] = float(val)
                elif concept == "ph" or concept == "ph_outlet_d1":
                    std_row['ph_outlet_d1'] = float(val)
                    std_row['ph'] = float(val)
                elif concept == "pressure":
                    std_row['pressure_bar'] = float(val)
                elif concept == "feedstock":
                    std_row['feedstock_mass_kg'] = float(val * 1000.0) if "kg -> MT" in c_note else float(val)
                    std_row['total_incoming_mt'] = float(val)
                    std_row['total_processed_mt'] = float(val)
                    std_row['feed_total_m3'] = float(val * 1.2)
                elif concept in NINE_GRU_FEATURES:
                    std_row[concept] = float(val)

            standardized_rows.append(std_row)

        # 5. Model Eligibility Assessment
        # Distinct separation: DATA ANALYSIS vs FORECAST ELIGIBILITY vs DOMAIN VALIDATION
        model_eligibility: Dict[str, ModelEligibility] = {}
        hist_len = len(df)

        # Persistence (requires BIOGAS_PRODUCTION, history >= 1)
        has_biogas = any(c == "biogas_production" or c == "biogas_today_nm3" for c in mapped_col_map.values())
        p_missing = [] if has_biogas else ["biogas_production"]
        p_eligible = has_biogas and hist_len >= 1
        model_eligibility["Persistence"] = ModelEligibility(
            model_name="Persistence",
            eligible=p_eligible,
            required_history=1,
            available_history=hist_len,
            missing_features=p_missing,
            reasons=(["Sufficient biogas observations available"] if p_eligible else ["Missing biogas production history" if not has_biogas else "History < 1"])
        )

        # EMA-0.90 (requires BIOGAS_PRODUCTION, history >= 3)
        ema_missing = [] if has_biogas else ["biogas_production"]
        ema_eligible = has_biogas and hist_len >= 3
        model_eligibility["EMA-0.90"] = ModelEligibility(
            model_name="EMA-0.90",
            eligible=ema_eligible,
            required_history=3,
            available_history=hist_len,
            missing_features=ema_missing,
            reasons=(["Sufficient 3-day biogas observations available"] if ema_eligible else ["Missing biogas production history" if not has_biogas else "History < 3"])
        )

        # GRU-14d Residual (requires all 9 features, history >= 14)
        gru_missing = []
        for feat in NINE_GRU_FEATURES:
            feat_present = any(col == feat or mapped_col_map.get(col) == feat for col in orig_cols)
            if not feat_present:
                gru_missing.append(feat)

        gru_eligible = (len(gru_missing) == 0 and hist_len >= 14)
        gru_reasons = []
        if len(gru_missing) > 0:
            gru_reasons.append(f"Missing {len(gru_missing)} required model feature(s): {', '.join(gru_missing)}")
        if hist_len < 14:
            gru_reasons.append(f"Insufficient history: minimum 14 consecutive observations required (got {hist_len})")
        if gru_eligible:
            gru_reasons.append("All 9 input features and >= 14 sequence observations confirmed.")

        model_eligibility["GRU-14d Residual"] = ModelEligibility(
            model_name="GRU-14d Residual",
            eligible=gru_eligible,
            required_history=14,
            available_history=hist_len,
            missing_features=gru_missing,
            reasons=gru_reasons
        )

        # XCO-Net: strictly 7 timesteps required (Authoritative lookback)
        xco_missing = list(gru_missing)
        xco_eligible = (len(xco_missing) == 0 and hist_len >= 7)
        xco_reasons = []
        if len(xco_missing) > 0:
            xco_reasons.append(f"Missing {len(xco_missing)} required model feature(s): {', '.join(xco_missing)}")
        if hist_len < 7:
            xco_reasons.append(f"Insufficient history: minimum 7 observations required (got {hist_len})")
        if xco_eligible:
            xco_reasons.append("All 9 input features and >= 7 sequence observations confirmed.")

        model_eligibility["XCO-Net"] = ModelEligibility(
            model_name="XCO-Net",
            eligible=xco_eligible,
            required_history=7,
            available_history=hist_len,
            missing_features=xco_missing,
            reasons=xco_reasons
        )

        recognized_count = sum(1 for m in mappings if m.semantic_concept is not None)
        unmapped_count = total_cols - recognized_count

        report = IngestionReportResponse(
            filename=filename,
            total_rows=total_rows,
            total_columns=total_cols,
            recognized_columns_count=recognized_count,
            extra_columns_count=unmapped_count,
            unmapped_columns_count=unmapped_count,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            sampling_interval=sampling_interval,
            duplicate_timestamps=duplicate_timestamps,
            missing_timestamps=missing_timestamps,
            timestamp_status=timestamp_status,
            mappings=mappings,
            statistics=statistics,
            model_eligibility=model_eligibility,
            data_source="USER_UPLOAD",
            domain_valid=False,
            domain_status="UNVALIDATED USER DATASET",
            domain_note="Uploaded dataset has not been validated against the operational training domain."
        )

        return report, standardized_rows

ingestion_service = IngestionService()

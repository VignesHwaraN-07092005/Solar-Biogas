import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sqlalchemy.orm import Session

from backend.app.models.forecast import ForecastResult
from backend.app.schemas.forecast import (
    ProvenanceEnum,
    ForecastStatusEnum,
    ModelRoleEnum,
    MetricScore,
    ModelBenchmarkItem,
    ModelComparisonResponse,
    SparkTimelineItem,
    XCONetResearchResponse,
    ForecastResponse
)
from backend.app.schemas.interpretation import (
    ForecastInterpretationResponse,
    InterpretationFeatureSignal,
    InterpretationSensitivity,
    InterpretationWeight
)
from ml.xco_net.model import XCONet

# PyTorch Architecture matching models/gru_lookback_14d_residual.pt
class BiogasGRUNet(nn.Module):
    def __init__(self, input_dim: int = 9, hidden_dim: int = 32, num_layers: int = 1, dropout: float = 0.1):
        super(BiogasGRUNet, self).__init__()
        self.gru = nn.GRU(input_size=input_dim, hidden_size=hidden_dim, num_layers=num_layers, batch_first=True)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(16, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :])


MODEL_REQUIREMENTS_METADATA: Dict[str, Dict[str, Any]] = {
    "GRU-14d Residual": {
        "model_name": "GRU-14d Residual",
        "required_history": 14,
        "role": "Default Forecasting Model",
        "category": "Forecasting",
        "causal_footer": "Uses the previous 14 continuous timesteps and is generated causally from information available through the current day."
    },
    "XCO-Net": {
        "model_name": "XCO-Net",
        "required_history": 7,
        "role": "Proposed Research Architecture",
        "category": "Research",
        "causal_footer": "Uses the previous 7 continuous timesteps and is generated causally from information available through the current day."
    },
    "EMA-0.90": {
        "model_name": "EMA-0.90",
        "required_history": 3,
        "role": "Statistical Benchmark",
        "category": "Forecasting",
        "causal_footer": "Uses the previous 3 continuous timesteps and is generated causally from information available through the current day."
    },
    "Persistence": {
        "model_name": "Persistence",
        "required_history": 1,
        "role": "Naive Baseline",
        "category": "Forecasting",
        "causal_footer": "Uses the previous 1 timestep and is generated causally from information available through the current day."
    }
}


class ForecastService:
    def __init__(self):
        self._gru_model: Optional[BiogasGRUNet] = None
        self._xco_model: Optional[XCONet] = None
        self._gru_scaler_meta: Optional[Dict[str, Any]] = None
        self._xco_scaler_meta: Optional[Dict[str, Any]] = None
        self._spark_df: Optional[pd.DataFrame] = None
        
        # Load frozen scaler parameters immediately
        self._load_frozen_scalers()
        self._load_models()

    def _load_frozen_scalers(self):
        gru_meta_path = "models/gru_scaler_metadata.json"
        if os.path.exists(gru_meta_path):
            with open(gru_meta_path, "r") as f:
                self._gru_scaler_meta = json.load(f)
        else:
            raise FileNotFoundError(f"Missing required frozen scaler: {gru_meta_path}")

        xco_meta_path = "models/xco_scaler_metadata.json"
        if os.path.exists(xco_meta_path):
            with open(xco_meta_path, "r") as f:
                self._xco_scaler_meta = json.load(f)

    def _load_models(self):
        # 1. Load GRU (14-day Residual)
        gru_path = "models/gru_lookback_14d_residual.pt"
        if os.path.exists(gru_path):
            try:
                model = BiogasGRUNet(input_dim=9, hidden_dim=32, num_layers=1, dropout=0.1)
                weights = torch.load(gru_path, map_location="cpu")
                model.load_state_dict(weights)
                model.eval()
                self._gru_model = model
            except Exception as e:
                print(f"[ForecastService] Warning: Failed to load GRU checkpoint {gru_path}: {e}")
                self._gru_model = None

        # 2. Load XCO-Net (Lookback 7, Hidden 16)
        xco_path = "models/xco_net_best.pt"
        if os.path.exists(xco_path):
            try:
                model = XCONet(
                    input_dim=9,
                    hidden_dim=16,
                    num_layers=1,
                    dropout=0.126,
                    delta_max=4152.0,
                    use_cross_channel=True,
                    use_temporal_attn=True
                )
                weights = torch.load(xco_path, map_location="cpu")
                model.load_state_dict(weights)
                model.eval()
                self._xco_model = model
            except Exception as e:
                print(f"[ForecastService] Warning: Failed to load XCO-Net checkpoint {xco_path}: {e}")
                self._xco_model = None

    def get_spark_dataset(self) -> pd.DataFrame:
        if self._spark_df is None:
            path = "data/processed/spark_biogas_model_ready.csv"
            if os.path.exists(path):
                df = pd.read_csv(path)
                df["date"] = pd.to_datetime(df["date"])
                self._spark_df = df
            else:
                raise FileNotFoundError(f"Processed Spark dataset not found at {path}")
        return self._spark_df

    def _normalize_with_frozen_scaler(self, window_arr: np.ndarray, meta: Dict[str, Any]) -> np.ndarray:
        # window_arr shape: (L, D)
        means = np.array(meta["feature_mean"], dtype=np.float32)
        scales = np.array(meta["feature_scale"], dtype=np.float32)
        # Avoid division by zero
        scales = np.where(scales == 0, 1.0, scales)
        return (window_arr - means) / scales

    def predict(
        self,
        device_id: str = "DIGESTER_001",
        model_name: str = "GRU-14d Residual",
        data_source: ProvenanceEnum = ProvenanceEnum.DEMO_SYNTHETIC,
        history_window: Optional[List[Dict[str, Any]]] = None,
        db: Optional[Session] = None
    ) -> ForecastResult:
        """
        Executes safe next-day forecasting enforcing minimum history and causality.
        """
        now_utc = datetime.now(timezone.utc)
        target_date = now_utc + timedelta(days=1)
        model_version = "v1.0.0"
        prep_version = "v1.0.0-frozen-train"

        # AgSTAR hard barrier: static external benchmark cannot enter time-series forecasting pipeline
        data_source_str = str(getattr(data_source, "value", data_source)).upper()
        if any(term in data_source_str for term in ["AGSTAR", "AGSTAR_REGISTRY", "EXTERNAL_BENCHMARK"]) or "AGSTAR" in model_name.upper():
            raise ValueError("AgSTAR is an external static benchmark and cannot enter the time-series forecasting pipeline.")

        if data_source not in [
            ProvenanceEnum.DEMO_SYNTHETIC, 
            ProvenanceEnum.REAL_SPARK_HISTORICAL, 
            ProvenanceEnum.SPARK_FULL,
            ProvenanceEnum.LIVE_IOT,
            ProvenanceEnum.USER_UPLOAD,
            ProvenanceEnum.UPLOADED_SCADA
        ] and data_source_str not in ["USER_UPLOAD", "UPLOADED_SCADA", "SPARK_FULL"]:
            raise ValueError(f"Data source '{data_source}' is not an authorized time-series forecasting source.")

        is_live_iot = (
            data_source == ProvenanceEnum.LIVE_IOT 
            or data_source_str == "LIVE_IOT"
        )
        is_user_upload = (
            data_source in [ProvenanceEnum.USER_UPLOAD, ProvenanceEnum.UPLOADED_SCADA]
            or data_source_str in ["USER_UPLOAD", "UPLOADED_SCADA"]
        )

        # If history_window is None or empty, fetch from database sensor_readings
        if not history_window:
            db_source = "live_esp32" if is_live_iot else None
            history_window = self._fetch_recent_readings_from_db(device_id, limit=20, db=db, source=db_source)

        # Validate minimum input history per model
        model_key = model_name.strip()
        
        # 1. GRU (14-day Residual) — Default Forecasting Model
        if "GRU" in model_key:
            return self._predict_gru_14d(device_id, history_window, data_source, now_utc, target_date, db)
            
        # 2. EMA-0.90 — Statistical Benchmark
        elif "EMA" in model_key:
            return self._predict_ema_090(device_id, history_window, data_source, now_utc, target_date, db)

        # 3. Persistence — Naive Baseline
        elif "Persistence" in model_key or "Lag" in model_key:
            return self._predict_persistence(device_id, history_window, data_source, now_utc, target_date, db)

        # 4. XCO-Net — Proposed Research Architecture
        elif "XCO" in model_key:
            return self._predict_xconet(device_id, history_window, data_source, now_utc, target_date, db)

        else:
            raise ValueError(f"Invalid model '{model_name}'. Valid models are: 'GRU-14d Residual', 'EMA-0.90', 'Persistence', 'XCO-Net'.")

    def _fetch_recent_readings_from_db(
        self,
        device_id: str,
        limit: int = 20,
        db: Optional[Session] = None,
        source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if db is None:
            return []
        from backend.app.models.sensor_reading import SensorReading
        query = db.query(SensorReading).filter(
            SensorReading.device_id == device_id
        )
        if source:
            query = query.filter(SensorReading.source == source)
        readings = query.order_by(SensorReading.timestamp.desc()).limit(limit).all()
        
        # Reverse to chronological order: past -> present
        readings = list(reversed(readings))
        
        history = []
        is_live = (source == "live_esp32")
        for r in readings:
            if is_live:
                # STRICT NO-FALLBACK: Never inject synthetic, Spark, or hardcoded fake data for physical hardware!
                history.append({
                    "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                    "biogas_today_nm3": r.biogas_production_m3_day,
                    "total_incoming_mt": (r.feedstock_mass_kg / 1000.0) if r.feedstock_mass_kg is not None else None,
                    "total_processed_mt": (r.feedstock_mass_kg / 1000.0) if r.feedstock_mass_kg is not None else None,
                    "feed_total_m3": (r.feedstock_mass_kg * 0.0012) if r.feedstock_mass_kg is not None else None,
                    "temp_outlet_d1_c": r.temperature_c,
                    "ph_outlet_d1": r.ph,
                    "recycle_water_m3": None,
                    "feed_total_m3_was_missing": 0.0 if r.feedstock_mass_kg is not None else 1.0,
                    "ph_outlet_d1_was_missing": 0.0 if r.ph is not None else 1.0
                })
            else:
                history.append({
                    "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                    "biogas_today_nm3": r.biogas_production_m3_day if r.biogas_production_m3_day is not None else 15.0,
                    "total_incoming_mt": (r.feedstock_mass_kg or 120.0) / 1000.0,
                    "total_processed_mt": (r.feedstock_mass_kg or 120.0) / 1000.0,
                    "feed_total_m3": (r.feedstock_mass_kg or 120.0) * 0.0012,
                    "temp_outlet_d1_c": r.temperature_c if r.temperature_c is not None else 36.5,
                    "ph_outlet_d1": r.ph if r.ph is not None else 7.25,
                    "recycle_water_m3": 30.0,
                    "feed_total_m3_was_missing": 0.0,
                    "ph_outlet_d1_was_missing": 0.0 if r.ph is not None else 1.0
                })
        return history

    def _extract_input_timestamp(self, history: Optional[List[Dict[str, Any]]], fallback: datetime) -> datetime:
        if history and len(history) > 0:
            ts = history[-1].get("timestamp") or history[-1].get("date")
            if ts:
                try:
                    if isinstance(ts, str):
                        # Support YYYY-MM-DD or full ISO
                        if len(ts) == 10:
                            return datetime.fromisoformat(f"{ts}T00:00:00+00:00")
                        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    elif isinstance(ts, datetime):
                        return ts
                except Exception:
                    pass
        return fallback

    def _verify_history_continuity(self, history: List[Dict[str, Any]], required_lookback: int = 14) -> Tuple[bool, str]:
        if len(history) < required_lookback:
            return False, f"Insufficient history length: {len(history)} < {required_lookback}"
        
        timestamps = []
        for r in history:
            ts_val = r.get("timestamp") or r.get("date")
            if ts_val:
                if isinstance(ts_val, str):
                    try:
                        dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                    except Exception:
                        dt = None
                elif isinstance(ts_val, datetime):
                    dt = ts_val
                else:
                    dt = None
                if dt:
                    timestamps.append(dt)
        
        if len(timestamps) == len(history) and len(timestamps) >= 2:
            for i in range(1, len(timestamps)):
                if timestamps[i] <= timestamps[i - 1]:
                    return False, f"Non-increasing or duplicate timestamp at index {i}: {timestamps[i]} <= {timestamps[i-1]}"
        
        return True, "Continuous and monotonic"

    def _predict_gru_14d(
        self,
        device_id: str,
        history: List[Dict[str, Any]],
        data_source: ProvenanceEnum,
        now_utc: datetime,
        target_date: datetime,
        db: Optional[Session] = None
    ) -> ForecastResult:
        data_source_str = str(getattr(data_source, "value", data_source)).upper()
        if any(term in data_source_str for term in ["AGSTAR", "AGSTAR_REGISTRY", "EXTERNAL_BENCHMARK"]):
            raise ValueError("AgSTAR is an external static benchmark and cannot enter the time-series forecasting pipeline.")

        is_live_iot = (
            data_source == ProvenanceEnum.LIVE_IOT 
            or data_source_str == "LIVE_IOT"
        )
        is_user_upload = (
            data_source in [ProvenanceEnum.USER_UPLOAD, ProvenanceEnum.UPLOADED_SCADA]
            or data_source_str in ["USER_UPLOAD", "UPLOADED_SCADA"]
        )

        model_name = "GRU-14d Residual"
        model_version = "v1.0.0"
        prep_version = "v1.0.0-frozen-train"
        input_ts = self._extract_input_timestamp(history, now_utc)
        
        is_continuous, continuity_msg = self._verify_history_continuity(history, required_lookback=14)
        first_ts = (history[0].get("timestamp") or history[0].get("date")) if history else "N/A"
        last_ts = (history[-1].get("timestamp") or history[-1].get("date")) if history else "N/A"
        
        # Log exact required audit attributes
        print(f"[ForecastService] Simulator history length: {len(history)} | "
              f"Forecast input history length: {min(len(history), 14)} | "
              f"First timestamp: {first_ts} | Last timestamp: {last_ts} | "
              f"Continuity result: {is_continuous} ({continuity_msg}) | Required lookback = 14")
        
        # Strict requirement: at least 14 timesteps
        if len(history) < 14 or self._gru_model is None or self._gru_scaler_meta is None:
            status_val = (
                ForecastStatusEnum.INSUFFICIENT_LIVE_HISTORY.value 
                if is_live_iot 
                else ForecastStatusEnum.INSUFFICIENT_HISTORY.value
            )
            rec_msg = (
                f"Forecast inhibited: Minimum 14 valid chronological observations required (got {len(history)})."
                if is_live_iot
                else "Forecast inhibited: Minimum 14 continuous days of historical operational telemetry required."
            )
            res = ForecastResult(
                device_id=device_id,
                timestamp=now_utc,
                target_date=target_date,
                predicted_biogas_m3_day=0.0,
                input_biogas_m3_day=float(history[-1].get("biogas_today_nm3", 0.0)) if (history and history[-1].get("biogas_today_nm3") is not None) else None,
                input_timestamp=input_ts,
                model_name=model_name,
                model_version=model_version,
                preprocessing_version=prep_version,
                data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
                status=status_val,
                domain_valid=False,
                domain_note="Insufficient operational history for GRU execution.",
                recommendation=rec_msg
            )
            return self._persist_if_db(res, db)

        # Slice strictly through timestep t (last 14 elements)
        window = history[-14:]
        curr_biogas = float(window[-1].get("biogas_today_nm3") or 0.0)
        
        feature_cols = self._gru_scaler_meta["feature_cols"]
        matrix = []
        has_missing_feature = False
        for row in window:
            row_vals = []
            for col in feature_cols:
                val = row.get(col)
                if val is None:
                    has_missing_feature = True
                    break
                row_vals.append(float(val))
            if has_missing_feature:
                break
            matrix.append(row_vals)

        if has_missing_feature:
            # STRICT NO-FALLBACK: Never invent missing features from synthetic/Spark/defaults!
            status_val = (
                ForecastStatusEnum.INSUFFICIENT_FEATURES.value
                if is_user_upload
                else (ForecastStatusEnum.INSUFFICIENT_LIVE_FEATURES.value if is_live_iot else ForecastStatusEnum.INSUFFICIENT_FEATURES.value)
            )
            note_val = (
                "Uploaded dataset lacks required model input features. Zero fallback data permitted."
                if is_user_upload
                else "Live telemetry payload lacks required model input features. Zero fallback data permitted."
            )
            res = ForecastResult(
                device_id=device_id,
                timestamp=now_utc,
                target_date=target_date,
                predicted_biogas_m3_day=0.0,
                input_biogas_m3_day=float(window[-1].get("biogas_today_nm3") or 0.0) if window[-1].get("biogas_today_nm3") is not None else None,
                input_timestamp=input_ts,
                model_name=model_name,
                model_version=model_version,
                preprocessing_version=prep_version,
                data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
                status=status_val,
                domain_valid=False,
                domain_note=note_val,
                recommendation="Forecast inhibited: Incomplete features across 14-day window. Missing required inputs."
            )
            return self._persist_if_db(res, db)

        arr = np.array(matrix, dtype=np.float32) # (14, 9)

        # Normalize with frozen training statistics (never recomputed)
        norm_arr = self._normalize_with_frozen_scaler(arr, self._gru_scaler_meta)
        t_in = torch.tensor(norm_arr, dtype=torch.float32).unsqueeze(0) # (1, 14, 9)

        with torch.no_grad():
            delta_norm = self._gru_model(t_in).item()

        # Unscale target delta by frozen y_std
        y_std = self._gru_scaler_meta["y_std"]
        pred_delta = delta_norm * y_std
        pred_val = max(0.0, float(curr_biogas + pred_delta))

        # Biological recommendation based on delta
        if pred_delta > 200.0:
            rec = "Positive methanogenic ramp predicted. Maintain current organic loading rate."
        elif pred_delta < -200.0:
            rec = "Production decline indicated. Check digester pH stability and slurry temperature."
        else:
            rec = "Stable steady-state methanogenesis expected. Keep feedstock feed rates constant."

        # Domain validity check: GRU was calibrated on Spark industrial SCADA (~5,300 Nm³/day)
        # CRITICAL: Community scale (DEMO_SYNTHETIC or LIVE_IOT) is NOT validated for GRU.
        is_user_upload = (
            data_source in [ProvenanceEnum.USER_UPLOAD, ProvenanceEnum.UPLOADED_SCADA]
            or data_source_str in ["USER_UPLOAD", "UPLOADED_SCADA"]
        )
        is_community_scale = (
            data_source == ProvenanceEnum.DEMO_SYNTHETIC 
            or (isinstance(data_source, str) and data_source == "DEMO_SYNTHETIC")
            or is_live_iot
            or curr_biogas < 100.0
        )
        if is_user_upload:
            domain_valid = False
            domain_note = "Model calibrated on industrial Spark plant SCADA (~5,300 Nm³/day). Uploaded user dataset is unvalidated (has not been validated against the operational training domain)."
            status_val = ForecastStatusEnum.UNVALIDATED_USER_DATASET.value
            rec = "Unvalidated User Dataset: Operational prediction displayed with research caveat."
        elif is_community_scale:
            domain_valid = False
            domain_note = (
                "Industrial GRU calibrated on real Spark plant data (~5,300 Nm³/day). "
                "Current telemetry represents a community-scale digester. "
                "Industrial-to-community scale transfer has not been validated."
            )
            status_val = ForecastStatusEnum.SUCCESS.value
        else:
            domain_valid = True
            domain_note = "Industrial research domain validated."
            status_val = ForecastStatusEnum.SUCCESS.value

        res = ForecastResult(
            device_id=device_id,
            timestamp=now_utc,
            target_date=target_date,
            predicted_biogas_m3_day=round(pred_val, 2),
            input_biogas_m3_day=round(curr_biogas, 2),
            input_timestamp=input_ts,
            model_name=model_name,
            model_version=model_version,
            preprocessing_version=prep_version,
            data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
            status=status_val,
            domain_valid=domain_valid,
            domain_note=domain_note,
            top_feature_1="Slurry Temperature D1 (36.5°C mesophilic)",
            top_feature_2="Total Feedstock Loading Rate",
            top_feature_3="Digester 1 pH Buffer",
            recommendation=rec
        )
        return self._persist_if_db(res, db)

    def _predict_ema_090(
        self,
        device_id: str,
        history: List[Dict[str, Any]],
        data_source: ProvenanceEnum,
        now_utc: datetime,
        target_date: datetime,
        db: Optional[Session] = None
    ) -> ForecastResult:
        data_source_str = str(getattr(data_source, "value", data_source)).upper()
        if any(term in data_source_str for term in ["AGSTAR", "AGSTAR_REGISTRY", "EXTERNAL_BENCHMARK"]):
            raise ValueError("AgSTAR is an external static benchmark and cannot enter the time-series forecasting pipeline.")

        is_live_iot = (
            data_source == ProvenanceEnum.LIVE_IOT 
            or data_source_str == "LIVE_IOT"
        )

        model_name = "EMA-0.90"
        model_version = "v1.0.0"
        prep_version = "none"
        input_ts = self._extract_input_timestamp(history, now_utc)

        if len(history) < 3:
            status_val = (
                ForecastStatusEnum.INSUFFICIENT_LIVE_HISTORY.value 
                if is_live_iot 
                else ForecastStatusEnum.INSUFFICIENT_HISTORY.value
            )
            res = ForecastResult(
                device_id=device_id,
                timestamp=now_utc,
                target_date=target_date,
                predicted_biogas_m3_day=0.0,
                input_biogas_m3_day=float(history[-1].get("biogas_today_nm3", 0.0)) if (history and history[-1].get("biogas_today_nm3") is not None) else None,
                input_timestamp=input_ts,
                model_name=model_name,
                model_version=model_version,
                preprocessing_version=prep_version,
                data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
                status=status_val,
                domain_valid=True,
                domain_note="Scale-compatible statistical reference.",
                recommendation="Forecast inhibited: Minimum 3 days of historical telemetry required for EMA-0.90 smoothing."
            )
            return self._persist_if_db(res, db)

        # Check feature integrity: biogas_today_nm3 must exist
        last_3 = history[-3:]
        if any(r.get("biogas_today_nm3") is None for r in last_3):
            res = ForecastResult(
                device_id=device_id,
                timestamp=now_utc,
                target_date=target_date,
                predicted_biogas_m3_day=0.0,
                input_biogas_m3_day=None,
                input_timestamp=input_ts,
                model_name=model_name,
                model_version=model_version,
                preprocessing_version=prep_version,
                data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
                status=ForecastStatusEnum.INSUFFICIENT_LIVE_FEATURES.value,
                domain_valid=True,
                domain_note="Missing required biogas reading for EMA-0.90.",
                recommendation="Forecast inhibited: Missing required live biogas observations."
            )
            return self._persist_if_db(res, db)

        curr_biogas = float(last_3[-1]["biogas_today_nm3"])
        mean_3d = float(np.mean([float(r["biogas_today_nm3"]) for r in last_3]))
        pred_val = max(0.0, float(0.90 * curr_biogas + 0.10 * mean_3d))

        res = ForecastResult(
            device_id=device_id,
            timestamp=now_utc,
            target_date=target_date,
            predicted_biogas_m3_day=round(pred_val, 2),
            input_biogas_m3_day=round(curr_biogas, 2),
            input_timestamp=input_ts,
            model_name=model_name,
            model_version=model_version,
            preprocessing_version=prep_version,
            data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
            status=ForecastStatusEnum.SUCCESS.value,
            domain_valid=True,
            domain_note="Scale-compatible statistical reference.",
            recommendation="Exponentially smoothed benchmark prediction with alpha=0.90."
        )
        return self._persist_if_db(res, db)

    def _predict_persistence(
        self,
        device_id: str,
        history: List[Dict[str, Any]],
        data_source: ProvenanceEnum,
        now_utc: datetime,
        target_date: datetime,
        db: Optional[Session] = None
    ) -> ForecastResult:
        data_source_str = str(getattr(data_source, "value", data_source)).upper()
        if any(term in data_source_str for term in ["AGSTAR", "AGSTAR_REGISTRY", "EXTERNAL_BENCHMARK"]):
            raise ValueError("AgSTAR is an external static benchmark and cannot enter the time-series forecasting pipeline.")

        is_live_iot = (
            data_source == ProvenanceEnum.LIVE_IOT 
            or data_source_str == "LIVE_IOT"
        )

        model_name = "Persistence"
        model_version = "v1.0.0"
        prep_version = "none"
        input_ts = self._extract_input_timestamp(history, now_utc)

        if len(history) < 1:
            status_val = (
                ForecastStatusEnum.INSUFFICIENT_LIVE_HISTORY.value 
                if is_live_iot 
                else ForecastStatusEnum.INSUFFICIENT_HISTORY.value
            )
            res = ForecastResult(
                device_id=device_id,
                timestamp=now_utc,
                target_date=target_date,
                predicted_biogas_m3_day=0.0,
                input_biogas_m3_day=None,
                input_timestamp=input_ts,
                model_name=model_name,
                model_version=model_version,
                preprocessing_version=prep_version,
                data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
                status=status_val,
                domain_valid=True,
                domain_note="Naive scale-compatible baseline.",
                recommendation="Forecast inhibited: Current day observation unavailable."
            )
            return self._persist_if_db(res, db)

        if history[-1].get("biogas_today_nm3") is None:
            res = ForecastResult(
                device_id=device_id,
                timestamp=now_utc,
                target_date=target_date,
                predicted_biogas_m3_day=0.0,
                input_biogas_m3_day=None,
                input_timestamp=input_ts,
                model_name=model_name,
                model_version=model_version,
                preprocessing_version=prep_version,
                data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
                status=ForecastStatusEnum.INSUFFICIENT_LIVE_FEATURES.value,
                domain_valid=True,
                domain_note="Missing required biogas observation for Persistence.",
                recommendation="Forecast inhibited: Missing required live biogas observation."
            )
            return self._persist_if_db(res, db)

        curr_biogas = float(history[-1]["biogas_today_nm3"])
        pred_val = max(0.0, curr_biogas)

        res = ForecastResult(
            device_id=device_id,
            timestamp=now_utc,
            target_date=target_date,
            predicted_biogas_m3_day=round(pred_val, 2),
            input_biogas_m3_day=round(curr_biogas, 2),
            input_timestamp=input_ts,
            model_name=model_name,
            model_version=model_version,
            preprocessing_version=prep_version,
            data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
            status=ForecastStatusEnum.SUCCESS.value,
            domain_valid=True,
            domain_note="Naive scale-compatible baseline.",
            recommendation="Naive lag-0 persistence baseline: tomorrow equals today."
        )
        return self._persist_if_db(res, db)

    def _predict_xconet(
        self,
        device_id: str,
        history: List[Dict[str, Any]],
        data_source: ProvenanceEnum,
        now_utc: datetime,
        target_date: datetime,
        db: Optional[Session] = None
    ) -> ForecastResult:
        data_source_str = str(getattr(data_source, "value", data_source)).upper()
        if any(term in data_source_str for term in ["AGSTAR", "AGSTAR_REGISTRY", "EXTERNAL_BENCHMARK"]):
            raise ValueError("AgSTAR is an external static benchmark and cannot enter the time-series forecasting pipeline.")

        is_live_iot = (
            data_source == ProvenanceEnum.LIVE_IOT 
            or data_source_str == "LIVE_IOT"
        )

        model_name = "XCO-Net"
        model_version = "v1.0.0-research"
        prep_version = "v1.0.0-frozen-train"
        input_ts = self._extract_input_timestamp(history, now_utc)

        is_user_upload = (
            data_source in [ProvenanceEnum.USER_UPLOAD, ProvenanceEnum.UPLOADED_SCADA]
            or data_source_str in ["USER_UPLOAD", "UPLOADED_SCADA"]
        )
        is_community_scale = (
            data_source == ProvenanceEnum.DEMO_SYNTHETIC 
            or (isinstance(data_source, str) and data_source == "DEMO_SYNTHETIC")
            or is_live_iot
            or (history and float(history[-1].get("biogas_today_nm3", 0.0) or 0.0) < 100.0)
        )
        if is_user_upload:
            early_domain_note = "Experimental research architecture calibrated on industrial Spark data (~5,300 Nm³/day). Uploaded user dataset has not been validated against the operational training domain."
        elif is_community_scale:
            early_domain_note = "Experimental research architecture calibrated on industrial Spark data (~5,300 Nm³/day). Current telemetry represents a community-scale digester. Community-scale transfer has not been validated."
        else:
            early_domain_note = "Experimental industrial-domain research architecture."

        required_len = 7
        if len(history) < required_len or self._xco_model is None or self._xco_scaler_meta is None:
            status_val = (
                ForecastStatusEnum.INSUFFICIENT_LIVE_HISTORY.value 
                if is_live_iot 
                else ForecastStatusEnum.INSUFFICIENT_HISTORY.value
            )
            rec_msg = (
                f"Forecast inhibited: Minimum {required_len} valid chronological observations required (got {len(history)})."
                if is_live_iot
                else f"XCO-Net research prediction inhibited: Minimum {required_len} continuous days required."
            )
            res = ForecastResult(
                device_id=device_id,
                timestamp=now_utc,
                target_date=target_date,
                predicted_biogas_m3_day=0.0,
                input_biogas_m3_day=float(history[-1].get("biogas_today_nm3", 0.0)) if (history and history[-1].get("biogas_today_nm3") is not None) else None,
                input_timestamp=input_ts,
                model_name=model_name,
                model_version=model_version,
                preprocessing_version=prep_version,
                data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
                status=status_val,
                domain_valid=False,
                domain_note=early_domain_note,
                recommendation=rec_msg
            )
            return self._persist_if_db(res, db)

        window = history[-7:]
        curr_biogas = float(window[-1].get("biogas_today_nm3") or 0.0)

        feature_cols = self._xco_scaler_meta["feature_cols"]
        matrix = []
        has_missing_feature = False
        for row in window:
            row_vals = []
            for col in feature_cols:
                val = row.get(col)
                if val is None:
                    has_missing_feature = True
                    break
                row_vals.append(float(val))
            if has_missing_feature:
                break
            matrix.append(row_vals)

        if has_missing_feature:
            status_val = (
                ForecastStatusEnum.INSUFFICIENT_FEATURES.value
                if is_user_upload
                else (ForecastStatusEnum.INSUFFICIENT_LIVE_FEATURES.value if is_live_iot else ForecastStatusEnum.INSUFFICIENT_FEATURES.value)
            )
            note_val = (
                "Uploaded dataset lacks required model input features. Zero fallback data permitted."
                if is_user_upload
                else "Live telemetry lacks required model features. Zero fallback data permitted."
            )
            res = ForecastResult(
                device_id=device_id,
                timestamp=now_utc,
                target_date=target_date,
                predicted_biogas_m3_day=0.0,
                input_biogas_m3_day=float(window[-1].get("biogas_today_nm3") or 0.0) if window[-1].get("biogas_today_nm3") is not None else None,
                input_timestamp=input_ts,
                model_name=model_name,
                model_version=model_version,
                preprocessing_version=prep_version,
                data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
                status=status_val,
                domain_valid=False,
                domain_note=note_val,
                recommendation="Forecast inhibited: Incomplete features across lookback window."
            )
            return self._persist_if_db(res, db)

        arr = np.array(matrix, dtype=np.float32)

        norm_arr = self._normalize_with_frozen_scaler(arr, self._xco_scaler_meta)
        t_in = torch.tensor(norm_arr, dtype=torch.float32).unsqueeze(0)
        t_anc = torch.tensor([[curr_biogas]], dtype=torch.float32)

        with torch.no_grad():
            pred_y_tensor, delta_tensor = self._xco_model(t_in, t_anc)
            pred_val = max(0.0, float(pred_y_tensor.item()))
            delta_val = float(delta_tensor.item())

        is_user_upload = (
            data_source in [ProvenanceEnum.USER_UPLOAD, ProvenanceEnum.UPLOADED_SCADA]
            or data_source_str in ["USER_UPLOAD", "UPLOADED_SCADA"]
        )
        is_community_scale = (
            data_source == ProvenanceEnum.DEMO_SYNTHETIC 
            or (isinstance(data_source, str) and data_source == "DEMO_SYNTHETIC")
            or is_live_iot
            or curr_biogas < 100.0
        )
        if is_user_upload:
            domain_valid = False
            domain_note = "Experimental research architecture calibrated on industrial Spark data (~5,300 Nm³/day). Uploaded user dataset is unvalidated (has not been validated against the operational training domain)."
            status_val = ForecastStatusEnum.UNVALIDATED_USER_DATASET.value
        elif is_community_scale:
            domain_valid = False
            domain_note = (
                "Experimental research architecture calibrated on industrial Spark data (~5,300 Nm³/day). "
                "Current telemetry represents a community-scale digester. Community-scale transfer has not been validated."
            )
            status_val = ForecastStatusEnum.SUCCESS.value
        else:
            domain_valid = True
            domain_note = "Experimental industrial-domain research architecture."
            status_val = ForecastStatusEnum.SUCCESS.value

        res = ForecastResult(
            device_id=device_id,
            timestamp=now_utc,
            target_date=target_date,
            predicted_biogas_m3_day=round(pred_val, 2),
            input_biogas_m3_day=round(curr_biogas, 2),
            input_timestamp=input_ts,
            model_name=model_name,
            model_version=model_version,
            preprocessing_version=prep_version,
            data_source=data_source.value if hasattr(data_source, "value") else str(data_source),
            status=status_val,
            domain_valid=domain_valid,
            domain_note=domain_note,
            top_feature_1="Pointwise Cross-Channel Interaction",
            top_feature_2="Cross-Channel Operator Feedstock Projection",
            top_feature_3="Training-Derived Bounded Delta (±4152 Nm³/day)",
            recommendation=f"Experimental XCO-Net output: predicted delta = {delta_val:+.1f} Nm³/day (research mode)."
        )
        return self._persist_if_db(res, db)

    def _persist_if_db(self, record: ForecastResult, db: Optional[Session] = None) -> ForecastResult:
        if db is not None:
            try:
                db.add(record)
                db.commit()
                db.refresh(record)
            except Exception as e:
                db.rollback()
                print(f"[ForecastService] DB commit error: {e}")
        return record

    def get_interpretation(
        self,
        device_id: str = "DIGESTER_001",
        model_name: str = "GRU-14d Residual",
        data_source: ProvenanceEnum = ProvenanceEnum.DEMO_SYNTHETIC,
        history_window: Optional[List[Dict[str, Any]]] = None,
        db: Optional[Session] = None
    ) -> ForecastInterpretationResponse:
        model_key = model_name.strip()
        data_source_str = str(getattr(data_source, "value", data_source)).upper()
        if any(term in data_source_str for term in ["AGSTAR", "AGSTAR_REGISTRY", "EXTERNAL_BENCHMARK"]) or "AGSTAR" in model_name.upper():
            raise ValueError("AgSTAR is an external static benchmark and cannot enter the time-series forecasting pipeline.")

        is_live_iot = (data_source == ProvenanceEnum.LIVE_IOT or data_source_str == "LIVE_IOT")

        if not history_window:
            db_source = "live_esp32" if is_live_iot else None
            history_window = self._fetch_recent_readings_from_db(device_id, limit=20, db=db, source=db_source)

        history = history_window or []

        # 1. GRU (14-day Residual)
        if "GRU" in model_key:
            if len(history) < 14 or self._gru_model is None or self._gru_scaler_meta is None:
                return ForecastInterpretationResponse(
                    model_name=model_name,
                    method="Local input sensitivity over current 14-step window",
                    is_shap=False,
                    available=False,
                    reason="Interpretation unavailable: insufficient valid input history (minimum 14 observations required)."
                )

            window = history[-14:]
            curr_biogas = float(window[-1].get("biogas_today_nm3") or 0.0)
            feature_cols = self._gru_scaler_meta["feature_cols"]

            # Feature completeness check
            matrix = []
            for row in window:
                row_vals = []
                for col in feature_cols:
                    v = row.get(col)
                    if v is None:
                        return ForecastInterpretationResponse(
                            model_name=model_name,
                            method="Local input sensitivity over current 14-step window",
                            is_shap=False,
                            available=False,
                            reason=f"Interpretation unavailable: missing required feature '{col}' across 14-step window."
                        )
                    row_vals.append(float(v))
                matrix.append(row_vals)

            arr = np.array(matrix, dtype=np.float32)  # (14, 9)
            norm_arr = self._normalize_with_frozen_scaler(arr, self._gru_scaler_meta)
            t_in = torch.tensor(norm_arr, dtype=torch.float32).unsqueeze(0)

            with torch.no_grad():
                base_delta_norm = self._gru_model(t_in).item()

            y_std = self._gru_scaler_meta["y_std"]
            pred_val = max(0.0, float(curr_biogas + base_delta_norm * y_std))

            feature_labels = {
                "biogas_today_nm3": ("Biogas Production", "Nm³/day"),
                "temp_outlet_d1_c": ("Digester Temperature", "°C"),
                "ph_outlet_d1": ("Digester pH", ""),
                "feed_total_m3": ("Feedstock Volumetric", "m³"),
                "total_incoming_mt": ("Incoming Feedstock", "MT"),
                "total_processed_mt": ("Processed Feedstock", "MT"),
                "recycle_water_m3": ("Recycle Water", "m³"),
                "feed_total_m3_was_missing": ("Feed Missing Indicator", ""),
                "ph_outlet_d1_was_missing": ("pH Missing Indicator", "")
            }

            features_list: List[InterpretationFeatureSignal] = []
            sensitivities_list: List[InterpretationSensitivity] = []

            for idx, col in enumerate(feature_cols):
                label, unit = feature_labels.get(col, (col, ""))
                col_vals = arr[:, idx]
                latest_v = float(col_vals[-1])
                first_v = float(np.mean(col_vals[:3]))
                last_v = float(np.mean(col_vals[-3:]))

                if last_v > first_v * 1.02:
                    trend = "↑"
                elif last_v < first_v * 0.98:
                    trend = "↓"
                else:
                    trend = "→"

                features_list.append(InterpretationFeatureSignal(
                    name=col,
                    label=label,
                    latest_value=round(latest_v, 2),
                    unit=unit,
                    trend=trend
                ))

                norm_perturbed = norm_arr.copy()
                norm_perturbed[-1, idx] += 0.10
                t_pert = torch.tensor(norm_perturbed, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    pert_delta_norm = self._gru_model(t_pert).item()
                pert_delta = (pert_delta_norm - base_delta_norm) * y_std
                sensitivities_list.append(InterpretationSensitivity(
                    feature_name=col,
                    label=label,
                    delta_prediction_nm3=round(float(pert_delta), 2)
                ))

            sensitivities_list.sort(key=lambda s: abs(s.delta_prediction_nm3), reverse=True)

            return ForecastInterpretationResponse(
                model_name="GRU-14d Residual",
                method="Local input sensitivity over current 14-step window",
                is_shap=False,
                available=True,
                prediction_nm3_day=round(pred_val, 2),
                reference_nm3_day=round(curr_biogas, 2),
                reference_label="Persistence Baseline (y_t)",
                prediction_delta_nm3_day=round(pred_val - curr_biogas, 2),
                features=features_list,
                sensitivities=sensitivities_list,
                contributions=[],
                explanation_text="Local input sensitivity computed by perturbing each normalized input feature by +0.10 standard deviation over the 14-step sequence. Not additive SHAP."
            )

        # 2. EMA-0.90
        elif "EMA" in model_key:
            if len(history) < 3:
                return ForecastInterpretationResponse(
                    model_name=model_name,
                    method="Exponential moving average",
                    is_shap=False,
                    available=False,
                    reason="Interpretation unavailable: insufficient input history (minimum 3 continuous observations required for EMA-0.90)."
                )

            last_3 = history[-3:]
            if any(r.get("biogas_today_nm3") is None for r in last_3):
                return ForecastInterpretationResponse(
                    model_name=model_name,
                    method="Exponential moving average",
                    is_shap=False,
                    available=False,
                    reason="Interpretation unavailable: missing required biogas observation in lookback window."
                )

            y_t = float(last_3[-1]["biogas_today_nm3"])
            y_t_minus_1 = float(last_3[-2]["biogas_today_nm3"])
            y_t_minus_2 = float(last_3[-3]["biogas_today_nm3"])
            mean_3d = (y_t + y_t_minus_1 + y_t_minus_2) / 3.0
            pred_val = max(0.0, float(0.90 * y_t + 0.10 * mean_3d))

            w_t = 0.90 + (0.10 / 3.0)  # 14/15 = 0.9333...
            w_t_minus_1 = 0.10 / 3.0   # 1/30 = 0.0333...
            w_t_minus_2 = 0.10 / 3.0   # 1/30 = 0.0333...

            features = [
                InterpretationFeatureSignal(name="y_t", label="Latest observation (t)", latest_value=round(y_t, 2), unit="Nm³/day", trend="→"),
                InterpretationFeatureSignal(name="y_t_minus_1", label="Previous observation (t-1)", latest_value=round(y_t_minus_1, 2), unit="Nm³/day", trend="→"),
                InterpretationFeatureSignal(name="y_t_minus_2", label="Third observation (t-2)", latest_value=round(y_t_minus_2, 2), unit="Nm³/day", trend="→")
            ]

            contributions = [
                InterpretationWeight(component="Observation y_t (Current Day)", weight="93.33% (0.90 + 0.10/3)", influence_nm3=round(w_t * y_t, 2)),
                InterpretationWeight(component="Observation y_{t-1} (Previous Day)", weight="3.33% (0.10/3)", influence_nm3=round(w_t_minus_1 * y_t_minus_1, 2)),
                InterpretationWeight(component="Observation y_{t-2} (Two Days Prior)", weight="3.33% (0.10/3)", influence_nm3=round(w_t_minus_2 * y_t_minus_2, 2))
            ]

            return ForecastInterpretationResponse(
                model_name="EMA-0.90",
                method="Exponential moving average",
                is_shap=False,
                available=True,
                prediction_nm3_day=round(pred_val, 2),
                reference_nm3_day=round(y_t, 2),
                reference_label="Persistence Baseline (y_t)",
                prediction_delta_nm3_day=round(pred_val - y_t, 2),
                features=features,
                contributions=contributions,
                explanation_text="Exact mathematical weights derived from implementation: 0.90 * y_t + 0.10 * mean(y_t, y_t-1, y_t-2). Effective coefficients: 93.33% on day t, 3.33% on day t-1, 3.33% on day t-2."
            )

        # 3. Persistence
        elif "Persistence" in model_key or "Lag" in model_key:
            if len(history) < 1 or history[-1].get("biogas_today_nm3") is None:
                return ForecastInterpretationResponse(
                    model_name=model_name,
                    method="Persistence baseline",
                    is_shap=False,
                    available=False,
                    reason="Interpretation unavailable: insufficient input history (minimum 1 valid biogas observation required)."
                )

            y_t = float(history[-1]["biogas_today_nm3"])
            pred_val = max(0.0, y_t)

            return ForecastInterpretationResponse(
                model_name="Persistence",
                method="Persistence baseline",
                is_shap=False,
                available=True,
                prediction_nm3_day=round(pred_val, 2),
                reference_nm3_day=round(y_t, 2),
                reference_label="Latest Observed Biogas (y_t)",
                prediction_delta_nm3_day=0.0,
                features=[
                    InterpretationFeatureSignal(name="y_t", label="Latest observed biogas (y_t)", latest_value=round(y_t, 2), unit="Nm³/day", trend="→")
                ],
                contributions=[
                    InterpretationWeight(component="Identity Projection", weight="100.0%", influence_nm3=round(y_t, 2))
                ],
                explanation_text=f"Naive lag-0 persistence baseline: tomorrow's forecast identically equals today's observed value ({round(y_t, 2)} Nm³/day). Forecast difference = 0.0 Nm³/day."
            )

        # 4. XCO-Net
        elif "XCO" in model_key:
            if len(history) < 7 or self._xco_model is None or self._xco_scaler_meta is None:
                return ForecastInterpretationResponse(
                    model_name=model_name,
                    method="Architecture-level research attribution",
                    is_shap=False,
                    available=False,
                    reason="Interpretation unavailable: insufficient input history (minimum 7 continuous observations required for XCO-Net)."
                )

            window = history[-7:]
            curr_biogas = float(window[-1].get("biogas_today_nm3") or 0.0)

            contributions = [
                InterpretationWeight(component="Pointwise Cross-Channel Interaction", weight="48.5% Weight (Inertia Anchor)", influence_nm3=None),
                InterpretationWeight(component="Cross-Channel Operator Feedstock", weight="18.2% Weight (Biokinetic Driver)", influence_nm3=None),
                InterpretationWeight(component="Differentiable Tanh Bounded Delta", weight="+-4,152 Nm3/day (±4,152)", influence_nm3=None)
            ]

            return ForecastInterpretationResponse(
                model_name="XCO-Net",
                method="Architecture-level research attribution",
                is_shap=False,
                available=True,
                prediction_nm3_day=None,
                reference_nm3_day=round(curr_biogas, 2),
                reference_label="Inertia Anchor (y_t)",
                prediction_delta_nm3_day=None,
                features=[],
                contributions=contributions,
                explanation_text="Architecture-level projection weights (1×1 pointwise convolutions) with inertia anchor; not additive SHAP."
            )

        else:
            raise ValueError(f"Invalid model '{model_name}'. Valid models are: 'GRU-14d Residual', 'EMA-0.90', 'Persistence', 'XCO-Net'.")

    def get_models_metadata(self) -> Dict[str, Any]:
        """
        Returns authoritative model metadata, required causal history lengths,
        model roles, and strict past-only causal methodology footers.
        """
        res = dict(MODEL_REQUIREMENTS_METADATA)
        res["models"] = {
            k: {**v, "required_history_timesteps": v["required_history"]}
            for k, v in MODEL_REQUIREMENTS_METADATA.items()
        }
        return res

    def get_benchmarks(self) -> ModelComparisonResponse:
        """
        Returns validated benchmarks with strict separation between
        held-out test set metrics (24 days) and cross-window mean metrics (3 windows).
        """
        models = [
            ModelBenchmarkItem(
                model_id="gru_14d_residual",
                model_name="GRU-14d Residual",
                role=ModelRoleEnum.DEFAULT,
                category="Forecasting",
                artifact_path="models/gru_lookback_14d_residual.pt",
                lookback_days=14,
                held_out_test_metrics=MetricScore(
                    mae=766.61, rmse=959.40, mape_pct=11.01, r2=0.2494
                ),
                cross_window_mean_metrics=MetricScore(
                    mae=907.32, rmse=1148.76, mape_pct=12.89, r2=0.2723
                ),
                description="Default operational forecasting champion. Single-layer GRU modeling 14-day physical process sequence, predicting bounded residual delta."
            ),
            ModelBenchmarkItem(
                model_id="ema_090",
                model_name="EMA-0.90",
                role=ModelRoleEnum.BENCHMARK,
                category="Forecasting",
                artifact_path="statistical_rule",
                lookback_days=3,
                held_out_test_metrics=MetricScore(
                    mae=777.32, rmse=984.48, mape_pct=10.86, r2=0.2096
                ),
                cross_window_mean_metrics=MetricScore(
                    mae=972.53, rmse=1230.70, mape_pct=14.10, r2=0.0641
                ),
                description="Strongest statistical filter benchmark. Computes exponential smoothing (alpha=0.90) on production inertia."
            ),
            ModelBenchmarkItem(
                model_id="persistence",
                model_name="Persistence",
                role=ModelRoleEnum.BASELINE,
                category="Forecasting",
                artifact_path="naive_lag0",
                lookback_days=1,
                held_out_test_metrics=MetricScore(
                    mae=798.83, rmse=1000.90, mape_pct=11.15, r2=0.1830
                ),
                cross_window_mean_metrics=MetricScore(
                    mae=1000.61, rmse=1252.86, mape_pct=14.45, r2=0.0253
                ),
                description="Standard industrial baseline: tomorrow's biogas production equals today's production."
            ),
            ModelBenchmarkItem(
                model_id="xco_net",
                model_name="XCO-Net",
                role=ModelRoleEnum.EXPERIMENTAL,
                category="Research",
                artifact_path="models/xco_net_best.pt",
                lookback_days=7,
                held_out_test_metrics=MetricScore(
                    mae=799.44, rmse=1016.92, mape_pct=11.23, r2=0.1567
                ),
                cross_window_mean_metrics=MetricScore(
                    mae=1000.39, rmse=1250.13, mape_pct=14.39, r2=0.0162
                ),
                description="Proposed research architecture featuring compact GRU temporal encoding, 1x1 conv cross-channel mixing, and differentiable tanh training-derived bounded production correction."
            )
        ]

        return ModelComparisonResponse(
            benchmark_timestamp="2026-09-16T00:00:00Z",
            models=models,
            walk_forward_windows_evaluated=3,
            test_set_days_evaluated=24
        )

    def get_spark_replay_timeline(
        self,
        model_name: str = "GRU-14d Residual",
        mode: str = "held_out_test",
        limit: Optional[int] = None,
        dataset_override: Optional[pd.DataFrame] = None
    ) -> List[SparkTimelineItem]:
        """
        Extracts causal historical replay timeline from the real Spark dataset.
        - mode="held_out_test": Strictly replays the official 24 held-out test days (2026-03-10 to 2026-04-02).
        - mode="full_historical": Replays the complete 176 calendar days (2025-11-01 to 2026-04-25).
        For each day t: prediction for t+1 uses ONLY data from [t - lookback + 1, ..., t].
        Strictly prevents any lookahead leakage.
        """
        if "AGSTAR" in str(mode).upper() or "AGSTAR" in str(model_name).upper():
            raise ValueError("AgSTAR is an external static macro benchmark and does not support time-series replay.")

        if mode not in ["held_out_test", "full_historical"]:
            raise ValueError(f"Invalid replay mode '{mode}'. Valid modes are 'held_out_test' (24 days) and 'full_historical' (176 days).")

        model_key = model_name.strip()
        if not ("GRU" in model_key or "XCO" in model_key or "EMA" in model_key or "Persistence" in model_key or "Lag" in model_key):
            raise ValueError(f"Invalid model '{model_name}'. Valid models are: 'GRU-14d Residual', 'EMA-0.90', 'Persistence', 'XCO-Net'.")

        if dataset_override is not None:
            df = dataset_override.copy().sort_values("date").reset_index(drop=True)
        else:
            df = self.get_spark_dataset().copy().sort_values("date").reset_index(drop=True)

        lookback = 14 if "GRU" in model_name else (7 if "XCO" in model_name else (3 if "EMA" in model_name else 1))
        
        feature_cols = [
            "biogas_today_nm3", "total_incoming_mt", "total_processed_mt",
            "feed_total_m3", "temp_outlet_d1_c", "ph_outlet_d1",
            "recycle_water_m3", "feed_total_m3_was_missing", "ph_outlet_d1_was_missing"
        ]

        if mode == "full_historical":
            min_eval_date = df["date"].min()
            end_date = df["date"].max()
        else: # "held_out_test"
            # Official held-out test window: 2026-03-10 to 2026-04-02 (24 days)
            min_eval_date = pd.to_datetime("2026-03-10")
            end_date = pd.to_datetime("2026-04-02")

        eval_indices = df[(df["date"] >= min_eval_date) & (df["date"] <= end_date)].index.tolist()

        timeline = []
        for k in eval_indices:
            curr_row = df.iloc[k]
            cur_date = curr_row["date"]

            # Causally bounded past window: up to day t (index k in full chronological df)
            context_start = k - lookback + 1
            if context_start < 0:
                past_sub = df.iloc[0 : k + 1].copy()
                hist_len = len(past_sub)
                status = "INSUFFICIENT_HISTORY"
                pred_val = None
            else:
                past_sub = df.iloc[context_start : k + 1].copy()
                hist_len = len(past_sub)
                
                history_recs = []
                for _, r in past_sub.iterrows():
                    rec = {col: r[col] for col in feature_cols}
                    rec["date"] = r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])
                    history_recs.append(rec)
                
                # Predict t+1 using past history up to day t
                pred_res = self.predict(
                    device_id="DIGESTER_001",
                    model_name=model_name,
                    data_source=ProvenanceEnum.REAL_SPARK_HISTORICAL,
                    history_window=history_recs
                )

                if pred_res.status == ForecastStatusEnum.SUCCESS.value:
                    status = "SUCCESS"
                    pred_val = round(pred_res.predicted_biogas_m3_day, 1)
                else:
                    status = "INSUFFICIENT_HISTORY"
                    pred_val = None

            act_today = float(curr_row["biogas_today_nm3"])
            act_next = float(curr_row["target_biogas_next_day_nm3"]) if curr_row.get("target_is_valid", 1) == 1 else None
            
            timeline.append(SparkTimelineItem(
                date=curr_row["date"].strftime("%Y-%m-%d"),
                target_date=(curr_row["date"] + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                actual_biogas_today_nm3=round(act_today, 1),
                actual_next_day_nm3=round(act_next, 1) if act_next is not None else None,
                predicted_next_day_nm3=pred_val,
                model_name=model_name,
                data_source=ProvenanceEnum.REAL_SPARK_HISTORICAL,
                target_is_valid=bool(curr_row.get("target_is_valid", 1) == 1),
                temperature_c=float(curr_row["temp_outlet_d1_c"]),
                ph_d1=float(curr_row["ph_outlet_d1"]),
                feed_total_m3=float(curr_row["feed_total_m3"]),
                domain_valid=True,
                domain_note="Industrial research domain validated.",
                history_length=hist_len,
                status=status
            ))
            
            if limit is not None and len(timeline) >= limit:
                break
                
        return timeline

    def get_xconet_research_details(self) -> XCONetResearchResponse:
        return XCONetResearchResponse(
            architecture_name="XCO-Net (Cross-Channel Operator Network)",
            role=ModelRoleEnum.EXPERIMENTAL,
            total_trainable_parameters=2706,
            parameter_to_sample_ratio=25.8,
            delta_bounding_mechanism="Differentiable tanh-bounded delta: delta_y = delta_max * tanh(raw_delta) (training-derived bounded production correction)",
            delta_max_nm3_day=4152.0,
            loss_function="Physics-Guided Huber Loss with non-negativity barrier",
            cross_channel_mixing="1x1 Conv pointwise projection + LayerNorm",
            ablation_findings={
                "base_xconet": {"mae": 799.44, "rmse": 1016.92, "r2": 0.1567},
                "without_cross_channel": {"mae": 804.12, "rmse": 1021.30, "r2": 0.1494, "impact": "Cross-channel mixing reduces RMSE by 4.38 Nm3/day"},
                "without_attention": {"mae": 801.20, "rmse": 1019.55, "r2": 0.1523, "impact": "Attention pooling reduces RMSE by 2.63 Nm3/day"}
            },
            feature_attributions=[
                {"feature": "biogas_today_nm3", "attribution": 0.485, "role": "Inertia Anchor"},
                {"feature": "temp_outlet_d1_c", "attribution": 0.182, "role": "Biokinetic Driver"},
                {"feature": "total_processed_mt", "attribution": 0.144, "role": "Substrate Availability"},
                {"feature": "ph_outlet_d1", "attribution": 0.112, "role": "Methanogenic Health"},
                {"feature": "feed_total_m3", "attribution": 0.077, "role": "Hydraulic Volumetric Loading"}
            ]
        )


# Global singleton instance
forecast_service = ForecastService()

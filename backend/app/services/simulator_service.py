import os
import datetime
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from simulation.synthetic_data_generator.generate_dataset import generate_ad_timeseries
from backend.app.schemas.forecast import ProvenanceEnum, ForecastStatusEnum
from backend.app.services.forecast_service import forecast_service

class SimulatorService:
    def __init__(self, seed: int = 42, default_days: int = 180):
        self.seed = seed
        self.default_days = default_days
        self._cached_df: Optional[pd.DataFrame] = None
        self._timeline: Optional[List[Dict[str, Any]]] = None

    def get_raw_dataframe(self, days: Optional[int] = None) -> pd.DataFrame:
        if days is None:
            days = self.default_days
        if self._cached_df is None or len(self._cached_df) != days:
            self._cached_df = generate_ad_timeseries(
                days=days,
                sampling_hours=24,
                reactor_volume_m3=3.0,
                seed=self.seed,
                include_disturbances=True
            )
        return self._cached_df

    def get_simulator_timeline(self, days: int = 180, warmup_days: int = 14) -> List[Dict[str, Any]]:
        """
        Generates continuous synthetic AD operational history with a designated warm-up buffer.
        For each day t:
        - Maintains continuous daily timestamps.
        - Provides all 9 GRU feature columns.
        - For t >= warmup_days - 1: executes causal GRU-14d prediction for t+1 using x[t-13..t].
        - For t < warmup_days - 1: flags status as 'Warming up forecast model' with no forecast.
        """
        df = self.get_raw_dataframe(days=days).copy()
        
        timeline = []
        history_buffer: List[Dict[str, Any]] = []

        for i, row in df.iterrows():
            ts_str = str(row["timestamp"])
            feed_kg = float(row["feedstock_mass_kg"])
            biogas_nm3 = float(row["biogas_production_m3_day"])
            temp_c = float(row["temperature_c"])
            ph_val = float(row["ph"])
            
            # Map into the 9 GRU feature definitions
            incoming_mt = round(feed_kg / 1000.0, 4)
            processed_mt = round(feed_kg / 1000.0, 4)
            feed_vol_m3 = round(feed_kg * 0.0012, 4)
            
            item_features = {
                "timestamp": ts_str,
                "biogas_today_nm3": round(biogas_nm3, 2),
                "total_incoming_mt": incoming_mt,
                "total_processed_mt": processed_mt,
                "feed_total_m3": feed_vol_m3,
                "temp_outlet_d1_c": round(temp_c, 2),
                "ph_outlet_d1": round(ph_val, 2),
                "recycle_water_m3": 30.0,
                "feed_total_m3_was_missing": 0.0,
                "ph_outlet_d1_was_missing": 0.0
            }
            history_buffer.append(item_features)
            
            # Determine warm-up status
            # For 14-day lookback: warmup completes at day index 13 (Day 14)
            history_len = len(history_buffer)
            is_warmup_ready = history_len >= warmup_days
            history_available = min(warmup_days, history_len)
            
            predicted_val: Optional[float] = None
            forecast_status = "SUCCESS"
            forecast_rec = "Stable steady-state operation."
            
            domain_valid = False
            domain_note = "Industrial-to-community scale transfer not yet validated."

            if is_warmup_ready:
                # Causally strictly slice past 14 timesteps: x[t-13..t]
                input_slice = history_buffer[-warmup_days:]
                pred_result = forecast_service.predict(
                    device_id="DIGESTER_001",
                    model_name="GRU-14d Residual",
                    data_source=ProvenanceEnum.DEMO_SYNTHETIC,
                    history_window=input_slice
                )
                predicted_val = pred_result.predicted_biogas_m3_day
                forecast_status = pred_result.status
                forecast_rec = pred_result.recommendation or forecast_rec
                domain_valid = pred_result.domain_valid
                domain_note = pred_result.domain_note
            else:
                forecast_status = "WARMING_UP"
                forecast_rec = f"Warming up forecast model ({history_len}/{warmup_days} timesteps accumulated)."
                domain_valid = True
                domain_note = "Accumulating initial continuous history."

            # Compute scale-compatible community predictions
            ema_val = round(float(0.90 * biogas_nm3 + 0.10 * np.mean([float(r["biogas_today_nm3"]) for r in history_buffer[-3:]])), 2) if len(history_buffer) >= 3 else None
            persistence_val = round(biogas_nm3, 2)

            # Target date is strictly t+1
            cur_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            target_dt_str = (cur_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            # Dynamic electricity calculations (LHV = 9.94 kWh/Nm3, Assumed Generator Efficiency = 30%)
            ch4_frac = float(row["methane_percent"]) / 100.0
            est_elec_kwh = round(biogas_nm3 * ch4_frac * 9.94 * 0.30, 2)
            avg_power_kw = round(est_elec_kwh / 24.0, 3)
            pred_elec_kwh = round(predicted_val * ch4_frac * 9.94 * 0.30, 2) if predicted_val is not None else None

            timeline.append({
                "day_index": i,
                "timestamp": ts_str,
                "date": cur_dt.strftime("%Y-%m-%d"),
                "target_date": target_dt_str,
                "temperature_c": round(temp_c, 2),
                "ambient_temperature_c": round(float(row["ambient_temperature_c"]), 2),
                "ph": round(ph_val, 2),
                "inlet_ph": round(float(row["inlet_ph"]), 2),
                "pressure_bar": round(float(row["pressure_bar"]), 3),
                "gas_flow_m3_day": round(float(row["gas_flow_m3_day"]), 2),
                "biogas_production_m3_day": round(biogas_nm3, 2),
                "biogas_today_nm3": round(biogas_nm3, 2),
                "actual_biogas_today_nm3": round(biogas_nm3, 2),
                "actual_next_day_nm3": None, # Populated below
                "estimated_electricity_kwh": est_elec_kwh,
                "predicted_electricity_kwh": pred_elec_kwh,
                "average_equivalent_power_kw": avg_power_kw,
                "generator_status": "NOT CONNECTED",
                "actual_next_day_electricity_kwh": None, # Populated below
                "methane_percent": round(float(row["methane_percent"]), 1),
                "co2_percent": round(float(row["co2_percent"]), 1),
                "feedstock_mass_kg": round(feed_kg, 1),
                "feedstock_type": str(row["feedstock_type"]),
                "solar_voltage_v": round(float(row["solar_voltage_v"]), 2),
                "solar_current_a": round(float(row["solar_current_a"]), 2),
                "solar_power_w": round(float(row["solar_power_w"]), 2),
                "battery_soc_percent": round(float(row["battery_soc_percent"]), 1),
                "solar_status": str(row["solar_status"]),
                "history_length": history_len,
                "history_available": history_available,
                "required_lookback": warmup_days,
                "warmup_ready": is_warmup_ready,
                "status": "SUCCESS" if is_warmup_ready else "Warming up forecast model",
                "status_label": "SUCCESS (Causal past-only)" if is_warmup_ready else "Warming up forecast model",
                "predicted_next_day_nm3": predicted_val,
                "ema_predicted_next_day_nm3": ema_val,
                "persistence_predicted_next_day_nm3": persistence_val,
                "domain_valid": domain_valid,
                "domain_note": domain_note,
                "unit": "Nm³/day",
                "model_name": "GRU-14d Residual",
                "model_version": "v1.0.0",
                "preprocessing_version": "v1.0.0-frozen-train",
                "data_source": ProvenanceEnum.DEMO_SYNTHETIC.value,
                "recommendation": forecast_rec,
                "features": item_features
            })

        # Second pass: attach actual_next_day values for time-series evaluation
        for idx in range(len(timeline)):
            if idx < len(timeline) - 1:
                timeline[idx]["actual_next_day_nm3"] = timeline[idx + 1]["biogas_today_nm3"]
                timeline[idx]["actual_next_day_electricity_kwh"] = timeline[idx + 1]["estimated_electricity_kwh"]

        self._timeline = timeline
        return timeline

    def verify_simulator_continuity(self, days: int = 180) -> Tuple[bool, Dict[str, Any]]:
        """
        Verifies that simulator timestamps strictly increase without duplicates,
        intervals are strictly 24 hours, and 14-day history is strictly continuous.
        """
        timeline = self.get_simulator_timeline(days=days)
        if len(timeline) < 14:
            return False, {"error": "Timeline has fewer than 14 days"}
        
        timestamps = [datetime.datetime.strptime(t["timestamp"], "%Y-%m-%d %H:%M:%S") for t in timeline]
        
        # Check strictly monotonic increasing with 24h delta
        for i in range(1, len(timestamps)):
            delta = timestamps[i] - timestamps[i - 1]
            if delta.total_seconds() != 86400:
                return False, {
                    "error": f"Inconsistent interval at index {i}: expected 86400s, got {delta.total_seconds()}s"
                }
            if timestamps[i] <= timestamps[i - 1]:
                return False, {
                    "error": f"Duplicate or non-increasing timestamp at index {i}"
                }

        # Check GRU input features present in first 14 days
        df = self.get_raw_dataframe(days=days)
        required_cols = [
            "biogas_production_m3_day", "feedstock_mass_kg", "temperature_c", "ph"
        ]
        for col in required_cols:
            if col not in df.columns or df[col].isnull().any():
                return False, {"error": f"Missing or null values in required column {col}"}

        first_ts = timeline[0]["timestamp"]
        last_ts = timeline[-1]["timestamp"]
        warmup_end_ts = timeline[13]["timestamp"]

        log_data = {
            "simulator_history_length": len(timeline),
            "warmup_buffer_length": 14,
            "forecast_input_history_length": 14,
            "first_timestamp": first_ts,
            "warmup_end_timestamp": warmup_end_ts,
            "last_timestamp": last_ts,
            "continuity_result": True,
            "required_lookback": 14,
            "provenance": ProvenanceEnum.DEMO_SYNTHETIC.value
        }
        return True, log_data

simulator_service = SimulatorService()

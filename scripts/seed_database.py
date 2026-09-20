#!/usr/bin/env python3
"""
Database Seeding Script
=======================
Seeds the local database with:
1. Default test device (DIGESTER_001)
2. Historical synthetic community AD telemetry (from ml/data/synthetic_community_ad.csv)
3. Initial solar telemetry metrics
4. A sample baseline model record
5. Initial next-day forecast and decision support advisory
"""

import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal, init_db
from backend.app.models.device import Device
from backend.app.models.sensor_reading import SensorReading
from backend.app.models.forecast import ForecastResult
from backend.app.models.model_run import ModelRun
from backend.app.models.alert import Alert
from backend.app.models.solar import SolarMetric
from backend.app.services.alert_service import evaluate_reading_for_alerts
from backend.app.services.decision_support import generate_operator_recommendation

def seed():
    print("Initializing database tables...")
    init_db()
    
    db: Session = SessionLocal()
    try:
        # 1. Register Default Device
        device = db.query(Device).filter(Device.id == "DIGESTER_001").first()
        if not device:
            print("Registering device DIGESTER_001...")
            device = Device(
                id="DIGESTER_001",
                name="Community Digester Alpha",
                location="Sholinganallur Green Energy Center",
                status="ONLINE",
                mode="DEMO",
                last_seen=datetime.now(timezone.utc)
            )
            db.add(device)
            db.commit()
            
        # 2. Ingest Synthetic AD Telemetry
        csv_path = "ml/data/synthetic_community_ad.csv"
        if os.path.exists(csv_path):
            existing_count = db.query(SensorReading).filter(SensorReading.device_id == "DIGESTER_001").count()
            if existing_count == 0:
                print(f"Loading synthetic telemetry from {csv_path}...")
                df = pd.read_csv(csv_path)
                readings = []
                for _, row in df.iterrows():
                    ts = datetime.strptime(str(row["timestamp"]), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    reading = SensorReading(
                        device_id="DIGESTER_001",
                        timestamp=ts,
                        temperature_c=float(row["temperature_c"]) if pd.notnull(row["temperature_c"]) else None,
                        ambient_temperature_c=float(row["ambient_temperature_c"]) if pd.notnull(row["ambient_temperature_c"]) else None,
                        ph=float(row["ph"]) if pd.notnull(row["ph"]) else None,
                        inlet_ph=float(row["inlet_ph"]) if pd.notnull(row["inlet_ph"]) else None,
                        pressure_bar=float(row["pressure_bar"]) if pd.notnull(row["pressure_bar"]) else None,
                        gas_flow_m3_day=float(row["gas_flow_m3_day"]) if pd.notnull(row["gas_flow_m3_day"]) else None,
                        biogas_production_m3_day=float(row["biogas_production_m3_day"]) if pd.notnull(row["biogas_production_m3_day"]) else None,
                        methane_percent=float(row["methane_percent"]) if pd.notnull(row["methane_percent"]) else None,
                        co2_percent=float(row["co2_percent"]) if pd.notnull(row["co2_percent"]) else None,
                        h2s_ppm=float(row["h2s_ppm"]) if pd.notnull(row["h2s_ppm"]) else None,
                        feedstock_mass_kg=float(row["feedstock_mass_kg"]) if pd.notnull(row["feedstock_mass_kg"]) else None,
                        feedstock_type=str(row["feedstock_type"]) if pd.notnull(row["feedstock_type"]) else None,
                        agitator_runtime_min=float(row["agitator_runtime_min"]) if pd.notnull(row["agitator_runtime_min"]) else None,
                        source="synthetic"
                    )
                    readings.append(reading)
                    
                    # Also seed solar metrics from the synthetic row
                    solar = SolarMetric(
                        device_id="DIGESTER_001",
                        timestamp=ts,
                        solar_voltage_v=float(row["solar_voltage_v"]) if pd.notnull(row["solar_voltage_v"]) else None,
                        solar_current_a=float(row["solar_current_a"]) if pd.notnull(row["solar_current_a"]) else None,
                        solar_power_w=float(row["solar_power_w"]) if pd.notnull(row["solar_power_w"]) else None,
                        battery_voltage_v=float(row["battery_voltage_v"]) if pd.notnull(row["battery_voltage_v"]) else None,
                        battery_soc_percent=float(row["battery_soc_percent"]) if pd.notnull(row["battery_soc_percent"]) else None,
                        system_load_current_ma=float(row["system_load_current_ma"]) if pd.notnull(row["system_load_current_ma"]) else None,
                        system_load_power_w=float(row["system_load_power_w"]) if pd.notnull(row["system_load_power_w"]) else None,
                        solar_status=str(row["solar_status"]) if pd.notnull(row["solar_status"]) else "NORMAL"
                    )
                    db.add(solar)
                
                db.bulk_save_objects(readings)
                db.commit()
                print(f"Inserted {len(readings)} historical sensor readings & solar records.")
                
                # Check for any alerts on recent readings
                for r in readings[-10:]:
                    evaluate_reading_for_alerts(db, r)
                db.commit()
            else:
                print(f"Device DIGESTER_001 already has {existing_count} readings. Skipping telemetry insert.")
        
        # 3. Seed Sample Registered Model
        model = db.query(ModelRun).filter(ModelRun.model_name == "Ridge_Baseline").first()
        if not model:
            print("Registering baseline model record...")
            model = ModelRun(
                model_name="Ridge_Baseline",
                model_type="baseline",
                version="v1.0.0",
                dataset_source="synthetic_community_ad",
                mae=0.28,
                rmse=0.41,
                r2=0.86,
                nnse=0.84,
                hyperparameters='{"alpha": 1.0, "fit_intercept": true}',
                feature_list='["feedstock_mass_kg", "ph", "temperature_c", "lag_biogas_1d", "lag_biogas_2d"]'
            )
            db.add(model)
            db.commit()
            
        # 4. Seed Sample Next-Day Forecast
        forecast = db.query(ForecastResult).filter(ForecastResult.device_id == "DIGESTER_001").first()
        if not forecast:
            print("Creating sample next-day forecast...")
            now = datetime.now(timezone.utc)
            rec = generate_operator_recommendation(
                predicted_yield=3.45,
                current_temp=35.4,
                current_ph=7.35,
                recent_yield=3.20,
                feedstock_mass=65.0
            )
            forecast = ForecastResult(
                device_id="DIGESTER_001",
                timestamp=now,
                target_date=now + timedelta(days=1),
                predicted_biogas_m3_day=3.45,
                lower_bound_m3_day=3.10,
                upper_bound_m3_day=3.80,
                model_name="Ridge_Baseline",
                model_version="v1.0.0",
                top_feature_1="feedstock_mass_kg (+0.42 m3)",
                top_feature_2="lag_biogas_1d (+0.31 m3)",
                top_feature_3="temperature_c (+0.12 m3)",
                recommendation=rec
            )
            db.add(forecast)
            db.commit()
            print("Sample forecast created.")

        print("Database seeding completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed()

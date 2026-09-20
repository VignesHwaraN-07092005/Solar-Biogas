#!/usr/bin/env python3
"""
First-Principles Synthetic Anaerobic Digestion (AD) Dataset Generator
===================================================================
Project: Biogas Intelligence Platform
Module: First-Principles Synthetic Anaerobic Digestion Simulator

Generates physically and biologically realistic time-series data for a
small/community-scale anaerobic digester (1-5 m3 volume, 30-150 kg/day feed).

Every record generated is explicitly marked with:
  source = "synthetic"

Models:
- Feedstock loading and Volatile Solids (VS) conversion
- Anaerobic microbial kinetics (mesophilic regime, modified Hill/Monod lag)
- Acidogenesis/methanogenesis pH dynamics
- Environmental & slurry temperature interactions
- Headspace gas pressure and gas flow
- Solar PV generation and battery storage state-of-charge
- Operational disturbances (shock loading, acidification, temperature dip)
"""

import argparse
import datetime
import math
import os
import numpy as np
import pandas as pd

def generate_ad_timeseries(
    days: int = 180,
    sampling_hours: int = 24,
    reactor_volume_m3: float = 3.0,
    seed: int = 42,
    include_disturbances: bool = True
) -> pd.DataFrame:
    """
    Simulate anaerobic digestion time-series over a specified duration.
    """
    np.random.seed(seed)
    
    start_date = datetime.datetime(2026, 1, 1, 0, 0, 0)
    total_steps = (days * 24) // sampling_hours
    
    records = []
    
    # Initial state variables
    digester_temp = 35.5 # degrees C (mesophilic optimum)
    digester_ph = 7.45
    internal_substrate_pool = 80.0 # kg VS inside reactor
    methanogen_activity = 0.95
    battery_soc = 85.0 # percent
    
    # Disturbance schedules (day indices)
    acid_shock_days = [40, 41, 110, 111] if include_disturbances else []
    temp_drop_days = [75, 76, 77] if include_disturbances else []
    underfeed_days = [140, 141, 142] if include_disturbances else []
    
    for step in range(total_steps):
        current_time = start_date + datetime.timedelta(hours=step * sampling_hours)
        day_of_year = current_time.timetuple().tm_yday
        hour_of_day = current_time.hour
        current_day = step * sampling_hours // 24
        
        # 1. Environmental Conditions
        # Ambient temperature seasonal cycle + diurnal cycle
        seasonal_temp = 28.0 + 5.0 * math.sin(2 * math.pi * (day_of_year - 80) / 365)
        diurnal_temp = 4.0 * math.sin(2 * math.pi * (hour_of_day - 9) / 24)
        ambient_temp = round(seasonal_temp + diurnal_temp + np.random.normal(0, 0.8), 2)
        
        # Solar Irradiance & PV generation (0 at night, peak around noon)
        if 6 <= hour_of_day <= 18:
            solar_zenith_factor = math.sin(math.pi * (hour_of_day - 6) / 12)
            solar_voltage = round(18.0 + 3.0 * solar_zenith_factor + np.random.normal(0, 0.3), 2)
            solar_current = round(2.5 * solar_zenith_factor + np.random.normal(0, 0.1), 2)
            solar_current = max(0.0, solar_current)
            solar_power = round(solar_voltage * solar_current, 2)
            solar_status = "CHARGING"
            battery_soc = min(100.0, battery_soc + solar_current * 1.5 * (sampling_hours / 24))
        else:
            solar_voltage = round(max(0.0, np.random.normal(0.5, 0.2)), 2)
            solar_current = 0.0
            solar_power = 0.0
            solar_status = "NORMAL"
            # Battery discharge for ESP32 + sensors (~180 mA load)
            battery_soc = max(15.0, battery_soc - 0.8 * (sampling_hours / 24))
        
        system_load_current = round(180.0 + np.random.normal(0, 10.0), 1) # mA
        system_load_power = round(5.0 * (system_load_current / 1000.0), 2) # Watts
        battery_voltage = round(11.8 + (battery_soc / 100.0) * 1.2, 2)
        
        # 2. Feedstock Loading
        # Base feeding mass: ~60 kg/day (co-digestion of food waste, vegetable waste, cow dung)
        base_mass = 60.0 + 15.0 * math.sin(2 * math.pi * current_day / 7) # weekly variation
        if current_day in acid_shock_days:
            feedstock_mass = base_mass * 2.2 # Shock organic overload
            feedstock_type = "food_waste" # high volatile fatty acid risk
            inlet_ph = round(4.8 + np.random.normal(0, 0.1), 2)
        elif current_day in underfeed_days:
            feedstock_mass = base_mass * 0.2 # starvation
            feedstock_type = "cow_dung"
            inlet_ph = round(6.8 + np.random.normal(0, 0.1), 2)
        else:
            feedstock_mass = max(20.0, base_mass + np.random.normal(0, 5.0))
            feedstock_type = "co_digestion"
            inlet_ph = round(6.2 + np.random.normal(0, 0.15), 2)
        feedstock_mass = round(feedstock_mass, 2)
        
        # Organic fraction and solids
        ts_percent = round(10.5 + np.random.normal(0, 0.5), 2) # 10.5% Total Solids
        vs_percent = round(80.0 + np.random.normal(0, 1.5), 2) # 80% Volatile Solids of TS
        daily_vs_kg = feedstock_mass * (ts_percent / 100.0) * (vs_percent / 100.0)
        
        # 3. Reactor Thermal State
        # Heating element regulates to 35C unless a heater fault occurs
        if current_day in temp_drop_days:
            digester_temp = max(24.0, digester_temp - 0.8) # Thermal loss
        else:
            # Gentle thermostatic adjustment toward 35.5C
            digester_temp += 0.3 * (35.5 - digester_temp) + np.random.normal(0, 0.15)
        digester_temp = round(digester_temp, 2)
        
        # Temperature kinetic factor (Arrhenius / Ratkowsky mesophilic bell curve)
        # Peak at 36-37C; drops sharply below 30C or above 45C
        temp_kinetic_factor = math.exp(-((digester_temp - 36.0) ** 2) / 32.0)
        
        # 4. pH and Biochemical State Dynamics
        # Overloading adds volatile acids -> pH drops; methanogens consume acids -> pH buffers
        vfa_accumulation = max(0.0, (daily_vs_kg - 5.0) * 0.12)
        if current_day in acid_shock_days:
            digester_ph = max(5.8, digester_ph - 0.35 + np.random.normal(0, 0.05))
            methanogen_activity = max(0.3, methanogen_activity - 0.2)
        else:
            # Natural buffering back to 7.45
            digester_ph += 0.15 * (7.45 - digester_ph) - vfa_accumulation * 0.05 + np.random.normal(0, 0.02)
            methanogen_activity = min(1.0, methanogen_activity + 0.08)
        digester_ph = round(digester_ph, 2)
        
        # pH inhibition factor (methanogenesis inhibited if pH < 6.6 or pH > 8.2)
        ph_factor = 1.0 / (1.0 + math.exp(-6.0 * (digester_ph - 6.6))) * (1.0 / (1.0 + math.exp(6.0 * (digester_ph - 8.2))))
        
        # 5. Biogas Generation Dynamics
        # Substrate enters pool; methanogens convert pool to biogas with kinetic lag
        internal_substrate_pool += daily_vs_kg
        biokinetic_rate = 0.18 * temp_kinetic_factor * ph_factor * methanogen_activity
        substrate_digested_kg = internal_substrate_pool * biokinetic_rate
        internal_substrate_pool = max(10.0, internal_substrate_pool - substrate_digested_kg)
        
        # Specific Biogas Yield (~0.55 m3 biogas per kg VS digested)
        gross_biogas_m3 = substrate_digested_kg * 0.55 + np.random.normal(0, 0.08)
        gross_biogas_m3 = max(0.1, round(gross_biogas_m3, 3))
        
        # Methane and CO2 fractions
        methane_pct = round(60.0 * ph_factor * temp_kinetic_factor + np.random.normal(0, 1.0), 1)
        methane_pct = min(72.0, max(42.0, methane_pct))
        co2_pct = round(100.0 - methane_pct - 1.5, 1)
        h2s_ppm = round(120.0 + 30.0 * math.sin(current_day / 10.0) + np.random.normal(0, 10.0), 1)
        
        # Pressure & Flow
        gas_pressure_bar = round(1.15 + (gross_biogas_m3 / 8.0) * 0.2 + np.random.normal(0, 0.02), 3)
        gas_flow_rate = round(gross_biogas_m3, 3) # m3/day rate
        
        # Agitation
        agitator_min = round(240.0 + np.random.normal(0, 15.0), 0)
        
        # Build record
        record = {
            "device_id": "DIGESTER_001",
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "temperature_c": digester_temp,
            "ambient_temperature_c": ambient_temp,
            "ph": digester_ph,
            "inlet_ph": inlet_ph,
            "pressure_bar": gas_pressure_bar,
            "gas_flow_m3_day": gas_flow_rate,
            "biogas_production_m3_day": gross_biogas_m3,
            "methane_percent": methane_pct,
            "co2_percent": co2_pct,
            "h2s_ppm": h2s_ppm,
            "feedstock_mass_kg": feedstock_mass,
            "feedstock_type": feedstock_type,
            "total_solids_percent": ts_percent,
            "volatile_solids_percent": vs_percent,
            "agitator_runtime_min": agitator_min,
            "solar_voltage_v": solar_voltage,
            "solar_current_a": solar_current,
            "solar_power_w": solar_power,
            "battery_voltage_v": battery_voltage,
            "battery_soc_percent": round(battery_soc, 1),
            "system_load_current_ma": system_load_current,
            "system_load_power_w": system_load_power,
            "solar_status": solar_status,
            "source": "synthetic"
        }
        records.append(record)
        
    df = pd.DataFrame(records)
    return df

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic AD time-series dataset.")
    parser.add_argument("--days", type=int, default=180, help="Simulation duration in days (default: 180)")
    parser.add_argument("--interval", type=int, default=24, help="Sampling interval in hours (default: 24)")
    parser.add_argument("--volume", type=float, default=3.0, help="Reactor volume in m3 (default: 3.0)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--output", type=str, default="ml/data/synthetic_community_ad.csv", help="Output file path")
    parser.add_argument("--no-disturbances", action="store_true", help="Disable disturbance injection")
    
    args = parser.parse_args()
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    print(f"Simulating {args.days} days of community AD operations (interval={args.interval}h)...")
    df = generate_ad_timeseries(
        days=args.days,
        sampling_hours=args.interval,
        reactor_volume_m3=args.volume,
        seed=args.seed,
        include_disturbances=not args.no_disturbances
    )
    
    df.to_csv(args.output, index=False)
    print(f"Generated {len(df)} records -> Saved to {args.output}")
    print(f"Columns ({len(df.columns)}): {list(df.columns)}")
    print(f"Biogas yield range: {df['biogas_production_m3_day'].min():.2f} to {df['biogas_production_m3_day'].max():.2f} m3/day (Mean: {df['biogas_production_m3_day'].mean():.2f})")
    print(f"pH range: {df['ph'].min():.2f} to {df['ph'].max():.2f} (Mean: {df['ph'].mean():.2f})")
    print(f"Temperature range: {df['temperature_c'].min():.2f} to {df['temperature_c'].max():.2f} C (Mean: {df['temperature_c'].mean():.2f})")
    print("Verification: Every record tagged with source = 'synthetic'")

if __name__ == "__main__":
    main()

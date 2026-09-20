from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from backend.app.database import get_db
from backend.app.models.sensor_reading import SensorReading
from backend.app.schemas.energy import (
    GeneratorSpec,
    EnergyCalculationRequest,
    EnergyCalculationResponse,
    CommunityDemandProfile,
    HourlyBalanceEntry,
    EnergyBalanceResponse,
)

router = APIRouter(prefix="/api/energy", tags=["Energy Management"])

CONVERSION_FACTORS = {
    "pure_ch4_lhv_kwh_per_nm3": 9.94,
    "pure_ch4_lhv_mj_per_m3": 35.8,
    "conversion_formula": "E (kWh) = Biogas_Volume (Nm³) * (CH4% / 100) * 9.94 kWh/Nm³ * Electrical_Efficiency",
    "power_formula": "24-h Average Equivalent Power (kW) = E (kWh) / 24 h",
}

@router.get("/config")
def get_energy_configuration() -> Dict[str, Any]:
    """
    Returns baseline configuration for energy generation and illustrative community demand.
    """
    return {
        "generator": GeneratorSpec().model_dump(),
        "community_demand": CommunityDemandProfile().model_dump(),
        "conversion_factors": CONVERSION_FACTORS,
    }

@router.post("/calculate", response_model=EnergyCalculationResponse)
def calculate_energy(req: EnergyCalculationRequest):
    """
    Dynamically calculates calorific content, electricity potential, and 24-h average equivalent power.
    """
    ch4_fraction = req.methane_percent / 100.0
    lhv_factor = CONVERSION_FACTORS["pure_ch4_lhv_kwh_per_nm3"]
    calorific_energy = req.biogas_volume_m3 * ch4_fraction * lhv_factor
    electricity_potential = calorific_energy * req.efficiency
    continuous_power = electricity_potential / 24.0

    fuel_rate = (
        1.0 / (ch4_fraction * lhv_factor * req.efficiency)
        if (ch4_fraction * lhv_factor * req.efficiency) > 0
        else 0.0
    )

    return EnergyCalculationResponse(
        biogas_volume_m3=round(req.biogas_volume_m3, 3),
        methane_percent=round(req.methane_percent, 1),
        efficiency_used=round(req.efficiency, 3),
        calorific_energy_lhv_kwh=round(calorific_energy, 3),
        electricity_potential_kwh=round(electricity_potential, 3),
        continuous_power_kw=round(continuous_power, 4),
        fuel_consumption_rate_m3_per_kwh=round(fuel_rate, 3),
        provenance="[CALCULATED]",
        continuous_power_label="24-h Average Equivalent Power",
        calculation_formula="E = V_biogas * (CH4% / 100) * 9.94 kWh/Nm³ * η_elec",
    )

@router.get("/generation/current")
def get_current_generation(
    device_id: Optional[str] = Query(None),
    efficiency: float = Query(0.30, ge=0.10, le=0.60),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns current calculated generation potential from active telemetry.
    Generator status is strictly NOT CONNECTED.
    """
    query = db.query(SensorReading)
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)
    latest = query.order_by(SensorReading.timestamp.desc()).first()

    spec = GeneratorSpec(default_electrical_efficiency=efficiency)

    if not latest or latest.biogas_production_m3_day is None:
        return {
            "generator_specification": spec.model_dump(),
            "biogas_production_m3_day": None,
            "methane_percent": None,
            "calorific_energy_lhv_kwh": None,
            "electricity_potential_kwh": None,
            "continuous_power_kw": None,
            "continuous_power_label": "24-h Average Equivalent Power",
            "provenance": "[CALCULATED]",
            "timestamp": None,
        }

    biogas = float(latest.biogas_production_m3_day)
    methane = float(latest.methane_percent) if latest.methane_percent is not None else 60.0
    ch4_fraction = methane / 100.0
    lhv = biogas * ch4_fraction * CONVERSION_FACTORS["pure_ch4_lhv_kwh_per_nm3"]
    elec = lhv * efficiency
    power = elec / 24.0

    return {
        "generator_specification": spec.model_dump(),
        "biogas_production_m3_day": round(biogas, 3),
        "methane_percent": round(methane, 1),
        "calorific_energy_lhv_kwh": round(lhv, 3),
        "electricity_potential_kwh": round(elec, 3),
        "continuous_power_kw": round(power, 4),
        "continuous_power_label": "24-h Average Equivalent Power",
        "provenance": "[CALCULATED]" if latest.methane_percent is not None else "[CALCULATED @ ASSUMED 60% CH₄]",
        "timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
    }

@router.get("/community/balance", response_model=EnergyBalanceResponse)
def get_community_energy_balance(
    daily_demand_kwh: float = Query(5.20, ge=0.1, le=10000.0),
    biogas_volume_m3: Optional[float] = Query(None, ge=0.0),
    methane_percent: float = Query(60.0, ge=0.0, le=100.0),
    efficiency: float = Query(0.30, ge=0.10, le=0.60),
    db: Session = Depends(get_db),
):
    """
    Computes community energy supply vs demand balance and 24-hour diurnal profile.
    Daily demand is an illustrative prototype configuration.
    """
    if biogas_volume_m3 is None:
        latest = db.query(SensorReading).order_by(SensorReading.timestamp.desc()).first()
        if latest and latest.biogas_production_m3_day is not None:
            biogas_volume_m3 = float(latest.biogas_production_m3_day)
            if latest.methane_percent is not None:
                methane_percent = float(latest.methane_percent)
        else:
            biogas_volume_m3 = 3.40  # default community simulation reference

    ch4_fraction = methane_percent / 100.0
    elec_kwh = biogas_volume_m3 * ch4_fraction * 9.94 * efficiency
    continuous_power = elec_kwh / 24.0

    profile = CommunityDemandProfile(daily_demand_kwh=daily_demand_kwh)
    hourly_entries = []
    hourly_gen = continuous_power  # 1 hour at continuous power = continuous_power kWh

    for h in range(24):
        weight = profile.hourly_distribution[h]
        d_kwh = round(daily_demand_kwh * weight, 4)
        g_kwh = round(hourly_gen, 4)
        net = round(g_kwh - d_kwh, 4)
        time_str = f"{h:02d}:00"
        hourly_entries.append(
            HourlyBalanceEntry(
                hour=h,
                time_label=time_str,
                demand_kwh=d_kwh,
                generation_potential_kwh=g_kwh,
                net_kwh=net,
                is_surplus=(net >= 0.0),
            )
        )

    coverage = min(100.0, round((elec_kwh / daily_demand_kwh) * 100.0, 1)) if daily_demand_kwh > 0 else 0.0
    net_bal = round(elec_kwh - daily_demand_kwh, 3)

    return EnergyBalanceResponse(
        daily_demand_kwh=round(daily_demand_kwh, 2),
        electricity_potential_kwh=round(elec_kwh, 3),
        coverage_percent=coverage,
        net_balance_kwh=net_bal,
        continuous_power_kw=round(continuous_power, 4),
        continuous_power_label="24-h Average Equivalent Power",
        hourly_balance=hourly_entries,
        provenance="[CALCULATED]",
        demand_label="Illustrative Prototype Community Demand — Configurable",
        hardware_status="NOT CONNECTED",
    )

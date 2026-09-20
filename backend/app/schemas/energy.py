from pydantic import BaseModel, Field
from typing import List, Optional

class GeneratorSpec(BaseModel):
    name: str = "Biogas Engine-Generator Unit (Illustrative Specification)"
    status: str = "NOT CONNECTED"
    runtime_hours: str = "N/A"
    rated_power_kw: float = 5.0
    fuel_type: str = "Conditioned Biogas (CH4 + CO2)"
    default_electrical_efficiency: float = 0.30
    min_electrical_efficiency: float = 0.20
    max_electrical_efficiency: float = 0.45
    efficiency_label: str = "Assumed / Configurable Generator Electrical Efficiency"
    hardware_note: str = (
        "No physical generator hardware integrated in current prototype. "
        "Electricity potential is calculated dynamically from biogas yield and methane concentration."
    )

class EnergyCalculationRequest(BaseModel):
    biogas_volume_m3: float = Field(..., ge=0.0, description="Biogas volume in m3 or Nm3")
    methane_percent: float = Field(default=60.0, ge=0.0, le=100.0, description="Methane volume percentage")
    efficiency: float = Field(default=0.30, ge=0.10, le=0.60, description="Assumed generator electrical efficiency")

class EnergyCalculationResponse(BaseModel):
    biogas_volume_m3: float
    methane_percent: float
    efficiency_used: float
    calorific_energy_lhv_kwh: float
    electricity_potential_kwh: float
    continuous_power_kw: float
    fuel_consumption_rate_m3_per_kwh: float
    provenance: str = "[CALCULATED]"
    continuous_power_label: str = "24-h Average Equivalent Power"
    calculation_formula: str = "E = V_biogas * (CH4% / 100) * 9.94 kWh/Nm3 * eta_elec"

class CommunityDemandProfile(BaseModel):
    name: str = "Illustrative Prototype Community Demand"
    daily_demand_kwh: float = 5.20
    is_configurable_illustrative_default: bool = True
    demand_label: str = "Illustrative Prototype Community Demand — Configurable"
    hourly_distribution: List[float] = [
        0.025, 0.020, 0.015, 0.015, 0.020, 0.035,
        0.055, 0.065, 0.060, 0.045, 0.040, 0.035,
        0.035, 0.035, 0.035, 0.040, 0.045, 0.055,
        0.080, 0.090, 0.085, 0.070, 0.045, 0.035
    ]

class HourlyBalanceEntry(BaseModel):
    hour: int
    time_label: str
    demand_kwh: float
    generation_potential_kwh: float
    net_kwh: float
    is_surplus: bool

class EnergyBalanceResponse(BaseModel):
    daily_demand_kwh: float
    electricity_potential_kwh: float
    coverage_percent: float
    net_balance_kwh: float
    continuous_power_kw: float
    continuous_power_label: str = "24-h Average Equivalent Power"
    hourly_balance: List[HourlyBalanceEntry]
    provenance: str = "[CALCULATED]"
    demand_label: str = "Illustrative Prototype Community Demand — Configurable"
    hardware_status: str = "NOT CONNECTED"

# DATA DICTIONARY SPECIFICATION

**Project Title:** AI-Driven Solar-Biogas System for Sustainable Communities  
**Team:** Espada  
**Document Version:** 1.0 (Definitive Standard)  
**Date:** September 14, 2026  

---

## 1. Overview & Data Philosophy

The data dictionary defines the complete schema for all telemetry, process variables, solar monitoring metrics, model features, and prediction outputs used in the platform.
The architecture explicitly supports:
1. **Missing / Optional Fields:** Sensors may fail or be absent in low-cost installations; algorithms must not expect every field to be populated. Missing values are represented as `null`/`NaN` rather than dummy zeros.
2. **Measurement Attribution:** Every field specifies whether it is **Measured** (direct hardware sensor), **Calculated** (deterministic arithmetic/stoichiometric formula), or **Predicted** (ML inference).
3. **Multi-scale Compatibility:** Accommodates both small community digesters ($m^3/day$, $kg/day$) and industrial facilities ($Nm^3/day$, $MT/day$).

---

## 2. Core Operational & Sensor Telemetry Dictionary

| Field Name | Description | Engineering Unit | Data Type | Expected Range | Measurement Type | Data Source | Nullable? |
|---|---|---|---|---|---|---|---|
| `timestamp` | UTC ISO-8601 observation timestamp | YYYY-MM-DDTHH:MM:SSZ | String / DateTime | Valid timestamp | System Generated | ESP32 RTC / Server NTP | No |
| `device_id` | Unique hardware identifier of monitoring node | Dimensionless | String (Varchar 64)| `DIGESTER_001` - `999`| System Metadata | Firmware Config | No |
| `source` | Telemetry origin mode | Enum | String | `live_esp32`, `synthetic`, `research_spark` | System Tag | System Flag | No |
| `digester_temperature_c` | Anaerobic digester slurry core temperature | Degrees Celsius (°C) | Float | $15.0 - 55.0$ (Mesophilic opt: $35-38$) | Measured | DS18B20 / RTD probe | Yes |
| `ambient_temperature_c` | Outside ambient air temperature | Degrees Celsius (°C) | Float | $5.0 - 50.0$ | Measured / Virtual | DHT22 / Weather API | Yes |
| `ph` | Reactor slurry acidity/alkalinity | pH scale ($0-14$) | Float | $5.5 - 8.5$ (Optimal: $7.2-7.8$) | Measured | Analog glass pH electrode | Yes |
| `inlet_ph` | Freshly fed substrate slurry pH | pH scale ($0-14$) | Float | $4.0 - 7.5$ | Measured | Laboratory / In-line pH | Yes |
| `digester_pressure` | Headspace biogas gauge pressure | Bar ($10^5\text{ Pa}$) or kPa | Float | $0.0 - 2.5\text{ bar}$ ($0-250\text{ kPa}$) | Measured | MPX5010DP Transducer | Yes |
| `gas_flow_m3_day` | Cumulative or instantaneous biogas flow | $m^3/day$ (or $Nm^3/day$) | Float | $0.1 - 25.0$ (comm.) / $0-15000$ (ind.) | Measured | Pulse flowmeter / Orifice | Yes |
| `biogas_production_m3_day`| Total gross daily biogas generated | $m^3/day$ (or $Nm^3/day$) | Float | $0.1 - 25.0$ (comm.) / $0-15000$ (ind.) | Calculated / Measured | Flowmeter summation | Yes |
| `feedstock_mass_kg` | Total daily substrate mass loaded | Kilograms ($kg/day$) or MT | Float | $5.0 - 500.0\text{ kg}$ (comm.) | Measured | Weighbridge / Load Cell | Yes |
| `feedstock_type` | Primary organic waste category | Categorical / Enum | String | `food_waste`, `cow_dung`, `vegetable_waste`, `co_digestion` | Metadata / Manual | Operator entry | Yes |
| `moisture_percent` | Moisture content of organic feed | Percentage (%) | Float | $60.0 - 95.0$ | Measured / Estimated | Lab drying oven / Near-IR | Yes |
| `total_solids_percent` | Total Solids (TS) content in slurry | Percentage (%) | Float | $4.0 - 15.0$ | Measured / Estimated | Gravimetric laboratory test | Yes |
| `volatile_solids_percent`| Volatile Solids (VS) fraction of TS | Percentage (%) of TS | Float | $65.0 - 92.0$ | Measured / Estimated | Muffle furnace combustion | Yes |
| `organic_loading_rate` | Volumetric loading rate ($OLR$) | $kg\text{ }VS / m^3 \cdot day$ | Float | $0.5 - 6.0$ | Calculated | $OLR = \frac{\text{Feed }VS}{\text{Reactor Vol}}$ | Yes |
| `hydraulic_retention_time`| Average fluid residence time ($HRT$) | Days | Float | $15.0 - 60.0$ | Calculated | $HRT = \frac{\text{Reactor Vol}}{\text{Daily Inflow}}$ | Yes |
| `agitator_runtime_min` | Daily mechanical slurry mixing duration | Minutes/day | Float | $0.0 - 1440.0$ (Typically $180-480$) | Measured / Logged | Agitator motor relay state | Yes |
| `methane_percent` | Methane ($CH_4$) gas concentration | Volume Percentage (%) | Float | $45.0 - 75.0$ (Typically $55-65$) | Measured | NDIR Infrared gas sensor | Yes |
| `carbon_dioxide_percent`| Carbon Dioxide ($CO_2$) concentration | Volume Percentage (%) | Float | $25.0 - 50.0$ (Typically $35-42$) | Measured | NDIR Infrared gas sensor | Yes |
| `h2s_ppm` | Toxic Hydrogen Sulfide concentration | Parts per Million (ppm) | Float | $10.0 - 4000.0$ | Measured | Electrochemical sensor | Yes |
| `operational_status` | Current physical state of digester | Enum | String | `OPTIMAL`, `SUB_OPTIMAL`, `ACIDIFIED`, `OVERPRESSURE`, `MAINTENANCE` | Calculated | Rule engine | No |

---

## 3. Solar Telemetry & Battery Monitoring Dictionary

| Field Name | Description | Engineering Unit | Data Type | Expected Range | Measurement Type | Data Source | Nullable? |
|---|---|---|---|---|---|---|---|
| `solar_voltage_v` | Open-circuit / operating PV panel voltage | Volts (V) | Float | $0.0 - 22.0$ | Measured | INA219 / Resistor divider | Yes |
| `solar_current_a` | PV panel current delivered to controller | Amperes (A) | Float | $0.0 - 4.5$ | Measured | INA219 Hall-effect sensor | Yes |
| `solar_power_w` | Instantaneous solar power output | Watts (W) | Float | $0.0 - 55.0$ | Calculated | $P = V_{solar} \times I_{solar}$ | Yes |
| `battery_voltage_v` | Terminal voltage of 12V storage battery | Volts (V) | Float | $10.5 - 14.6$ | Measured | INA219 DC bus reading | Yes |
| `battery_soc_percent` | Estimated Battery State-of-Charge | Percentage (%) | Float | $0.0 - 100.0$ (Cutoff at $20\%$) | Calculated | Coulomb counting / OCV curve| Yes |
| `system_load_current_ma`| Current consumed by ESP32 + sensors | Milliamperes (mA) | Float | $80.0 - 450.0$ | Measured | Shunt resistor on 5V rail | Yes |
| `system_load_power_w` | Power consumed by monitoring subsystem | Watts (W) | Float | $0.4 - 2.5$ | Calculated | $P = V_{bus} \times I_{load}$ | Yes |
| `solar_status` | Power subsystem health state | Enum | String | `NORMAL`, `CHARGING`, `LOW_BATTERY`, `NIGHT_DISCHARGE` | Calculated | Rule engine | No |

---

## 4. Machine Learning & Forecasting Data Dictionary

| Field Name | Description | Engineering Unit | Data Type | Expected Range | Measurement Type | Data Source | Nullable? |
|---|---|---|---|---|---|---|---|
| `forecast_target` | Quantity being predicted | Label | String | `next_day_biogas_production` | Metadata | Pipeline definition | No |
| `predicted_biogas_m3_day`| Predicted biogas output for day $t+1$ | $m^3/day$ | Float | $0.0 - 30.0$ (comm.) / $0-15000$ (ind.) | Predicted | ML Model Inference | No |
| `lower_bound_m3_day` | 90% confidence interval lower bound | $m^3/day$ | Float | $\ge 0.0$ | Predicted | Residual quantile | Yes |
| `upper_bound_m3_day` | 90% confidence interval upper bound | $m^3/day$ | Float | $\ge 0.0$ | Predicted | Residual quantile | Yes |
| `model_name` | Name of model generating forecast | String | String | `Ridge`, `RandomForest`, `XGBoost`, `LSTM`, `GRU`, `XCO-Net` | Metadata | Model registry | No |
| `model_version` | Semantic version string of model | String | String | `v1.0.0`, `v1.1.0` | Metadata | Model artifact | No |
| `top_influencing_feature_1`| Feature with highest SHAP attribution | String | String | E.g. `feedstock_mass_kg`, `ph` | Calculated | SHAP explainer | Yes |
| `top_influencing_feature_2`| Feature with 2nd highest SHAP attribution| String | String | E.g. `lag_biogas_1d`, `temperature`| Calculated | SHAP explainer | Yes |
| `decision_recommendation` | Natural-language operator guidance | Text | String | Actionable plain-text sentence | Calculated | Decision support rule | Yes |

---

## 5. Alerts & System Events Dictionary

| Field Name | Description | Engineering Unit | Data Type | Expected Range | Measurement Type | Data Source | Nullable? |
|---|---|---|---|---|---|---|---|
| `alert_id` | Unique identifier for system event | UUID / Int | String / Integer | Sequential / UUID | System Generated | Alert Manager | No |
| `severity` | Alert criticality level | Enum | String | `INFO`, `WARNING`, `CRITICAL` | Metadata | Threshold Rule | No |
| `parameter` | Physical metric triggering alert | String | String | `ph`, `temperature`, `pressure`, `battery` | Metadata | Alert Manager | No |
| `triggered_value` | Actual sensor value that triggered alert | Variable | Float | Out-of-bounds number | Measured | Sensor Telemetry | No |
| `threshold_limit` | Boundary breached | Variable | Float | Configured threshold | Configuration | Alert Policy | No |
| `message` | Human-readable alert summary | Text | String | Clear explanation of risk | Template | Alert Rule | No |
| `is_acknowledged` | Operator acknowledgment status | Boolean | Boolean | `true`, `false` | Interaction | Dashboard UI | No |

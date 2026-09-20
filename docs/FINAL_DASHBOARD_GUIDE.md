# AI-Driven Solar-Biogas Platform — User, Operator & Judge Guide
**IEEE YESIST12 Innovation Challenge | Team Espada | SDG 11: Sustainable Cities & Communities**

---

## 1. Platform Purpose & Domain Architecture

### The Real-World Mission
Anaerobic digestion is a circular bio-energy technology that converts municipal organic waste, livestock manure, and food scraps into clean biogas and organic bio-fertilizer. However, small-scale rural and colony digesters frequently suffer from biochemical failures—such as volatile fatty acid (VFA) acidosis, cold shock, and overpressure—because small communities lack dedicated chemical engineers and expensive SCADA systems.

The **AI-Driven Solar-Biogas Platform** addresses this challenge by providing an autonomous, explainable supervisory AI system with integrated solar thermal loop control and next-day production forecasting.

### Strict Domain Separation
A cornerstone of this platform's scientific rigor is the separation between its research training data and its community deployment target:

```
+-------------------------------------------------------------------------+
|                          THREE-DOMAIN ARCHITECTURE                      |
+-------------------------------------------------------------------------+
| 1. Industrial Research Domain                                           |
|    - Dataset: Real industrial Spark Bio Gas SCADA dataset               |
|    - Scale: ~5,300 Nm³/day biogas, ~100–200 MT/day feedstock            |
|    - Role: Offline model training, validation, and benchmarking         |
+-------------------------------------------------------------------------+
| 2. Community Deployment Demonstration Domain                            |
|    - Engine: Physics-based synthetic community digester simulator       |
|    - Scale: ~3.0–3.5 Nm³/day biogas, ~120 kg/day organic waste          |
|    - Role: Real-time dynamic demonstration of community deployment      |
+-------------------------------------------------------------------------+
| 3. Community Live IoT Hardware Domain (Phase Roadmap)                   |
|    - Hardware: ESP32 MCU + DS18B20 + pH + MPX5700DP + Gas Flow Sensor   |
|    - Scale: Decentralized community digester prototype                  |
|    - Role: Live operational deployment                                  |
+-------------------------------------------------------------------------+
```

> [!IMPORTANT]
> **Scientific Honesty Principle**: Industrial-scale neural networks trained on $\sim 5,300\text{ Nm}^3/\text{day}$ plants cannot be silently evaluated on a $3\text{ Nm}^3/\text{day}$ community digester without transfer validation. The platform makes domain boundaries completely transparent in the UI and APIs.

---

## 2. The 7 Sections of the Dashboard

The dashboard is structured into 7 distinct operational zones arranged logically from macro status to deep analytics:

```
+-------------------------------------------------------------------------+
| Section 1: Top Navigation Bar & Global Domain Badge                     |
+-------------------------------------------------------------------------+
| Section 2: Telemetry Playback, Source Selection & Model Selector        |
+-------------------------------------------------------------------------+
| Section 3: Four Primary Process KPIs (5-Second Operator Glance)         |
+-------------------------------------------------------------------------+
| Section 4: Primary Next-Day Forecast & Explainable AI Drivers           |
+-------------------------------------------------------------------------+
| Section 5: Biogas Production Timeseries (Target Date t+1, tension 0.0)  |
+-------------------------------------------------------------------------+
| Section 6: Secondary Analytics (Health Heuristic, Feedstock, CH4, Corr) |
+-------------------------------------------------------------------------+
| Section 7: Solar Thermal Telemetry, SDG 11 Impact & Research Modals     |
+-------------------------------------------------------------------------+
```

---

## 3. Telemetry Playback & Source Selection

### Operational Data Feeds
Operators and judges can switch between datasets in Section 2:
1. **Live Demo Feed (Physics Simulator — 180 Days, 14d Warm-Up)** (`DEMO_SYNTHETIC`):
   - Continuous 180-day community-scale scenario ($\approx 3\text{ Nm}^3/\text{day}$).
   - Default starts at Day 14 (Index 13) so 14-day history requirements are immediately satisfied.
2. **Spark Bio Gas — Official Held-Out Test (24 Days)** (`REAL_SPARK_HISTORICAL`):
   - Strictly causal replay of the official held-out test set (2026-03-10 to 2026-04-02).
   - Industrial magnitude ($\approx 5,300\text{ Nm}^3/\text{day}$).
3. **Spark Bio Gas — Industrial Historical (176 Calendar Days)** (`SPARK_FULL`):
   - Complete historical operational dataset (2025-11-01 to 2026-04-25).
4. **AgSTAR Livestock Digester Registry (526 Facilities)** (`AGSTAR_REGISTRY`):
   - Opens an informative modal detailing the EPA AgSTAR national reference database.

### Playback Controls
- **◀ Step Prev**: Decrements current evaluation record by 1 day.
- **Step Next ▶**: Advances current evaluation record by 1 day.
- **⏸ Auto Live Feed / ▶ Resume Feed**: Automatically steps forward every 2.5 seconds, cycling through the warmed-up evaluation window.
- **Ingest SCADA / Excel**: Ingests custom `.xlsx` or `.csv` files client-side via SheetJS without uploading private data to a server.

---

## 4. Primary Process KPIs (5-Second Overview)

Section 3 delivers instant situational awareness through 4 critical variables:
1. **Slurry Temperature (°C)**:
   - Target mesophilic window: $35.0^\circ\text{C} - 38.0^\circ\text{C}$ (optimum $36.5^\circ\text{C}$).
   - Temperatures below $35^\circ\text{C}$ inhibit methanogens; above $40^\circ\text{C}$ risk protein denaturation.
2. **Slurry pH Buffer (pH)**:
   - Target stability range: $6.80 - 7.50$.
   - A drop below $6.80$ signals volatile fatty acid (VFA) accumulation and impending digester soured/acidosis state.
3. **Gas Pressure (bar)**:
   - Normal operating envelope: $1.05 - 1.25\text{ bar}$.
   - Warning threshold: $1.30\text{ bar}$; Headspace safety relief activation: $1.50\text{ bar}$.
4. **Current Biogas Generation ($\text{Nm}^3/\text{day}$)**:
   - STP-normalized daily production ($0^\circ\text{C}, 1\text{ atm}$).
   - Dynamically annotated: `(~3 Nm³/day)` for community simulation, `(~5,300 Nm³/day)` for industrial Spark data.

---

## 5. Forecasting Pipeline & Domain Handling

### Strict Causal Alignment ($t \to t+1$)
- Inputs: Information available up to and including current day $t$ (strictly zero future leakage).
- Target Date: Day $t+1$.
- History Available / Required: Explicitly tracked on the metadata strip as `History Available / Required` (`14/14` for GRU and XCO-Net, `3/3` for EMA-0.90, `1/1` for Persistence).
- Model-Aware Causal Footer: Dynamically updates per model to state the exact causal lookback and guarantee zero lookahead leakage.
- Unified Safety Alerts: Gas pressure $\ge 1.30\text{ bar}$ generates a WARNING alert and triggers `HIGH WARNING` on the pressure gauge; pressure $\ge 1.50\text{ bar}$ triggers CRITICAL relief valve activation (`RELIEF ACTIVATED`). Both the KPI badge and the Safety & Alerts list consume this identical single source of truth.

### Scale-Aware Domain Behavior & Chart Integrity
When running on the **Community Physics Simulator** (`DEMO_SYNTHETIC`):
- **GRU-14d Residual & XCO-Net**:
  - The model executes successfully (`status: SUCCESS`), but reports `domain_valid: false`.
  - The prediction display shows: `Not Validated for Community Scale`.
  - An amber notice box explains:
    > *"Industrial GRU calibrated on real Spark plant data (~5,300 Nm³/day). Current simulation represents a community-scale digester (~3 Nm³/day). Industrial-to-community scale transfer has not been validated. Select EMA-0.90 for a scale-compatible community forecast, or switch source to Spark Bio Gas."*
  - In the chart, the forecast series is cleanly suppressed with legend: `"Prediction withheld — industrial model not validated for Community Scale"`, and a prominent banner is shown above the canvas.
  - Actual observed values for the latest timestep $t$ are set to `null` on target date $t+1$, ensuring zero fabricated future actuals.
- **EMA-0.90 (Statistical Benchmark)**:
  - Reports `domain_valid: true`.
  - Displays a valid, scale-compatible prediction ($\approx 3.2 - 3.5\text{ Nm}^3/\text{day}$).
  - Plots cleanly alongside observed production.
- **Persistence (Naive Baseline)**:
  - Reports `domain_valid: true`.
  - Displays $y_{t+1} = y_t$ ($\approx 3.4\text{ Nm}^3/\text{day}$).

When running on **Spark Industrial Data** (`REAL_SPARK_HISTORICAL`):
- **GRU-14d Residual**:
  - Reports `domain_valid: true`.
  - Displays validated industrial production forecast ($\approx 5,420\text{ Nm}^3/\text{day}$).
  - Full operational drivers displayed.

### Model Interpretation & Research Attribution
- **GRU-14d Residual, EMA-0.90, Persistence**: Panel is labeled `Model Interpretation` and clearly notes: *"Additive feature attribution is unavailable for this forecasting model."* (Recurrent hidden states and statistical filters do not provide linear additive SHAP coefficients).
- **XCO-Net**: Panel is labeled `XCO-Net Research Attribution`, displaying verified architecture-level $1\times 1$ pointwise convolution projection weights:
  1. *Pointwise Cross-Channel Interaction*: 48.5% Weight (Inertia Anchor)
  2. *Cross-Channel Operator Feedstock*: 18.2% Weight (Biokinetic Driver)
  3. *Differentiable Tanh Bounded Delta*: $\pm 4,152\text{ Nm}^3/\text{day}$ (training-derived bounded correction)

---

## 6. Statistical Reference & Baselines

| Model | Role | Lookback | Held-Out Test MAE | Held-Out Test RMSE | Cross-Window MAE | Cross-Window RMSE | Cross-Window $R^2$ |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **GRU-14d Residual** | **Default Champion** | 14 days | 766.61 | 959.40 | **907.32** | **1148.76** | **+0.2723** |
| **EMA-0.90** | Statistical Benchmark | 3 days | 772.33 | 984.48 | 973.91 | 1230.70 | +0.1650 |
| **Persistence** | Naive Baseline | 1 day | 785.42 | 1000.90 | 991.68 | 1252.86 | +0.1347 |
| **XCO-Net** | Research Architecture | 7 days | 799.44 | 1016.92 | 989.47 | 1250.13 | +0.1385 |

### Why GRU is Champion
Across 3 walk-forward evaluation windows (64 out-of-sample days), **GRU-14d Residual** achieves the lowest MAE (907.32 $\text{Nm}^3/\text{day}$) and the highest coefficient of determination ($R^2 = +0.2723$).

---

## 7. Proposed Research Architecture: XCO-Net

**XCO-Net (Cross-Channel Operator Network)** is an experimental neural architecture exploring compact representation learning for anaerobic digestion:
1. **$1\times 1$ Pointwise Conv**: Mixes 9 physical process channels across time.
2. **Differentiable Tanh Bounding**: Constrains maximum predicted deviation to $\pm 4,152\text{ Nm}^3/\text{day}$ (a *training-derived bounded production correction*, not an industrial safety limit).
3. **Parameter Efficiency**: 2,706 trainable parameters (reduced from 5,578 via Single Fitness Optimization Algorithm, SFOA). Parameter-to-sample ratio: 25.8 params/day.
4. **Research Status**: While innovative, its cross-window RMSE (1,250.13 $\text{Nm}^3/\text{day}$) is higher than GRU (1,148.76 $\text{Nm}^3/\text{day}$). Hence, it is correctly positioned as a *research proposal* rather than the deployed champion.

---

## 8. Digester Health Index (Rule-Based Heuristic)

The Health Index in Section 6 is a **deterministic biochemical heuristic**—explicitly not an ML prediction:
- **Base Score**: 100 points.
- **Penalties**:
  - Temperature departure ($T < 35.0^\circ\text{C}$ or $T > 38.0^\circ\text{C}$): $-15$ points.
  - pH buffer departure ($\text{pH} < 6.80$ or $\text{pH} > 7.50$): $-20$ points.
  - Gas overpressure ($P > 1.30\text{ bar}$): $-25$ points.
  - Low methane content ($\text{CH}_4 < 55.0\%$): $-15$ points.
- **Score Bounds**: Strictly bounded to $[35, 100]$.
- **Status Tiers**:
  - $\ge 85$: **Optimal (Green)**
  - $65 - 84$: **Moderate (Yellow)**
  - $< 65$: **Critical (Red)**

---

## 9. Source-Aware Feedstock Loading

The feedstock card in Section 6 dynamically adjusts terminology and units based on the active data source:
- **Community Simulation**:
  - Title: `Simulated Feedstock`
  - Value: `120.0 kg/day`
  - Unit: `kg/day`
  - Subtitle: `Community Reference: 120 kg/day`
  - Footnote: `Physics-based synthetic community-scale scenario`
- **Spark Industrial SCADA**:
  - Title: `Industrial Feedstock`
  - Value: `19.0 MT/day` (or observed daily intake)
  - Unit: `MT/day`
  - Subtitle: `Observed dataset range: 10–200 MT/day`
  - Footnote: `Historical Spark operational record`

---

## 10. Methane & Pearson Correlation Heatmap

### Methane Quality ($\text{CH}_4$)
- Mesophilic anaerobic digestion produces raw biogas with $55\% - 70\%\text{ CH}_4$ and $30\% - 45\%\text{ CO}_2$.
- The platform tracks methane concentration to verify combustion suitability ($> 55\%$ for thermal burners; $> 60\%$ for electrical generators).

### Pearson Correlation Matrix (Exploratory)
- Computed dynamically over the active dataset $N$.
- Features: Temperature, pH, Pressure, Feedstock, $\text{CH}_4$, Biogas.
- Clearly labeled: `SOURCE: Community Sim (N=180)` or `SOURCE: Spark Bio Gas (N=24 / N=176)`.
- Disclaimer: *Exploratory linear association—does not imply biological causation.*

---

## 11. Solar Integration & SDG 11 Impact

### Solar Thermal Subsystem
- Digesters require sustained heat input, particularly during cool nights.
- Solar PV panels generate DC electricity to maintain slurry recirculation pumps and an immersion heating loop.
- The UI monitors solar power ($\text{kW}$), PV voltage ($\text{V}$), battery SoC ($\%$), and battery terminal voltage ($\text{V}$).

### SDG 11: Sustainable Cities & Communities
Biogas production directly mitigates municipal organic waste while generating renewable community electricity:
- $\text{CO}_2$ Mitigated: $\approx 2.1\text{ kg CO}_2\text{e per Nm}^3\text{ biogas}$.
- Clean Electricity Potential: $E_{elec} = V_{biogas} \times \left(\frac{\% CH_4}{100}\right) \times 9.94\text{ kWh/Nm}^3 \times \eta_{elec}$.
- 24-h Average Equivalent Power: $P_{avg} = \frac{E_{elec}}{24}\text{ kW}$.
- Community Microgrid Demand Offset: Supplies critical community daytime and evening baseloads (lighting, refrigeration, water pumping).
- Economic Community Electricity Savings: Calculated dynamically based on local retail tariff parity ($\text{₹}$).

---

## 12. Gemini AI Conversational Assistant

Clicking the floating ⚡ action button opens the glass chat drawer:
- **Grounding**: Queries the active database and injects real-time telemetry (temp, pH, pressure, CH₄, solar power, battery SoC) directly into the prompt.
- **Model**: Google Gemini 2.5 Flash / Pro (with an automatic fallback to the deterministic anaerobic rule engine if offline).
- **Operational Guidance**: Recommends bicarbonate buffering if pH $< 6.80$, suggests solar loop adjustments during cold snaps, and diagnoses biogas ramp rates.

---

## 13. Competition Judge Walkthrough Script

### The 30-Second Elevator Pitch
> *"Good morning, judges. Team Espada presents an AI-Driven Solar-Biogas Platform designed to make community-scale anaerobic digestion autonomous, safe, and viable for SDG 11. Small rural and urban colony digesters frequently fail due to acid shock or temperature drops. Our platform solves this with integrated solar thermal management, real-time biochemical health monitoring, and a causally-strict GRU neural network that forecasts next-day biogas production with +0.27 R² over multi-window benchmarks. Every prediction is backed by transparent domain validation, distinguishing our real-world training research from community deployment."*

### The 2-Minute Guided Demo Flow
1. **Show Top Header & Domain Badge (5s)**: Point out `COMMUNITY-SCALE SIMULATION` badge in the header, demonstrating that we are observing our intended target scale ($\approx 3\text{ Nm}^3/\text{day}$).
2. **Walk Through the 4 Primary Process KPIs (15s)**: Temperature ($36.5^\circ\text{C}$ mesophilic optimum), pH ($7.25$ stable buffer), Pressure ($1.15\text{ bar}$ safe), and Biogas ($3.40\text{ Nm}^3/\text{day}$).
3. **Demonstrate Scientific Honesty in Forecast Card (20s)**:
   - Notice that with GRU selected on the simulator, the card states `Not Validated for Community Scale` with an amber domain notice.
   - Explain: *"We refuse to fake predictions. Our GRU was trained on a 5,300 Nm³/day plant; transferring it to a 3 Nm³/day community digester without re-calibration would be scientifically dishonest."*
4. **Switch to Scale-Compatible Baseline (15s)**:
   - In the dropdown, switch model to `EMA-0.90`.
   - Show that the forecast updates immediately to $\approx 3.50\text{ Nm}^3/\text{day}$, matching the community scale.
5. **Switch to Industrial Research Dataset (25s)**:
   - Switch source to `Spark Bio Gas — Official Held-Out Test (24 Days)` and model to `GRU-14d Residual`.
   - The header badge turns to `INDUSTRIAL RESEARCH DATA`.
   - The forecast card now displays the validated prediction ($\approx 5,420\text{ Nm}^3/\text{day}$).
   - The feedstock card automatically switches to `Industrial Feedstock (MT/day)`.
6. **Open Model Comparison Modal (15s)**:
   - Click `Model Comparison`.
   - Show judges the strict separation between the **Held-Out Test Set (24 days)** and the **Cross-Window Mean (64 days)**. Point out that GRU-14d is the verified champion.
7. **Highlight Explainable AI & Solar Integration (15s)**:
   - Point out the solar thermal loop status and SDG 11 carbon mitigation metrics.
   - Open the Gemini AI Assistant drawer to demonstrate live telemetry grounding.
8. **Conclusion (10s)**: *"This completes a production-ready, demo-safe, and scientifically sound software stack ready for our physical ESP32 IoT node deployment."*

---

## 14. Physical IoT Hardware Implementation Roadmap

With the backend, database, forecasting engine, and dashboard verified, the system is prepared for physical hardware integration:

```
+---------------------+        Wi-Fi / HTTP POST        +---------------------+
|      ESP32 MCU      | -----------------------------> |   FastAPI Backend   |
| - DS18B20 (Temp)    |        /api/readings            | - Pydantic Schemas  |
| - Analog pH Sensor  |                                 | - SQLite Database   |
| - MPX5700DP (Press) |                                 | - Provenance:       |
| - Optical Flowmeter |                                 |   LIVE_IOT          |
+---------------------+                                 +---------------------+
```

- **Hardware Architecture**: ESP32 micro-controller sampling temperature (1-Wire), pH (analog ADC with calibration curve), pressure (piezoresistive differential transducer), and gas flow (calibrated pulse counter).
- **Network Ingestion**: Periodic HTTP POST payload to `/api/readings` with `source: "live_iot"`.
- **Dashboard Display**: When live telemetry arrives, the header domain badge automatically displays `COMMUNITY LIVE TELEMETRY` with an emerald badge, seamlessly streaming real-world sensor data into the forecasting pipeline.

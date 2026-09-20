# Biogas Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-teal.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Architecture](https://img.shields.io/badge/Scale-Industrial%20%26%20Community-indigo.svg)]()
[![Status](https://img.shields.io/badge/Status-Multi--Scale%20Analytics-green.svg)]()

An intelligent, multi-scale IoT monitoring, next-day biogas forecasting, solar telemetry, and explainable decision support platform designed for anaerobic digestion (AD) systems across industrial research facilities and community deployments.

---

## 1. System Overview

The **Biogas Intelligence Platform** bridges physical telemetry, physics-based simulation, and machine learning to optimize anaerobic digester operation, prevent reactor souring (acidosis), and forecast next-day biogas production (Nm3/day or m3/day).

Key capabilities:
- **Multi-Scale Domain Separation**: Strictly separates large-scale industrial research facilities (~5,300 Nm3/day) from community-scale digesters (~3-15 m3/day) and external static benchmarks.
- **Strict Past-Only Causality**: Next-day forecasts (t -> t+1) strictly depend on observations available through timestep t, guaranteeing zero future data leakage.
- **Domain Transfer Validation Barriers**: Machine learning models calibrated on industrial data legitimately withhold operational predictions when applied to unvalidated community or third-party datasets (domain_valid = False), avoiding hazardous miscalibrations.
- **Transparent Model Interpretation**: Replaces generic black-box claims with local input sensitivity analysis, mathematical weight decompositions, and architectural attributions (is_shap: false).
- **Flexible SCADA & Excel Ingestion**: Accepts arbitrary spreadsheets and SCADA exports with robust semantic alias matching, automatic unit conversions (deg F -> deg C, kPa/psi -> bar, kg -> MT), and standalone column statistics.
- **Modular Hardware IoT Path**: Direct ESP32 hardware ingest endpoint with configurable connectivity freshness tracking and zero synthetic fallback substitution.

---

## 2. End-to-End System Topology

`
+---------------------------+     +----------------------------+     +-----------------------------+
|    Community Digesters    |     |   Industrial Research SCADA|     |     User SCADA / Excel      |
|  (ESP32 / Physics Sim)    |     |      (Spark Bio Gas)       |     |     (Arbitrary Format)      |
+-------------+-------------+     +--------------+-------------+     +--------------+--------------+
              |                                  |                                  |
              v                                  v                                  v
      HTTP / REST Ingest                 Preprocessed Replay                Semantic Ingestion Service
   (/api/readings/iot-ingest)           (/api/forecast/spark-replay)         (/api/ingestion/analyze)
              |                                  |                                  |
              +----------------------------------+----------------------------------+
                                                 |
                                                 v
                                     +-----------------------+
                                     |  FastAPI Core Backend |
                                     |  (Database & State)   |
                                     +-----------+-----------+
                                                 |
                                                 v
                                     +-----------------------+
                                     |  Forecasting Engine   |
                                     |  (History Validation) |
                                     +-----------+-----------+
                                                 |
             +-----------------------------------+-----------------------------------+
             |                                   |                                   |
             v                                   v                                   v
    GRU-14d Residual                         EMA-0.90 / Persistence               XCO-Net Research
(Industrial Validated ML)             (Scale-Compatible References)        (Cross-Channel Conv Architecture)
             |                                   |                                   |
             +-----------------------------------+-----------------------------------+
                                                 |
                                                 v
                                     +-----------------------+
                                     | Model Interpretation  |
                                     | (/api/forecast/interp)|
                                     +-----------+-----------+
                                                 |
                                                 v
                                     +-----------------------+
                                     | Web Dashboard UI      |
                                     | (Multi-Scale Engine)  |
                                     +-----------------------+
`

---

## 3. Data Sources & Operational Scales

The platform implements strict provenance tracking across distinct data domains:

| Source Identifier | Display Name | Scale & Domain | Description |
| :--- | :--- | :--- | :--- |
| LIVE_IOT | Community Live Telemetry -- ESP32 / IoT | Community Scale | Real-time sensor readings pushed by physical ESP32 edge nodes. Requires hardware connectivity within offline_threshold_minutes. Zero fallback to synthetic data. |
| DEMO_SYNTHETIC | Live Demo Feed (Physics Simulator) | Community Scale | Continuous 180-day bio-kinetic anaerobic digestion simulation with 14-day initialization warm-up. |
| REAL_SPARK_HISTORICAL | Spark Bio Gas -- Official Held-Out Test | Industrial Scale | 24-day held-out test set from the operational Spark Bio Gas industrial plant (~5,300 Nm3/day). |
| SPARK_FULL | Spark Bio Gas -- Industrial Historical | Industrial Scale | Full 176-calendar-day operational SCADA research dataset with continuous time-series history. |
| AGSTAR_REGISTRY | AgSTAR -- Livestock Digester Registry | Static Benchmark | USDA/EPA non-time-series registry of 526 commercial anaerobic digesters across 38 US states. Time-series forecasting is disabled. |
| USER_UPLOAD | User-Uploaded Data (Ingested SCADA) | Arbitrary User Data | Arbitrary CSV or Excel workbook parsed via semantic column matching and validated without synthetic data substitution. |

---

## 4. Forecasting Model Hierarchy

Four distinct models provide tiered forecasting and benchmark capabilities:

### 1. GRU-14d Residual (Industrial-Domain Validated Model)
- **Architecture**: 2-layer Gated Recurrent Unit (hidden dimension: 64, dropout: 0.20) with frozen feature scalers.
- **Required Lookback**: Exactly **14 continuous timesteps** of 9 operational features.
- **Domain Validation**: Validated strictly on industrial plant data (REAL_SPARK_HISTORICAL, SPARK_FULL). When evaluated on DEMO_SYNTHETIC, LIVE_IOT, or USER_UPLOAD, domain_valid is strictly False and operational numerical predictions are withheld for process safety.

### 2. EMA-0.90 (Scale-Compatible Statistical Reference)
- **Algorithm**: Exponentially smoothed rolling average combining immediate inertia with recent trend:
  \hat{y}_{t+1} = 0.90 \cdot y_t + 0.10 \cdot \text{mean}(y_t, y_{t-1}, y_{t-2})
- **Required Lookback**: 3 observations.
- **Domain Validation**: Scale-agnostic statistical filter authorized across both community and industrial scales.

### 3. Persistence (Naive Baseline)
- **Algorithm**: Identity lag-0 forecast carrying current production forward:
  \hat{y}_{t+1} = y_t
- **Required Lookback**: 1 observation.
- **Domain Validation**: Scale-agnostic baseline authorized across all data domains.

### 4. XCO-Net (Cross-Channel Operator Research Architecture)
- **Architecture**: Deep convolutional model featuring 1x1 cross-channel interactions, temporal convolutions, and a bounded differentiable tanh production correction:
  \Delta y = 4152 \cdot \tanh(\mathbf{W} \mathbf{h} + b)
- **Required Lookback**: Exactly **14 continuous timesteps**.
- **Domain Validation**: Experimental research architecture evaluated in the industrial domain (domain_valid = False for community or user uploads).

---

## 5. Model Interpretation Service

Accessible via POST /api/forecast/interpretation and GET /api/forecast/interpretation. All responses explicitly set is_shap: false to ensure scientific transparency:

- **GRU-14d Residual**: Evaluates local input perturbation sensitivity by perturbing each normalized input feature by +0.10 sigma and measuring the change in predicted production. Features include window-level directional trends.
- **EMA-0.90**: Evaluates the exact mathematical coefficient decomposition:
  \text{Weight}(y_t) = 93.33\%,\quad \text{Weight}(y_{t-1}) = 3.33\%,\quad \text{Weight}(y_{t-2}) = 3.33\%
- **Persistence**: Reports the 100% identity assignment from $ with zero memory overhead.
- **XCO-Net**: Exposes architectural projection weights (48.5% pointwise cross-channel interaction, 18.2% feedstock operator, +/-4,152 Nm3/day bounded correction).

---

## 6. SCADA & Spreadsheet Ingestion Engine

The ingestion service (POST /api/ingestion/analyze) enables arbitrary third-party Excel (.xlsx, .xls) or CSV datasets to be analyzed and activated without manual schema adjustments:

1. **Semantic Alias Dictionary**: Recognizes varied headers (e.g. Temp_Outlet, 
eactor_temp, 	emp_c, ph_outlet_d1, gas_pressure_kpa, iogas_nm3, organic_feed_kg).
2. **Automatic Unit Normalization**:
   - Temperature: deg F -> deg C
   - Gas Pressure: kPa -> bar (/ 100), psi -> bar (/ 14.5038)
   - Feedstock Loading: kg -> MT (/ 1000)
3. **Independent Pipeline Separation**:
   - **Data Analysis**: Computes standalone descriptive statistics (count, nulls, min, max, mean, median, standard deviation) across **all** numeric columns regardless of model eligibility.
   - **Forecast Eligibility**: Validates whether mandatory features and lookback requirements are satisfied for each model.
   - **Domain Validation**: Decoupled from file parsing. User-uploaded data maintains domain_valid = False for ML models, preserving scientific integrity.
4. **Zero Data Fallback**: Missing features are never silently imputed with synthetic or industrial constants. Incomplete datasets trigger an explicit INSUFFICIENT_FEATURES status.

---

## 7. Energy Generation & Community Microgrid Management

The platform transforms raw bioprocess monitoring into an intelligent biogas-to-electricity energy management platform:

$$\text{Organic Waste} \longrightarrow \text{Anaerobic Digestion} \longrightarrow \text{Biogas} \longrightarrow \text{Gas Conditioning} \longrightarrow \text{Biogas Generator} \longrightarrow \text{Electricity} \longrightarrow \text{Community Loads}$$

### Key Capabilities:
- **Thermodynamic Conversion Formulation**:
  $$E_{electricity} = V_{biogas} \times \left(\frac{\% CH_4}{100}\right) \times 9.94\text{ kWh/Nm}^3 \times \eta_{electric}$$
- **24-h Average Equivalent Power**:
  $$P_{avg} = \frac{E_{electricity}}{24}\text{ kW}$$
- **Generator Operational Status**: Displays strictly `NOT CONNECTED` (or `SIMULATED`) for prototype integrity; physical telemetry is never fabricated.
- **Assumed Electrical Efficiency ($\eta_{electric}$)**: Configurable prototype baseline (default 30%, adjustable from 20% to 45%).
- **Community Microgrid Dispatch**: Dynamic supply-demand balance comparing calculated generation potential against illustrative community load profiles (lighting, vaccine refrigeration, water pumping).
- **5-Category Structured Safety Interlocks**: Categorized into `DIGESTER`, `GAS`, `SENSOR`, `ENERGY`, and `SOLAR` with prototype configurable threshold disclaimers.

---

## 8. Quickstart Guide

### Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Virtual environment (recommended)

### Installation

1. **Clone the repository**:
   `ash
   git clone https://github.com/your-org/biogas-intelligence-platform.git
   cd biogas-intelligence-platform
   `

2. **Create and activate virtual environment**:
   `ash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   `

3. **Install dependencies**:
   `ash
   pip install -r requirements.txt
   `

4. **Configure environment**:
   `ash
   cp .env.example .env
   `
   Edit .env to configure your database path, optional Gemini API key, and explicit CORS origins.

### Running the Application

Start the FastAPI application with Uvicorn:
`ash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
`

- **Interactive Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative API Documentation (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 9. Automated Testing

The repository contains an exhaustive test suite covering forensic provenance, time-series causality, model inference, interpretation mathematics, SCADA ingestion, and security boundaries:

```bash
# Run the complete test suite
pytest

# Run tests with verbose output
pytest -v
```

---

## 10. Security & Production Hosting

- **CORS Configuration**: Controlled strictly via `CORS_ORIGINS` in `.env`. Wildcard `*` is disabled in production (`DEBUG=False`).
- **Secret Management**: API keys and database credentials are read exclusively from environment variables; default `.env` files contain sanitized placeholders.
- **Configurable API Endpoint**: The dashboard UI supports dynamic deployment base paths via `window.__API_BASE__`.
- **System Integrity Badge**: Public UI displays neutral descriptive indicator `MULTI-SCALE BIOGAS ANALYTICS`.

---

## 11. License

This project is licensed under the MIT License.
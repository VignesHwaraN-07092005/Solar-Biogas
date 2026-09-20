# PROJECT PLAN & ROADMAP: AI-DRIVEN SOLAR-BIOGAS PLATFORM

**Project Title:** AI-Driven Solar-Biogas System for Sustainable Communities  
**Team:** Espada  
**Track:** IEEE YESIST12 Innovation Challenge (SDG 11: Sustainable Cities and Communities)  
**Status:** In Development (Engineered from Zero)  
**Date:** September 14, 2026  

---

## 1. Project Overview & Scope Definition

### 1.1 Objective
Build a technically defensible, modular, and realistic working software and hardware prototype for intelligent biogas monitoring, next-day yield forecasting, explainable operator insights, and solar power management tailored for small/community-scale anaerobic digestion (AD) systems.

### 1.2 Core Problem & Primary Prediction Target
Anaerobic digestion is biologically sensitive to feedstock loading, temperature swings, and pH shifts. Small-scale community digesters lack continuous instrumentation and predictive analytics, leading to acidification, odor, and volatile gas production.
- **Primary AI Prediction Target:** **Next-Day Biogas Production ($m^3/day$)** ($y_{t+1}$).
- **Secondary Targets (Future):** Methanogenic stability index, digester failure risk alert.
- **Operating Modes:**
  - **DEMO / SYNTHETIC MODE:** Simulated micro-digester telemetry and public/research data for UI demos, pipeline stress testing, and edge failure verification.
  - **LIVE / RESEARCH MODE:** Live telemetry from ESP32 edge devices or validated research datasets (e.g. Spark Bio Gas industrial daily logs).

### 1.3 Scientific Integrity & Non-Fabrication Commitment
All claims from the competition portal (0.38 RMSE, 0.92 NNSE, 39% improvement, XCO-Net, SFOA) are treated strictly as **target aspirational benchmarks**. No metric will ever be hardcoded or fabricated. Every reported metric will stem directly from reproducible script execution on real or clearly labeled synthetic data.

---

## 2. Multi-Phase Development Roadmap

```mermaid
gantt
    title AI-Driven Solar-Biogas Development Roadmap
    dateFormat  YYYY-MM-DD
    section Foundations
    Phase 0: Source & Dataset Audit       :done,    p0, 2026-09-14, 2026-09-14
    Phase 1: Backend, DB, Synthetic Gen   :active,  p1, 2026-09-14, 2026-09-15
    section AI & Modeling
    Phase 2: Data Pipeline & Baselines    :         p2, 2026-09-15, 2026-09-16
    Phase 3: Deep Temporal Models         :         p3, 2026-09-16, 2026-09-17
    Phase 4: Explainability (SHAP)        :         p4, 2026-09-17, 2026-09-18
    Phase 5: XCO-Net Architecture         :         p5, 2026-09-18, 2026-09-19
    Phase 6: Starfish Optimization (SFOA) :         p6, 2026-09-19, 2026-09-20
    section IoT & Solar
    Phase 7: IoT Telemetry & ESP32        :         p7, 2026-09-20, 2026-09-21
    Phase 8: Solar Power Monitoring       :         p8, 2026-09-21, 2026-09-22
    section Integration
    Phase 9: Full Dashboard Integration  :         p9, 2026-09-22, 2026-09-23
    Phase 10: Validation & Benchmarking   :         p10, 2026-09-23, 2026-09-24
```

---

### PHASE 0: Source & Dataset Audit (COMPLETED)
- **Objective:** Exhaustively audit all 5 workspace files, extract portal claims, audit datasets, establish primary vs secondary data, and set scientific integrity rules.
- **Files Created:** `docs/SOURCE_AUDIT.md`, `docs/DATASET_AUDIT.md`.
- **Completion Criteria:** All sources categorized according to 7-tier classification; datasets verified non-combinable; Spark Biogas chosen as primary data.

---

### PHASE 1: Project Foundation, Database, Backend & Synthetic Data Generator
- **Objective:** Set up a clean modular repository, database schemas, FastAPI backend endpoints, and a biokinetics-based synthetic anaerobic digestion generator.
- **Key Files:**
  - `backend/app/main.py`: FastAPI server setup with CORS and routers.
  - `backend/app/database.py`: SQLAlchemy session management (SQLite local default, PostgreSQL ready).
  - `backend/app/models/`: SQLAlchemy ORM models (`Device`, `SensorReading`, `ForecastResult`, `ModelRun`, `ModelMetric`, `Alert`, `SolarMetric`).
  - `backend/app/schemas/`: Pydantic validation schemas with range checking and null handling.
  - `backend/app/api/`: REST routes (`health`, `devices`, `readings`, `forecast`, `models`, `alerts`, `solar`).
  - `simulation/synthetic_data_generator/generate_dataset.py`: First-principles community digester simulation.
  - `backend/tests/`: Automated unit tests for database CRUD, schema validation, and health checks.
- **Completion Criteria:** Backend starts on port 8000; database tables auto-create; synthetic generator produces reproducible community-scale time-series; tests pass.

---

### PHASE 2: Data Preprocessing, Cleaning & Baseline ML Models
- **Objective:** Build leakage-free feature engineering and train tabular regression baselines.
- **Key Files:**
  - `ml/preprocessing/clean_spark_data.py`: Parser for Spark Biogas dataset (162 days).
  - `ml/feature_engineering/build_features.py`: Chronological lag features ($t-1, t-2, t-3$), rolling means (3-day, 7-day), rolling std, and rate of change.
  - `ml/baselines/train_baselines.py`: Naive persistence baseline, Linear Regression (Ridge), Random Forest Regressor, XGBoost Regressor.
  - `ml/results/model_comparison.csv`: Machine-readable metrics logging MAE, RMSE, $R^2$, and optional NNSE.
- **Completion Criteria:** Strictly chronological train/val/test splits (70/15/15%); no future leakage; baseline metrics computed and logged.

---

### PHASE 3: Temporal Sequence Models (LSTM & GRU)
- **Objective:** Implement deep recurrent sequence models to capture multi-day inertia and non-linear substrate digestion lag.
- **Key Files:**
  - `ml/temporal_models/dataset_windowing.py`: Sliding window sequence generator ($N$ past time steps to predict $y_{t+1}$).
  - `ml/temporal_models/lstm_model.py`: PyTorch LSTM forecasting architecture.
  - `ml/temporal_models/gru_model.py`: PyTorch GRU forecasting architecture.
  - `ml/temporal_models/train_temporal.py`: Chronological training loop with early stopping and gradient clipping.
- **Completion Criteria:** LSTM and GRU train with real convergence; compared against baselines; actual RMSE and MAE reported.

---

### PHASE 4: Explainable AI (SHAP & Operator Decision Support)
- **Objective:** Unpack model predictions into operator-friendly feature attributions.
- **Key Files:**
  - `ml/explainability/shap_explainer.py`: TreeExplainer / DeepExplainer attribution module.
  - `backend/app/services/decision_support.py`: Rule-based and attribution-based operator recommendations (e.g., "pH drop of 0.4 detected; reduce food waste feed by 20%").
- **Completion Criteria:** API endpoint `/api/explanations` returns the top 5 contributing factors for any given forecast.

---

### PHASE 5: XCO-Net (Explainable Conjoined O-Net) Architecture
- **Objective:** Implement our proposed dual-branch conjoined neural network architecture transparently.
- **Key Files:**
  - `ml/xco_net/architecture.py`: PyTorch module with:
    - *Operational Branch:* Encoders for dynamic variables (pH, temperature, agitation, pressure).
    - *Feedstock Branch:* Encoders for loading mass and organic substrate ratios.
    - *Conjoined Fusion Layer:* Cross-attention / dense fusion connecting the two branches.
    - *Prediction Head:* Output dense layer forecasting $y_{t+1}$.
    - *Explainability Head:* Inherent branch attention weights.
  - `ml/xco_net/train_xco_net.py`: Training script with ablation comparison against standalone LSTM/GRU.
- **Completion Criteria:** XCO-Net builds, trains, and evaluates on identical test splits; documentation explains its mathematical structure without unsupported novelty claims.

---

### PHASE 6: Starfish Optimization Algorithm (SFOA)
- **Objective:** Implement the bio-inspired Starfish Optimization Algorithm for automated hyperparameter optimization.
- **Key Files:**
  - `ml/sfoa/starfish_optimizer.py`: SFOA algorithm modeling starfish foraging, regeneration, and movement behaviors.
  - `ml/sfoa/tune_hyperparameters.py`: Evaluates fitness (validation RMSE) over hyperparameter search space (learning rate, hidden units, sequence length, dropout).
  - `ml/sfoa/benchmark_tuning.py`: Empirical comparison against Random Search and Bayesian Optimization.
- **Completion Criteria:** Convergence log recorded; hyperparameter improvements objectively tested; retained only if empirically justified.

---

### PHASE 7: IoT System & ESP32 Firmware
- **Objective:** Implement modular edge firmware for ESP32 and telemetry ingestion.
- **Key Files:**
  - `iot/esp32/firmware.ino` / C++ PlatformIO code: ADC reading, sensor calibration, local ring-buffer, Wi-Fi auto-reconnect, HTTP POST / MQTT publish.
  - `iot/sensors/sensor_drivers.h`: Modular drivers for DS18B20 (temperature), Analog pH probe, Flow pulse counter, and Pressure transducer.
  - `backend/app/api/ingestion.py`: High-throughput telemetry ingestion with validation and device heartbeat tracking.
- **Completion Criteria:** Edge payload adheres to strict JSON schema; handles offline reconnection; gracefully marks missing sensor fields with nulls.

---

### PHASE 8: Solar Telemetry & Energy Monitoring
- **Objective:** Monitor and display solar generation and battery status powering the IoT electronics.
- **Key Files:**
  - `iot/sensors/ina219_solar.h`: I2C sensor driver for solar panel voltage, current, and battery state of charge.
  - `backend/app/services/solar_service.py`: Power budget modeling and state-of-charge tracking.
- **Completion Criteria:** Solar voltage/current logged; battery state displayed; low-battery alerts generated.

---

### PHASE 9: Modern Web Engineering Dashboard
- **Objective:** Build an operator-grade web interface for real-time visualization and decision support.
- **Key Files:**
  - `frontend/`: React/Vite application with clean modular components.
  - Pages: Overview, Live Telemetry, Biogas Forecast, AI Models & Benchmarks, Explainability (SHAP), Solar Power, Alerts, Device Management.
  - Clear toggle badge: `MODE: DEMO (SYNTHETIC)` vs `MODE: LIVE (ESP32/RESEARCH)`.
- **Completion Criteria:** Renders live charts (Plotly / Chart.js / Recharts); connects to backend REST endpoints; displays active alerts and SHAP waterfall.

---

### PHASE 10: Validation, Safety Analysis & Documentation
- **Objective:** Complete end-to-end integration tests, safety failure mode analysis, and final documentation.
- **Key Files:**
  - `docs/VALIDATION.md`: Full empirical report of all models.
  - `docs/SAFETY.md`: Hazard analysis (methane leakage, overpressure, hydrogen sulfide).
  - `docs/DEPLOYMENT.md`: Step-by-step local and edge deployment instructions.
- **Completion Criteria:** All test suites pass; final metrics logged; documentation complete.

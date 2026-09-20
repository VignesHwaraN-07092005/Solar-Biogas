# Final Dashboard Forensic Audit & Domain Investigation
**Smart Solar-AI Biogas Platform** · *IEEE YESIST12 Team Espada (SDG 11)*  
**Date**: September 2026 · **Status**: Audited & Corrected

---

## Executive Summary
This document provides the definitive forensic audit of all UI, presentation, domain-transfer, and data-flow mechanisms across the AI-Driven Solar-Biogas Platform prior to physical IoT hardware integration. 

The audit establishes a formal separation between the **Industrial Research/Training Domain** (Spark Bio Gas SCADA, $\approx 5,300\text{ Nm}^3/\text{day}$), the **Community Deployment Demonstration Domain** (Physics Simulator, $\approx 1.3 - 8.4\text{ Nm}^3/\text{day}$), and the future **Community Live IoT Deployment Domain** (ESP32 + physical sensors).

---

## Itemized Forensic Investigation

### 1. Physics Simulator vs. Industrial GRU Scale Mismatch
- **Issue**: Under `DEMO_SYNTHETIC`, the physics simulator produces community-scale biogas ($\approx 1.3 - 8.4\text{ Nm}^3/\text{day}$), but running the industrial GRU-14d model yielded predictions of $\approx 1,570\text{ Nm}^3/\text{day}$ ($500\times$ higher than the physical digester volume).
- **Reproduction Steps**: Select `Live Demo Feed (Physics Simulator)`, choose model `GRU-14d Residual`, inspect predicted value at $t \ge 13$.
- **Empirical Trace & Root Cause**:
  * Feature distribution comparison across all 9 inputs:
    - `biogas_today_nm3`: Simulator mean $2.98\text{ Nm}^3/\text{day}$ vs. Training mean $5,300.09\text{ Nm}^3/\text{day}$ (Out of Distribution: SEVERE).
    - `total_incoming_mt`: Simulator mean $0.06\text{ MT/day}$ vs. Training mean $132.75\text{ MT/day}$ (Out of Distribution: SEVERE).
    - `total_processed_mt`: Simulator mean $0.06\text{ MT/day}$ vs. Training mean $99.09\text{ MT/day}$ (Out of Distribution: SEVERE).
    - `feed_total_m3`: Simulator mean $0.07\text{ m}^3/\text{day}$ vs. Training mean $206.18\text{ m}^3/\text{day}$ (Out of Distribution: SEVERE).
    - `temp_outlet_d1_c`: Simulator mean $35.41^\circ\text{C}$ vs. Training mean $34.75^\circ\text{C}$ (In Distribution).
    - `ph_outlet_d1`: Simulator mean $7.38$ vs. Training mean $7.47$ (In Distribution).
    - `recycle_water_m3`: Simulator $30.0\text{ m}^3$ vs. Training mean $49.70\text{ m}^3$ (In Distribution).
  * The industrial GRU unscales its output delta by the frozen training target deviation $y_{\text{std}} = 1,203.2777\text{ Nm}^3/\text{day}$. Adding an industrial-scale delta to a $3\text{ Nm}^3/\text{day}$ baseline produces $\approx 1,570\text{ Nm}^3/\text{day}$.
- **Affected Files**: `backend/app/services/forecast_service.py`, `backend/app/services/simulator_service.py`, `frontend/public/app.js`.
- **Fix**:
  * Scientifically honest domain handling: The backend sets `domain_valid = False` and attaches an explicit notice: *"Industrial-trained GRU. Community-scale transfer not yet validated."*
  * The UI Forecast Panel renders: `Predicted Next-Day: Not Validated for Community Scale (OOD)` and displays a clear explanation.
  * When scale-compatible statistical references (**EMA-0.90** or **Persistence**) are selected, the system calculates and displays verified community-scale forecasts ($\approx 3.2 - 3.5\text{ Nm}^3/\text{day}$).
- **Verification Method**: Automated tests `test_domain_valid_false_for_simulator_gru` and manual UI inspection.

---

### 2. 14/14 History but Blank/Warming Forecast States
- **Issue**: Dashboard previously showed `History: 14/14` but reported `Status: Warming up` with blank prediction `—`.
- **Reproduction Steps**: Initialize dashboard at index 179 and observe autoplay timer tick 1.
- **Root Cause**: `app.js` initialized at index 179 (last day) and wrapped via `(179 + 1) % 180 = 0` on tick 1, resetting the client index to day 0 ($< 13$) and triggering `INSUFFICIENT_HISTORY`.
- **Affected Files**: `frontend/public/app.js`.
- **Fix**: Simulator initialization sets `currentRecordIndex = 13` (Day 14, 14 continuous days accumulated), and autoplay cycles post-warmup range $[13 \dots 179]$.
- **Verification Method**: Automated test `test_simulator_provides_14_continuous_timesteps` and `test_gru_forecast_succeeds_once_history_ge_14`.

---

### 3. Industrial Feedstock Displayed with Community Nominal Limits
- **Issue**: When displaying Spark industrial SCADA records ($19,000\text{ kg/day}$), the feedstock card displayed community-scale limits (`Nominal 120 kg/day`), causing gauge saturation and confusing judges.
- **Reproduction Steps**: Select `Spark Bio Gas — Industrial Historical (176 Days)` and view the Feedstock Input card.
- **Root Cause**: Hardcoded static text in `index.html` and single-scale gauge normalization in `app.js`.
- **Affected Files**: `frontend/public/index.html`, `frontend/public/app.js`.
- **Fix**: Source-aware display logic:
  * In `DEMO_SYNTHETIC`: Displays `SIMULATED FEEDSTOCK: 120 kg/day`, `Community Reference: 120 kg/day`, note: *"Physics-based synthetic community-scale scenario"*.
  * In `REAL_SPARK_HISTORICAL`: Displays `INDUSTRIAL FEEDSTOCK: 19.0 MT/day`, `Observed dataset range: 10–200 MT/day`, note: *"Historical Spark operational record"*.
- **Verification Method**: Manual UI test switching between `DEMO_SYNTHETIC` and `SPARK_FULL`.

---

### 4. Health Index Appearing More Authoritative Than Justified
- **Issue**: Digester Health Index was previously displayed without explicit indication of its heuristic status, risking misinterpretation as an AI probability or machine-learned certainty.
- **Reproduction Steps**: Inspect Digester Health Index widget in default dashboard.
- **Root Cause**: Lack of operational methodology labeling and missing heuristic disclaimers.
- **Affected Files**: `frontend/public/index.html`, `frontend/public/app.js`.
- **Fix**:
  * Labeled clearly as **"Digester Health Index — Rule-Based"**.
  * Added subtitle: *"Deterministic heuristic — not an ML prediction"*.
  * Added source context: `SOURCE: Current simulated telemetry` or `SOURCE: Spark historical telemetry`.
  * Clamped bounds strictly to $[35, 100]$.
  * Added modal documenting the 4 biochemical variables (temperature, pH, pressure, methane) and deduction penalties.
- **Verification Method**: Automated test `test_8_health_index_bounds_and_heuristic_penalties`.

---

### 5. Methane Qualitative Descriptions Potentially Overstated
- **Issue**: Methane card displayed claims such as *"High Quality Cooking Fuel"* based on simulated purity without qualification.
- **Reproduction Steps**: View Methane purity card in default dashboard.
- **Root Cause**: Unqualified static promotional copy.
- **Affected Files**: `frontend/public/index.html`, `frontend/public/app.js`.
- **Fix**: Labeled card strictly as **"Methane Concentration: 62.5%"** and added secondary label: *"Heuristic interpretation: Methane enrichment within anaerobic operational envelope"*.
- **Verification Method**: Visual code review and regression check.

---

### 6. Correlation Widget Source Context & Causality Warnings
- **Issue**: Pearson correlation matrix showed numerical values without specifying sample size $N$ or explicitly cautioning against causal interpretations.
- **Reproduction Steps**: Inspect Correlation widget in secondary analytics.
- **Root Cause**: Unlabeled calculations computed on static client datasets.
- **Affected Files**: `frontend/public/index.html`, `frontend/public/app.js`.
- **Fix**:
  * Labeled as **"Historical Pearson Correlation — Exploratory"**.
  * Dynamically computes and displays active dataset sample size ($N$) and correlation ($r$).
  * Added visible warning footer: *"Exploratory correlation. Correlation does not imply causation."*
- **Verification Method**: Automated test `test_9_correlation_n_and_isolated_calculation`.

---

### 7. Forecast Graph Presentation & Alignment
- **Issue**: The time-series chart plotted points on observation date $t$ rather than target date $t+1$, used spline smoothing (`tension: 0.35`), and had hidden legends.
- **Reproduction Steps**: Inspect line chart under historical playback.
- **Root Cause**: Misaligned X-axis dates and default Chart.js bezier curve smoothing.
- **Affected Files**: `frontend/public/app.js`.
- **Fix**:
  * Aligned X-axis strictly to target date $t+1$.
  * Set `tension: 0.0` (zero spline smoothing).
  * Line 1 plots actual production observed on target date $t+1$ (`null` for future unobserved dates).
  * Line 2 plots causal prediction generated at day $t$ for $t+1$.
  * In `DEMO_SYNTHETIC` + `GRU-14d Residual`, invalid industrial predictions are excluded from the community graph.
- **Verification Method**: Automated test `test_3_t_to_t_plus_1_chart_alignment`.

---

### 8. Benchmark Presentation & Metric Segregation
- **Issue**: Dashboard previously conflated the 24-day held-out test split with the 64-day 3-window cross-validation mean, obscuring model rankings.
- **Reproduction Steps**: Open Model Comparison modal.
- **Root Cause**: Hardcoded single-table layout in client JavaScript.
- **Affected Files**: `backend/app/schemas/forecast.py`, `backend/app/services/forecast_service.py`, `frontend/public/index.html`, `frontend/public/app.js`.
- **Fix**:
  * Segregated metrics into two distinct columns: **Held-Out Test Set (24 operating days)** and **Cross-Window Mean (64 out-of-sample days)**.
  * Dynamic loading from FastAPI endpoint `GET /api/forecast/benchmarks`.
  * Hierarchy clearly establishes **GRU-14d Residual** as Default Forecasting Model, **EMA-0.90** as Statistical Benchmark, **Persistence** as Naive Baseline, and **XCO-Net** as Proposed Research Architecture.
- **Verification Method**: Automated test `test_2_benchmark_api_values_and_labels`.

---

### 9. Dataset & Source Semantics
- **Issue**: AgSTAR registry was listed alongside operational time-series data without clarifying that it is a static cross-sectional census.
- **Reproduction Steps**: View telemetry source selector.
- **Root Cause**: Ungrouped `<select>` options in legacy markup.
- **Affected Files**: `frontend/public/index.html`, `frontend/public/app.js`.
- **Fix**:
  * Grouped into `FORECAST DATA` (Physics Simulator 180d, Spark 24d Held-Out Test, Spark 176d Industrial Historical) and `EXTERNAL BENCHMARK` (AgSTAR 526 facilities).
  * Selecting AgSTAR displays an explanatory modal stating it is a static USDA/EPA livestock digester registry not fed into the forecasting model.
  * Labeled Spark 176 records strictly as *"176 calendar days"*, noting maintenance and missing periods.
- **Verification Method**: Automated tests `test_4_spark_full_count_176_calendar_records` and `test_5_spark_test_count_24_operating_days`.

---

### 10. Header Branding & Logo Alignment
- **Issue**: Top-left branding container experienced flex shrinking and vertical misalignment on narrow browser viewports.
- **Reproduction Steps**: Shrink viewport to $< 1200\text{px}$.
- **Root Cause**: Missing `shrink-0` flex properties on logo wrapper.
- **Affected Files**: `frontend/public/index.html`.
- **Fix**: Added `shrink-0` and vertical centering (`items-center`) to logo and title containers.
- **Verification Method**: Responsive layout testing across viewports from 1920px to mobile.

---

### 11. Stale Nomenclature & Deprecated References Cleanup
- **Issue**: Residual code contained references to "Cross-Channel Orthogonal Network", old Ridge UI references, and placeholder formula comments.
- **Reproduction Steps**: Static grep search across project root.
- **Root Cause**: Historical development iterations prior to architecture freeze.
- **Affected Files**: `frontend/public/index.html`, `backend/app/schemas/forecast.py`, `backend/app/services/forecast_service.py`, `docs/FORECASTING_SYSTEM.md`.
- **Fix**: Systematically standardized XCO-Net to **"Cross-Channel Operator Network"** and removed all obsolete runtime references.
- **Verification Method**: Automated test and static ripgrep audit.

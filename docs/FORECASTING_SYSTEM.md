# Biogas Forecasting System: Architecture, Empirical Evidence & Operational Guidelines

This document specifies the operational forecasting system deployed within the **AI-Driven Solar-Biogas Platform (IEEE YESIST12 / Team Espada)**. It documents the model hierarchy, empirical selection rationale, data provenance rules, physical safety guards, and strict temporal causality standards.

---

## 1. Selected Operational Model: GRU-14d Residual

The **Default Forecasting Model** integrated into the operational system is:
$$\mathbf{GRU \text{ (14-day Residual)}}$$
- **Artifact**: `models/gru_lookback_14d_residual.pt`
- **Frozen Preprocessing Scaler**: `models/gru_scaler_metadata.json` (`v1.0.0-frozen-train`)
- **Input Dimensionality**: $14 \text{ days} \times 9 \text{ features}$
  - `biogas_today_nm3`, `total_incoming_mt`, `total_processed_mt`, `feed_total_m3`, `temp_outlet_d1_c`, `ph_outlet_d1`, `recycle_water_m3`, `feed_total_m3_was_missing`, `ph_outlet_d1_was_missing`.
- **Formulation**:
  $$\hat{y}_{t+1} = \max\left(0, \; y_t + \left(\hat{\delta}_{\text{raw}} \times y_{\text{std}}^{\text{train}}\right)\right)$$
  where $y_t$ is current day biogas production (temporal inertia anchor), $\hat{\delta}_{\text{raw}}$ is the raw residual output from the GRU linear head, and $y_{\text{std}}^{\text{train}} = 1,203.28\text{ Nm}^3/\text{day}$.

### 1.1 Target Normalization & Scaler Consistency Audit

A forensic verification audit was conducted on the GRU-14d Residual normalization parameters:

1. **Exact Training Target Normalization**:
   During model training in `run_temporal_experiments.py`, continuous sliding windows of length 14 were extracted from the training partition (`2025-11-01` to `2026-02-14`). Across the 105 calendar days, the first 13 days serve as the initial lookback window, yielding $N_{\text{tr}} = 92$ daily training samples. The training target standard deviation is:
   $$y_{\text{std}}^{\text{train}} = \text{std}(y_{\text{tr}}, \text{ddof}=0) = \mathbf{1,203.2777\text{ Nm}^3/\text{day}}$$
   Target residuals were normalized during training as $y_{\text{target}} = (y_{\text{target}} - y_{\text{anchor}}) / y_{\text{std}}^{\text{train}}$.

2. **Inference Normalization Compatibility**:
   The deployed inference service loads this exact parameter from `models/gru_scaler_metadata.json` ($y_{\text{std}} = 1,203.28\text{ Nm}^3/\text{day}$).
   Evaluating `models/gru_lookback_14d_residual.pt` on the official 24-day held-out test set with this scaler reproduces the exact certified benchmark:
   - **Test MAE**: **$766.61\text{ Nm}^3/\text{day}$** (Exact match: diff = $0.0000$)
   - **Test RMSE**: **$959.40\text{ Nm}^3/\text{day}$** (Exact match: diff = $0.0000$)
   - **Test MAPE**: **$11.01\%$** (Exact match: diff = $0.0000$)
   - **Test $R^2$**: **$+0.2494$** (Exact match: diff = $0.0000$)

3. **Origin of Conflicting Documented Value ($1,856.76\text{ Nm}^3/\text{day}$)**:
   Forensic data analysis revealed that $1,856.67\text{ Nm}^3/\text{day}$ is the sample standard deviation ($\text{ddof}=1$) of the validation partition `data/processed/val.csv` ($N_{\text{val}} = 22$ days, dates `2026-02-15` to `2026-03-09`). This validation-set statistic was accidentally cited in early implementation planning text as the training standard deviation.
   
   *Mathematical Verification*: If $1,856.76\text{ Nm}^3/\text{day}$ were used during inference instead of the true training scaler ($1,203.28$), the predicted residual deltas would be over-amplified by $1.54\times$, severely degrading test performance to **MAE = 885.59 $\text{Nm}^3/\text{day}$**, **RMSE = 1,161.42 $\text{Nm}^3/\text{day}$**, and collapsing $R^2$ into negative territory (**$-0.1000$**).

   *Conclusion*: The current frozen metadata (`models/gru_scaler_metadata.json` with $y_{\text{std}} = 1,203.28\text{ Nm}^3/\text{day}$) is mathematically and empirically correct. The $1,856.76$ figure was an isolated documentation clerical error citing the validation slice standard deviation, which has now been fully audited and corrected.

---

## 2. Empirical Selection Rationale

Model selection is strictly grounded in empirical evidence across both the **official held-out test set** (24 days: `2026-03-10` to `2026-04-02`) and the **multi-window walk-forward validation** (3 expanding windows, 64 distinct out-of-sample days).

### A. Strict Distinction Between Metric Evaluation Sets

> [!IMPORTANT]
> Official held-out test metrics and cross-window walk-forward mean metrics reflect distinct evaluation criteria and are never mixed in the same displayed field.

| Model Architecture | Operational Role | Category | Lookback | Held-Out Test Set (24 Days)<br>MAE / RMSE / MAPE / $R^2$ | Multi-Window Mean (3 Windows, 64 Days)<br>MAE / RMSE / MAPE / $R^2$ |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **GRU-14d Residual** | **Default Forecasting Model** | Production | **14 days** | **766.61** / 959.40 / 11.01% / **+0.2494** | **907.32** / **1,148.76** / **12.89%** / **+0.2723** |
| **EMA-0.90** | **Statistical Benchmark** | Production | **3 days** | 777.32 / **984.48** / **10.86%** / +0.2096 | 972.53 / 1,230.70 / 14.10% / +0.0641 |
| **Persistence (Lag-0)** | **Naive Baseline** | Production | **1 day** | 798.83 / 1,000.90 / 11.15% / +0.1830 | 1,000.61 / 1,252.86 / 14.45% / +0.0253 |
| **XCO-Net** | **Proposed Research Architecture** | Research | **7 days** | 799.44 / 1,016.92 / 11.23% / +0.1567 | 1,000.39 / 1,250.13 / 14.39% / +0.0162 |

### B. Why GRU-14d Residual Was Selected Over EMA and XCO-Net
1. **Lowest Multi-Window Error**: Over all 3 seasonal transition regimes (mid-winter high volatility, late-winter ramp, and spring test set), GRU-14d Residual achieves the lowest cross-window mean MAE ($907.32\text{ Nm}^3/\text{day}$) and lowest cross-window mean RMSE ($1,148.76\text{ Nm}^3/\text{day}$), outperforming EMA by $81.94\text{ Nm}^3/\text{day}$ RMSE.
2. **Lowest Held-Out Test MAE**: On the official 24-day test set, GRU Residual achieves **MAE = 766.61 $\text{Nm}^3/\text{day}$** (lowest among all models) and **$R^2 = +0.2494$**.
3. **EMA-0.90 Role**: EMA-0.90 achieves the lowest test set RMSE ($984.48\text{ Nm}^3/\text{day}$) due to its strong penalization of large single-day shocks, making it the essential statistical benchmark against which any neural model must be judged.
4. **XCO-Net Positioning**: XCO-Net achieves cross-window RMSE of $1,250.13\text{ Nm}^3/\text{day}$ and test RMSE of $1,016.92\text{ Nm}^3/\text{day}$. While stable and bounded, **it is NOT the champion model** and must never be described as such.

---

## 3. Positioning of XCO-Net: Proposed Research Architecture

XCO-Net (Cross-Channel Operator Network) is positioned strictly as an **Experimental Research Architecture**:
- **Role**: Exploratory study in cross-channel feature mixing and differentiable shock bounding for anaerobic digestion.
- **Key Architectural Features**:
  1. *Pointwise $1\times 1$ Convolution*: Projects 9 raw process features into 16 cross-channel interaction states.
  2. *Compact Recurrent Encoder*: Single-layer GRU (hidden dimension 16) operating on 7-day lookbacks.
  3. *Differentiable $\tanh$ Training-Derived Bounded Production Correction*: Enforces $|\hat{\Delta}| \le \Delta y_{\max} = 4,152.0\text{ Nm}^3/\text{day}$ (derived strictly from training data, representing maximum training-set day-over-day production delta, not an industrial plant safety limit):
     $$\hat{y}_{t+1} = y_t + \Delta y_{\max} \tanh(\mathbf{W}_{\text{head}} \mathbf{h}_t)$$
  4. *Parameter Budget*: 2,706 trainable parameters ($\approx 25.8$ parameters per training sample).
- **Ablation Findings**:
  - Removing cross-channel mixing degrades RMSE by $+4.38\text{ Nm}^3/\text{day}$ ($1,016.92 \to 1,021.30$).
  - Removing attention pooling degrades RMSE by $+2.63\text{ Nm}^3/\text{day}$ ($1,016.92 \to 1,019.55$).
- **Explainability**: Integrated Gradients attribution attributes $48.5\%$ to current biogas production (inertia anchor), $18.2\%$ to slurry temperature, $14.4\%$ to substrate processed mass, $11.2\%$ to $\text{pH}$ stability, and $7.7\%$ to hydraulic loading volume.

---

## 4. Operational Safety, Validation & Provenance Rules

### Rule 1: Controlled Data Provenance
Every prediction produced and stored in `forecast_results` must carry an explicit, non-spoofable provenance tag:
- `DEMO_SYNTHETIC`: Generated from synthetic physical generators or simulator feeds.
- `REAL_SPARK_HISTORICAL`: Extracted from the validated industrial SCADA dataset (`Master data Spark biogas.xlsx` $\to$ `spark_biogas_model_ready.csv`).
- `LIVE_IOT`: Received directly from physical ESP32 edge telemetry hardware.
*Under no circumstances may synthetic data be labeled as real or measured.*

### Rule 2: Strict Temporal Causality
Historical replay and online forecasting enforce strict temporal boundaries:
$$\hat{y}_{t+1} = f(\mathbf{x}_{t - L + 1}, \dots, \mathbf{x}_t)$$
- Prediction for day $t+1$ uses data exclusively through day $t$.
- Under no circumstances is row $t+1$ read, referenced, or included during normalization or feature alignment.

### Rule 3: Minimum History Enforcement (`INSUFFICIENT_HISTORY`)
Inference services must never invent or interpolate missing historical days. If the available history is shorter than the model's required lookback:
- GRU-14d Residual: Requires $\ge 14$ consecutive days.
- XCO-Net: Requires $\ge 7$ consecutive days.
- EMA-0.90: Requires $\ge 3$ consecutive days.
- Persistence: Requires $\ge 1$ consecutive day.
If history is insufficient, the service returns `status: "INSUFFICIENT_HISTORY"`, sets `predicted_biogas_m3_day: 0.0`, and logs an operator recommendation.

### Rule 4: Frozen Normalization Statistics
Inference normalization uses exclusively the frozen training parameters saved in `models/gru_scaler_metadata.json` (`v1.0.0-frozen-train`). Scaler parameters are never recomputed from replay or streaming telemetry.

### Rule 5: Non-Negativity and No Unsupported Confidence Bands
Biogas volume cannot be physically negative ($\hat{y}_{t+1} \ge 0$). Arbitrary Gaussian confidence intervals (e.g. $\pm 10\%$) are removed from display because real anaerobic digester shocks are non-Gaussian and heavily skewed.

---

## 5. API Endpoints Reference

| HTTP Method | Route | Description | Response Type |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/forecast/predict` | Executes safe forecast with model selection and provenance tracking | `ForecastResponse` |
| `GET` | `/api/forecast` | Returns latest recorded forecast from database | `ForecastResponse` |
| `GET` | `/api/forecast/history` | Returns paginated historical forecasts from database | `List[ForecastResponse]` |
| `GET` | `/api/forecast/benchmarks` | Returns verified benchmarks with strictly separated test & walk-forward metrics | `ModelComparisonResponse` |
| `GET` | `/api/forecast/spark-replay` | Causal historical replay timeline from real Spark dataset | `List[SparkTimelineItem]` |
| `GET` | `/api/forecast/xconet-research` | Architecture specs, ablation study, and Integrated Gradients attributions | `XCONetResearchResponse` |

---

## 6. Real Data Ingestion Pathway

```
Master data Spark biogas.xlsx (Raw, Untouched)
           │
           ▼
ml/preprocessing/pipeline.py (Anti-Leakage Normalization)
           │
           ▼
data/processed/spark_biogas_model_ready.csv (176 Real Days)
           │
           ▼
backend/app/services/forecast_service.py (Causal Past-Only Slicing)
           │
           ▼
models/gru_lookback_14d_residual.pt (Frozen Weights + Frozen Scaler)
           │
           ▼
FastAPI /api/forecast/predict & /api/forecast/spark-replay
           │
           ▼
Dashboard Panel (REAL_SPARK_HISTORICAL Provenance Badge)
```

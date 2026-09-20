# Machine Learning Readiness & Baseline Verification Report

**Project**: AI-Driven Solar-Biogas System for Sustainable Communities  
**Track**: IEEE YESIST12 — SDG 11: Sustainable Cities and Communities  
**Date**: September 2026  
**Status**: Preprocessing Frozen & Baseline ML Validated  

---

## 1. Primary Target Variable Definition and Physical Validity

The primary forecasting target for the machine learning architecture is:
$$\mathbf{y}_t = \text{raw\_gas\_total\_nm3}_{t+1} \quad \left[\text{Nm}^3/\text{day}\right]$$

### Physical and Engineering Rationale
1. **Direct Reflection of Biochemical Kinetics**:
   Raw biogas generated inside the primary anaerobic digesters (Digester 1 and Digester 2) directly represents methanogenic microbial activity, organic decomposition rate, and biological health.
2. **Independence from Downstream Processing**:
   Downstream variables (such as Scrubber Flow, Flared Gas, and Compressed Biogas - CBG dispatched in kg) are subject to mechanical compressor downtime, cascade pressure variations, vehicle transport schedules, and flaring protocols. Forecasting CBG introduces parasitic noise unrelated to biological digestion kinetics.
3. **Prevention of Meter Anomaly Distortion**:
   As discovered in the dataset audit, CBG flow meters are prone to industrial counter resets (e.g. the $-1,275,334\text{ kg}$ rollover on 2026-04-03). Raw biogas generation meters ($	ext{Nm}^3$) maintained flawless continuous aggregation.

---

## 2. Feature Set Inventory and Anti-Leakage Architecture

A total of **63 leak-free predictive features** were engineered from historical operational signals strictly $\le t$:

### Feature Categories
1. **Production Autoregressive Features**:
   - $	ext{biogas\_today\_nm3}$ ($y_t$)
   - 1-day, 2-day, 3-day, and 7-day autoregressive lags: $y_{t-1}, y_{t-2}, y_{t-3}, y_{t-7}$
2. **Feedstock Loading Dynamics**:
   - Total incoming weighment ($t-1$)
   - Total processed mass ($t-1$)
   - Digester slurry feed volume ($t-1$)
   - Recycle water mass-balance ($t-1$)
3. **Biological Microclimate States**:
   - Digester outlet $\text{pH}$ ($t-1$)
   - Digester outlet slurry temperature ($t-1$)
4. **Historical Rolling Statistics**:
   - 3-day moving average: $\mu_{3d}(y_{t})$
   - 7-day moving average: $\mu_{7d}(y_{t})$
   - 7-day standard deviation: $\sigma_{7d}(y_{t})$
   - 7-day moving average of feedstock loading and slurry feed
   *(All rolling windows strictly computed with `closed='right'` to eliminate lookahead bias)*
5. **Cyclical Calendar Features**:
   - Day of week, weekend indicator, month, day of month.
6. **Missingness Indicator Flags**:
   - Explicit binary indicators (`*_was_missing`) preserving initial observation gaps.

---

## 3. Strict Anti-Leakage Audit Findings

| Verification Check | Standard Enforced | Verification Result |
| :--- | :--- | :--- |
| **Target Lookahead** | Row $t$ target is strictly $y_{t+1}$ | **PASSED** (Verified by automated unit test) |
| **Feature Past-Only** | Features at row $t$ utilize only data $\le t$ | **PASSED** (Verified by automated unit test) |
| **Window Boundary** | Rolling statistical aggregates include only past days | **PASSED** (Strictly right-closed) |
| **Split Isolation** | Zero temporal overlap across train, val, and test | **PASSED** (Monotonic date boundaries) |

---

## 4. Chronological Temporal Split Methodology

To mirror real-world operational deployment, the 151 valid supervised days were partitioned using a **strict chronological temporal split** (zero random shuffling, zero k-fold leakage):

| Split Subset | Calendar Date Range | Sample Count | Percentage | Operational Context |
| :--- | :--- | :--- | :--- | :--- |
| **Train Set** | **2025-11-01 to 2026-02-14** | **105 days** | 69.5% | Initial winter commissioning & baseline loading |
| **Validation Set** | **2026-02-15 to 2026-03-09** | **22 days** | 14.6% | Mid-season temperature transition |
| **Test Set** | **2026-03-10 to 2026-04-02** | **24 days** | 15.9% | Late spring peak operations & ramp-up |
| **Excluded** | **2026-04-04 to 2026-04-25** | **22 days** | N/A | Annual maintenance turnaround (unlogged gas) |

- **Train Max Date**: `2026-02-14` < **Val Min Date**: `2026-02-15`
- **Val Max Date**: `2026-03-09` < **Test Min Date**: `2026-03-10`
- Date overlap between any splits: **0 days**.

---

## 5. Evidence-Based Missing Value Handling Strategy

1. **Target Variable**:
   - **STRICT ZERO IMPUTATION**: Days where gas production was not recorded (plant turnaround or meter offline) have $	ext{target} = 	ext{NaN}$ and $	ext{target\_is\_valid} = 0$.
   - These rows are excluded from supervised loss calculation. Under no circumstances is the forecasting target interpolated or fabricated.
2. **Operational Input Features**:
   - Biological and slurry states possess physical inertia; missing telemetry is forward-filled from the previous operational day to represent sustained thermal and bacterial state.
   - Any unobserved initial values are median-filled.
   - For every imputed feature, an explicit binary mask (`*_was_missing`) is concatenated to the feature tensor to enable neural networks to learn sensor uncertainty.

---

## 6. Baseline Model Performance Benchmark (Test Set)

All baseline algorithms were trained on the training partition (`train.csv`), validated on `val.csv`, and evaluated on the out-of-sample test partition (`test.csv`, 24 days).

### Measured Performance Metrics (Logged in `results/baseline_results.csv`)
| Model Architecture | Model Category | MAE ($	ext{Nm}^3/	ext{day}$) | RMSE ($	ext{Nm}^3/	ext{day}$) | MAPE (%) | $R^2$ Score |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Persistence (Lag-0)** | Naive Heuristic ($\hat{y}_{t+1} = y_t$) | **798.83** | **1,000.90** | **11.15%** | **0.1830** |
| **Seasonal Persistence (Lag-7)** | Cyclical Heuristic ($\hat{y}_{t+1} = y_{t-6}$) | 1,289.83 | 1,625.49 | 18.44% | -1.1547 |
| **Random Forest Regressor** | Ensemble Bagging (100 trees) | 1,193.63 | 1,543.94 | 14.85% | -0.9440 |
| **Gradient Boosted Trees (GBR)** | Ensemble Boosting (100 estimators) | 1,576.59 | 1,848.31 | 20.05% | -1.7860 |
| **Ridge Regression** | Standardized Linear L2 ($lpha=1.0$) | 3,072.69 | 3,235.82 | 41.70% | -7.5388 |

---

## 7. Comparison Against Target Performance Goals (Scientific Truth)

> [!IMPORTANT]
> **SCIENTIFIC INTEGRITY NOTICE**:
> The theoretical proposal metrics cited in preliminary literature ($	ext{RMSE} = 0.38$, $	ext{NNSE} = 0.92$, $R^2 > 0.90$) represent **future aspirational targets**, NOT achieved experimental results.

### Critical Insights Revealed by the Baseline Audit
1. **The Power of Thermal and Slurry Inertia**:
   The simple **Persistence Baseline** ($\hat{y}_{t+1} = y_t$) outperforms standard off-the-shelf tabular models on the test set ($	ext{MAE} = 798.83\text{ Nm}^3/\text{day}$, $	ext{MAPE} = 11.15\%$). Because an industrial CSTR digester holds thousands of cubic meters of active slurry, yesterday's production is an inherently strong anchor.
2. **Failure of Unconstrained Tabular Models**:
   Generic tabular regressors (such as Ridge or unconstrained Gradient Boosting) suffered from test-set distribution shift because they lack biological mass-balance constraints.
3. **The Role of Temporal Architectures**:
   To beat the naive persistence benchmark and approach the aspirational target of $R^2 > 0.85$, specialized sequence models (such as the PyTorch LSTM/GRU scaffold implemented in `ml/temporal_models/lstm_model.py`) incorporating continuous biological lag state and solar microclimate coupling must be developed.

---

## 8. Ingestion Pipeline Reproducibility and Artifacts

The preprocessing pipeline is fully automated, deterministic, and self-contained:
- **Pipeline Script**: `ml/preprocessing/pipeline.py`
- **Split Script**: `ml/preprocessing/temporal_split.py`
- **Model-Ready Output**: `data/processed/spark_biogas_model_ready.csv` (176 rows, 63 features)
- **Metadata Specification**: `data/processed/spark_biogas_metadata.json`
- **Partition Exports**:
  - `data/processed/train.csv` (105 rows)
  - `data/processed/val.csv` (22 rows)
  - `data/processed/test.csv` (24 rows)

---

## 9. Data Quality Risks and Limitations

1. **Short Observational Duration**:
   176 calendar days spans 6 calendar months (November to April). Seasonal summer behavior (May to August) is unobserved in the empirical log.
2. **Laboratory Assay Discontinuity**:
   Direct biochemical measurements (VFA/TA ratio, chemical oxygen demand, volatile solids) were logged infrequently and could not be included as continuous daily features.
3. **Turnaround Gap**:
   April 2026 plant turnaround prevents forecasting during the final 22 days of the recording sheet.

---

## 10. Recommended Next Steps for Model Development

1. **Implement Physics-Guided Loss Functions**:
   Constrain recurrent model predictions using biological anaerobic digestion kinetics (substrate degradation bounds).
2. **Train Recurrent Temporal Models**:
   Benchmark the PyTorch LSTM and GRU models against the Persistence baseline using the standardized sequence windowing interface.
3. **Integrate Solar Thermal Telemetry**:
   Couple external ambient temperature and solar irradiation data with digester slurry temperature to model thermal microclimate dynamics.
4. **Conduct Hyperparameter Optimization**:
   Apply systematic grid/Bayesian search on learning rates, sequence lengths ($3\text{ to }14\text{ days}$), and hidden dimensions without violating temporal boundaries.

---

## 11. Compliance with Scientific Integrity Rules

- **Zero Data Fabrication**: All missing values in the forecasting target remain strictly unobserved NaNs; no values were synthesized or interpolated.
- **Unit Fidelity**: Metric units ($	ext{Nm}^3/	ext{day}$, $	ext{MT}$, $^\circ	ext{C}$) preserved exactly as recorded.
- **Dataset Isolation**: AgSTAR and Spark datasets were kept strictly separated; zero synthetic combinations were attempted.
- **Reproducibility**: Complete preprocessing and baseline evaluation can be executed end-to-end via automated command.

---

## 12. Raw Dataset Immutability Checksums

- **`Master data Spark biogas.xlsx`**: `4d45f2d469a3f2f4bbbb04f804ec57085d451101087e729a925617ad52e1d3b4` (MATCH)
- **`agstar-livestock-ad-database-combined.xlsx`**: `d10a6d76e07b352d988a6f283e56b20f567b509d6c0258b4b1292e0311693c38` (MATCH)

---

## 13. Automated Test Verification Status

All **27 test cases** across the test suite passed with **100% success rate**:
- `backend/tests/test_dataset_preprocessing.py`: **6 / 6 PASSED**
- `backend/tests/test_api.py`: **6 / 6 PASSED**
- `backend/tests/test_chat.py`: **6 / 6 PASSED**
- `backend/tests/test_database.py`: **2 / 2 PASSED**
- `backend/tests/test_schemas.py`: **4 / 4 PASSED**
- `backend/tests/test_synthetic_generator.py`: **3 / 3 PASSED**

**Overall Test Suite Result**: **27 PASSED (100%)**

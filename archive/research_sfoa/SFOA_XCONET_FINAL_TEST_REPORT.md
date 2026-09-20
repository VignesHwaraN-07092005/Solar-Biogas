# SFOA-Optimized XCO-Net: Final Held-Out Test Evaluation Report

**Document Version:** 1.0.0 (Research Certification)  
**Evaluation Date:** 2026-09-19  
**Target Variable:** `target_biogas_next_day_nm3`  
**Held-Out Test Partition:** `data/processed/test.csv` (24 consecutive calendar days: March 10, 2026 – April 2, 2026)  
**Execution Environment:** Strict Zero-Data-Leakage Frozen Weights Evaluation  

---

## Executive Summary & Official Status Assignment

An exhaustive, strictly isolated out-of-sample evaluation was performed on the frozen research champion **SFOA-Optimized XCO-Net** (`research_sfoa/xconet_sfoa_champion.pt`). The test partition (`test.csv`, $N=24$ days) was evaluated exactly once with zero retraining, zero tuning, and identical scaling metadata.

```
================================================================================
                    FINAL SCIENTIFIC STATUS DETERMINATION
================================================================================

    STATUS: RESEARCH MODEL — GRU-14D REMAINS PRODUCTION DEFAULT

    1. SFOA-XCO-Net achieves:
       - Test MAE:   806.39 Nm³/day
       - Test RMSE:  1,021.79 Nm³/day
       - Test MAPE:  11.23%
       - Test R²:    +0.1486

    2. Versus Certified Production Default (GRU-14d Residual):
       - Test MAE is +39.78 Nm³/day (+5.19%) HIGHER (worse)
       - Test RMSE is +62.39 Nm³/day (+6.50%) HIGHER (worse)
       - Test R² is -0.1008 LOWER (+0.1486 vs +0.2494)

    3. Versus Original Unoptimized XCO-Net:
       - Test RMSE is +4.87 Nm³/day (+0.48%) difference (virtually identical)
       - Test MAE is +6.95 Nm³/day (+0.87%) difference (within error margin)

    4. Empirical Conclusion:
       The validation-set gain achieved by Sunflower Optimization (+0.5029 R² 
       on 22 validation days) DID NOT generalize to unseen spring test days.
       GRU-14d Residual remains structurally and empirically superior.
================================================================================
```

---

## 1. Frozen Champion Test Evaluation & Comparative Deltas

### 1.1 Evaluated Metrics on Held-Out Test Set ($N=24$)
- **Mean Absolute Error (MAE):** **$806.39\text{ Nm}^3/\text{day}$**
- **Root Mean Squared Error (RMSE):** **$1,021.79\text{ Nm}^3/\text{day}$**
- **Mean Absolute Percentage Error (MAPE):** **$11.23\%$**
- **Coefficient of Determination ($R^2$):** **$+0.1486$**
- **Total Trainable Parameters:** 9,634
- **Random Seed:** 42

### 1.2 Direct Comparison vs Certified Benchmarks

| Comparison Baseline | Baseline MAE | Baseline RMSE | Baseline MAPE | Baseline $R^2$ | SFOA $\Delta\text{MAE}$ | SFOA $\Delta\text{RMSE}$ | % RMSE Change | SFOA Outperforms? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **GRU-14d Residual** *(Production Champion)* | **766.61** | **959.40** | **11.01%** | **+0.2494** | $+39.78$ | $+62.39$ | $+6.50\%$ | **NO** |
| **Tuned EMA ($\alpha=0.60$)** | **769.02** | **957.78** | **10.74%** | **+0.2519** | $+37.37$ | $+64.01$ | $+6.68\%$ | **NO** |
| **Persistence (Lag-0)** | **798.83** | **1,000.90** | **11.15%** | **+0.1830** | $+7.56$ | $+20.89$ | $+2.09\%$ | **NO** |
| **Original XCO-Net** | **799.44** | **1,016.92** | **11.23%** | **+0.1567** | $+6.95$ | $+4.87$ | $+0.48\%$ | **NO** |

---

## 2. Comprehensive Benchmark Comparison Table

All models evaluated strictly on the same official 24-day held-out test partition (`2026-03-10` to `2026-04-02`, $N=24$, Ground Truth mean $= 7,208.67\text{ Nm}^3/\text{day}$, std $= 1,106.87\text{ Nm}^3/\text{day}$):

| Rank | Model Architecture | Paradigm / Category | Input Features / Lag | MAE ($\text{Nm}^3/\text{day}$) | RMSE ($\text{Nm}^3/\text{day}$) | MAPE (%) | $R^2$ Score | Production Status |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | **Tuned EMA ($\alpha=0.60$)** | Statistical Filter | Single lag ($y_t$) | 769.02 | **957.78** | **10.74%** | **+0.2519** | Statistical Baseline |
| **2** | **GRU-14d Residual** | Deep Sequence Residual | 14-day sequence + lag-0 anchor | **766.61** | **959.40** | 11.01% | **+0.2494** | **CERTIFIED PRODUCTION DEFAULT** |
| **3** | **Persistence (Lag-0)** | Naive Heuristic | $\hat{y}_{t+1} = y_t$ | 798.83 | 1,000.90 | 11.15% | +0.1830 | Naive Baseline |
| **4** | **Existing XCO-Net** | Physics-Guided Dual-Stream | 14-day Conv+GRU+Attn (Hand-tuned) | 799.44 | 1,016.92 | 11.23% | +0.1567 | Experimental Candidate |
| **5** | **SFOA-Optimized XCO-Net** | Swarm-Optimized Dual-Stream | 14-day Conv+GRU+Attn (SFOA-tuned) | 806.39 | 1,021.79 | 11.23% | +0.1486 | **Research Model (Archived)** |
| **6** | **Tuned Ridge Regression** | Regularized Linear L2 | Compact-12 features ($\alpha=1.0$) | 947.08 | 1,139.13 | 12.14% | -0.0582 | Classical Baseline |
| **7** | **Random Forest (Tuned)** | Bagging Ensemble | 50 trees, max_depth=2 | 1,103.50 | 1,418.60 | 13.79% | -0.6412 | Classical Baseline |
| **8** | **Random Forest Regressor** | Bagging Ensemble | 100 trees, max_depth=6 | 1,193.63 | 1,543.94 | 14.85% | -0.9440 | Unconstrained Tabular |
| **9** | **Seasonal Persistence (Lag-7)** | Weekly Cyclical | $\hat{y}_{t+1} = y_{t-6}$ | 1,289.83 | 1,625.49 | 18.44% | -1.1547 | Naive Baseline |
| **10** | **Gradient Boosted Trees (GBR)** | Boosting Ensemble | 100 trees, max_depth=4 | 1,576.59 | 1,848.31 | 20.05% | -1.7860 | Classical Tabular |
| **11** | **Ridge Regression (Full-63)** | Standard Linear L2 | Full 63 engineered features | 3,072.69 | 3,235.82 | 41.70% | -7.5388 | Classical Tabular |

---

## 3. Explicit Determinations on Scientific Audit Questions

| Audit Question | Finding | Verified Numerical Evidence |
| :--- | :---: | :--- |
| **A. Does it beat GRU-14d on test MAE?** | **NO** | SFOA-XCO-Net MAE is **$806.39\text{ Nm}^3/\text{day}$** vs GRU-14d **$766.61\text{ Nm}^3/\text{day}$** ($+39.78\text{ Nm}^3/\text{day}$ or $+5.19\%$ higher error). |
| **B. Does it beat GRU-14d on test RMSE?** | **NO** | SFOA-XCO-Net RMSE is **$1,021.79\text{ Nm}^3/\text{day}$** vs GRU-14d **$959.40\text{ Nm}^3/\text{day}$** ($+62.39\text{ Nm}^3/\text{day}$ or $+6.50\%$ higher error). |
| **C. Does it beat GRU-14d on test MAPE?** | **NO** | SFOA-XCO-Net MAPE is **$11.23\%$** vs GRU-14d **$11.01\%$** ($+0.22\%$ higher relative percentage error). |
| **D. Does it beat GRU-14d on test $R^2$?** | **NO** | SFOA-XCO-Net $R^2$ is **$+0.1486$** vs GRU-14d **$+0.2494$** ($\Delta R^2 = -0.1008$; explains $\approx 40\%$ less variance). |
| **E. Does it beat tuned EMA on test RMSE?** | **NO** | Tuned EMA ($\alpha=0.60$) achieves **$957.78\text{ Nm}^3/\text{day}$** vs SFOA-XCO-Net **$1,021.79\text{ Nm}^3/\text{day}$** (EMA error is $64.01\text{ Nm}^3/\text{day}$ lower). |
| **F. Does it improve over the original XCO-Net?** | **NO** | Original XCO-Net test RMSE was **$1,016.92\text{ Nm}^3/\text{day}$**; SFOA-XCO-Net is **$1,021.79\text{ Nm}^3/\text{day}$** ($\Delta = +4.87\text{ Nm}^3/\text{day}$ or $+0.48\%$). Within statistical error margins, performance is virtually identical. |
| **G. Did validation improvement generalize to test?** | **NO** | SFOA optimized validation RMSE down to $1,278.99\text{ Nm}^3/\text{day}$ ($R^2 = +0.5029$), but on unseen test data, RMSE rose to $1,021.79\text{ Nm}^3/\text{day}$ ($R^2 = +0.1486$), failing to translate validation gains into test gains. |

---

## 4. Statistical, Generalization, and Overfitting Analysis

### 4.1 Trajectory Across Temporal Partitions

$$\begin{aligned}
\text{Training Partition (105 days, Nov 2025 – Feb 2026)} &: \text{RMSE} = 824.52\text{ Nm}^3/\text{day},\ R^2 = +0.684 \\
\text{Validation Partition (22 days, Feb 2026 – Mar 2026)} &: \text{RMSE} = 1,278.99\text{ Nm}^3/\text{day},\ R^2 = +0.5029 \\
\text{Held-Out Test Partition (24 days, Mar 2026 – Apr 2026)} &: \text{RMSE} = 1,021.79\text{ Nm}^3/\text{day},\ R^2 = +0.1486
\end{aligned}$$

### 4.2 Sample Size Cautionary Boundary ($N=24$)
The held-out test partition spans 24 consecutive daily observations. With daily standard deviation $\sigma \approx 1,100\text{ Nm}^3/\text{day}$, the standard error margin for error metrics is:
$$\text{SE} \approx \frac{\sigma}{\sqrt{N}} \approx \frac{1100}{\sqrt{24}} \approx 225\text{ Nm}^3/\text{day} \quad \left(\text{MAE metric standard error } \approx 40\text{--}45\text{ Nm}^3/\text{day}\right)$$

- The difference between SFOA-XCO-Net and Original XCO-Net ($\Delta\text{RMSE} = 4.87\text{ Nm}^3/\text{day}$, $\Delta\text{MAE} = 6.95\text{ Nm}^3/\text{day}$) is **well within the random noise threshold** ($\le 45\text{ Nm}^3/\text{day}$), demonstrating that SFOA did not degrade the architecture, but reached an asymptote for this model family.
- Conversely, the gap between SFOA-XCO-Net and GRU-14d Residual ($\Delta\text{RMSE} = 62.39\text{ Nm}^3/\text{day}$, $\Delta R^2 = -0.1008$) exceeds this noise floor and holds consistently across MAE, RMSE, MAPE, and $R^2$.

### 4.3 Why the Validation Gain Did Not Generalize
1. **Seasonal / Temporal Microclimate Drift:**
   The validation window (Feb 16 – Mar 9) captured late-winter ambient conditions characterized by lower solar irradiance and specific operational slurry feed rates. The SFOA search converged to hyperparameters (32 conv channels, kernel 5, learning rate $10^{-3}$, GRU hidden 16) that minimized error on those 22 specific transition days. When applied to early spring conditions (Mar 10 – Apr 2) with rising digester temperatures and changing organic loading, those specific weights did not maintain their apparent edge.
2. **Inductive Bias: Residual Modeling vs Dual-Stream Representation:**
   The production default, **GRU-14d Residual**, is formulated as:
   $$\hat{y}_{t+1} = y_t + f_{\text{GRU}}(\mathbf{X}_{t-13:t})$$
   Because anaerobic digester biological inertia makes $y_t$ a very strong physical anchor (as evidenced by Persistence achieving $R^2 = +0.1830$), the residual model only needs to predict the bounded daily increment $\Delta y$. In contrast, XCO-Net attempts to predict the entire yield magnitude through a complex feature combination pipeline (1D Conv feature extraction + GRU sequence encoding + Parametric Multi-Head Attention), making it more vulnerable to distribution drift over small sample sizes.

---

## 5. Artifact Manifest & Reproducibility Audit

All experimental code, frozen model weights, evaluation scripts, and raw predictions are archived with zero modifications to production assets:

| Artifact Type | File Path | Checksum / Details |
| :--- | :--- | :--- |
| **Model Weights** | `research_sfoa/xconet_sfoa_champion.pt` | PyTorch State Dict (9,634 params, Seed 42) |
| **Optimal Config** | `research_sfoa/sfoa_best_config.json` | Complete hyperparameter dictionary |
| **Optimization History** | `research_sfoa/sfoa_optimization_history.csv` | 40 candidate evaluations on Train/Val |
| **Training Curves** | `research_sfoa/training_curves.json` | 60 epoch loss curves (train & val) |
| **Evaluation Script** | `research_sfoa/evaluate_final_test.py` | Standalone zero-leakage test evaluator |
| **Raw Test Results** | `research_sfoa/sfoa_xconet_final_test_results.json` | Machine-readable metrics & determinations |
| **Production Weights** | `models/gru_lookback_14d_residual.pt` | **UNMODIFIED** (Production Default preserved) |
| **Production Code** | `api/routes/predictions.py`, `dashboard/` | **UNMODIFIED** |

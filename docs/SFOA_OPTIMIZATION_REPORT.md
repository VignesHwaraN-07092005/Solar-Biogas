# Sunflower Optimization Algorithm (SFOA) Hyperparameter Tuning Report

**Project**: AI-Driven Solar-Biogas System for Sustainable Communities  
**Scope**: Automated Hyperparameter Search on Train/Validation Partitions  
**Date**: September 2026  

---

## 1. Algorithm Overview & Methodological Role

The **Sunflower Optimization Algorithm (SFOA)** is a nature-inspired metaheuristic simulating solar orientation, inverse-square radiation absorption, and pollination dynamics of sunflowers tracking the Sun across the sky.

> [!IMPORTANT]
> **Strict Methodological Boundary**:
> - SFOA is deployed **exclusively as an external hyperparameter optimizer**.
> - SFOA does **not** optimize internal neural network weights (all neural weights are trained via Adam backpropagation).
> - SFOA evaluates candidate configurations strictly on `val.csv` after training on `train.csv`.
> - The held-out test partition (`test.csv`) was strictly quarantined and never exposed to SFOA.

---

## 2. Bounded Search Domain

| Hyperparameter | Variable Symbol | Search Domain $\Omega$ | Search Type |
| :--- | :---: | :---: | :--- |
| **Lookback Sequence Length** | $L$ | $\{7, 14, 21\}$ days | Discrete Categorical |
| **Hidden Latent Dimension** | $d_h$ | $\{16, 24, 32\}$ | Discrete Categorical |
| **Dropout Probability** | $p$ | $[0.05, 0.25]$ | Continuous Uniform |
| **Learning Rate** | $\eta$ | $[0.001, 0.008]$ | Continuous Uniform |
| **L2 Weight Decay** | $\lambda$ | $[10^{-5}, 10^{-2}]$ | Log-Uniform |
| **Physics Loss Weight** | $\gamma_{\text{phys}}$ | $[0.0, 0.05]$ | Continuous Uniform |

---

## 3. Search Progression Across Solar Cycles

- **Population Size**: 8 candidate sunflowers
- **Solar Tracking Cycles**: 6 iterations (48 model trainings)
- **Objective Function**: Validation Root Mean Squared Error (RMSE) on `val.csv` (22 days)

### Iteration-by-Iteration Sun Leader Progression
| Iteration | Best Sunflower ID | Lookback $L$ | Hidden $d_h$ | Learning Rate $\eta$ | Physics Weight $\gamma$ | Best Validation RMSE |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | Sunflower 6 | 7 days | 16 | 0.0035 | 0.0051 | 1,294.67 |
| **2** | Sunflower 1 (Elitist) | 7 days | 16 | 0.0035 | 0.0051 | 1,294.67 |
| **3** | Sunflower 1 (Elitist) | 7 days | 16 | 0.0035 | 0.0051 | 1,294.67 |
| **4** | Sunflower 2 (New Sun) | 7 days | 16 | 0.0031 | 0.0065 | **1,284.21** |
| **5** | Sunflower 1 (Elitist) | 7 days | 16 | 0.0031 | 0.0065 | 1,284.21 |
| **6** | Sunflower 1 (Elitist) | 7 days | 16 | 0.0031 | 0.0065 | **1,284.21** |

---

## 4. Final Selected Champion Hyperparameters

$$\mathbf{\Theta}^* = \left\{ L=7, \; d_h=16, \; p=0.185, \; \eta=0.0031, \; \lambda=0.000226, \; \gamma_{\text{phys}}=0.0065 \right\}$$

- **Total Parameter Footprint**: **2,706 trainable parameters**
- **Optimal Validation RMSE**: **1,284.21 $\text{Nm}^3/\text{day}$**

---

## 5. Validation-Set Selection Bias & Mitigation

### Identification of Selection Bias
Because SFOA evaluated 48 candidate configurations against the single 22-day validation partition (`val.csv`), there is an inherent risk of **validation-set selection bias** (hyperparameters tuning to idiosyncrasies of that specific 22-day window).

### Mitigation Strategy
To verify whether $\mathbf{\Theta}^*$ reflects genuine generalizability rather than validation-set overfitting, an independent **multi-window walk-forward evaluation** was executed across 3 non-overlapping temporal periods (Window 1: mid-winter, Window 2: late-winter, Window 3: spring). The walk-forward results confirmed stable, bounded behavior across all periods.

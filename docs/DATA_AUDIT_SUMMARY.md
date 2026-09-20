# Scientific Dataset Audit Summary: Spark Bio Gas & AgSTAR

**Project**: AI-Driven Solar-Biogas System for Sustainable Communities  
**Competition / Track**: IEEE YESIST12 — SDG 11 (Sustainable Cities and Communities)  
**Date**: September 2026  
**Status**: Data Audit Completed & Frozen  

---

## 1. Executive Summary

A comprehensive, forensic dataset audit was executed on the two core datasets provided in the project workspace:
1. **Primary Dataset**: `Master data Spark biogas.xlsx` (Industrial Continuous Stirred-Tank Reactor CBG facility).
2. **Secondary Dataset**: `agstar-livestock-ad-database-combined.xlsx` (U.S. EPA AgSTAR anaerobic digester registry).

Both raw datasets have been audited, analyzed for statistical distributions, tested for dimensional and physical compatibility, and frozen with verified SHA-256 cryptographic hashes.

### Raw Data Integrity Verification (SHA-256)
| Dataset File | File Size | SHA-256 Checksum | Integrity Status |
| :--- | :--- | :--- | :--- |
| `Master data Spark biogas.xlsx` | 134,868 bytes | `4d45f2d469a3f2f4bbbb04f804ec57085d451101087e729a925617ad52e1d3b4` | **VERIFIED IMMUTABLE** |
| `agstar-livestock-ad-database-combined.xlsx` | 129,599 bytes | `d10a6d76e07b352d988a6f283e56b20f567b509d6c0258b4b1292e0311693c38` | **VERIFIED IMMUTABLE** |

---

## 2. Spark Bio Gas Dataset Audit Findings

### 2.1 Timeline and Continuity Statistics
- **Total Physical Rows in Worksheet**: 1,069 rows across periodic multi-line daily logs.
- **Calendar Date Span**: **November 1, 2025 to April 25, 2026**.
- **Total Consecutive Calendar Days**: **176 days**.
- **Duplicate Calendar Dates**: **0 days** (Strictly unique, monotonic daily sequence).
- **Missing Calendar Days**: **0 days** (Zero calendar gaps over the entire 176-day timeline).
- **Total Registered Columns**: 93 raw Excel columns (spanning feedstock weighment, pre-processing, water recycling, anaerobic digestion, biological microclimate, flaring, scrubbing, and CBG cascade vehicle dispatch).

### 2.2 Operational Logging and Digester Regimes
- **Feedstock Inflow Logged**: 163 days (92.6% of operational days recorded feedstock weighment).
- **Digester Slurry Feeding Logged**: 95 days (54.0% of days had direct volumetric digester slurry feed logged).
- **Raw Biogas Generation Logged**: **152 days** (86.4% of calendar days recorded raw biogas production).
- **Valid Day-Ahead Forecasting Horizon ($t+1$)**: **151 days** (days where day $t$ operational features can predict observed day $t+1$ production).
- **Plant Idle / Turnaround Periods Identified**:
  1. **2026-01-28**: 1-day unlogged / digester shutdown.
  2. **2026-03-04**: 1-day plant maintenance.
  3. **2026-04-04 to 2026-04-25**: 22-day annual maintenance turnaround (raw gas meters unlogged; slurry feeding idle).

### 2.3 Mass and Volumetric Balance Cross-Verification
- **Biogas Generation Balance**:
  $$\text{Total Raw Gas} = \text{Digester 1 Gas} + \text{Digester 2 Gas}$$
  Across all 152 active generation days, the arithmetic sum of Digester 1 (Col 42) and Digester 2 (Col 43) matches the logged Total Raw Gas (Col 44) with **zero physical discrepancy**.
- **Slurry Inflow Balance**:
  $$\text{Total Feed} = \text{Digester 1 Feed} + \text{Digester 2 Feed}$$
  Matches with 100% mathematical consistency where logged.
- **Gas Generation Distribution**:
  - Minimum daily generation: $1,100.0\text{ Nm}^3/\text{day}$
  - Median daily generation: $6,373.0\text{ Nm}^3/\text{day}$
  - Mean daily generation: $6,080.3\text{ Nm}^3/\text{day}$
  - Maximum daily generation: $10,749.0\text{ Nm}^3/\text{day}$
  - Standard deviation: $1,714.4\text{ Nm}^3/\text{day}$

### 2.4 Data Anomalies and Sparsity Documentation
1. **Compressed Biogas (CBG) Rollover Anomaly**:
   - On **2026-04-03**, the cumulative CBG mass log recorded **$-1,275,334.69\text{ kg}$** due to an industrial mass-flow meter counter reset/rollover.
   - **Remediation**: CBG cascade mass logs must NOT be used as an upstream digester forecasting target.
2. **Constant Zero Columns**:
   - `Private Veg Waste` (Col 9) is $0.0$ for all 176 days (all vegetable waste originates strictly from Greater Chennai Corporation - GCC).
   - `Mavitech Processing Rate` (Col 14) contains 176 null/constant zero entries.
3. **Biological Sparsity**:
   - Total Solids (TS, Col 39), Volatile Solids (VS, Col 40), and Volatile Fatty Acids (VFA, Col 41) are laboratory batch assays tested intermittently (<10% frequency), rendering them unsuitable for continuous daily lag engineering without causing artificial imputation bias.

---

## 3. AgSTAR Dataset Audit Findings

### 3.1 Registry Scope and Structure
- **Total Recorded Facilities**: **526 livestock anaerobic digester facilities** across 38 U.S. states.
- **Temporal Nature**: **Static annual survey records** (single snapshot per facility; no daily timestamps or continuous timeseries).
- **Operational Status Breakdown**:
  - Operational: **344 facilities** (65.4%)
  - Shut down: **125 facilities** (23.8%)
  - Under construction: **32 facilities** (6.1%)
  - Proposed / planned: **25 facilities** (4.8%)
- **Animal Waste Types**:
  - Dairy cattle: 431 facilities (81.9%)
  - Swine: 79 facilities (15.0%)
  - Poultry / other: 16 facilities (3.0%)
- **Digester System Technologies**:
  - Complete Mix: 184 facilities (35.0%)
  - Plug Flow: 153 facilities (29.1%)
  - Covered Lagoon: 108 facilities (20.5%)
  - Other / Induced Blanket: 81 facilities (15.4%)

### 3.2 Quantitative Availability and Missingness
- `Biogas Generation Estimate (cu-ft/day)`: **55.89% missing** (294 of 526 rows unrecorded).
- `Electricity Generation Capacity (kW)`: **32.70% missing** (172 of 526 rows unrecorded).
- `Methane Percentage (%)`: **Not recorded**.
- `Daily Ambient / Digester Temperature`: **Not recorded**.

### 3.3 Compatibility Determination: Why AgSTAR Cannot be Merged
1. **Temporal Incommensurability**: Spark is a **daily operational timeseries** ($\Delta t = 1\text{ day}$, 176 steps). AgSTAR is a **static cross-sectional database** ($\Delta t = \text{annual static snapshot}$, 0 temporal steps).
2. **Unit Incommensurability**: Spark logs in metric industrial units ($	ext{Nm}^3/	ext{day}$, $	ext{MT}$, $^\circ	ext{C}$). AgSTAR logs in imperial annual estimates ($	ext{cu-ft/yr}$, $	ext{kWh/yr}$).
3. **Feedstock Incommensurability**: Spark operates on mixed co-digestion of urban food waste, cow dung, and vegetable waste. AgSTAR represents rural dairy/swine manure lagoons.
4. **Conclusion**: Any mathematical concatenation or horizontal merge of AgSTAR with Spark constitutes **unscientific synthetic chimera creation**. AgSTAR is strictly isolated as an auxiliary macro-scale operational benchmark.

---

## 4. Summary Matrix of Dataset Characteristics

| Attribute | Spark Bio Gas Dataset | AgSTAR Livestock Database |
| :--- | :--- | :--- |
| **Data Topology** | Longitudinal timeseries | Cross-sectional spatial registry |
| **Observation Count** | 176 consecutive calendar days | 526 facility survey records |
| **Sampling Interval** | Daily (24-hour aggregate) | Annual static snapshot |
| **Primary Target Viability** | **High** ($y_t = 	ext{Raw Gas Total}_{t+1}$) | **Zero** (no sequential target) |
| **Microclimate Variables** | Monitored daily ($	ext{pH}$, $T$) | None |
| **Feedstock Weighment** | Monitored daily ($	ext{MT}$) | Static head count estimates |
| **Project Role** | **Core ML Training & Validation** | **Auxiliary Macro Benchmark** |

---

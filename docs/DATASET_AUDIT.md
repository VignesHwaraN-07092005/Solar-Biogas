# DATASET AUDIT REPORT: ANAEROBIC DIGESTION & BIOGAS DATASETS

**Project Title:** AI-Driven Solar-Biogas System for Sustainable Communities  
**Team:** Espada  
**Date:** September 14, 2026  
**Auditor:** Lead AI/ML Engineer & Systems Architect  

---

## 1. Executive Summary & Compatibility Determination

Two primary quantitative datasets reside in the workspace:
1. **Dataset 1:** `Master data Spark biogas.xlsx` (Industrial Anaerobic Digestion Logbook, Spark Bio Gas Pvt Ltd, Sholinganallur)
2. **Dataset 2:** `agstar-livestock-ad-database-combined.xlsx` (US EPA AgSTAR Livestock Anaerobic Digester National Project Registry)

### Scientific Determination on Dataset Merging:
> [!CAUTION]
> **CANNOT SCIENTIFICALLY BE COMBINED. THE DATASETS MUST REMAIN STRICTLY SEPARATE.**
> 
> Merging these two datasets is scientifically invalid and technically impossible for the following definitive reasons:
> 1. **Fundamental Process Mismatch:** Dataset 1 is a continuous, dynamic daily operational time-series tracking biokinetics, daily feeding, pH, slurry temperature, and daily gas generation in a commercial plant. Dataset 2 is a static, cross-sectional registry of farm-scale project metadata across the United States.
> 2. **Temporal Incompatibility:** Dataset 1 possesses daily time stamps (and sub-daily 2-hour feeding schedules) essential for lag features, rolling windows, and temporal sequence forecasting (LSTM/GRU/XCO-Net). Dataset 2 has **zero** temporal resolution (only static years of commissioning/decommissioning).
> 3. **Unit & Scale Discrepancies:** Biogas production in Dataset 1 is measured in Normal Cubic Meters per day ($Nm^3/day$), whereas Dataset 2 records rough static estimates in Standard Cubic Feet per day ($cu\text{-}ft/day$) spanning orders of magnitude ($5,000$ to $3,454,500$ cu-ft/day). Feedstock in Dataset 1 is measured in Metric Tonnes ($MT$) of urban organic waste (cow dung, food waste, vegetable market waste), while Dataset 2 records headcounts of livestock (dairy cows, swine, poultry).
> 4. **Target Incompatibility:** Dataset 1 provides a true, empirical next-day gas generation target ($Nm^3/day$). Dataset 2 contains a static engineering capacity estimate that is missing in 55.9% of rows.
> 
> **Decision:** **DO NOT MERGE.** Dataset 1 will be used as the **Primary Dataset** for operational analysis and ML feature development. Dataset 2 will be relegated to **Secondary Domain Analysis** for macroscopic cross-facility benchmarking.

---

## 2. Dataset 1 Audit: Spark Bio Gas Master Data

### 2.1 File & Provenance Overview
- **Filename:** `Master data Spark biogas.xlsx`
- **File Format:** Microsoft Excel OpenXML Spreadsheet (.xlsx)
- **File Size:** 3,177,947 bytes (3.18 MB)
- **Source / Facility:** Spark Bio Gas Private Limited, MDR-1 Plant, Sholinganallur, Chennai, Tamil Nadu, India.
- **Facility Type:** Industrial co-digestion bio-methanation and Compressed Biogas (CBG) upgrading plant.
- **Operating Context:** Co-digests Municipal Solid Waste (Greater Chennai Corporation - GCC vegetable/food waste) with segregated bulk private food waste and dairy cow dung. Upgrades raw biogas through water scrubbing and compression into cascades and pipelines (Torrent Gas).
- **Classification:** **[CATEGORY C] ACTUAL INDUSTRIAL OPERATIONAL DATA**.
- **Data Authenticity:** Real industrial operations logbook with empirical weighbridge records, laboratory slurry readings, and flowmeter readings.

### 2.2 Sheet Breakdown
The workbook contains 4 sheets:
1. `Master data` (Active operational sheet: 10,938 total rows, 93 columns, 162 daily master summary rows interleaved with vehicle weighbridge transaction slips and cascade dispensing logs).
2. `Sheet1` (Completely empty: 0 rows, 0 columns; placeholder).
3. `Raw materials feed` (Sub-daily feeding schedule: 393 rows, 10 columns covering 31 days in September 2024 at 2-hour intervals from 06:00 to 04:00).
4. `Gas filling` (Cascade and vehicle dispensing logs: 84 rows, 11 columns covering September 2024 pressure and volume fills).

### 2.3 Master Data Sheet: Structural & Temporal Schema
- **Observation Count:** 162 unique daily operational records.
- **Calendar Span:** November 1, 2025 to April 25, 2026 (176 calendar days).
- **Time Resolution:** Daily ($\Delta t = 24\text{ hours}$) for macro balances, with sub-daily transactional logs.
- **Temporal Continuity:** 162 operating days out of 176 days (92% operating uptime; 14 unrecorded/shutdown days).
- **Duplicate Records:** 0 duplicate dates. Every date entry represents a unique operational day.
- **Column Count:** 93 hierarchical columns organized across 4 operational modules: `WEIGHMENT`, `GENERATION`, `PURIFICATION`, and `MARKETING`.

#### Detailed Column Audit & Engineering Dictionary (Key Columns)

| Col # | Exact Hierarchy & Column Name | Physical Quantity | Engineering Unit | Data Type | Missing Count | Observed Range (Min – Max) | Operational Role & Leakage Risk |
|---|---|---|---|---|---|---|---|
| **C01** | `DATE` | Calendar Date | YYYY-MM-DD | Datetime | 0 (0.0%) | 2025-11-01 – 2026-04-25 | Temporal index. Strictly chronological. |
| **C02** | `WEIGHMENT // COW DUNG (MT) // GCC` | Cow Dung Mass (Municipal) | Metric Tonnes (MT) | Float64 | 11 (6.8%) | 0.00 – 40.27 (Mean: 16.85) | Primary Input Feature. Inoculum/substrate. |
| **C05** | `WEIGHMENT // FOOD WASTE (MT) // GCC` | Food Waste Mass (Municipal) | Metric Tonnes (MT) | Float64 | 14 (8.6%) | 2.20 – 47.15 (Mean: 23.07) | Primary Input Feature. High volatile solids. |
| **C08** | `WEIGHMENT // VEG WASTE (MT) // GCC` | Vegetable Market Waste | Metric Tonnes (MT) | Float64 | 13 (8.0%) | 0.00 – 178.38 (Mean: 100.74) | Primary Input Feature. Bulk wet organic fraction. |
| **C11** | `WEIGHMENT // TOTAL INCOMING QTY (MT)` | Total Substrate Received | Metric Tonnes (MT) | Float64 | 13 (8.0%) | 10.83 – 205.14 (Mean: 140.72) | Aggregated daily loading. Safe input feature. |
| **C12** | `PROCESSED (MT) // Cow dung(MT)` | Pretreated Cow Dung | Metric Tonnes (MT) | Float64 | 11 (6.8%) | 0.00 – 33.71 (Mean: 17.06) | Process input. |
| **C13** | `PROCESSED (MT) // Food waste (MT)` | Pretreated Food Waste | Metric Tonnes (MT) | Float64 | 11 (6.8%) | 2.20 – 48.83 (Mean: 22.32) | Process input. |
| **C14** | `GENERATION // PROCESSED (MT) // Mavitech`| Depackager Pretreatment | Metric Tonnes (MT) | Float64 | 11 (6.8%) | 0.00 – 176.50 (Mean: 59.44) | Mechanical sorting line throughput. |
| **C15** | `GENERATION // PROCESSED (MT) // Bio Grinder`| Bio-grinder Pretreatment | Metric Tonnes (MT) | Float64 | 11 (6.8%) | 0.00 – 118.75 (Mean: 23.68) | Slurry preparation line throughput. |
| **C17** | `GENERATION // Rejects Shifted by GCC (MT)`| Inorganic/Non-digestible Rejects| Metric Tonnes (MT) | Float64 | 11 (6.8%) | 0.00 – 46.90 (Mean: 14.38) | Process efficiency metric. |
| **C20** | `GENERATION // TOTAL PROCESSED (MT)` | Total Slurry Mass Feedable | Metric Tonnes (MT) | Float64 | 12 (7.4%) | 25.60 – 195.90 (Mean: 108.28) | Net digestible loading. Key feature. |
| **C21** | `GENERATION // WATER UTILISED // Recycle water`| Recycled Process Water | Cubic Meters ($m^3$) | Float64 | 57 (35.2%)| 5.00 – 109.00 (Mean: 49.94) | Moisture conditioning. |
| **C24** | `GENERATION // Feed to Digesters // Digester-1`| Volumetric Feed to D1 | Cubic Meters ($m^3$) | Float64 | 35 (21.6%)| 46.00 – 180.00 (Mean: 104.98) | Reactor hydraulic loading rate. |
| **C25** | `GENERATION // Feed to Digesters // Digester-2`| Volumetric Feed to D2 | Cubic Meters ($m^3$) | Float64 | 35 (21.6%)| 0.00 – 165.00 (Mean: 91.85) | Reactor hydraulic loading rate. |
| **C27** | `GENERATION // Agitator running // Digester-1`| Mixing Runtime | Minutes/day | Float64 | 64 (39.5%)| 178.00 – 729.00 (Mean: 327.06)| Mass transfer / agitation feature. |
| **C28** | `GENERATION // Agitator running // Digester-2`| Mixing Runtime | Minutes/day | Float64 | 64 (39.5%)| 178.00 – 729.00 (Mean: 327.23)| Mass transfer / agitation feature. |
| **C31** | `GENERATION // pH // Inlet` | Feed Slurry pH | pH units (0-14) | Float64 | 44 (27.2%)| 4.85 – 6.50 (Mean: 6.05) | Critical biokinetic state (acidogenesis). |
| **C32** | `GENERATION // pH // Outlet D1` | Anaerobic Digester 1 pH | pH units (0-14) | Float64 | 24 (14.8%)| 7.30 – 8.10 (Mean: 7.61) | Methanogenic stability ($7.2-7.8$ optimal). |
| **C33** | `GENERATION // pH // Outlet D2` | Anaerobic Digester 2 pH | pH units (0-14) | Float64 | 24 (14.8%)| 7.20 – 8.20 (Mean: 7.83) | Methanogenic stability. |
| **C35** | `GENERATION // Temperature // Outlet D1` | Slurry Core Temperature | Degrees Celsius (°C) | Float64 | 24 (14.8%)| 33.00 – 38.10 (Mean: 35.41) | Mesophilic microbial kinetic state. |
| **C36** | `GENERATION // Temperature // Outlet D2` | Slurry Core Temperature | Degrees Celsius (°C) | Float64 | 24 (14.8%)| 32.00 – 38.00 (Mean: 34.77) | Mesophilic microbial kinetic state. |
| **C38** | `GENERATION // TDS // Outlet` | Total Dissolved Solids | ppm / mg/L | Float64 | 16 (9.9%) | 1,927.0 – 17,994.0 (Mean: 6,495.8)| Salinity / ionic strength indicator. |
| **C39-41**| `GENERATION // Slurry // TS, VS, VFA` | Solids & Organic Acids | % / mg/L | Float64 | 162 (100%)| UNKNOWN / NOT RECORDED | Completely unpopulated in Excel sheet. |
| **C42** | `GENERATION // Raw gas generated // Digester-1`| Gross Biogas Volume D1 | Normal $m^3/day$ | Float64 | 24 (14.8%)| 1,389.0 – 5,817.0 (Mean: 3,045.71)| Primary Output Candidate (D1). |
| **C43** | `GENERATION // Raw gas generated // Digester-2`| Gross Biogas Volume D2 | Normal $m^3/day$ | Float64 | 15 (9.3%) | 0.00 – 5,117.0 (Mean: 2,641.27) | Primary Output Candidate (D2). |
| **C44** | `GENERATION // Raw gas generated // Total` | Plant Total Gross Biogas | Normal $m^3/day$ | Float64 | 15 (9.3%) | 1,781.0 – 9,661.0 (Mean: 5,585.93)| **PRIMARY TARGET VARIABLE ($y_{t+1}$)**. |
| **C45-47**| `GENERATION // Raw gas Flaring // Total` | Emergency Flared Biogas | Normal $m^3/day$ | Float64 | 24 (14.8%)| 0.00 – 1,649.0 (Mean: 178.63) | Downstream operational disposition. |
| **C48-50**| `PURIFICATION // Raw gas Utilized // Total` | Net Gas Sent to Upgrading | Normal $m^3/day$ | Float64 | 15 (9.3%) | 360.0 – 5,765.0 (Mean: 2,923.95) | **TARGET LEAKAGE RISK IF USED CONCURRENTLY**. |
| **C51-53**| `PURIFICATION // Scrubber gas flow // Avg` | Upgraded Gas Flow | Normal $m^3/day$ | Float64 | 17 (10.5%)| 3,885.0 – 58,935.0 (Mean: 14,206.8)| Downstream processing flow. |
| **C56-59**| `PURIFICATION // Storage cascade pressure` | High-Pressure Buffer | Bar ($10^5$ Pa) | Float64 | 16 (9.9%) | 0.00 – 240.00 (Mean: 152.0) | Downstream gas storage state. |
| **C60-72**| `PURIFICATION // Supplied to Pipeline / CBG`| Commercial Gas Sales | $scm$, $kg$ | Mixed | Variable | Variable | Commercial distribution (Downstream). |

### 2.4 Data Leakage Analysis for Dataset 1
> [!WARNING]
> **CRITICAL DATA LEAKAGE IDENTIFICATION:**
> In forecasting **Next-Day Biogas Production ($y_{t+1} = \text{Total Raw Gas}_{t+1}$)**:
> 1. **Downstream Variables:** Columns C48–C50 (`Raw gas Utilized`), C51–C53 (`Scrubber flow`), C56–C59 (`Cascade pressure`), and C60–C72 (`Gas sales`) occur **after** gas generation. Including contemporaneous ($t+1$) values of these columns causes 100% target leakage.
> 2. **Legitimate Features:** Only historical parameters known at or before day $t$ (e.g., Feedstock mass at day $t$, pH at day $t$, Temperature at day $t$, Agitator runtime at day $t$, and lagged gas generation $y_t, y_{t-1}, y_{t-2}$) may enter the model feature matrix $X_t$.

### 2.5 Outliers and Statistical Anomalies in Dataset 1
1. **Closing reading scum (C62):** Extreme value of $29,186,736.0$ detected on one day due to an accumulator reset or typographical error (mean is $279,829$). Downstream column; must be excluded from feature pipeline.
2. **Zero Gas Generation Days on Digester-2:** In early November 2025, Digester-2 recorded $0\text{ Nm}^3/day$ while Digester-1 generated $\sim 3,443\text{ Nm}^3/day$. This reflects plant commissioning/maintenance of reactor 2, not sensor error. Total plant gas accurately reflects available capacity.
3. **Missing Slurry Parameters:** Columns C39 (`TS`), C40 (`VS`), and C41 (`VFA`) are completely empty ($100\%$ null). The plant did not routinely record daily volatile fatty acids or laboratory solids in this digital sheet. These variables are marked **UNKNOWN/UNAVAILABLE**.

---

## 3. Dataset 2 Audit: AgSTAR Livestock AD Database

### 3.1 File & Provenance Overview
- **Filename:** `agstar-livestock-ad-database-combined.xlsx`
- **File Format:** Microsoft Excel OpenXML Spreadsheet (.xlsx)
- **File Size:** 62,203 bytes (62.2 KB)
- **Source / Authority:** United States Environmental Protection Agency (US EPA) AgSTAR Program.
- **Dataset Nature:** National registry and census of livestock anaerobic digester facilities across agricultural operations in the United States.
- **Classification:** **[CATEGORY C] PUBLIC PROJECT REGISTRY / CATALOG DATA**.
- **Data Authenticity:** Official US EPA published project database (curated metadata).

### 3.2 Structural Breakdown
- **Observation Count:** 526 farm/facility records.
- **Sheet Count:** 1 sheet (`Sheet1`).
- **Column Count:** 26 metadata attributes.
- **Temporal Resolution:** **NONE**. No time-series, no daily logs, no dynamic operational sensor telemetry.
- **Temporal Identifiers:** Only static calendar years: `Year Operational` (1972 to 2023, mean 2012.5, 17 nulls) and `Year Shutdown` (2000 to 2022, 86 shut down facilities recorded).
- **Duplicate Records:** 0 duplicate rows (each row is a distinct named facility).

#### Detailed Column Audit

| # | Column Name | Physical Meaning | Unit | Data Type | Null Count | Missing % | Unique | Observed Values / Distribution |
|---|---|---|---|---|---|---|---|---|
| 1 | `Project Name` | Facility Name | Text | Object | 0 | 0.0% | 526 | E.g., Cargill Sandy River, Butterfield RNG |
| 2 | `Cluster Name` | Regional Pipeline Cluster | Text | Object | 397 | 75.5% | 20 | Maas Calgren (21), CalBio (24), Aemetis (9) |
| 3 | `Project Type` | System Boundary | Categorical | Object | 0 | 0.0% | 4 | Farm Scale (476), Regional (23), Multiple (19), Research (8) |
| 4 | `City` | Municipality | Text | Object | 1 | 0.2% | 327 | Tulare (18), Hanford (16), Bakersfield (13) |
| 5 | `County` | County Administrative Area | Text | Object | 9 | 1.7% | 216 | Tulare (56), Merced (22), Kern (20) |
| 6 | `State` | US State Code | Categorical | Object | 0 | 0.0% | 38 | CA (157), WI (52), NY (49), PA (33) |
| 7 | `Digester Type` | Reactor Engineering Design | Categorical | Object | 1 | 0.2% | 14 | Covered Lagoon (194), Complete Mix (137), Mixed Plug Flow (115), Horizontal Plug Flow (34) |
| 8 | `Status` | Operational Lifecycle State | Categorical | Object | 0 | 0.0% | 3 | Operational (343), Shut down (97), Construction (86) |
| 9 | `Year Operational` | Commissioning Year | Year | Float64 | 17 | 3.2% | 37 | 1972 – 2023 (Median: 2012) |
| 10 | `Animal/Farm Type(s)`| Livestock Species | Categorical | Object | 0 | 0.0% | 12 | Dairy (438), Swine (56), Poultry (13), Cattle (5) |
| 11 | `Cattle` | Beef Cattle Population | Animal Headcount | Float64 | 514 | 97.7% | 11 | 30 – 40,000 (Mean: 7,509) |
| 12 | `Dairy` | Dairy Cow Population | Animal Headcount | Float64 | 105 | 20.0% | 205 | 30 – 39,000 (Mean: 4,133; Median: 2,500) |
| 13 | `Poultry` | Broiler/Layer Population | Bird Headcount | Float64 | 513 | 97.5% | 12 | 33,000 – 1,200,000 (Mean: 229,923) |
| 14 | `Swine` | Pig/Hog Population | Animal Headcount | Float64 | 467 | 88.8% | 50 | 10 – 239,200 (Mean: 24,797) |
| 15 | `Co-Digestion` | Codigested Co-substrates | Text | Object | 391 | 74.3% | 33 | Food Wastes (29), Process Water (21) |
| 16 | `Biogas Generation Estimate`| Estimated Design Yield | $cu\text{-}ft/day$ | Float64 | 294 | **55.9%** | 161 | 5,000 – 3,454,500 (Mean: 312,758 $cu\text{-}ft/day$) |
| 17 | `Electricity Generated` | Annual Power Production | $kWh/year$ | Object | 284 | 54.0% | 188 | Mixed formats (strings with commas) |
| 18 | `Biogas End Use(s)` | Utilization Pathway | Categorical | Object | 8 | 1.5% | 18 | Pipeline Gas (RNG), Cogeneration (CHP), Flared |
| 19 | `LCFS Pathway?` | CA Low Carbon Fuel Standard | Boolean | Object | 440 | 83.7% | 1 | "Yes" |
| 20 | `System Designer` | Engineering Vendor | Text | Object | 23 | 4.4% | 230 | Martin Construction, DVO, Regenis, etc. |
| 21 | `Receiving Utility` | Electrical/Gas Utility | Text | Object | 274 | 52.1% | 101 | PG&E, SoCalGas, Southwest Gas |
| 22 | `Total Emission Reductions`| Avoided GHG Emissions | $MTCO_2e/yr$ | Float64 | 127 | 24.1% | 358 | 4.2 – 390,000 (Mean: 35,128) |
| 23 | `Awarded USDA Funding?`| USDA Grant Recipient | Boolean | Object | 399 | 75.9% | 1 | "Yes" |
| 24 | `Sheet` | Excel Origin Sheet | Text | Object | 0 | 0.0% | 2 | "Operational and Construction", "Shut down" |
| 25 | `Year Shutdown` | Decommissioning Year | Year | Float64 | 440 | 83.7% | 21 | 2000 – 2022 |
| 26 | `Reason for Closure` | Root Cause for Shutdown | Text | Object | 463 | 88.0% | 57 | High maintenance, farm closed, odor issues |

### 3.3 Limitations and Incompatibility of Dataset 2
1. **Severe Missingness on Primary Target:** Biogas Generation Estimate is missing in **55.9% of records** (only 232 out of 526 rows have values).
2. **Coarse Sizing Metric:** The values are static nominal engineering capacity ratings calculated from livestock headcount multiplied by standard manure production coefficients, **not** measured meter readings.
3. **No Dynamic Operating Variables:** Zero measurements of pH, digester slurry temperature, ambient temperature, volatile fatty acids, daily feeding mass, or pressure.
4. **Cannot Train Temporal AI:** Algorithms requiring historical sequence inputs ($X_{t-k}, \dots, X_t$) cannot ingest this dataset.

---

## 4. Side-by-Side Comparison Matrix

| Evaluation Dimension | Dataset 1 (`Master data Spark biogas.xlsx`) | Dataset 2 (`agstar-livestock-ad-database-combined.xlsx`) | Harmony / Compatibility Verdict |
|---|---|---|---|
| **Underlying Physical Process** | Dynamic mesophilic industrial co-digestion of food/veg waste and cow dung | Static cross-sectional livestock farm manure digester registry | **Incompatible** |
| **Observation Entity** | Daily operation of a single continuous dual-reactor plant | Static census of 526 distinct geographical facilities | **Incompatible** |
| **Observation Count** | 162 daily log records | 526 project records | Heterogeneous scopes |
| **Temporal Basis** | Daily time-series ($\Delta t = 24\text{ h}$) | Static cross-sectional snapshot ($\Delta t = \infty$) | **Incompatible** |
| **Sampling Interval** | Continuous daily logging | One-off historical survey | **Incompatible** |
| **Target Variable** | Daily total raw biogas generated (`Total Nm3`) | Nominal estimated biogas capacity (`cu-ft/day`) | **Incompatible** |
| **Target Units** | Normal Cubic Meters per Day ($Nm^3/day$) | Standard Cubic Feet per Day ($cu\text{-}ft/day$) | Disparate (Conversion: $1\text{ Nm}^3 \approx 35.3147\text{ scf}$) |
| **Target Missingness** | 9.3% (15 out of 162 days) | 55.9% (294 out of 526 projects) | Dataset 1 significantly more complete |
| **Core Biochemical Predictors** | Daily pH, Slurry Temperature, Agitation minutes, Feedstock Tonnes | None (Only animal headcount: Dairy, Swine, Poultry) | **Incompatible** |
| **Feedstock Types** | Cow dung (MT), Food waste (MT), Veg market waste (MT) | Livestock headcount (Dairy cows, Swine, Chickens) | Different physical measurements |
| **Data Nature** | Real industrial operational telemetry | Public administrative catalog | Separate roles |
| **Can Legitimate Merging Occur?** | **NO** | **NO** | **STRICTLY SEPARATE** |

---

## 5. Dataset Recommendations & Role Allocation

### 5.1 Primary Dataset: `Master data Spark biogas.xlsx`
- **Role:** **Primary Development & Time-Series Modeling Dataset**.
- **Approved Uses:**
  1. Feature engineering of real-world temporal dynamics (lagged biogas production, rolling averages of pH and temperature, cumulative organic loading).
  2. Training and validating baseline regression models (Ridge, Random Forest, XGBoost).
  3. Training and validating deep temporal sequence models (LSTM, GRU, XCO-Net).
  4. Driving the SHAP explainability pipeline to explain how real temperature and pH variations affect gas production.
  5. Calibrating realistic parameter ranges (temperature $32–38^\circ\text{C}$, pH $7.2–8.1$, feeding rate $100–200\text{ MT}$) for the synthetic data generator.
- **Scientific Justification:** This is the **only** dataset in the workspace reflecting actual time-dependent anaerobic digestion kinetics. It contains daily continuous data with paired input loadings, reactor conditions, and actual gas outputs.

### 5.2 Secondary Dataset: `agstar-livestock-ad-database-combined.xlsx`
- **Role:** **Secondary Domain Analysis & Macro-Benchmark Dataset**.
- **Approved Uses:**
  1. Exploratory domain analysis on commercial digester configurations (e.g., Covered Lagoon vs Complete Mix vs Plug Flow).
  2. Benchmarking typical digester sizing and emission reduction capacities across agricultural sectors.
  3. Failure analysis: Studying the `Reason for Closure` column across 86 decommissioned facilities to identify operational risks (e.g., odor complaints, maintenance costs, lack of monitoring) to justify the smart solar-biogas platform in our documentation and presentation.
- **Forbidden Uses:**
  - **Do NOT use for time-series forecasting, LSTM/GRU training, or real-time IoT simulation.**
  - **Do NOT attempt to combine rows with Dataset 1.**

### 5.3 Synthetic Data Generator Role
- **Role:** **Simulation, Edge Ingestion Testing, and UI Demonstration**.
- **Rationale:** While Dataset 1 is an excellent industrial dataset, its absolute scale ($5,000\text{ Nm}^3/day$, $150\text{ MT}/day$) represents a regional utility plant rather than the proposed small/community-scale digester ($2–10\text{ m}^3/day$, $50–200\text{ kg}/day$).
- **Implementation Mandate:** Build `simulation/synthetic_data_generator/generate_dataset.py` calibrated with first-principles AD biokinetics (modified Hill model / simplified ADM1 kinetics) to produce realistic daily community-scale data ($m^3/day$). Every record from this generator must be visibly tagged: `DATA_SOURCE = "SYNTHETIC / DEMO"`.

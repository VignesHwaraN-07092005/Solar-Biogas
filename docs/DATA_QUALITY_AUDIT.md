# Data Quality Audit Report
**Project:** AI-Driven Solar-Biogas System for Sustainable Communities  
**Track:** IEEE YESIST12 Innovation Challenge (SDG 11)  
**Date:** September 15, 2026  
**Audited Files:**  
1. `Master data Spark biogas.xlsx` (Industrial Compressed Biogas Plant Log)  
2. `agstar-livestock-ad-database-combined.xlsx` (US EPA/USDA National Farm Digester Database)  

---

## 1. Spark Bio Gas Dataset Quality Assessment

### 1.1 Structural Organization & Header Layout
- The workbook contains 4 worksheets: `Master data` (10,938 total rows, 93 columns), `Sheet1` (empty), `Raw materials feed` (digester loading times), and `Gas filling` (dispensing logs).
- The `Master data` sheet employs a three-tier hierarchical header structure:
  - Row 3: High-level section (`WEIGHMENT`, `GENERATION`, `PURIFICATION`, `MARKETING`)
  - Row 4: Category / Substrate name (`COW DUNG (MT)`, `FOOD WASTE (MT)`, `pH`, `Raw gas generated Nm3`)
  - Row 5: Stream / Digester allocation (`GCC`, `Private`, `Total`, `Digester-1`, `Outlet D1`)
- Data records begin on **Row 6** and conclude with the operational period on **Row 493**. The remaining ~10,400 rows are unpopulated template rows in Excel.

### 1.2 Temporal Continuity & Integrity
- **Calendar Span:** Exactly 176 consecutive calendar days from **2025-11-01** to **2026-04-25**.
- **Duplicate Dates:** Exactly **0 duplicate dates**. Every calendar date appears exactly once as a primary entry.
- **Missing Calendar Days:** Exactly **0 missing calendar days** across the 176-day span.
- **Operational Reality:**
  - Active incoming feedstock weighment is recorded for **163 days**.
  - Active raw gas utilization (scrubbing feed) is recorded for **161 days**.
  - Direct digester raw gas generation meters are actively populated for **139 days**.
  - The final 12 days of April 2026 (2026-04-14 to 2026-04-25) represent plant turnaround/maintenance where weighment continues but active gas generation is unrecorded.

### 1.3 Missingness Breakdown by Subsystem
1. **Feedstock Weighment (Cols 2–11):**
   - Cow Dung Total: **6.25% missing** (11/176 days).
   - Food Waste Total: **7.39% missing** (13/176 days).
   - Veg Waste Total: **7.39% missing** (13/176 days).
   - Total Incoming Qty: **7.39% missing**.
2. **Reactor Feeding & Microclimate (Cols 21–36):**
   - Recycle Water ($m^3$): **34.66% missing**.
   - Raw materials feed to Digester-1 ($m^3$): **22.16% missing** (mean 106.2 m³/day).
   - Raw materials feed to Digester-2 ($m^3$): **22.16% missing** (mean 94.1 m³/day).
   - Digester-1 Outlet pH: **14.20% missing** (mean 7.55, range 7.10–7.80).
   - Digester-2 Outlet pH: **13.64% missing** (mean 7.53, range 7.10–7.99).
   - Digester-1 Outlet Temp (°C): **13.64% missing** (mean 35.46°C, range 33.0–38.1°C).
   - Digester-2 Outlet Temp (°C): **13.64% missing** (mean 34.81°C, range 32.0–38.0°C).
3. **Biogas Generation Targets (Cols 42–44):**
   - Raw gas generated Digester-1: **13.64% missing** (mean 3,077.3 Nm³/day).
   - Raw gas generated Digester-2: **13.64% missing** (mean 2,971.5 Nm³/day).
   - Raw gas generated Total: **21.02% missing** in reported total column. However, `Total = D1 + D2` holds with zero discrepancy across all recorded rows, allowing total gas to be imputed directly with **13.64% missingness**.
4. **Completely Unpopulated / Dead Columns (100% Missing):**
   - Pending materials (Cow dung & Food waste) (Cols 18, 19)
   - Fresh water ($m^3$) & Water Utilised Total (Cols 22, 23)
   - Temperature Inlet (Col 34)
   - TDS Inlet & Outlet (Cols 37, 38)
   - Slurry TS, VS, VFA (Cols 39, 40, 41)
   - Marketing Dispenser readings (Cols 73–93)

### 1.4 Anomalies, Outliers & Sensor Malfunctions
- **CBG Cumulative Counter Rollover (Col 72):**
  - Minimum value reported is **-1,275,334.69 kg** on 2025-12-04. This is a classic industrial mass-flow meter counter reset/rollover where previous cumulative register exceeded maximum capacity. This downstream variable must NOT be used for anaerobic digestion modeling.
- **Scrubber Gas Flow Surge (Col 51):**
  - Inlet flow reaches **109,880 Nm³** on a single isolated day compared to a normal median of 17,939 Nm³. Downstream scrubber instrumentation surge.
- **Zero-Variance Constant Columns:**
  - `WEIGHMENT _ COW DUNG (MT) _ Private` = 0.0 MT for all 176 days.
  - `WEIGHMENT _ FOOD WASTE (MT) _ Private` = 0.0 MT for all 176 days.
  - `WEIGHMENT _ VEG WASTE (MT) _ Private` = 0.0 MT for all 176 days.
  - `GENERATION _ PROCESSED (MT) _ Bio Grinder` = 0.0 MT for all 176 days.
  - All feedstock is sourced through GCC municipal supply; private streams are unused.

---

## 2. AgSTAR Dataset Quality Assessment

### 2.1 Overview & Structure
- 526 rows representing unique livestock anaerobic digester installations in the United States.
- 26 columns providing descriptive facility characteristics.

### 2.2 Severe Missingness in Quantitative Metrics
- `Biogas Generation Estimate (cu-ft/day)`: **55.89% missing** (294 out of 526 facilities lack generation figures).
- `Electricity Generated (kWh/yr)`: **53.99% missing** (284 facilities lack electrical output).
- `Total Emission Reductions (MTCO2e/yr)`: **24.14% missing**.
- `Cluster Name`: **75.48% missing**.
- `Awarded USDA Funding?`: **75.86% missing**.
- `Year Shutdown`: **83.65% missing** (applicable only to closed facilities).

### 2.3 Time Granularity Limitation
- AgSTAR records only static annualized figures (`Year Operational`, estimated `cu-ft/day`, annual `kWh/yr`).
- There are **no timestamps, no daily observations, no seasonal weather variations, and no sensor readings**.
- It is physically impossible to construct a day-ahead time-series forecasting model from AgSTAR.

---

## 3. Data Cleaning & Preparation Recommendations

1. **Spark Master Data Cleaning Protocol:**
   - Extract records strictly where `DATE` is valid (Rows 6 to 181, spanning 176 calendar days).
   - Compute `biogas_generated_total_nm3 = gas_d1 + gas_d2` when total is blank but digester meters are available.
   - Drop the 100% missing columns (TDS, slurry TS/VS/VFA, marketing dispenser logs).
   - Drop the zero-variance constant columns (Private cow dung, Private food waste, Private veg waste, Bio Grinder).
   - Formulate next-day prediction target by leading total biogas by 1 calendar day ($t+1$).
   - For missing operational values on active days, apply deterministic forward-fill ($t-1$) followed by median imputation, creating explicit boolean indicators (`_was_missing`).
2. **AgSTAR Isolation Protocol:**
   - Do NOT attempt to row-bind or concatenate AgSTAR with Spark.
   - Use AgSTAR exclusively as an auxiliary static benchmark table for digester technology comparisons and specific yield meta-analysis.

# Dataset Compatibility & Integration Analysis
**Project:** AI-Driven Solar-Biogas System for Sustainable Communities  
**Track:** IEEE YESIST12 Innovation Challenge (SDG 11)  
**Date:** September 15, 2026  
**Primary Dataset:** Spark Bio Gas Private Limited (`Master data Spark biogas.xlsx`)  
**Secondary Dataset:** US EPA/USDA AgSTAR Database (`agstar-livestock-ad-database-combined.xlsx`)  

---

## 1. Column-by-Column Comparative Compatibility Matrix

To establish scientific rigor, every variable across both datasets has been audited and classified into four standardized compatibility categories:
- **Category A:** Directly comparable (Identical concept and unit).
- **Category B:** Comparable after documented unit conversion.
- **Category C:** Conceptually related, but structurally distinct (e.g. daily measurement vs annual static rating).
- **Category D:** Not comparable (Unique to one domain or unrelated).

| Primary Variable (Spark Bio Gas) | Secondary Variable (AgSTAR) | Compatibility Category | Mathematical / Unit Mapping | Scientific Justification |
| :--- | :--- | :--- | :--- | :--- |
| `DATE` (Daily timestamp) | None | **Category D** | None | Spark is a daily time-series; AgSTAR is a static snapshot with no time dimension. |
| `Raw gas generated Total (Nm³/day)` | `Biogas Generation Estimate (cu-ft/day)` | **Category C** | $1\text{ cu-ft/day} = 0.0283168\text{ m}^3/\text{day}$ | Conceptually related, but Spark is actual metered daily yield at a single industrial plant, while AgSTAR is a static engineering nameplate estimate missing in 56% of rows. |
| `Cow dung (MT/day)` | `Cattle` / `Dairy` (Head count) | **Category C** | $1\text{ Dairy Cow} \approx 0.055\text{ MT dung/day}$ | AgSTAR counts animals; Spark measures metric tons of collected dung received at the gate. |
| `Food waste (MT/day)` | `Co-Digestion` (Boolean/Text) | **Category C** | Binary indicator vs MT | AgSTAR notes whether co-digestion occurs; Spark measures exact metric tons of commercial food waste. |
| `Veg waste (MT/day)` | `Co-Digestion` (Boolean/Text) | **Category C** | Binary indicator vs MT | Same as above. |
| `pH Outlet D1 / D2` | None | **Category D** | N/A | Biochemical process sensor; absent from AgSTAR registry. |
| `Temperature Outlet D1 / D2 (°C)` | None | **Category D** | N/A | Thermal microclimate sensor; absent from AgSTAR registry. |
| `Water utilised (m³)` | None | **Category D** | N/A | Plant operational utility parameter; absent from AgSTAR registry. |
| `Digester-1 / 2 Feed (m³)` | `Digester Type` (Categorical) | **Category C** | Volumetric load vs design category | AgSTAR specifies design type (e.g. Mixed Plug Flow); Spark logs daily slurry loading volume. |
| None | `State` / `County` / `City` | **Category D** | N/A | US geographic coordinates; inapplicable to Chennai plant. |
| None | `Total Emission Reductions (MTCO2e/yr)` | **Category C** | Annualized GHG offset calculation | Related to SDG 11 impact calculation, but AgSTAR is annual static estimate. |
| None | `Electricity Generated (kWh/yr)` | **Category C** | Annual power estimate | AgSTAR assumes power generation; Spark produces purified biomethane for vehicular CBG / pipeline injection. |

---

## 2. Scientific Decision: Can the Datasets Be Combined?

### Verdict: **ABSOLUTELY NOT.**

Combining `Master data Spark biogas.xlsx` and `agstar-livestock-ad-database-combined.xlsx` into a single training dataframe would represent a fatal methodological error:
1. **Dimensional Incommensurability:**
   - Spark represents $N=176$ continuous time-series observations of a single real-world bioprocess system over 6 months ($X_t \in \mathbb{R}^d$ for $t=1, \dots, 176$).
   - AgSTAR represents $N=526$ cross-sectional survey records across independent farms across North America ($X_i \in \mathbb{R}^k$ for $i=1, \dots, 526$).
   - Concatenating rows would mix time-series steps with distinct physical entities.
2. **Missing Daily Dynamics in AgSTAR:**
   - AgSTAR contains zero day-to-day dynamic drivers: no temperature logs, no pH logs, no daily loading fluctuations, and no temporal lag structures.
3. **Unit & Target Divergence:**
   - Spark measures metered volumetric generation ($Nm^3/\text{day}$) of raw biogas and purified CBG ($kg$).
   - AgSTAR contains a design rating estimate ($cu\text{-}ft/\text{day}$) that is absent in 56% of entries.

---

## 3. Legitimate Roles of Each Dataset in the Project

### Primary Role: Spark Bio Gas Private Limited
- **Exclusive Machine Learning Training Dataset:**
  - Used for time-series next-day biogas forecasting ($Nm^3/\text{day}$).
  - Drives lag feature generation, rolling statistical averages, and feature importance analysis (SHAP).
  - Ground truth for evaluating Persistence, Ridge, Random Forest, XGBoost, and LSTM temporal models.

### Secondary Role: AgSTAR Database
- **Auxiliary Cross-Sectional Domain Benchmark & Context:**
  - Provides macro-level benchmark distributions for specific methane yield per animal head.
  - Contextualizes digester technology designs (Covered Lagoon vs Complete Mix vs Plug Flow).
  - Supplies reference empirical factors for SDG 11 emission reduction modeling ($MTCO_2e/\text{year}$).

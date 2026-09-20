# Project Data Dictionary
**Project:** AI-Driven Solar-Biogas System for Sustainable Communities  
**Track:** IEEE YESIST12 Innovation Challenge (SDG 11)  
**Scope:** Complete Column-by-Column Inventory and Machine Learning Viability Assessment  
**Source Files:** `Master data Spark biogas.xlsx` (Industrial CBG Plant) & `agstar-livestock-ad-database-combined.xlsx` (US Farm Digester Registry)  

---

## 1. Spark Bio Gas Private Limited (Industrial CBG Operational Log)
- **File:** `Master data Spark biogas.xlsx`
- **Sheet:** `Master data`
- **Facility:** Commercial Compressed Biogas (CBG) facility (MDR-1, Chennai, India)
- **Temporal Scope:** 176 consecutive calendar days (2025-11-01 to 2026-04-25)
- **Active Operational Days:** 161 days with active raw gas utilization; 139 days with metered raw gas generation
- **Total Columns:** 93

| Col | Original Header | Normalized Name | Physical Unit | Dtype | Missing (%) | Min | Max | Mean | Median | ML Feature? | ML Target? | Interpretation & Process Context |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 01 | `DATE` | `date` | Date (YYYY-MM-DD) | object | 0.0% | N/A | N/A | N/A | N/A | **Index** | **No** | Temporal index for time-series chronological sorting. |
| 02 | `WEIGHMENT _ COW DUNG (MT) _ GCC` | `cow_dung_mt___gcc` | Metric Tons (MT) | numeric | 6.25% | 0.0 | 40.27 | 16.53 | 15.36 | **YES (Substrate breakdown)** | **No** | GCC municipal substrate supply component. |
| 03 | `WEIGHMENT _ COW DUNG (MT) _ Private` | `cow_dung_mt___private` | Metric Tons (MT) | numeric | 6.25% | 0.0 | 0.0 | 0.0 | 0.0 | **No (Constant 0)** | **No** | Zero private incoming supply throughout monitored period. |
| 04 | `WEIGHMENT _ COW DUNG (MT) _ Total` | `cow_dung_mt___total` | Metric Tons (MT) | numeric | 6.25% | 0.0 | 40.27 | 16.54 | 15.27 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 05 | `WEIGHMENT _ FOOD WASTE (MT) _ GCC` | `food_waste_mt___gcc` | Metric Tons (MT) | numeric | 7.39% | 2.2 | 47.15 | 22.92 | 22.98 | **YES (Substrate breakdown)** | **No** | GCC municipal substrate supply component. |
| 06 | `WEIGHMENT _ FOOD WASTE (MT) _ Private` | `food_waste_mt___private` | Metric Tons (MT) | numeric | 7.95% | 0.0 | 0.0 | 0.0 | 0.0 | **No (Constant 0)** | **No** | Zero private incoming supply throughout monitored period. |
| 07 | `WEIGHMENT _ FOOD WASTE (MT) _ Total` | `food_waste_mt___total` | Metric Tons (MT) | numeric | 7.39% | 2.2 | 47.15 | 22.73 | 22.82 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 08 | `WEIGHMENT _ VEG WASTE (MT) _ GCC` | `veg_waste_mt___gcc` | Metric Tons (MT) | numeric | 7.39% | 0.0 | 178.38 | 102.6 | 108.53 | **YES (Substrate breakdown)** | **No** | GCC municipal substrate supply component. |
| 09 | `WEIGHMENT _ VEG WASTE (MT) _ Private` | `veg_waste_mt___private` | Metric Tons (MT) | numeric | 7.39% | 0.0 | 0.0 | 0.0 | 0.0 | **No (Constant 0)** | **No** | Zero private incoming supply throughout monitored period. |
| 10 | `WEIGHMENT _ VEG WASTE (MT) _ Total` | `veg_waste_mt___total` | Metric Tons (MT) | numeric | 7.39% | 0.0 | 178.38 | 102.6 | 108.53 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 11 | `WEIGHMENT _ TOTAL INCOMING QTY  (MT)` | `total_incoming_qty__mt` | Metric Tons (MT) | numeric | 7.39% | 10.83 | 205.14 | 142.11 | 149.66 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 12 | `WEIGHMENT _ PROCESSED (MT) _ Cow dung(MT)` | `processed_mt___cow_dungmt` | Metric Tons (MT) | numeric | 6.25% | 0.0 | 33.71 | 16.73 | 16.13 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 13 | `WEIGHMENT _ PROCESSED (MT) _ Food waste (MT)` | `processed_mt___food_waste_mt` | Metric Tons (MT) | numeric | 6.25% | 0.85 | 48.83 | 22.17 | 21.86 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 14 | `GENERATION _ PROCESSED (MT) _ Mavitech` | `processed_mt___mavitech` | Metric Tons (MT) | numeric | 6.25% | 0.0 | 176.5 | 63.05 | 54.88 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 15 | `GENERATION _ PROCESSED (MT) _ Bio Grinder` | `processed_mt___bio_grinder` | Metric Tons (MT) | numeric | 6.25% | 0.0 | 118.75 | 23.23 | 20.25 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 16 | `GENERATION _ Rejects Shifted to windrow    (MT)` | `rejects_shifted_to_windrow__` | Metric Tons (MT) | numeric | 68.75% | 0.0 | 0.0 | 0.0 | 0.0 | **No** | **No** | Operational parameter. |
| 17 | `GENERATION _ Rejects Shifted by GCC    (MT)` | `rejects_shifted_by_gcc____mt` | Metric Tons (MT) | numeric | 6.25% | 0.0 | 49.38 | 14.66 | 12.64 | **No** | **No** | Operational parameter. |
| 18 | `GENERATION _ Pending materials (Cow dung & Food waste)(MT)` | `pending_materials_cow_dung_&` | Metric Tons (MT) | object | 100.0% | N/A | N/A | N/A | N/A | **YES (Substrate breakdown)** | **No** | GCC municipal substrate supply component. |
| 19 | `GENERATION _ Pending materials(Veg waste) (MT)` | `pending_materialsveg_waste_m` | Metric Tons (MT) | object | 100.0% | N/A | N/A | N/A | N/A | **YES (Substrate breakdown)** | **No** | GCC municipal substrate supply component. |
| 20 | `GENERATION _ TOTAL PROCESSED (MT)` | `total_processed_mt` | Metric Tons (MT) | numeric | 6.25% | 19.59 | 200.08 | 111.11 | 108.25 | **YES (Key Feature)** | **No** | Organic feedstock volatile solids mass entering the plant. |
| 21 | `GENERATION _ WATER UTILISED _ Recycle water (m3)` | `water_utilised___recycle_wat` | Cubic Meters (m³) | numeric | 34.66% | 5.0 | 109.0 | 50.69 | 51.0 | **YES** | **No** | Recycled liquid digestate utilized for slurry dilution. |
| 22 | `GENERATION _ WATER UTILISED _ Fresh water (m3)` | `water_utilised___fresh_water` | Cubic Meters (m³) | object | 100.0% | N/A | N/A | N/A | N/A | **No (>80% missing)** | **No** | Unrecorded or non-instrumented variable. |
| 23 | `GENERATION _ WATER UTILISED _ Total (m3)` | `water_utilised___total_m3` | Cubic Meters (m³) | object | 100.0% | N/A | N/A | N/A | N/A | **No (>80% missing)** | **No** | Unrecorded or non-instrumented variable. |
| 24 | `GENERATION _ Raw materials feed to Digesters _ Digester-1 (m3)` | `raw_materials_feed_to_digest` | Cubic Meters (m³) | numeric | 22.16% | 46.0 | 180.0 | 106.2 | 100.0 | **YES (Key Feature)** | **No** | Slurry volume fed directly into anaerobic reactors. |
| 25 | `GENERATION _ Raw materials feed to Digesters _ Digester-2 (m3)` | `raw_materials_feed_to_digest` | Cubic Meters (m³) | numeric | 22.16% | 0.0 | 165.0 | 94.09 | 99.0 | **YES (Key Feature)** | **No** | Slurry volume fed directly into anaerobic reactors. |
| 26 | `GENERATION _ Raw materials feed to Digesters _ Total (m3)` | `raw_materials_feed_to_digest` | Cubic Meters (m³) | numeric | 46.02% | 64.0 | 325.0 | 195.88 | 192.0 | **YES (Key Feature)** | **No** | Slurry volume fed directly into anaerobic reactors. |
| 27 | `GENERATION _ High flow agitator running _ Digester-1 Min` | `high_flow_agitator_running__` | Minutes | numeric | 44.32% | 178.0 | 729.0 | 327.06 | 275.0 | **YES** | **No** | Mixing and mass transfer duration inside digesters. |
| 28 | `GENERATION _ High flow agitator running _ Digester-2 Min` | `high_flow_agitator_running__` | Minutes | numeric | 44.32% | 178.0 | 729.0 | 327.23 | 275.0 | **YES** | **No** | Mixing and mass transfer duration inside digesters. |
| 29 | `GENERATION _ SLS running mins _ SLS-1` | `sls_running_mins___sls_1` | Minutes | numeric | 13.64% | 0.0 | 0.0 | 0.0 | 0.0 | **No** | **No** | Operational parameter. |
| 30 | `GENERATION _ SLS running mins _ SLS-2` | `sls_running_mins___sls_2` | Minutes | numeric | 13.64% | 0.0 | 395.0 | 58.5 | 0.0 | **No** | **No** | Operational parameter. |
| 31 | `GENERATION _ pH _ Inlet` | `ph___inlet` | pH Scale (0-14) | numeric | 21.59% | 4.85 | 6.5 | 6.05 | 6.1 | **YES (Key Feature)** | **No** | Methanogenic buffer stability and volatile fatty acid indicator. |
| 32 | `GENERATION _ pH _ Outlet D1` | `ph___outlet_d1` | pH Scale (0-14) | numeric | 14.2% | 7.1 | 7.8 | 7.55 | 7.6 | **YES (Key Feature)** | **No** | Methanogenic buffer stability and volatile fatty acid indicator. |
| 33 | `GENERATION _ pH _ Outlet D2` | `ph___outlet_d2` | pH Scale (0-14) | numeric | 13.64% | 7.1 | 7.99 | 7.53 | 7.59 | **YES (Key Feature)** | **No** | Methanogenic buffer stability and volatile fatty acid indicator. |
| 34 | `GENERATION _ Temperature _ Inlet` | `temperature___inlet` | Degrees Celsius (°C) | object | 100.0% | N/A | N/A | N/A | N/A | **No (>80% missing)** | **No** | Unrecorded or non-instrumented variable. |
| 35 | `GENERATION _ Temperature _ Outlet D1` | `temperature___outlet_d1` | Degrees Celsius (°C) | numeric | 13.64% | 33.0 | 38.1 | 35.46 | 35.0 | **YES (Key Feature)** | **No** | Mesophilic digester internal slurry temperature (biological window 33-38°C). |
| 36 | `GENERATION _ Temperature _ Outlet D2` | `temperature___outlet_d2` | Degrees Celsius (°C) | numeric | 13.64% | 32.0 | 38.0 | 34.81 | 34.0 | **YES (Key Feature)** | **No** | Mesophilic digester internal slurry temperature (biological window 33-38°C). |
| 37 | `GENERATION _ TDS _ Inlet` | `tds___inlet` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (>80% missing)** | **No** | Unrecorded or non-instrumented variable. |
| 38 | `GENERATION _ TDS _ Outlet` | `tds___outlet` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (>80% missing)** | **No** | Unrecorded or non-instrumented variable. |
| 39 | `GENERATION _ Slurry _ TS` | `slurry___ts` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (>80% missing)** | **No** | Unrecorded or non-instrumented variable. |
| 40 | `GENERATION _ Slurry _ VS` | `slurry___vs` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (>80% missing)** | **No** | Unrecorded or non-instrumented variable. |
| 41 | `GENERATION _ Slurry _ VFA` | `slurry___vfa` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (>80% missing)** | **No** | Unrecorded or non-instrumented variable. |
| 42 | `GENERATION _ Raw gas generated Nm3 _ Digester-1                     Nm3` | `raw_gas_generated_nm3___dige` | Cubic Meters (m³) | numeric | 13.64% | 1389.0 | 5817.0 | 3077.32 | 2861.0 | **Lagged only** | **PRIMARY TARGET** | Primary daily raw biogas yield from anaerobic digestion. |
| 43 | `GENERATION _ Raw gas generated Nm3 _ Digester-2                     Nm3` | `raw_gas_generated_nm3___dige` | Cubic Meters (m³) | numeric | 13.64% | 0.0 | 5516.0 | 2971.54 | 2946.0 | **No** | **No** | Operational parameter. |
| 44 | `GENERATION _ Raw gas generated Nm3 _ Total  Nm3` | `raw_gas_generated_nm3___tota` | Cubic Meters (m³) | numeric | 21.02% | 2070.0 | 10749.0 | 6080.2 | 5610.0 | **Lagged only** | **PRIMARY TARGET** | Primary daily raw biogas yield from anaerobic digestion. |
| 45 | `GENERATION _ Raw gas Flaring Nm3 _ Digester-1                     Nm3` | `raw_gas_flaring_nm3___digest` | Cubic Meters (m³) | numeric | 13.64% | 0.0 | 2019.0 | 219.43 | 0.0 | **No** | **No** | Operational parameter. |
| 46 | `GENERATION _ Raw gas Flaring Nm3 _ Digester-2                     Nm3` | `raw_gas_flaring_nm3___digest` | Cubic Meters (m³) | numeric | 13.64% | 0.0 | 3998.0 | 389.27 | 0.0 | **No** | **No** | Operational parameter. |
| 47 | `GENERATION _ Raw gas Flaring Nm3 _ Total  Nm3` | `raw_gas_flaring_nm3___total_` | Cubic Meters (m³) | numeric | 17.61% | 0.0 | 5431.0 | 576.23 | 0.0 | **No** | **No** | Operational parameter. |
| 48 | `PURIFICATION _ Raw gas Utilized Nm3 _ Digester-1                     Nm3` | `raw_gas_utilized_nm3___diges` | Cubic Meters (m³) | numeric | 8.52% | 360.0 | 5765.0 | 2905.88 | 2724.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 49 | `PURIFICATION _ Raw gas Utilized Nm3 _ Digester-2                     Nm3` | `raw_gas_utilized_nm3___diges` | Cubic Meters (m³) | numeric | 8.52% | 0.0 | 5117.0 | 2624.28 | 2726.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 50 | `PURIFICATION _ Raw gas Utilized Nm3 _ Total  Nm3` | `raw_gas_utilized_nm3___total` | Cubic Meters (m³) | numeric | 8.52% | 1220.0 | 9661.0 | 5556.43 | 5482.0 | **Lagged only** | **Secondary Target** | Daily biogas drawn for downstream biogas purification/scrubbing. |
| 51 | `PURIFICATION _ Scrubber gas flow _ Inlet` | `scrubber_gas_flow___inlet` | None | numeric | 9.66% | 4731.0 | 109880.0 | 23646.84 | 17939.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 52 | `PURIFICATION _ Scrubber gas flow _ Outlet` | `scrubber_gas_flow___outlet` | None | numeric | 9.09% | 1526.0 | 17994.0 | 6369.77 | 6172.5 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 53 | `PURIFICATION _ Scrubber gas flow _ Avg Nm3` | `scrubber_gas_flow___avg_nm3` | Cubic Meters (m³) | numeric | 9.09% | 1980.0 | 58935.0 | 14845.5 | 11907.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 54 | `PURIFICATION _ Utilized water m3` | `utilized_water_m3` | Cubic Meters (m³) | numeric | 9.09% | 165.0 | 1229.0 | 636.83 | 631.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 55 | `PURIFICATION _ HP compressor ran time Hrs` | `hp_compressor_ran_time_hrs` | Hours / Timestamp | object | 10.23% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 56 | `PURIFICATION _ Storage cascade pressure bar _ Cascade-40-255-06` | `storage_cascade_pressure_bar` | Bar | numeric | 9.66% | 0.0 | 240.0 | 165.28 | 215.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 57 | `PURIFICATION _ Storage cascade pressure bar _ Cascade-40-255-03` | `storage_cascade_pressure_bar` | Bar | numeric | 9.09% | 0.0 | 240.0 | 158.56 | 215.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 58 | `PURIFICATION _ Storage cascade pressure bar _ Cascade-40-260M-01` | `storage_cascade_pressure_bar` | Bar | numeric | 9.09% | 30.0 | 240.0 | 153.56 | 150.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 59 | `PURIFICATION _ Storage cascade pressure bar _ Cascade-40-255-04` | `storage_cascade_pressure_bar` | Bar | numeric | 9.09% | 40.0 | 240.0 | 144.69 | 120.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 60 | `PURIFICATION _ Supplied to TORRENT Pipeline _ Starting reading scum` | `supplied_to_torrent_pipeline` | None | numeric | 8.52% | 0.0 | 292228.41 | 79553.18 | 0.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 61 | `PURIFICATION _ Supplied to TORRENT Pipeline _ Closing reading scum` | `supplied_to_torrent_pipeline` | None | numeric | 7.95% | 0.0 | 29186736.0 | 259244.98 | 0.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 62 | `PURIFICATION _ Supplied to TORRENT Pipeline _ Avg scm` | `supplied_to_torrent_pipeline` | None | numeric | 7.95% | 0.0 | 120.98 | 14.86 | 0.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 63 | `PURIFICATION _ Supplied to TORRENT Pipeline _ Kgs` | `supplied_to_torrent_pipeline` | Kilograms (kg) | numeric | 7.95% | 0.0 | 88.31 | 10.95 | 0.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 64 | `PURIFICATION _ Supplied to TORRENT Pipeline _ DC No` | `supplied_to_torrent_pipeline` | None | numeric | 7.95% | 0.0 | 84.0 | 16.96 | 0.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 65 | `PURIFICATION _ CBG - supplied details _ Vehicle Number` | `cbg___supplied_details___veh` | None | str | 6.82% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 66 | `PURIFICATION _ CBG - supplied details _ Vehicle Filling time` | `cbg___supplied_details___veh` | Hours / Timestamp | object | 6.25% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 67 | `PURIFICATION _ CBG - supplied details _ Vehicle Out time` | `cbg___supplied_details___veh` | Hours / Timestamp | object | 6.25% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 68 | `PURIFICATION _ CBG - supplied details _ Starting pressure Bar` | `cbg___supplied_details___sta` | Bar | numeric | 6.82% | 30.0 | 90.0 | 48.53 | 50.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 69 | `PURIFICATION _ CBG - supplied details _ Final pressure bar` | `cbg___supplied_details___fin` | Bar | numeric | 6.25% | 170.0 | 240.0 | 234.57 | 240.0 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 70 | `PURIFICATION _ CBG - supplied details _ Starting reading kgs` | `cbg___supplied_details___sta` | Kilograms (kg) | numeric | 5.11% | 860441.37 | 1296050.3 | 1054548.77 | 1048001.35 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 71 | `PURIFICATION _ CBG - supplied details _ Closing reading kgs` | `cbg___supplied_details___clo` | Kilograms (kg) | numeric | 5.11% | 0.61 | 1296518.5 | 1047296.02 | 1044979.25 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 72 | `PURIFICATION _ CBG - supplied details _ Total kgs` | `cbg___supplied_details___tot` | Kilograms (kg) | numeric | 5.68% | -1275334.69 | 482.53 | -7304.34 | 437.41 | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 73 | `MARKETING _ Vehicle unloading _ Date` | `vehicle_unloading___date` | Date (YYYY-MM-DD) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 74 | `MARKETING _ Vehicle unloading _ Vehicle in time` | `vehicle_unloading___vehicle_` | Hours / Timestamp | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 75 | `MARKETING _ Vehicle unloading _ Vehicle No` | `vehicle_unloading___vehicle_` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 76 | `MARKETING _ Vehicle unloading _ DC No` | `vehicle_unloading___dc_no` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 77 | `MARKETING _ Vehicle unloading _ Starting pressure bar` | `vehicle_unloading___starting` | Bar | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 78 | `MARKETING _ Vehicle unloading _ Starting reading kgs` | `vehicle_unloading___starting` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 79 | `MARKETING _ Vehicle unloading _ Closing Pressure bar` | `vehicle_unloading___closing_` | Bar | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 80 | `MARKETING _ Vehicle unloading _ Closing reading kgs` | `vehicle_unloading___closing_` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 81 | `MARKETING _ Vehicle unloading _ Utilized gas Bar` | `vehicle_unloading___utilized` | Bar | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 82 | `MARKETING _ Vehicle unloading _ Total kgs` | `vehicle_unloading___total_kg` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 83 | `MARKETING _ Vehicle unloading _ Vehicle out time` | `vehicle_unloading___vehicle_` | Hours / Timestamp | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 84 | `MARKETING _ Dispenser-1 _ Starting reading kgs` | `dispenser_1___starting_readi` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 85 | `MARKETING _ Dispenser-1 _ Closing reading kgs` | `dispenser_1___closing_readin` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 86 | `MARKETING _ Dispenser-1 _ Avg kgs` | `dispenser_1___avg_kgs` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 87 | `MARKETING _ Dispenser-2 _ Starting reading kgs` | `dispenser_2___starting_readi` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 88 | `MARKETING _ Dispenser-2 _ Closing reading kgs` | `dispenser_2___closing_readin` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 89 | `MARKETING _ Dispenser-2 _ Avg kgs` | `dispenser_2___avg_kgs` | Kilograms (kg) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 90 | `MARKETING _ Solid Fertilizer Sale (un-sieved) MT` | `solid_fertilizer_sale_un_sie` | Metric Tons (MT) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 91 | `MARKETING _ Solid Fertilizer Sale (sieved) MT` | `solid_fertilizer_sale_sieved` | Metric Tons (MT) | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 92 | `MARKETING _ Liquid fertilizer (KL)` | `liquid_fertilizer_kl` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |
| 93 | `MARKETING _ REMARKS` | `remarks` | None | object | 100.0% | N/A | N/A | N/A | N/A | **No (Downstream)** | **No** | Post-digestion scrubbing, compression, cascade filling, or commercial vehicle sales. |

---

## 2. AgSTAR Livestock Anaerobic Digester Database
- **File:** `agstar-livestock-ad-database-combined.xlsx`
- **Sheet:** `Sheet1`
- **Custodian:** US EPA / USDA AgSTAR Program
- **Structure:** Static cross-sectional facility registry (526 livestock farms across 38 US states)
- **Temporal Scope:** Single static cross-sectional snapshot (No daily timestamps, no continuous sensor logs)
- **Total Columns:** 26

| Col | Original Header | Normalized Name | Physical Unit | Dtype | Missing (%) | Unique | ML Feature (for Daily Biogas)? | Interpretation & Domain Relevance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 01 | `Project Name` | `project_name` | None | str | 0.0% | 526 | **NO (Static Registry)** | Facility metadata. |
| 02 | `Cluster Name` | `cluster_name` | None | str | 75.48% | 20 | **NO (Static Registry)** | Facility metadata. |
| 03 | `Project Type` | `project_type` | None | str | 0.0% | 4 | **NO (Static Registry)** | Facility metadata. |
| 04 | `City` | `city` | None | str | 0.19% | 327 | **NO (Static Registry)** | Facility metadata. |
| 05 | `County` | `county` | None | str | 1.71% | 216 | **NO (Static Registry)** | Facility metadata. |
| 06 | `State` | `state` | None | str | 0.0% | 38 | **NO (Static Registry)** | Facility metadata. |
| 07 | `Digester Type` | `digester_type` | None | str | 0.19% | 14 | **Benchmark context only** | Categorical engineering design (Plug Flow, Covered Lagoon, Complete Mix). |
| 08 | `Status` | `status` | None | str | 0.0% | 3 | **NO (Static Registry)** | Facility metadata. |
| 09 | `Year Operational` | `year_operational` | Year (YYYY) | numeric | 3.23% | 37 | **NO (Static Registry)** | Facility metadata. |
| 10 | `Animal/Farm Type(s)` | `animal_farm_types` | None | str | 0.0% | 12 | **NO (Static Registry)** | Facility metadata. |
| 11 | `Cattle` | `cattle` | Head Count (Animals) | float64 | 97.72% | 11 | **NO (Static Registry)** | Facility metadata. |
| 12 | `Dairy` | `dairy` | Head Count (Animals) | numeric | 19.96% | 205 | **Benchmark context only** | Livestock population supported by the digestion system. |
| 13 | `Poultry` | `poultry` | Head Count (Animals) | float64 | 97.53% | 12 | **NO (Static Registry)** | Facility metadata. |
| 14 | `Swine` | `swine` | Head Count (Animals) | float64 | 88.78% | 50 | **Benchmark context only** | Livestock population supported by the digestion system. |
| 15 | `Co-Digestion` | `co_digestion` | None | str | 74.33% | 33 | **NO (Static Registry)** | Facility metadata. |
| 16 | `Biogas Generation Estimate (cu-ft/day)` | `biogas_generation_estimat` | Cubic Feet/day (cu-ft/day) | numeric | 55.89% | 161 | **NO (Static Registry)** | Estimated annual/daily facility design rating (missing in 55.9% of records). |
| 17 | `Electricity Generated (kWh/yr)` | `electricity_generated_kwh` | None | numeric | 53.99% | 188 | **NO (Static Registry)** | Annual electricity generation potential (missing in 54.0% of records). |
| 18 | `Biogas End Use(s)` | `biogas_end_uses` | None | str | 1.52% | 18 | **NO (Static Registry)** | Facility metadata. |
| 19 | `LCFS Pathway?` | `lcfs_pathway` | None | str | 83.65% | 1 | **NO (Static Registry)** | Facility metadata. |
| 20 | `System Designer(s)/Developer(s) and Affiliates` | `system_designers_develope` | None | str | 4.37% | 230 | **NO (Static Registry)** | Facility metadata. |
| 21 | `Receiving Utility` | `receiving_utility` | None | str | 52.09% | 101 | **NO (Static Registry)** | Facility metadata. |
| 22 | `Total Emission Reductions (MTCO2e/yr)` | `total_emission_reductions` | None | numeric | 24.14% | 358 | **NO (Static Registry)** | Facility metadata. |
| 23 | `Awarded USDA Funding?` | `awarded_usda_funding` | None | str | 75.86% | 1 | **NO (Static Registry)** | Facility metadata. |
| 24 | `Sheet` | `sheet` | None | str | 0.0% | 2 | **NO (Static Registry)** | Facility metadata. |
| 25 | `Year Shutdown` | `year_shutdown` | Year (YYYY) | float64 | 83.65% | 21 | **NO (Static Registry)** | Facility metadata. |
| 26 | `Reason for Closure` | `reason_for_closure` | None | str | 88.02% | 57 | **NO (Static Registry)** | Facility metadata. |
# Cleanup Review Required: Preserved & Candidate Items

**Audit Date:** 2026-09-19  
**Repository Scope:** `c:\Users\gssr2\Desktop\yesist`  
**Safety Protocol:** Strict Zero-Destabilization Rule — When Uncertain, KEEP.

---

## Executive Summary

During the repository hygiene and cleanup operation, all confirmed caches (76 files across 13 directories) were safely deleted, loose diagnostic scripts were organized into `archive/scratch/`, unreferenced reference media were organized into `archive/reference_media/`, and the SFOA research record was preserved in `archive/research_sfoa/`.

The following items were identified during inventory but **INTENTIONALLY NOT DELETED** because they are either actively referenced by backend tests, required by data processing pipelines, or serve as primary competition documentation.

---

## 1. Preserved Test Fixtures: `scratch/audit_test_files/`

- **Path:** `scratch/audit_test_files/` (8 files: `test_A_exact_schema.xlsx` through `test_H_missing_intervals.xlsx`, 41.9 KB)
- **Why it looks like a cleanup candidate:** Located within a folder named `scratch/`, which typically implies temporary or disposable files.
- **References Found:**
  - `backend/tests/test_safety_provenance.py` (line 333: `excel_path = os.path.join("scratch", "audit_test_files", "test_A_exact_schema.xlsx")`)
  - `docs/ANTIGRAVITY_FRONTEND_FORENSIC_AUDIT.md` (Table 3.1: Ingestion validation audit matrix)
  - `docs/ANTIGRAVITY_FULL_BROWSER_AUDIT.md` (Section 5: File ingestion audit)
- **Why Deletion Was NOT Safe:** Deleting or moving this folder would immediately break `backend/tests/test_safety_provenance.py` (Test 12: User Upload Ingestion Exact Schema & Zero Fallbacks).
- **Recommendation:** **KEEP PERMANENTLY IN PLACE** as active test fixtures.

---

## 2. Primary Raw Datasets in Root Directory

### 2.1 `Master data Spark biogas.xlsx`
- **Path:** `Master data Spark biogas.xlsx` (Root directory, 3.10 MB, SHA256: `4d45f2d469a3f2f4bbbb04f804ec57085d451101087e729a925617ad52e1d3b4`)
- **Why it looks like a cleanup candidate:** Large Excel workbook located directly in the project root.
- **References Found:**
  - `ml/preprocessing/pipeline.py` (line 21: `RAW_EXCEL_PATH = "Master data Spark biogas.xlsx"`)
  - `data/processed/spark_biogas_metadata.json` (`"primary_source_file": "Master data Spark biogas.xlsx"`)
  - `docs/DATASET_AUDIT.md`, `docs/DATA_AUDIT_SUMMARY.md`, `docs/SOURCE_AUDIT.md`
- **Why Deletion Was NOT Safe:** This is the authentic, immutable SCADA operational logbook from Spark Bio Gas Pvt Ltd. Deleting it would break the ML data preprocessing pipeline.
- **Recommendation:** **KEEP PERMANENTLY IN ROOT** as the authoritative primary raw dataset.

### 2.2 `agstar-livestock-ad-database-combined.xlsx`
- **Path:** `agstar-livestock-ad-database-combined.xlsx` (Root directory, 60.7 KB)
- **Why it looks like a cleanup candidate:** Loose Excel file in root.
- **References Found:**
  - `docs/DATASET_COMPATIBILITY.md`, `docs/DATASET_AUDIT.md`, `docs/DATA_DICTIONARY.md`
- **Why Deletion Was NOT Safe:** Represents the public AgSTAR benchmark database documented in the repository audit.
- **Recommendation:** **KEEP IN ROOT** or relocate only if documentation paths are updated concurrently.

---

## 3. Reference Documents & Presentation PDFs in Root

### 3.1 `Scanned_20260821_081824.pdf`
- **Path:** `Scanned_20260821_081824.pdf` (Root directory, 5.64 MB)
- **Content:** 30-page scan of the IEEE YESIST12 competition portal abstract submission.
- **References Found:** `docs/SOURCE_AUDIT.md` (Table 3.1, Section 3.3).

### 3.2 `BIO GAS SYSTEM (1).pdf`
- **Path:** `BIO GAS SYSTEM (1).pdf` (Root directory, 1.76 MB)
- **Content:** Earlier preliminary project report.
- **References Found:** `docs/SOURCE_AUDIT.md` (Table 3.1, Section 3.1).

### 3.3 `yesist ppt final .pdf`
- **Path:** `yesist ppt final .pdf` (Root directory, 1.25 MB)
- **Content:** Presentation slide deck for the competition.
- **References Found:** `docs/SOURCE_AUDIT.md` (Table 3.1, Section 3.2).

- **Why Deletion Was NOT Safe:** These are primary project submission artifacts evaluated in the source audit. They contain no executable code, but deleting them would remove original competition records.
- **Recommendation for Future Cleanup:** If root cleanliness is preferred, these three files can safely be moved into a dedicated subfolder (e.g., `docs/reference_documents/` or `archive/reference_documents/`) and their citations in `docs/SOURCE_AUDIT.md` updated. Currently **KEPT IN ROOT** to avoid breaking any external links.

---

## 4. Frontend Viewport Inspection Screenshots: `docs/audit_screenshots/`

- **Path:** `docs/audit_screenshots/` (38 PNG images, 11.27 MB)
- **Why it looks like a cleanup candidate:** Image files occupying significant disk space (11.27 MB).
- **References Found:**
  - `docs/ANTIGRAVITY_FRONTEND_FORENSIC_AUDIT.md` (lines 408–450 explicitly link to each of the 38 screenshot filenames).
- **Why Deletion Was NOT Safe:** Deleting these images would create 38 broken image links in `docs/ANTIGRAVITY_FRONTEND_FORENSIC_AUDIT.md`.
- **Recommendation:** **KEEP IN PLACE** as long as forensic audit documentation is maintained.

---

## 5. Machine Learning Checkpoint Variations: `models/`

- **Path:** `models/` (15 files, 314.9 KB)
  - `gru_lookback_14d_residual.pt` (Production Default — **CRITICAL PROTECTED ASSET**)
  - `gru_scaler_metadata.json` (Production Scaler — **CRITICAL PROTECTED ASSET**)
  - `xco_net_best.pt` (Active Benchmark Model served by API — **CRITICAL PROTECTED ASSET**)
  - `xco_scaler_metadata.json` (Active Scaler — **CRITICAL PROTECTED ASSET**)
  - `gru_lookback_3d_direct.pt`, `gru_lookback_3d_residual.pt`, `gru_lookback_7d_direct.pt`, `gru_lookback_7d_residual.pt`, `gru_lookback_14d_direct.pt`
  - `lstm_lookback_3d_direct.pt`, `lstm_lookback_3d_residual.pt`, `lstm_lookback_7d_direct.pt`, `lstm_lookback_7d_residual.pt`, `lstm_lookback_14d_direct.pt`, `lstm_lookback_14d_residual.pt`
- **Why it looks like a cleanup candidate:** Multiple lookback variations (3d, 7d, 14d, direct, residual).
- **References Found:**
  - `results/temporal_model_results.csv`
  - `docs/BASELINE_AND_TEMPORAL_MODEL_REPORT.md`
  - `backend/app/services/forecast_service.py`
- **Why Deletion Was NOT Safe:** These 15 files represent the complete empirical matrix of the research project. Total size across all 15 files is only 314.9 KB.
- **Recommendation:** **KEEP ALL 15 FILES** for full research reproducibility.

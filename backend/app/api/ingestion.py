from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from backend.app.schemas.ingestion import IngestionAnalyzeRequest, IngestionReportResponse
from backend.app.services.ingestion_service import ingestion_service

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])

@router.post("/analyze")
def analyze_uploaded_data(req: IngestionAnalyzeRequest) -> Dict[str, Any]:
    """
    Analyze arbitrary uploaded Excel/SCADA data.
    Performs semantic column mapping, explicit unit conversion,
    computes standalone statistics for all numeric columns,
    validates time series, checks model requirements, and enforces
    strict zero-fallback validation rules with explicit domain isolation.
    """
    report, standardized_rows = ingestion_service.analyze_dataset(req.filename, req.rows)
    rep_dict = report.model_dump()
    return {
        **rep_dict,
        "report": rep_dict,
        "standardized_rows": standardized_rows,
        "clean_rows": standardized_rows,
        "total_records": rep_dict["total_rows"],
        "columns_recognized": rep_dict["recognized_columns_count"],
        "column_mappings": rep_dict["mappings"],
        "column_statistics": rep_dict["statistics"]
    }

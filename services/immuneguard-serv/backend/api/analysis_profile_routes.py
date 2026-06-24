import os

from fastapi import APIRouter, HTTPException

import requests as req

from backend.api.analysis_profile_store_routes import build_analysis_profile_document
from backend.database.mongodb import db
from backend.models.schemas import (
    AnalysisProfileCreateRequest,
    AnalysisProfileProposalResponse,
    SignalScanResponse,
)
from backend.api.signal_scanner_routes import scan_signals_by_dataset_id
from core.signal_scanner.profile_builder import build_analysis_profile_from_scan


router = APIRouter(prefix="/analysis-profile", tags=["Analysis Profile"])


@router.get("/{dataset_id}")
async def get_analysis_profile(dataset_id: str):
    if db is None:
        raise HTTPException(503, "Database not connected")

    doc = await db.immuneguard_analysis_profiles.find_one({"dataset_id": dataset_id})
    if not doc:
        raise HTTPException(404, "Analysis profile not found")

    doc.pop("_id", None)
    return doc


@router.post("/{dataset_id}/auto", response_model=AnalysisProfileProposalResponse)
async def generate_analysis_profile_proposal(dataset_id: str):
    try:
        scan_result_dict = await scan_signals_by_dataset_id(dataset_id)
        # Convert dict to Pydantic model to avoid AttributeError in profile_builder
        scan_result = SignalScanResponse(**scan_result_dict)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Error scanning signals: {exc}") from exc

    cleaning_url = os.getenv("CLEANING_SERVICE_URL", "http://localhost:8004")
    try:
        response = req.get(f"{cleaning_url}/dataset/{dataset_id}/json", timeout=20)
        if response.status_code != 200:
            raise HTTPException(
                404,
                f"Dataset {dataset_id} not found in cleaning-service (status={response.status_code})",
            )
        payload = response.json()
        dataset_name = payload.get("name") or payload.get("dataset_name") or dataset_id
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Unable to fetch dataset metadata from cleaning-service: {exc}") from exc

    proposal = build_analysis_profile_from_scan(scan_result, dataset_id=dataset_id, dataset_name=dataset_name)
    return AnalysisProfileProposalResponse(**proposal)


@router.post("/{dataset_id}")
async def create_analysis_profile(dataset_id: str, body: AnalysisProfileCreateRequest):
    if db is None:
        raise HTTPException(503, "Database not connected")

    document = build_analysis_profile_document(dataset_id, body)

    await db.immuneguard_analysis_profiles.update_one(
        {"dataset_id": dataset_id},
        {"$set": document},
        upsert=True,
    )

    return {"status": "created", "dataset_id": dataset_id, "analysis_profile": document}

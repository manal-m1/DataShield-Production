from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from backend.database.mongodb import db
from backend.models.schemas import AnalysisProfileCreateRequest


router = APIRouter(prefix="/analysis-profile-store", tags=["Analysis Profile"])
router_plural = APIRouter(prefix="/analysis-profiles", tags=["Analysis Profile"])


def build_analysis_profile_document(dataset_id: str, body: AnalysisProfileCreateRequest) -> dict:
    quasi_identifier_columns: List[str] = []
    sensitive_attribute: Optional[str] = None
    pii_columns: List[str] = []
    columns_dict: Dict[str, Any] = {}

    for column in body.columns:
        effective_roles = column.get_roles()
        columns_dict[column.name] = {
            "roles": effective_roles,
            "type": column.type,
            "description": column.description or column.name,
        }
        for role in effective_roles:
            if role == "quasi_identifier":
                quasi_identifier_columns.append(column.name)
            elif role == "sensitive_attribute":
                if sensitive_attribute is None:
                    sensitive_attribute = column.name
            elif role == "pii":
                pii_columns.append(column.name)

    quasi_identifier_columns = list(dict.fromkeys(quasi_identifier_columns))
    pii_columns = list(dict.fromkeys(pii_columns))

    if not quasi_identifier_columns:
        raise HTTPException(400, "Au moins un quasi-identifiant est requis.")
    if not sensitive_attribute:
        raise HTTPException(400, "Un attribut sensible est requis.")

    return {
        "dataset_id": dataset_id,
        "dataset_name": body.dataset_name,
        "description": body.description,
        "secteur": body.secteur or "rh",
        "columns": columns_dict,
        "attacks": {
            "quasi_identifiers": quasi_identifier_columns,
            "sensitive_attribute": sensitive_attribute,
            "public_sample_frac": body.public_sample_frac,
        },
        "checks": {
            "imbalance_columns": body.imbalance_columns or quasi_identifier_columns,
            "correlation_columns": body.correlation_columns or [],
            "id_column": body.id_column,
            "pii_columns": pii_columns,
            "sensitive_health_columns": body.sensitive_health_columns or [],
        },
        "created_at": datetime.now().isoformat(),
    }


@router.get("/{dataset_id}")
async def get_analysis_profile_record(dataset_id: str):
    if db is None:
        raise HTTPException(503, "Database not connected")

    document = await db.immuneguard_analysis_profiles.find_one({"dataset_id": dataset_id})
    if not document:
        raise HTTPException(404, "Analysis profile not found")

    document.pop("_id", None)
    return document


@router_plural.get("")
async def list_analysis_profiles():
    if db is None:
        return []
    cursor = db.immuneguard_analysis_profiles.find({}, {"_id": 0})
    return await cursor.to_list(length=100)


@router.post("/{dataset_id}")
async def create_analysis_profile_record(dataset_id: str, body: AnalysisProfileCreateRequest):
    if db is None:
        raise HTTPException(503, "Database not connected")

    profile_document = build_analysis_profile_document(dataset_id, body)

    await db.immuneguard_analysis_profiles.update_one(
        {"dataset_id": dataset_id},
        {"$set": profile_document},
        upsert=True,
    )

    return {"status": "created", "dataset_id": dataset_id, "analysis_profile": profile_document}


@router.delete("/{dataset_id}")
async def delete_analysis_profile_record(dataset_id: str):
    if db is None:
        raise HTTPException(503, "Database not connected")
    result = await db.immuneguard_analysis_profiles.delete_one({"dataset_id": dataset_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Analysis profile not found")
    return {"status": "deleted", "dataset_id": dataset_id}

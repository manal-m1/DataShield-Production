import os
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
import pandas as pd
import requests as req
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database.mongodb import db
from core.attack.attack import compute_succ, get_attack_config_from_profile
from core.risk_analysis import (
    build_xai,
    classify_risk,
    compute_c_factor,
    compute_score_b as risk_compute_score_b,
    compute_score_i as risk_compute_score_i,
)
from core.vulnerabilte.checks import run_all_checks_with_profile
from core.xai_generator import generate_xai_report

router = APIRouter(prefix="/score", tags=["Score"])
router_plural = APIRouter(prefix="/scores", tags=["Score"])
score_i_router = APIRouter(prefix="/score-i", tags=["Score I"])
stats_router = APIRouter(tags=["Stats"])
risk_router = APIRouter(tags=["Risk"])


class DatasetScoreRequest(BaseModel):
    dataset_id: str
    A: Optional[float] = None
    datacard: Optional[Dict[str, Any]] = None


async def _load_profile_and_dataframe(dataset_id: str) -> tuple[dict, pd.DataFrame, dict]:
    if db is None:
        raise HTTPException(503, "Database not connected")

    profile_doc = await db.immuneguard_analysis_profiles.find_one({"dataset_id": dataset_id})
    if not profile_doc:
        raise HTTPException(404, "Profil d'analyse introuvable. Veuillez d'abord configurer les colonnes.")
    profile_doc.pop("_id", None)

    cleaning_url = os.getenv("CLEANING_SERVICE_URL", "http://localhost:8004")
    try:
        resp = req.get(f"{cleaning_url}/dataset/{dataset_id}/json", timeout=20)
        if resp.status_code != 200:
            raise HTTPException(
                404,
                f"Dataset {dataset_id} introuvable dans le cleaning-service (status={resp.status_code})",
            )
        data = resp.json()
        df = pd.DataFrame(data.get("data", []))
        datacard = data.get("datacard") or {}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Erreur de communication avec le cleaning-service: {str(e)}")

    if df.empty:
        raise HTTPException(400, "Le dataset est vide.")
    return profile_doc, df, (datacard if isinstance(datacard, dict) else {})


@router.post("/{dataset_id}")
async def compute_score(dataset_id: str):
    """
    Compute Score A for a dataset.
    """
    if db is None:
        raise HTTPException(503, "Database not connected")

    # 1. Get analysis profile
    profile_doc = await db.immuneguard_analysis_profiles.find_one({"dataset_id": dataset_id})
    if not profile_doc:
        raise HTTPException(404, "Profil d'analyse introuvable. Veuillez d'abord configurer les colonnes.")

    profile_doc.pop("_id", None)

    # 2. Fetch dataset from cleaning-service
    CLEANING_URL = os.getenv("CLEANING_SERVICE_URL", "http://localhost:8004")
    try:
        resp = req.get(f"{CLEANING_URL}/dataset/{dataset_id}/json", timeout=15)
        if resp.status_code != 200:
            raise HTTPException(
                404,
                f"Dataset {dataset_id} introuvable dans le cleaning-service (status={resp.status_code})",
            )
        data = resp.json()
        df = pd.DataFrame(data.get("data", []))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Erreur de communication avec le cleaning-service: {str(e)}")

    if df.empty:
        raise HTTPException(400, "Le dataset est vide.")

    # 3. Run Score A computation
    try:
        attack_config = get_attack_config_from_profile(profile_doc)
        succ_result = compute_succ(df, attack_config)
        vuln_result = run_all_checks_with_profile(df, profile_doc)

        succ = float(succ_result["Succ"])
        vuln = float(vuln_result["Vuln"])
        score_a = 0.60 * succ + 0.40 * vuln

        # 4. XAI
        qi_list = profile_doc["attacks"]["quasi_identifiers"]
        sensitive_attr = profile_doc["attacks"]["sensitive_attribute"]
        xai_report = generate_xai_report(
            succ_result=succ_result,
            vuln_result=vuln_result,
            score_a=score_a,
            qi_list=qi_list,
            sensitive_attr=sensitive_attr,
        )

        result = {
            "dataset_id": dataset_id,
            "dataset_name": profile_doc.get("dataset_name", dataset_id),
            "computed_at": datetime.now().isoformat(),
            "taux_linkage": succ_result["taux_linkage"],
            "taux_singling": succ_result["taux_singling"],
            "taux_inference": succ_result["taux_inference"],
            "Succ": round(succ, 3),
            "detected_checks": vuln_result["detected_checks"],
            "Vuln": round(vuln, 3),
            "A": round(score_a, 3),
            "xai": xai_report,
        }

        # 5. Persist
        await db.immuneguard_scores.update_one(
            {"dataset_id": dataset_id},
            {"$set": result},
            upsert=True,
        )

        # Audit log
        await db.audit_logs.insert_one({
            "service": "IMMUNEGUARD",
            "action": "SCORE_A_EVALUATION",
            "user": "system",
            "status": "WARNING" if score_a >= 0.5 else "INFO",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "dataset_id": dataset_id,
                "score_a": round(score_a, 3),
                "succ": round(succ, 3),
                "vuln": round(vuln, 3),
            },
        })

        return result

    except ValueError as e:
        raise HTTPException(400, f"Erreur dans le calcul du score: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erreur interne: {str(e)}")


@router.get("/{dataset_id}")
async def get_score(dataset_id: str):
    """Retrieve the latest Score A for a dataset."""
    if db is None:
        raise HTTPException(503, "Database not connected")
    
    doc = await db.immuneguard_scores.find_one({"dataset_id": dataset_id})
    if not doc:
        raise HTTPException(404, "Aucun score trouvé. Lancez d'abord le calcul.")
    
    doc.pop("_id", None)
    return doc


@score_i_router.post("/{dataset_id}")
async def compute_score_i(dataset_id: str):
    """
    Compute Score I for a dataset.
    """
    if db is None:
        raise HTTPException(503, "Database not connected")

    profile_doc = await db.immuneguard_analysis_profiles.find_one({"dataset_id": dataset_id})
    if not profile_doc:
        raise HTTPException(404, "Profil d'analyse introuvable. Veuillez d'abord configurer les colonnes.")

    profile_doc.pop("_id", None)
    secteur = profile_doc.get("secteur", "rh")

    cleaning_url = os.getenv("CLEANING_SERVICE_URL", "http://localhost:8004")
    try:
        resp = req.get(f"{cleaning_url}/dataset/{dataset_id}/json", timeout=15)
        if resp.status_code != 200:
            raise HTTPException(
                404,
                f"Dataset {dataset_id} introuvable dans le cleaning-service (status={resp.status_code})",
            )
        data = resp.json()
        df = pd.DataFrame(data.get("data", []))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Erreur de communication avec le cleaning-service: {str(e)}")

    if df.empty:
        raise HTTPException(400, "Le dataset est vide.")

    try:
        raw_result = risk_compute_score_i(df, profile_doc)
        formatted_result = {
            "dataset_id": dataset_id,
            "dataset_name": profile_doc.get("dataset_name", dataset_id),
            "computed_at": datetime.now().isoformat(),
            "scoreI": raw_result["I"],
            "secteur": raw_result.get("secteur") or secteur,
            "domaines": raw_result.get("domaines_actives", []),
            "mapping_actions": raw_result.get("mapping_actions", []),
            "top3": [
                {
                    "incident_id": str(inc.get("incident_id", "")),
                    "titre": inc.get("title", ""),
                    "sim": float(inc.get("sim", 0)),
                    "grav": float(inc.get("grav", 0)),
                }
                for inc in raw_result.get("incidents", [])
            ],
            "score_i_details": raw_result,
        }

        await db.immuneguard_score_i.update_one(
            {"dataset_id": dataset_id},
            {"$set": formatted_result},
            upsert=True,
        )

        await db.audit_logs.insert_one({
            "service": "IMMUNEGUARD",
            "action": "SCORE_I_EVALUATION",
            "user": "system",
            "status": "INFO",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "dataset_id": dataset_id,
                "score_i": formatted_result["scoreI"],
                "secteur": formatted_result["secteur"],
            },
        })

        return formatted_result
    except ValueError as e:
        raise HTTPException(400, f"Erreur dans le calcul du score I: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erreur interne score I: {str(e)}")


@score_i_router.get("/{dataset_id}")
async def get_score_i(dataset_id: str):
    if db is None:
        raise HTTPException(503, "Database not connected")

    doc = await db.immuneguard_score_i.find_one({"dataset_id": dataset_id})
    if not doc:
        raise HTTPException(404, "Aucun score I trouve. Lancez d'abord le calcul.")

    doc.pop("_id", None)
    return doc


@risk_router.post("/score-b")
async def compute_score_b_from_body(body: DatasetScoreRequest):
    return await compute_score_b_endpoint(body.dataset_id)


@risk_router.post("/score-b/{dataset_id}")
async def compute_score_b_endpoint(dataset_id: str):
    profile_doc, df, _ = await _load_profile_and_dataframe(dataset_id)
    result = risk_compute_score_b(df, profile_doc)
    result.update({
        "dataset_id": dataset_id,
        "dataset_name": profile_doc.get("dataset_name", dataset_id),
        "computed_at": datetime.now().isoformat(),
    })
    if db is not None:
        await db.immuneguard_score_b.update_one({"dataset_id": dataset_id}, {"$set": result}, upsert=True)
    return result


@risk_router.post("/score-i")
async def compute_score_i_from_body(body: DatasetScoreRequest):
    return await compute_score_i_endpoint(body.dataset_id)


@risk_router.post("/score-i-risk/{dataset_id}")
async def compute_score_i_endpoint(dataset_id: str):
    profile_doc, df, _ = await _load_profile_and_dataframe(dataset_id)
    result = risk_compute_score_i(df, profile_doc)
    result.update({
        "dataset_id": dataset_id,
        "dataset_name": profile_doc.get("dataset_name", dataset_id),
        "computed_at": datetime.now().isoformat(),
    })
    if db is not None:
        await db.immuneguard_score_i_risk.update_one({"dataset_id": dataset_id}, {"$set": result}, upsert=True)
    return result


@risk_router.post("/compute-risk")
async def compute_risk_from_body(body: DatasetScoreRequest):
    return await _compute_risk_impl(body.dataset_id, body.A, body.datacard)


@risk_router.post("/compute-risk/{dataset_id}")
async def compute_risk_path(dataset_id: str, score_a_override: Optional[float] = None):
    return await _compute_risk_impl(dataset_id, score_a_override, None)


async def _compute_risk_impl(
    dataset_id: str,
    score_a_override: Optional[float] = None,
    datacard_override: Optional[Dict[str, Any]] = None,
):
    profile_doc, df, datacard_stored = await _load_profile_and_dataframe(dataset_id)
    merged: Dict[str, Any] = {}
    if isinstance(datacard_stored, dict):
        merged.update(datacard_stored)
    if isinstance(datacard_override, dict):
        merged.update(datacard_override)
    datacard = merged

    # Merge DataCard into profile for C-factor (and future I-filtering).
    # Frontend sends keys: secteur/finalite/population/pays/origine/information.
    if isinstance(datacard, dict):
        secteur_usage = datacard.get("secteur")
        finalite = datacard.get("finalite")
        population = datacard.get("population")
        if secteur_usage:
            profile_doc["Secteur d'activité"] = secteur_usage
        if finalite:
            profile_doc["Finalité du traitement"] = finalite
        if population:
            profile_doc["Personnes concernées"] = population
    b_result = risk_compute_score_b(df, profile_doc)
    i_result = risk_compute_score_i(df, profile_doc)

    if score_a_override is None:
        existing = await db.immuneguard_scores.find_one({"dataset_id": dataset_id}) if db is not None else None
        if existing and "A" in existing:
            score_a = float(existing["A"])
        else:
            attack_config = get_attack_config_from_profile(profile_doc)
            succ_result = compute_succ(df, attack_config)
            vuln_result = run_all_checks_with_profile(df, profile_doc)
            score_a = 0.50 * float(succ_result["Succ"]) + 0.50 * float(vuln_result["Vuln"])
    else:
        score_a = float(score_a_override)

    b = float(b_result["B"])
    i = float(i_result["I"])
    c_result = compute_c_factor(profile_doc)
    r_base = 0.20 * b + 0.60 * score_a + 0.20 * i
    r_final = 100 * min(1.0, r_base * float(c_result["C"]))
    explanations = build_xai(df, profile_doc, i_result)

    result = {
        "dataset_id": dataset_id,
        "dataset_name": profile_doc.get("dataset_name", dataset_id),
        "computed_at": datetime.now().isoformat(),
        "B": round(b, 4),
        "A": round(score_a, 4),
        "I": round(i, 4),
        "score_b_details": {k: b_result[k] for k in ("b1", "b2", "b3", "b4")},
        "score_i_details": i_result,
        "c1": c_result["c1"],
        "c2": c_result["c2"],
        "C": c_result["C"],
        "R_base": round(r_base, 4),
        "R_final": round(r_final, 2),
        "classification": classify_risk(r_final),
        "xai": explanations,
    }
    if db is not None:
        await db.immuneguard_risk_results.update_one({"dataset_id": dataset_id}, {"$set": result}, upsert=True)
    return result


@router_plural.get("")
async def list_scores():
    """List all computed scores."""
    if db is None:
        return []
    cursor = db.immuneguard_scores.find({}, {"_id": 0})
    docs = await cursor.to_list(length=100)
    return docs


@stats_router.get("/stats")
async def get_stats():
    """Get aggregate ImmuneGuard statistics for the dashboard."""
    if db is None:
        return {"average_score": 0, "total_evaluations": 0}

    try:
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "avg_score": {"$avg": "$A"},
                    "total_evals": {"$sum": 1},
                }
            }
        ]
        cursor = db.immuneguard_scores.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if result:
            return {
                "average_score": round(result[0]["avg_score"], 3),
                "total_evaluations": result[0]["total_evals"],
            }
        return {"average_score": 0, "total_evaluations": 0}
    except Exception as e:
        return {"error": str(e), "average_score": 0, "total_evaluations": 0}

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core.signal_scanner.scanner import SignalScannerService


SERVICE_DIR = os.path.dirname(os.path.dirname(__file__))


def _candidate_path(env_name: str, names: List[str]) -> Optional[str]:
    override = os.getenv(env_name)
    if override and os.path.exists(override):
        return override
    for name in names:
        candidate = os.path.join(SERVICE_DIR, name)
        if os.path.exists(candidate):
            return candidate
    return None


def _norm(value: Any) -> str:
    # Normalize for robust matching across UI/Excel variants (accents, punctuation, casing).
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # Remove common UI markers (stars, warning symbols) and non-informative punctuation.
    text = re.sub(r"[★☆⚠️⚠]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_float(value: Any) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0.0
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass
class RiskAnalysisReferences:
    scanner: SignalScannerService
    datacard_tables: Dict[str, pd.DataFrame]
    aiid: pd.DataFrame
    data_paths: Dict[str, Optional[str]]


REFERENCES: Optional[RiskAnalysisReferences] = None


def initialize_risk_references() -> RiskAnalysisReferences:
    global REFERENCES
    ref_path = _candidate_path(
        "SIGNAL_REFERENCE_PATH",
        [
            "data/Ref_Signaux_Sprint7.xlsx",
            "Ref_Signaux_Sprint7.xlsx",
            "Ref_Signaux_ImmuneGuard_sprint 6.xlsx",
            "Ref_Signaux_v5.xlsx",
            "Ref_Signaux_v5.json",
            "Template_Ref_Signaux.xlsx",
            "Template_Ref_Signaux.json",
            "data/Ref_Signaux_v5.xlsx",
            "data/Ref_Signaux_v5.json",
            "data/Template_Ref_Signaux.xlsx",
            "data/Template_Ref_Signaux.json",
        ],
    )
    datacard_path = _candidate_path(
        "DATACARD_PATH",
        [
            "data/DataCard_ImmuneGuard_Sprint7.xlsx",
            "DataCard_ImmuneGuard_Sprint7.xlsx",
            "DataCard_ImmuneGuard_sprint 6.xlsx",
            "DataCard_ImmuneGuard.xlsx",
            "data/DataCard_v4.xlsx",
        ],
    )
    aiid_path = _candidate_path(
        "AIID_PATH",
        [
            "data/AIID_Sprint7.xlsx",
            "AIID_Sprint7.xlsx",
            "AIID_v2.xlsx", 
            "AIID_v2.csv", 
            "data/AIID_v2.xlsx", 
            "data/AIID_v2.csv"
        ],
    )

    scanner = SignalScannerService.from_path(ref_path) if ref_path else SignalScannerService.load_default()
    datacard_tables = _read_datacard_tables(datacard_path) if datacard_path else {}
    aiid = _read_aiid(aiid_path)

    REFERENCES = RiskAnalysisReferences(
        scanner=scanner,
        datacard_tables=datacard_tables,
        aiid=aiid,
        data_paths={"ref_signaux": ref_path, "datacard": datacard_path, "aiid": aiid_path},
    )
    return REFERENCES


def _read_datacard_tables(path: str) -> Dict[str, pd.DataFrame]:
    """
    DataCard risk analysis has "Mapping_C1_C2" with a document-like layout.
    We extract two clean tables (c1 and c2) so the generic lookup works.
    """
    tables = pd.read_excel(path, sheet_name=None)
    if "Mapping_C1_C2" not in tables:
        return tables

    raw = pd.read_excel(path, sheet_name="Mapping_C1_C2", header=None)

    def _extract_table(label_cols: List[str], weight_cols: List[str]) -> pd.DataFrame:
        header_idx = None
        label_col = ""
        weight_col = ""
        for i in range(min(len(raw), 200)):
            row = [str(v).strip() for v in raw.iloc[i].tolist()]
            for label_candidate in label_cols:
                for weight_candidate in weight_cols:
                    if label_candidate in row and weight_candidate in row:
                        header_idx = i
                        label_col = label_candidate
                        weight_col = weight_candidate
                        break
                if header_idx is not None:
                    break
            if header_idx is not None:
                break
        if header_idx is None:
            return pd.DataFrame()

        headers = [str(v).strip() if str(v).strip() not in {"nan", ""} else f"unnamed_{j}" for j, v in enumerate(raw.iloc[header_idx].tolist())]
        label_idx = headers.index(label_col)
        weight_idx = headers.index(weight_col)
        rows: List[dict[str, Any]] = []
        for i in range(header_idx + 1, len(raw)):
            label_value = raw.iat[i, label_idx]
            weight_value = raw.iat[i, weight_idx]
            label_text = str(label_value).strip()
            if label_text in {"", "nan"} or re.search(r"TABLE|EXEMPLE|Secteur ajout", label_text):
                break
            if str(weight_value).strip() in {"", "nan"}:
                break
            rows.append({label_col: label_value, weight_col: weight_value})
        data = pd.DataFrame(rows)
        if data.empty or label_col not in data.columns or weight_col not in data.columns:
            return pd.DataFrame()

        data = data[[label_col, weight_col]].copy()
        return data

    c1_df = _extract_table(["Secteur DataCard", "Secteur d'activité"], ["c₁", "c1"])
    c2_df = _extract_table(["Finalité IA", "Finalité DataCard", "Finalité du traitement"], ["c₂", "c2"])

    # Normalize column names to what lookup expects
    if not c1_df.empty:
        c1_df = c1_df.rename(columns={"c₁": "c1", "Secteur DataCard": "Secteur d'activité"})
        tables["Mapping_C1_C2__c1"] = c1_df
    if not c2_df.empty:
        c2_df = c2_df.rename(columns={"c₂": "c2", "Finalité IA": "Finalité du traitement", "Finalité DataCard": "Finalité du traitement"})
        tables["Mapping_C1_C2__c2"] = c2_df

    return tables


def get_risk_references() -> RiskAnalysisReferences:
    return REFERENCES or initialize_risk_references()


def _read_aiid(path: Optional[str]) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    try:
        return pd.read_excel(path)
    except Exception:
        if path.lower().endswith(".csv"):
            return pd.read_csv(path, sep=None, engine="python")
        raise


def _datacard_column_values(refs: RiskAnalysisReferences, column_name: str) -> set[str]:
    values: set[str] = set()
    wanted = _norm(column_name)
    for dataframe in refs.datacard_tables.values():
        for column in dataframe.columns:
            if _norm(column) == wanted:
                values.update(_norm(v) for v in dataframe[column].dropna().tolist())
    return {v for v in values if v}


def _resolve_datacard_value(refs: RiskAnalysisReferences, profile: dict[str, Any], column_name: str) -> str:
    direct = profile.get(column_name)
    if direct:
        return str(direct)
    normalized_column_name = _norm(column_name)
    if "secteur" in normalized_column_name:
        direct = profile.get("secteur") or profile.get("sector")
        if direct:
            return str(direct)
    if "finalite" in normalized_column_name:
        direct = profile.get("finalite") or profile.get("purpose")
        if direct:
            return str(direct)
    if "personnes" in normalized_column_name or "population" in normalized_column_name:
        direct = profile.get("population") or profile.get("personnes")
        if direct:
            return str(direct)
    values = _datacard_column_values(refs, column_name)
    sector = _norm(profile.get("secteur"))
    for value in values:
        if value and (value == sector or value in sector or sector in value):
            return value
    return str(profile.get("secteur") or "")


def compute_c_factor(profile: dict[str, Any], refs: Optional[RiskAnalysisReferences] = None) -> dict[str, float]:
    refs = refs or get_risk_references()
    # Risk analysis semantics:
    # - c1: weight tied to "Secteur d'activité"
    # - c2: weight tied to "Finalité du traitement" (with special case: facial recognition => c2 forced to 1.0)
    secteur = _norm(_resolve_datacard_value(refs, profile, "Secteur d'activité") or profile.get("secteur"))
    finalite = _norm(_resolve_datacard_value(refs, profile, "Finalité du traitement")) 

    c1 = _lookup_context_weight(refs, "c1", secteur)
    facial_values = _datacard_column_values(refs, "Finalité du traitement")
    if _is_facial_recognition(finalite, facial_values):
        c2 = 1.0
    else:
        c2 = _lookup_context_weight(refs, "c2", finalite)

    c = 1 + 0.20 * (_clip01(c1) + _clip01(c2))
    return {"c1": round(_clip01(c1), 4), "c2": round(_clip01(c2), 4), "C": round(c, 4)}


def _lookup_context_weight(refs: RiskAnalysisReferences, weight_name: str, selected_value: str) -> float:
    selected = _norm(selected_value)
    for dataframe in refs.datacard_tables.values():
        normalized_columns = {_norm(column): column for column in dataframe.columns}
        if weight_name not in normalized_columns:
            continue
        weight_column = normalized_columns[weight_name]
        label_columns = [c for c in dataframe.columns if c != weight_column]
        for _, row in dataframe.iterrows():
            if any(selected and selected == _norm(row.get(c)) for c in label_columns):
                return _clip01(_safe_float(row.get(weight_column)))
    return 0.0


def compute_score_b(dataframe: pd.DataFrame, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    refs = get_risk_references()
    scan = refs.scanner.scan_dataframe(dataframe)
    columns = scan["columns"]
    detected = [col for col in columns if col.get("signal")]
    total_columns = max(1, len(columns))
    signal_count = len(detected)

    # b1 = "exposition directe" measures direct exposure of identifying/sensitive data.
    # Decision/protected variables are handled via the normative component (b2) and density (b3).
    direct_exposure_signals = {"S_pii", "S_sens"}
    exposed_direct = [
        col
        for col in detected
        if col.get("signal") in direct_exposure_signals and not _is_masked(col["raw_column"], profile)
    ]

    b1 = len(exposed_direct) / max(1, signal_count)
    b2 = sum(_clip01(_safe_float(col.get("p"))) for col in detected) / max(1, signal_count)
    b3 = signal_count / total_columns
    b4_details = _data_quality_risk(dataframe)
    b4 = b4_details["score"]
    b = 0.40 * b1 + 0.25 * b2 + 0.20 * b3 + 0.15 * b4

    return {
        "B": round(_clip01(b), 4),
        "b1": round(_clip01(b1), 4),
        "b2": round(_clip01(b2), 4),
        "b3": round(_clip01(b3), 4),
        "b4": round(_clip01(b4), 4),
        "details": {
            "detected_signals": detected,
            "exposed_columns": [col["raw_column"] for col in exposed_direct],
            "quality": b4_details,
        },
    }


def _is_masked(column_name: str, profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    masked = profile.get("masked_columns") or profile.get("anonymized_columns") or []
    return column_name in masked


def _data_quality_risk(dataframe: pd.DataFrame) -> dict[str, Any]:
    if dataframe.empty:
        return {"score": 1.0, "missing": 1.0, "imbalance": 1.0, "variance": 1.0}

    missing = float(dataframe.isna().sum().sum()) / float(max(1, dataframe.shape[0] * dataframe.shape[1]))
    imbalance_scores: List[float] = []
    variance_scores: List[float] = []

    for column in dataframe.columns:
        series = dataframe[column].dropna()
        if series.empty:
            imbalance_scores.append(1.0)
            variance_scores.append(1.0)
            continue
        top_ratio = float(series.value_counts(normalize=True).iloc[0])
        imbalance_scores.append(top_ratio)
        if pd.api.types.is_numeric_dtype(series):
            variance_scores.append(1.0 if float(series.var() or 0.0) == 0.0 else 0.0)
        else:
            variance_scores.append(1.0 - min(1.0, float(series.nunique()) / float(max(1, len(series)))))

    imbalance = float(np.mean(imbalance_scores)) if imbalance_scores else 0.0
    variance = float(np.mean(variance_scores)) if variance_scores else 0.0
    score = (missing + imbalance + variance) / 3.0
    return {
        "score": round(_clip01(score), 4),
        "missing": round(_clip01(missing), 4),
        "imbalance": round(_clip01(imbalance), 4),
        "variance": round(_clip01(variance), 4),
    }


def _domain_code(value: Any) -> str:
    match = re.match(r"\s*(\d+)", str(value or ""))
    return match.group(1) if match else ""


def _resolve_sector(profile: dict[str, Any] | None) -> str:
    if not profile:
        return ""
    return str(
        profile.get("Secteur d'activité")
        or profile.get("secteur")
        or profile.get("sector")
        or ""
    )


def _sector_similarity(profile_sector: str, incident_sector: str) -> float:
    selected = _norm(profile_sector)
    incident = _norm(incident_sector)
    if not selected or not incident:
        return 0.0
    aliases = {
        "rh": "ressources humaines emploi",
        "ressources humaines": "ressources humaines emploi",
        "recrutement": "ressources humaines emploi",
        "sante": "sante humaine action sociale",
        "medical": "sante humaine action sociale",
        "finance": "activites financieres assurance",
        "transport": "transport entreposage",
        "tech": "information communication",
        "information": "information communication",
        "education": "education",
        "administration": "administration publique",
        "justice": "administration publique",
    }
    selected = aliases.get(selected, selected)
    incident = incident.replace("/", " ")
    if selected == incident or selected in incident or incident in selected:
        return 1.0
    selected_tokens = {t for t in re.split(r"\W+", selected) if len(t) > 3}
    incident_tokens = {t for t in re.split(r"\W+", incident) if len(t) > 3}
    if not selected_tokens or not incident_tokens:
        return 0.0
    return len(selected_tokens & incident_tokens) / len(selected_tokens | incident_tokens)


def _severity_keys_from_detected(detected: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    fallback_by_signal = {
        "S_pii": "sev_privacy",
        "S_prot": "sev_discrimination",
        "S_sens": "sev_privacy",
        "S_dec": "sev_discrimination",
    }
    for column in detected:
        severity_columns = column.get("severity_columns") or {}
        keys.extend(str(key) for key in severity_columns.keys() if str(key).startswith("sev_"))
        fallback = fallback_by_signal.get(str(column.get("signal") or ""))
        if fallback:
            keys.append(fallback)
    return list(dict.fromkeys(keys))


def _row_severity(row: pd.Series, severity_keys: list[str]) -> float:
    keys = [key for key in severity_keys if key in row.index]
    if not keys:
        keys = [key for key in row.index if str(key).startswith("sev_")]
    values = [_clip01(_safe_float(row.get(key)) / 5.0) for key in keys]
    return float(np.mean(values)) if values else 0.0


def _top_aiid_incidents(
    aiid: pd.DataFrame,
    active_domain_codes: set[str],
    profile_sector: str,
    severity_keys: list[str],
    k: int = 3,
) -> list[dict[str, Any]]:
    if aiid.empty:
        return []

    scored: list[dict[str, Any]] = []
    for _, row in aiid.iterrows():
        domain = str(row.get("mit_domain") or "")
        incident_sector = str(row.get("sector_datacard") or row.get("sector") or "")
        domain_sim = 1.0 if _domain_code(domain) in active_domain_codes else 0.0
        sector_sim = _sector_similarity(profile_sector, incident_sector)
        similarity = 0.70 * domain_sim + 0.30 * sector_sim
        severity = _row_severity(row, severity_keys)
        relevance = 0.60 * similarity + 0.40 * severity
        if relevance <= 0:
            continue
        scored.append({
            "incident_id": str(row.get("incident_id") or row.get("id") or ""),
            "title": str(row.get("title") or row.get("titre") or ""),
            "description": str(row.get("description") or ""),
            "mit_domain": domain,
            "sector": incident_sector,
            "sim": round(_clip01(similarity), 4),
            "grav": round(_clip01(severity), 4),
            "relevance": round(_clip01(relevance), 4),
        })

    scored.sort(key=lambda item: (item["relevance"], item["sim"], item["grav"]), reverse=True)
    return scored[:k]


def compute_score_i(dataframe: pd.DataFrame, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    refs = get_risk_references()
    scan = refs.scanner.scan_dataframe(dataframe)
    detected = [col for col in scan["columns"] if col.get("signal")]
    signal_count = max(1, len(detected))
    active_domain_codes = {
        code for code in (_domain_code(col.get("mit_domain")) for col in detected) if code
    }
    severity_keys = _severity_keys_from_detected(detected)
    profile_sector = _resolve_sector(profile)
    incidents = _top_aiid_incidents(refs.aiid, active_domain_codes, profile_sector, severity_keys, k=3)
    if incidents:
        sim_mean = float(np.mean([item["sim"] for item in incidents]))
        grav_mean = float(np.mean([item["grav"] for item in incidents]))
        score_i = 0.60 * sim_mean + 0.40 * grav_mean
    else:
        sim_mean = 0.0
        grav_mean = 0.0
        score_i = 0.0

    # Map per-column severities exactly as provided by Ref Signaux (sev_privacy, sev_discrimination, ...).
    severity_by_column: Dict[str, Dict[str, float]] = {}
    severity_avg_by_column: Dict[str, float] = {}
    for col in detected:
        col_keys = _severity_keys_from_detected([col]) or severity_keys
        sev_cols = {
            key: (
                float(np.mean([
                    _clip01(_safe_float(refs.aiid.loc[refs.aiid["incident_id"].astype(str) == inc["incident_id"], key].iloc[0]) / 5.0)
                    for inc in incidents
                    if key in refs.aiid.columns
                    and not refs.aiid.loc[refs.aiid["incident_id"].astype(str) == inc["incident_id"], key].empty
                ]))
                if incidents and key in refs.aiid.columns
                else _safe_float((col.get("severity_columns") or {}).get(key))
            )
            for key in col_keys
        }
        severity_by_column[col["raw_column"]] = {k: round(_clip01(v), 4) for k, v in sev_cols.items()}
        values = list(sev_cols.values())
        severity_avg_by_column[col["raw_column"]] = round(sum(values) / len(values), 4) if values else 0.0

    return {
        "I": round(_clip01(score_i), 4),
        "mock": False,
        "formula_ready": not refs.aiid.empty,
        "n_signaux": signal_count,
        "secteur": profile_sector,
        "domaines_actives": sorted(active_domain_codes),
        "sim_moyen": round(_clip01(sim_mean), 4),
        "grav_moyen": round(_clip01(grav_mean), 4),
        "severity_by_column": severity_by_column,
        "severity_avg_by_column": severity_avg_by_column,
        "mapping_actions": [
            {
                "colonne": col["raw_column"],
                "signal": col.get("signal"),
                "domaine_mit": col.get("mit_domain", ""),
                "source_reglementaire": col.get("legal_source", ""),
                "action": col.get("action_corrective", ""),
            }
            for col in detected
        ],
        "incidents": incidents,
    }


def build_xai(dataframe: pd.DataFrame, profile: dict[str, Any], score_i_result: dict[str, Any]) -> List[dict[str, Any]]:
    refs = get_risk_references()
    scan = refs.scanner.scan_dataframe(dataframe)
    finalite = _norm(_resolve_datacard_value(refs, profile, "Finalité du traitement"))
    facial_values = _datacard_column_values(refs, "Finalité du traitement")

    if _is_facial_recognition(finalite, facial_values):
        return [{
            "column": "",
            "signal": "finalite",
            "explanation": (
                "AVERTISSEMENT : finalite de reconnaissance faciale detectee. "
                "AI Act Art.5 — interdiction de principe en espaces publics. "
                "RGPD Art.9(1) — donnees biometriques. "
                "Verification base legale obligatoire avant tout traitement."
            ),
            "severity": 5.0,
            "legal_source": "AI Act / RGPD",
        }]

    severity_by_column = score_i_result.get("severity_by_column", {}) or {}
    severity_avg_by_column = score_i_result.get("severity_avg_by_column", {}) or {}
    explanations: List[dict[str, Any]] = []
    for col in scan["columns"]:
        if not col.get("signal"):
            continue
        template = col.get("xai_template_fr") or "La colonne {{col}} active le signal de risque."
        per_key = severity_by_column.get(col["raw_column"], {}) or {}
        severity_avg = _safe_float(severity_avg_by_column.get(col["raw_column"], 0.0))
        text = template.replace("{{col}}", col["raw_column"])
        for token in re.findall(r"{{(sev_[^}]+)}}", text):
            value = per_key.get(token)
            if value is None:
                value = severity_avg
            text = text.replace("{{" + token + "}}", str(round(_safe_float(value), 2)))
        explanations.append({
            "column": col["raw_column"],
            "signal": col.get("signal"),
            "explanation": text,
            "severity": round(severity_avg, 2),
            "legal_source": col.get("legal_source") or "RGPD",
        })
    return explanations


def _is_facial_recognition(finalite: str, allowed_values: set[str]) -> bool:
    candidates = allowed_values | {finalite}
    normalized_finalite = _norm(finalite)
    return any(
        ("reconnaissance" in _norm(value) and "facial" in _norm(value))
        for value in candidates
        if _norm(value) == normalized_finalite
    )


def classify_risk(score: float) -> str:
    if score < 25:
        return "Faible"
    if score < 50:
        return "Modéré"
    if score < 75:
        return "Élevé"
    return "Critique"

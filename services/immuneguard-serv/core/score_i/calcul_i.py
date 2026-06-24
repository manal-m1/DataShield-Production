from __future__ import annotations

from typing import Any

import pandas as pd


SIGNAUX_EMBARQUES = {
    "nom": ("S_pii", 2, "2. Vie privee & Securite"),
    "prenom": ("S_pii", 2, "2. Vie privee & Securite"),
    "email": ("S_pii", 2, "2. Vie privee & Securite"),
    "telephone": ("S_pii", 2, "2. Vie privee & Securite"),
    "cin": ("S_pii", 2, "2. Vie privee & Securite"),
    "cnss": ("S_pii", 2, "2. Vie privee & Securite"),
    "patient_id": ("S_pii", 2, "2. Vie privee & Securite"),
    "adresse": ("S_pii", 2, "2. Vie privee & Securite"),
    "code_postal": ("S_pii", 2, "2. Vie privee & Securite"),
    "ville": ("S_pii", 2, "2. Vie privee & Securite"),
    "ip_address": ("S_pii", 2, "2. Vie privee & Securite"),
    "device_id": ("S_pii", 2, "2. Vie privee & Securite"),
    "genre": ("S_prot", 1, "1. Discrimination et Toxicite"),
    "age": ("S_prot", 1, "1. Discrimination et Toxicite"),
    "situation_familiale": ("S_prot", 1, "1. Discrimination et Toxicite"),
    "pays_origine": ("S_prot", 1, "1. Discrimination et Toxicite"),
    "origine": ("S_prot", 1, "1. Discrimination et Toxicite"),
    "religion": ("S_prot", 1, "1. Discrimination et Toxicite"),
    "handicap": ("S_prot", 1, "1. Discrimination et Toxicite"),
    "niveau_etude": ("S_prot", 1, "1. Discrimination et Toxicite"),
    "diagnostic": ("S_sens", 7, "7. Surete, Defaillances et Limites des systemes IA"),
    "medicament": ("S_sens", 7, "7. Surete, Defaillances et Limites des systemes IA"),
    "antecedent": ("S_sens", 7, "7. Surete, Defaillances et Limites des systemes IA"),
    "groupe_sanguin": ("S_sens", 7, "7. Surete, Defaillances et Limites des systemes IA"),
    "allergie": ("S_sens", 7, "7. Surete, Defaillances et Limites des systemes IA"),
    "salaire": ("S_sens", 2, "2. Vie privee & Securite"),
    "prime": ("S_sens", 2, "2. Vie privee & Securite"),
    "poste": ("S_dec", 1, "1. Discrimination et Toxicite"),
    "departement": ("S_dec", 1, "1. Discrimination et Toxicite"),
    "anciennete": ("S_dec", 1, "1. Discrimination et Toxicite"),
    "score_rh": ("S_dec", 1, "1. Discrimination et Toxicite"),
    "decision": ("S_dec", 1, "1. Discrimination et Toxicite"),
    "prediction": ("S_dec", 7, "7. Surete, Defaillances et Limites des systemes IA"),
}

ALIASES = {
    "full_name": "nom",
    "name": "nom",
    "first_name": "prenom",
    "mail": "email",
    "courriel": "email",
    "phone": "telephone",
    "mobile": "telephone",
    "id_patient": "patient_id",
    "sexe": "genre",
    "sex": "genre",
    "dob": "age",
    "pathologie": "diagnostic",
    "maladie": "diagnostic",
    "traitement": "medicament",
    "salary": "salaire",
    "revenu": "salaire",
    "medical_history": "antecedent",
    "job_title": "poste",
    "role": "poste",
    "score": "score_rh",
    "evaluation": "score_rh",
    "resultat": "decision",
    "outcome": "decision",
    "city": "ville",
    "address": "adresse",
    "hospital": "hopital",
    "ethnicity": "origine",
    "disability": "handicap",
    "education": "niveau_etude",
}

REFERENTIEL_EMBARQUE = [
    {"id": 37, "titre": "Amazon Hiring Algorithm", "secteur": "Administrative and Support Activities", "domaine_mit": 1, "gravite": 0.75},
    {"id": 489, "titre": "Workday Hiring Bias", "secteur": "Administrative and Support Activities", "domaine_mit": 1, "gravite": 1.00},
    {"id": 124, "titre": "Optum Health Algorithm Bias", "secteur": "Human Health and Social Work Activities", "domaine_mit": 1, "gravite": 0.75},
    {"id": 123, "titre": "Epic Sepsis Model Failure", "secteur": "Human Health and Social Work Activities", "domaine_mit": 7, "gravite": 1.00},
    {"id": 23, "titre": "Las Vegas Self-Driving Bus Accident", "secteur": "Transportation and Storage", "domaine_mit": 7, "gravite": 1.00},
    {"id": 4, "titre": "Uber AV Killed Pedestrian", "secteur": "Transportation and Storage", "domaine_mit": 7, "gravite": 1.00},
    {"id": 18, "titre": "Gender Biases of Google Image Search", "secteur": "Information and Communication", "domaine_mit": 1, "gravite": 0.25},
    {"id": 55, "titre": "Clearview AI Face Recognition", "secteur": "Public Administration and Defence", "domaine_mit": 2, "gravite": 1.00},
    {"id": 280, "titre": "Apple Card Credit Limit Gender Gap", "secteur": "Financial and Insurance Activities", "domaine_mit": 1, "gravite": 0.75},
]

SECTEUR_MAPPING = {
    "rh": "Administrative and Support Activities",
    "ressources humaines": "Administrative and Support Activities",
    "recrutement": "Administrative and Support Activities",
    "sante": "Human Health and Social Work Activities",
    "sante humaine et action sociale": "Human Health and Social Work Activities",
    "medical": "Human Health and Social Work Activities",
    "health": "Human Health and Social Work Activities",
    "transport": "Transportation and Storage",
    "finance": "Financial and Insurance Activities",
    "tech": "Information and Communication",
    "information": "Information and Communication",
    "administration publique": "Public Administration and Defence",
    "public administration": "Public Administration and Defence",
    "justice": "Public Administration and Defence",
}


def normaliser(texte: str) -> str:
    return str(texte).strip().lower()


def resoudre_colonne(col: str) -> str | None:
    col_norm = normaliser(col)
    if col_norm in SIGNAUX_EMBARQUES:
        return col_norm
    if col_norm in ALIASES:
        return ALIASES[col_norm]
    return None


def detecter_domaines(colonnes: list[str]) -> dict[int, dict[str, Any]]:
    domaines: dict[int, dict[str, Any]] = {}
    for col in colonnes:
        canon = resoudre_colonne(col)
        if canon and canon in SIGNAUX_EMBARQUES:
            signal, mit_num, mit_label = SIGNAUX_EMBARQUES[canon]
            if mit_num not in domaines:
                domaines[mit_num] = {"label": mit_label, "colonnes": [], "signaux": []}
            domaines[mit_num]["colonnes"].append(col)
            domaines[mit_num]["signaux"].append(signal)
    return domaines


def normaliser_secteur(secteur_brut: str) -> str:
    norm = normaliser(secteur_brut)
    return SECTEUR_MAPPING.get(norm, secteur_brut)


def calculer_sim(secteur_dataset: str, domaines_dataset: set[int], incident: dict[str, Any]) -> float:
    s_secteur = 1.0 if incident["secteur"] == secteur_dataset else 0.0
    s_domaine = 1.0 if incident["domaine_mit"] in domaines_dataset else 0.0
    return (s_secteur + s_domaine) / 2.0


def calculer_score_i(secteur_dataset: str, domaines_dataset: set[int], referentiel: list[dict[str, Any]], k: int = 3) -> dict[str, Any]:
    resultats = []
    for inc in referentiel:
        sim = calculer_sim(secteur_dataset, domaines_dataset, inc)
        resultats.append({**inc, "sim": sim})

    resultats.sort(key=lambda x: (x["sim"], x["gravite"]), reverse=True)
    top_k = resultats[:k]
    sim_moyen = sum(r["sim"] for r in top_k) / k
    grav_moyen = sum(r["gravite"] for r in top_k) / k
    score_i = 0.60 * sim_moyen + 0.40 * grav_moyen

    return {
        "score_I": round(score_i, 4),
        "sim_moyen": round(sim_moyen, 4),
        "grav_moyen": round(grav_moyen, 4),
        "top_k": top_k,
    }


def _safe_uniqueness_ratio(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns or len(df) == 0:
        return 0.0
    non_null = df[col].dropna()
    if non_null.empty:
        return 0.0
    return min(1.0, float(non_null.nunique()) / float(len(non_null)))


def _compute_dataset_profile_factor(dataset_df: pd.DataFrame, profile: dict[str, Any] | None) -> float:
    if profile is None:
        return 0.0

    attacks = profile.get("attacks", {}) if isinstance(profile, dict) else {}
    checks = profile.get("checks", {}) if isinstance(profile, dict) else {}

    qi_cols = attacks.get("quasi_identifiers", []) or []
    pii_cols = checks.get("pii_columns", []) or []
    sa_col = attacks.get("sensitive_attribute")

    tracked_cols = [c for c in dict.fromkeys([*qi_cols, *pii_cols, sa_col]) if isinstance(c, str) and c]
    tracked_in_df = [c for c in tracked_cols if c in dataset_df.columns]
    if not tracked_in_df:
        return 0.0

    uniqueness_scores = [_safe_uniqueness_ratio(dataset_df, col) for col in tracked_in_df]
    uniqueness_mean = sum(uniqueness_scores) / len(uniqueness_scores)
    sensitivity_density = min(1.0, len(tracked_in_df) / max(1, len(dataset_df.columns)))

    return round(0.65 * uniqueness_mean + 0.35 * sensitivity_density, 4)


def pipeline_from_dataframe(dataset_df: pd.DataFrame, secteur: str, profile: dict[str, Any] | None = None, k: int = 3) -> dict[str, Any]:
    colonnes = dataset_df.columns.tolist()
    domaines_dict = detecter_domaines(colonnes)
    domaines_set = set(domaines_dict.keys())
    secteur_dataset = normaliser_secteur(str(secteur or "rh"))
    resultat = calculer_score_i(secteur_dataset, domaines_set, REFERENTIEL_EMBARQUE, k)
    profile_factor = _compute_dataset_profile_factor(dataset_df, profile)
    score_i_adjusted = round((0.80 * resultat["score_I"]) + (0.20 * profile_factor), 4)
    return {
        "score_I": score_i_adjusted,
        "score_I_base": resultat["score_I"],
        "profile_factor": profile_factor,
        "sim_moyen": resultat["sim_moyen"],
        "grav_moyen": resultat["grav_moyen"],
        "secteur_normalise": secteur_dataset,
        "domaines_actives": domaines_dict,
        "top_k_incidents": resultat["top_k"],
        "k": k,
    }

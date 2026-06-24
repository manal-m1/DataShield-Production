"""
XAI Generator — Explainable AI for ImmuneGuard Score A
Generates human-readable, rule-based explanations for each attack
and vulnerability check result.
"""
from __future__ import annotations

from typing import Any, Dict, List


# ─── risk level helpers ───────────────────────────────────────────
def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "critique"
    if score >= 0.50:
        return "élevé"
    if score >= 0.25:
        return "modéré"
    return "faible"


def _risk_emoji(score: float) -> str:
    if score >= 0.75:
        return "🔴"
    if score >= 0.50:
        return "🟠"
    if score >= 0.25:
        return "🟡"
    return "🟢"


def _risk_color(score: float) -> str:
    if score >= 0.75:
        return "#ef4444"
    if score >= 0.50:
        return "#f97316"
    if score >= 0.25:
        return "#eab308"
    return "#22c55e"


# ─── attack explanations ─────────────────────────────────────────
def explain_linkage(rate: float, qi_list: List[str]) -> Dict[str, Any]:
    qi_str = ", ".join(qi_list)
    level = _risk_level(rate)
    
    if rate >= 0.50:
        text = (
            f"Le taux de ré-identification par croisement est de {rate:.1%}, "
            f"ce qui est {level}. En combinant les quasi-identifiants [{qi_str}] "
            f"avec une source publique simulée, un attaquant pourrait potentiellement "
            f"retrouver l'identité de {rate:.0%} des individus du dataset."
        )
        recommendation = (
            "Appliquer une généralisation (k-anonymat) sur les quasi-identifiants "
            "ou réduire la granularité des colonnes numériques (ex: tranches d'âge)."
        )
    elif rate >= 0.25:
        text = (
            f"Le taux de ré-identification est de {rate:.1%} ({level}). "
            f"Certains profils basés sur [{qi_str}] restent identifiables par croisement."
        )
        recommendation = (
            "Surveiller les combinaisons uniques de quasi-identifiants "
            "et envisager une suppression des colonnes les plus discriminantes."
        )
    else:
        text = (
            f"Le risque de linkage est {level} ({rate:.1%}). "
            f"Les quasi-identifiants [{qi_str}] ne permettent pas facilement "
            f"de croiser les données avec une source externe."
        )
        recommendation = "Aucune action immédiate requise."
    
    return {
        "attack": "Linkage Attack",
        "attack_id": "linkage",
        "score": round(rate, 3),
        "level": level,
        "color": _risk_color(rate),
        "emoji": _risk_emoji(rate),
        "explanation": text,
        "recommendation": recommendation,
    }


def explain_singling_out(rate: float, qi_list: List[str]) -> Dict[str, Any]:
    qi_str = ", ".join(qi_list)
    level = _risk_level(rate)
    
    if rate >= 0.50:
        text = (
            f"{rate:.0%} des individus ont une combinaison unique de "
            f"quasi-identifiants [{qi_str}], ce qui les rend directement "
            f"isolables (Singling Out). Ce niveau est {level}."
        )
        recommendation = (
            "Augmenter la taille des groupes d'équivalence (k-anonymat ≥ 5) "
            "ou supprimer/généraliser des quasi-identifiants."
        )
    elif rate >= 0.25:
        text = (
            f"Le taux d'unicité est de {rate:.1%} ({level}). "
            f"Un nombre significatif d'individus peuvent être isolés via [{qi_str}]."
        )
        recommendation = (
            "Considérer l'application d'un k-anonymat avec k ≥ 3."
        )
    else:
        text = (
            f"Le taux d'unicité est {level} ({rate:.1%}). "
            f"La plupart des individus partagent leur profil [{qi_str}] avec d'autres."
        )
        recommendation = "Aucune action immédiate requise."
    
    return {
        "attack": "Singling Out Attack",
        "attack_id": "singling_out",
        "score": round(rate, 3),
        "level": level,
        "color": _risk_color(rate),
        "emoji": _risk_emoji(rate),
        "explanation": text,
        "recommendation": recommendation,
    }


def explain_inference(rate: float, qi_list: List[str], sensitive_attr: str) -> Dict[str, Any]:
    qi_str = ", ".join(qi_list)
    level = _risk_level(rate)
    
    if rate >= 0.50:
        text = (
            f"Pour {rate:.0%} des individus, l'attribut sensible «{sensitive_attr}» "
            f"est entièrement devinable à partir de [{qi_str}]. "
            f"Cela signifie qu'un attaquant connaissant ces quasi-identifiants "
            f"peut déduire la valeur sensible avec certitude. Risque {level}."
        )
        recommendation = (
            f"Appliquer la l-diversité sur l'attribut «{sensitive_attr}» "
            f"(au moins 2 valeurs distinctes par groupe de QI)."
        )
    elif rate >= 0.25:
        text = (
            f"Le risque d'inférence est {level} ({rate:.1%}). "
            f"Certains groupes de [{qi_str}] ne contiennent qu'une seule valeur "
            f"pour «{sensitive_attr}»."
        )
        recommendation = (
            f"Vérifier manuellement la diversité de «{sensitive_attr}» "
            f"dans les groupes à faible effectif."
        )
    else:
        text = (
            f"Le risque d'inférence est {level} ({rate:.1%}). "
            f"La plupart des groupes de [{qi_str}] présentent une bonne diversité "
            f"de valeurs pour «{sensitive_attr}»."
        )
        recommendation = "Aucune action immédiate requise."
    
    return {
        "attack": "Attribute Inference Attack",
        "attack_id": "inference",
        "score": round(rate, 3),
        "level": level,
        "color": _risk_color(rate),
        "emoji": _risk_emoji(rate),
        "explanation": text,
        "recommendation": recommendation,
    }


# ─── vulnerability check explanations ────────────────────────────
_CHECK_LABELS = {
    "V1": "PII en clair",
    "V2": "Déséquilibre catégoriel",
    "V3": "Corrélation sensible",
    "V4": "Données médicales sensibles",
    "V5": "Identifiants séquentiels",
}

_CHECK_DESCRIPTIONS = {
    "V1": "Présence de colonnes directement identifiantes (PII) non anonymisées.",
    "V2": "Distribution statistique déséquilibrée dans les colonnes catégorielles pouvant révéler des biais.",
    "V3": "Corrélation significative entre colonnes pouvant permettre une inférence indirecte.",
    "V4": "Présence de données médicales/santé exposées en clair dans le dataset.",
    "V5": "Identifiants structurés ou séquentiels facilement prédictibles.",
}


def explain_check(check: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an XAI explanation for a single vulnerability check result."""
    check_id = check["check_id"]
    detected = check["detected"]
    reason = check["reason"]
    
    label = _CHECK_LABELS.get(check_id, check_id)
    description = _CHECK_DESCRIPTIONS.get(check_id, "")
    
    if not check["applicable"]:
        return {
            "check_id": check_id,
            "label": label,
            "description": description,
            "status": "non_applicable",
            "color": "#64748b",
            "emoji": "⚪",
            "detected": False,
            "explanation": reason,
        }
    
    return {
        "check_id": check_id,
        "label": label,
        "description": description,
        "status": "detected" if detected else "passed",
        "color": "#ef4444" if detected else "#22c55e",
        "emoji": "🔴" if detected else "🟢",
        "detected": bool(detected),
        "explanation": reason,
    }


# ─── global Score A explanation ───────────────────────────────────
def explain_score_a(score_a: float) -> Dict[str, Any]:
    """Generate an overall explanation for the Score A."""
    level = _risk_level(score_a)
    
    if score_a >= 0.75:
        summary = (
            f"Le Score A global est de {score_a:.3f} — niveau {level}. "
            f"Ce dataset présente des risques majeurs de ré-identification "
            f"et de vulnérabilités structurelles critiques. "
            f"Des mesures d'anonymisation immédiates sont fortement recommandées."
        )
        verdict = "CRITIQUE — Action immédiate requise"
    elif score_a >= 0.50:
        summary = (
            f"Le Score A global est de {score_a:.3f} — niveau {level}. "
            f"Ce dataset présente un niveau de risque significatif. "
            f"Plusieurs attaques simulées ont démontré des taux de succès préoccupants. "
            f"Des mesures correctives devraient être envisagées."
        )
        verdict = "ATTENTION — Mesures correctives nécessaires"
    elif score_a >= 0.25:
        summary = (
            f"Le Score A global est de {score_a:.3f} — niveau {level}. "
            f"Le dataset présente quelques vulnérabilités mineures "
            f"mais le risque global reste gérable avec une surveillance continue."
        )
        verdict = "MODÉRÉ — Surveillance recommandée"
    else:
        summary = (
            f"Le Score A global est de {score_a:.3f} — niveau {level}. "
            f"Le dataset est bien protégé. Les attaques simulées "
            f"n'ont pas révélé de risques significatifs."
        )
        verdict = "OK — Risque faible"
    
    return {
        "score": round(score_a, 3),
        "level": level,
        "color": _risk_color(score_a),
        "emoji": _risk_emoji(score_a),
        "summary": summary,
        "verdict": verdict,
    }


# ─── full XAI report ─────────────────────────────────────────────
def generate_xai_report(
    succ_result: Dict[str, Any],
    vuln_result: Dict[str, Any],
    score_a: float,
    qi_list: List[str],
    sensitive_attr: str,
) -> Dict[str, Any]:
    """Generate a complete XAI report for Score A."""
    
    attack_explanations = [
        explain_linkage(succ_result["taux_linkage"], qi_list),
        explain_singling_out(succ_result["taux_singling"], qi_list),
        explain_inference(succ_result["taux_inference"], qi_list, sensitive_attr),
    ]
    
    check_explanations = [
        explain_check(check) for check in vuln_result.get("checks", [])
    ]
    
    score_explanation = explain_score_a(score_a)
    
    return {
        "score_a": score_explanation,
        "attacks": attack_explanations,
        "checks": check_explanations,
        "succ_score": succ_result["Succ"],
        "vuln_score": vuln_result["Vuln"],
    }

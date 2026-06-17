from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, entropy

from core.profiles.loader import load_profile

IMBALANCE_THRESHOLD = 0.5
DEPENDENCY_THRESHOLD = 0.40
STRUCTURED_ID_RISK_THRESHOLD = 0.8


def _calculate_dependency(df: pd.DataFrame, col1: str, col2: str) -> float:
    if df[col1].dtype in ["int64", "float64"] and df[col2].dtype in ["int64", "float64"]:
        corr = df[col1].corr(df[col2])
        return abs(corr) if not pd.isna(corr) else 0.0

    if df[col1].dtype == "object" and df[col2].dtype in ["int64", "float64"]:
        try:
            dummies = pd.get_dummies(df[col1], prefix=col1, drop_first=True)
            correlations = dummies.corrwith(df[col2])
            max_corr = correlations.abs().max()
            return max_corr if not pd.isna(max_corr) else 0.0
        except Exception:
            return 0.0

    if df[col1].dtype in ["int64", "float64"] and df[col2].dtype == "object":
        return _calculate_dependency(df, col2, col1)

    if df[col1].dtype == "object" and df[col2].dtype == "object":
        try:
            contingency_table = pd.crosstab(df[col1], df[col2])
            chi2, _, _, _ = chi2_contingency(contingency_table)
            n = contingency_table.sum().sum()
            min_dim = min(contingency_table.shape) - 1
            return np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 else 0.0
        except Exception:
            return 0.0

    return 0.0


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    applicable: bool
    detected: int
    value: float | None
    threshold: str | None
    reason: str


def check_v1_pii_clear(df: pd.DataFrame, profile: dict) -> CheckResult:
    checks = profile["checks"]
    pii_column_names = checks.get("pii_columns", [])
    detected_pii_columns = [col for col in df.columns if col in pii_column_names]

    if not detected_pii_columns:
        return CheckResult("V1", True, 0, None, ">= 1 direct PII column", "Aucune colonne PII directe detectee.")

    return CheckResult(
        "V1",
        True,
        1,
        float(len(detected_pii_columns)),
        ">= 1 direct PII column",
        f"Colonnes PII detectees: {detected_pii_columns}",
    )


def check_v2_categorical_imbalance(df: pd.DataFrame, profile: dict) -> CheckResult:
    checks = profile["checks"]
    imbalance_column_names = checks.get("imbalance_columns", [])

    if not imbalance_column_names:
        return CheckResult(
            "V2",
            False,
            0,
            None,
            f"imbalance score > {IMBALANCE_THRESHOLD}",
            "Aucune colonne specifiee pour le check de desequilibre.",
        )

    imbalance_detected = False
    imbalance_scores = []
    imbalance_reasons = []

    for column_name in imbalance_column_names:
        if column_name not in df.columns:
            imbalance_reasons.append(f"Colonne '{column_name}' absente.")
            continue

        value_ratios = df[column_name].value_counts(normalize=True, dropna=False)
        if len(value_ratios) == 0:
            imbalance_reasons.append(f"Colonne '{column_name}' vide.")
            continue

        majority_ratio = value_ratios.max()
        entropy_value = entropy(value_ratios)

        if len(value_ratios) <= 1:
            normalized_entropy = 0.0
        else:
            max_entropy = np.log(len(value_ratios))
            normalized_entropy = entropy_value / max_entropy if max_entropy > 0 else 0.0

        gini_coefficient = 1 - np.sum(value_ratios**2)
        column_imbalance_score = 0.5 * majority_ratio + 0.3 * (1 - normalized_entropy) + 0.2 * (1 - gini_coefficient)
        imbalance_scores.append(column_imbalance_score)

        if column_imbalance_score > IMBALANCE_THRESHOLD:
            imbalance_detected = True
            imbalance_reasons.append(f"'{column_name}' desequilibree (score={column_imbalance_score:.3f})")
        else:
            imbalance_reasons.append(f"'{column_name}' equilibree (score={column_imbalance_score:.3f})")

    final_imbalance_value = float(np.mean(imbalance_scores)) if imbalance_scores else None
    return CheckResult(
        "V2",
        True,
        int(imbalance_detected),
        final_imbalance_value,
        f"imbalance score > {IMBALANCE_THRESHOLD}",
        " ; ".join(imbalance_reasons),
    )


def check_v3_sensitive_target_correlation(df: pd.DataFrame, profile: dict) -> CheckResult:
    checks = profile["checks"]
    correlation_column_names = checks.get("correlation_columns", [])

    if len(correlation_column_names) < 2:
        return CheckResult(
            "V3",
            False,
            0,
            None,
            f"dependency > {DEPENDENCY_THRESHOLD}",
            "Check non applicable: moins de 2 colonnes specifiees pour la correlation.",
        )

    dependency_values = []
    dependency_reasons = []

    for i in range(len(correlation_column_names)):
        for j in range(i + 1, len(correlation_column_names)):
            first_column = correlation_column_names[i]
            second_column = correlation_column_names[j]
            if first_column not in df.columns or second_column not in df.columns:
                dependency_reasons.append(f"Paire ignoree: '{first_column}' et/ou '{second_column}' absentes.")
                continue

            pair_dependency = _calculate_dependency(df, first_column, second_column)
            dependency_values.append(pair_dependency)
            dependency_reasons.append(f"Dependance entre '{first_column}' et '{second_column}' = {pair_dependency:.3f}")

    if not dependency_values:
        return CheckResult(
            "V3",
            False,
            0,
            None,
            f"dependency > {DEPENDENCY_THRESHOLD}",
            "Aucune paire valide trouvee pour calculer la dependance.",
        )

    max_dependency_value = max(dependency_values)
    mean_dependency_value = np.mean(dependency_values)
    final_dependency_score = 0.5 * max_dependency_value + 0.5 * mean_dependency_value

    return CheckResult(
        "V3",
        True,
        int(final_dependency_score > DEPENDENCY_THRESHOLD),
        round(final_dependency_score, 3),
        f"> {DEPENDENCY_THRESHOLD}",
        f"Score de dependance = {final_dependency_score:.3f} (0.5*max={max_dependency_value:.3f} + 0.5*mean={mean_dependency_value:.3f}) ({'; '.join(dependency_reasons)})",
    )


def check_v4_sensitive_data_clear(df: pd.DataFrame, profile: dict) -> CheckResult:
    checks = profile["checks"]
    sensitive_health_column_names = checks.get("sensitive_health_columns", [])
    detected_sensitive_columns = [col for col in df.columns if col in sensitive_health_column_names]

    if not sensitive_health_column_names:
        return CheckResult(
            "V4",
            True,
            0,
            None,
            "presence of sensitive health columns",
            "Aucune liste de colonnes sensibles definie dans le profil d'analyse.",
        )

    if not detected_sensitive_columns:
        return CheckResult(
            "V4",
            True,
            0,
            None,
            ">= 1 sensitive health column",
            "Aucune colonne sensible de sante detectee dans le dataset.",
        )

    return CheckResult(
        "V4",
        True,
        1,
        float(len(detected_sensitive_columns)),
        ">= 1 sensitive health column",
        f"Colonnes sensibles detectees: {detected_sensitive_columns}",
    )


def check_v5_sequential_id(df: pd.DataFrame, profile: dict) -> CheckResult:
    checks = profile["checks"]
    id_column = checks.get("id_column")

    if not id_column or id_column not in df.columns:
        return CheckResult(
            "V5",
            False,
            0,
            None,
            f"structured or sequential ID risk > {STRUCTURED_ID_RISK_THRESHOLD}",
            f"Check non applicable: colonne '{id_column}' absente.",
        )

    identifiers = df[id_column].astype(str).dropna().tolist()
    if not identifiers:
        return CheckResult(
            "V5",
            True,
            0,
            None,
            f"structured or sequential ID risk > {STRUCTURED_ID_RISK_THRESHOLD}",
            f"Colonne '{id_column}' vide.",
        )

    patterns = [
        re.compile(r"^[A-Za-z]+[_-]?\d{1,6}$"),
        re.compile(r"^\d{6,}$"),
        re.compile(r"^[0-9a-fA-F]{8,}$"),
    ]

    total_ids = len(identifiers)
    unique_ids = len(set(identifiers))
    uniqueness_ratio = unique_ids / total_ids
    collision_rate = 1 - uniqueness_ratio

    id_frequencies = pd.Series(identifiers).value_counts(normalize=True)
    entropy_value = entropy(id_frequencies)
    max_entropy = np.log(unique_ids) if unique_ids > 1 else 0
    normalized_entropy = entropy_value / max_entropy if max_entropy > 0 else 0.0
    entropy_risk = 1 - normalized_entropy

    structured_id_matches = sum(any(compiled_pattern.match(identifier) for compiled_pattern in patterns) for identifier in identifiers)
    pattern_risk = structured_id_matches / total_ids
    structured_id_risk_score = 0.4 * pattern_risk + 0.3 * collision_rate + 0.3 * entropy_risk

    return CheckResult(
        "V5",
        True,
        int(structured_id_risk_score > STRUCTURED_ID_RISK_THRESHOLD),
        round(structured_id_risk_score, 3),
        f"ID risk score > {STRUCTURED_ID_RISK_THRESHOLD}",
        f"Score de risque IDs = {structured_id_risk_score:.3f} (patterns={pattern_risk:.1%}, collisions={collision_rate:.1%}, entropy_risk={entropy_risk:.1%})",
    )


def run_all_checks(df: pd.DataFrame, dataset_name: str) -> Dict[str, Any]:
    dataset_profile = load_profile(dataset_name)
    check_results = [
        check_v1_pii_clear(df, dataset_profile),
        check_v2_categorical_imbalance(df, dataset_profile),
        check_v3_sensitive_target_correlation(df, dataset_profile),
        check_v4_sensitive_data_clear(df, dataset_profile),
        check_v5_sequential_id(df, dataset_profile),
    ]

    total_detected_checks = sum(result.detected for result in check_results)
    vulnerability_score = total_detected_checks / 5.0

    return {
        "dataset": dataset_name.upper(),
        "detected_checks": total_detected_checks,
        "Vuln": round(vulnerability_score, 3),
        "checks": [asdict(result) for result in check_results],
    }


def run_all_checks_with_profile(df: pd.DataFrame, profile: dict) -> Dict[str, Any]:
    check_results = [
        check_v1_pii_clear(df, profile),
        check_v2_categorical_imbalance(df, profile),
        check_v3_sensitive_target_correlation(df, profile),
        check_v4_sensitive_data_clear(df, profile),
        check_v5_sequential_id(df, profile),
    ]

    total_detected_checks = sum(result.detected for result in check_results)
    vulnerability_score = total_detected_checks / 5.0

    return {
        "dataset": profile.get("dataset_name", "UNKNOWN"),
        "detected_checks": total_detected_checks,
        "Vuln": round(vulnerability_score, 3),
        "checks": [asdict(result) for result in check_results],
    }

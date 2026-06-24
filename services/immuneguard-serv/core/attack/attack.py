from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from core.profiles.loader import load_profile


@dataclass(frozen=True)
class AttackConfig:
    dataset_name: str
    quasi_identifiers: List[str]
    sensitive_attribute: str
    public_sample_frac: float = 0.15
    random_state: int = 42
    noise_enabled: bool = True
    noise_age_range: int = 2
    drop_qi_column: bool = True


def validate_attack_inputs(df: pd.DataFrame, config: AttackConfig) -> None:
    required_columns = set(config.quasi_identifiers + [config.sensitive_attribute])
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"{config.dataset_name}: colonnes manquantes pour les attaques: {sorted(missing)}"
        )
    if df.empty:
        raise ValueError(f"{config.dataset_name}: dataset vide.")


def _add_noise_to_public_source(
    public_df: pd.DataFrame,
    quasi_identifiers: List[str],
    noise_age_range: int = 2,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Simule des données imparfaites côté attaquant :
    - Colonnes numériques : perturbation uniforme ± noise_age_range
    - Colonnes catégorielles : les catégories rares (< 5%) sont regroupées sous 'Autre'
    """
    rng = np.random.default_rng(random_state)
    df = public_df.copy()

    for col in quasi_identifiers:
        if col not in df.columns:
            continue

        if df[col].dtype in ["int64", "float64"]:
            noise = rng.integers(
                -noise_age_range, noise_age_range + 1, size=len(df)
            )
            df[col] = df[col] + noise
        elif df[col].dtype == "object":
            freq = df[col].value_counts(normalize=True)
            rare_categories = freq[freq < 0.05].index.tolist()
            if rare_categories:
                df[col] = df[col].replace(rare_categories, "Autre")

    return df


def _drop_least_discriminant_qi(
    public_df: pd.DataFrame,
    quasi_identifiers: List[str],
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Supprime la colonne QI ayant la plus faible cardinalité
    (la moins utile pour le matching exact).
    Ne supprime rien s'il reste 1 seul QI.
    """
    if len(quasi_identifiers) < 2:
        return public_df, quasi_identifiers

    available_qis = [q for q in quasi_identifiers if q in public_df.columns]
    if len(available_qis) < 2:
        return public_df, available_qis

    cardinalities = {col: public_df[col].nunique() for col in available_qis}
    col_to_drop = min(cardinalities, key=cardinalities.get)

    reduced_qis = [q for q in available_qis if q != col_to_drop]
    reduced_df = public_df.drop(columns=[col_to_drop])

    return reduced_df, reduced_qis


def build_public_simulated_source(
    df: pd.DataFrame,
    quasi_identifiers: List[str],
    sample_frac: float = 0.15,
    random_state: int = 42,
    noise_enabled: bool = True,
    noise_age_range: int = 2,
    drop_qi_column: bool = True,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Simule une source publique réaliste :
    1. Échantillonnage réduit (15% par défaut)
    2. Ajout de bruit sur les quasi-identifiants
    3. Suppression de la colonne QI la moins discriminante
    Retourne le DataFrame et la liste effective des QI utilisés.
    """
    public_df = df[quasi_identifiers].sample(
        frac=sample_frac,
        random_state=random_state,
        replace=False,
    ).copy()
    public_df = public_df.reset_index(drop=True)

    effective_qis = list(quasi_identifiers)

    if noise_enabled:
        public_df = _add_noise_to_public_source(
            public_df, effective_qis, noise_age_range, random_state
        )

    if drop_qi_column:
        public_df, effective_qis = _drop_least_discriminant_qi(
            public_df, effective_qis
        )

    return public_df, effective_qis


def linkage_attack(df: pd.DataFrame, config: AttackConfig) -> float:
    """
    Taux de lignes ré-identifiables par croisement avec une base publique simulée.
    """
    validate_attack_inputs(df, config)

    qids = config.quasi_identifiers
    public_df, effective_qis = build_public_simulated_source(
        df=df,
        quasi_identifiers=qids,
        sample_frac=config.public_sample_frac,
        random_state=config.random_state,
        noise_enabled=config.noise_enabled,
        noise_age_range=config.noise_age_range,
        drop_qi_column=config.drop_qi_column,
    )

    public_group_sizes = (
        public_df.groupby(effective_qis, dropna=False)
        .size()
        .reset_index(name="public_group_size")
    )

    unique_public_profiles = public_group_sizes.loc[
        public_group_sizes["public_group_size"] == 1, effective_qis
    ].copy()
    unique_public_profiles["is_reidentifiable"] = 1

    merged = df.merge(unique_public_profiles, on=effective_qis, how="left")
    merged["is_reidentifiable"] = merged["is_reidentifiable"].fillna(0)

    rate = merged["is_reidentifiable"].mean()
    return float(rate)


def singling_out_attack(df: pd.DataFrame, config: AttackConfig) -> float:
    """
    Taux de lignes dont la combinaison de quasi-identifiants est unique dans le dataset.
    """
    validate_attack_inputs(df, config)

    qids = config.quasi_identifiers
    grouped = df.groupby(qids, dropna=False).size().reset_index(name="group_size")
    merged = df.merge(grouped, on=qids, how="left")

    isolated_mask = merged["group_size"] == 1
    rate = isolated_mask.mean()
    return float(rate)


def attribute_inference_attack(df: pd.DataFrame, config: AttackConfig) -> float:
    """
    Taux de lignes pour lesquelles l'attribut sensible est devinable à partir des QI.
    """
    validate_attack_inputs(df, config)

    qids = config.quasi_identifiers
    sensitive = config.sensitive_attribute

    group_nunique = (
        df.groupby(qids, dropna=False)[sensitive]
        .nunique(dropna=False)
        .reset_index(name="sensitive_nunique")
    )

    merged = df.merge(group_nunique, on=qids, how="left")
    inferable_mask = merged["sensitive_nunique"] == 1

    rate = inferable_mask.mean()
    return float(rate)


def compute_succ(df: pd.DataFrame, config: AttackConfig) -> Dict[str, float]:
    linkage = linkage_attack(df, config)
    singling = singling_out_attack(df, config)
    inference = attribute_inference_attack(df, config)

    succ = (linkage + singling + inference) / 3.0

    return {
        "dataset": config.dataset_name,
        "taux_linkage": round(linkage, 3),
        "taux_singling": round(singling, 3),
        "taux_inference": round(inference, 3),
        "Succ": round(succ, 3),
    }


def get_attack_config(dataset_name: str) -> AttackConfig:
    profile = load_profile(dataset_name)
    attacks = profile["attacks"]
    
    return AttackConfig(
        dataset_name=profile["dataset_name"],
        quasi_identifiers=attacks["quasi_identifiers"],
        sensitive_attribute=attacks["sensitive_attribute"],
        public_sample_frac=attacks.get("public_sample_frac", 0.15),
        random_state=42,
    )


def get_attack_config_from_profile(profile: dict) -> AttackConfig:
    """Build an AttackConfig from an analysis profile dict (no file load required)."""
    attacks = profile["attacks"]
    return AttackConfig(
        dataset_name=profile["dataset_name"],
        quasi_identifiers=attacks["quasi_identifiers"],
        sensitive_attribute=attacks["sensitive_attribute"],
        public_sample_frac=attacks.get("public_sample_frac", 0.15),
        random_state=42,
    )

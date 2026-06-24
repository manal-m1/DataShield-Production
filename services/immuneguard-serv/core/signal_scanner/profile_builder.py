"""
Profile Builder — Fully Automatic Analysis Profile Generation
==============================================================
Every field is derived from the scan results (signals, ref_entries,
column names, MIT domains, etc.).  No hardcoded column names.
"""

import re
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from backend.models.schemas import (
    ColumnMapping,
    SignalScanColumnResult,
    SignalScanResponse,
)


# ───────────────────────────────────────────────────────────────────
# Constants
# ───────────────────────────────────────────────────────────────────

SENSITIVE_PRIORITY: Dict[str, int] = {
    "S_sens": 0,
    "S_dec": 1,
    "S_prot": 2,
}

# Sector keywords found in mit_domain / ref_entry / column names
_SECTOR_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(medical|health|hospital|hopital|patient|diagnost|medicament|pharma|clinic|sante|maladie|symptom)", re.I), "sante"),
    (re.compile(r"(financ|bank|banque|account|credit|debit|transaction|iban|swift|loan|pret)", re.I), "finance"),
    (re.compile(r"(employ|salaire|salary|rh|human.?resource|paie|contrat|poste|departement)", re.I), "rh"),
    (re.compile(r"(student|etudiant|school|ecole|universi|note|grade|diplom|education)", re.I), "education"),
    (re.compile(r"(customer|client|order|commande|product|produit|vente|sale|ecommerce)", re.I), "commerce"),
    (re.compile(r"(telecom|mobile|appel|sms|forfait|abonne)", re.I), "telecom"),
    (re.compile(r"(assurance|insurance|police|sinistre|claim|beneficiaire)", re.I), "assurance"),
]


# ───────────────────────────────────────────────────────────────────
# 1. Auto-detect SECTOR from scan metadata
# ───────────────────────────────────────────────────────────────────

def _detect_secteur(scan_result: SignalScanResponse) -> str:
    """Infer the governance sector from column names, ref_entries and
    MIT domains.  Falls back to 'general' if nothing matches."""

    votes: Dict[str, int] = {}

    for col in scan_result.columns:
        searchable = " ".join(filter(None, [
            col.raw_column,
            col.normalized,
            col.ref_entry,
            col.mit_domain,
            col.comment,
        ]))
        for pattern, sector in _SECTOR_RULES:
            if pattern.search(searchable):
                votes[sector] = votes.get(sector, 0) + 1

    if not votes:
        return "general"

    return max(votes, key=votes.get)


# ───────────────────────────────────────────────────────────────────
# 2. Auto-detect ID COLUMN via structural scoring
# ───────────────────────────────────────────────────────────────────

_SUFFIX_ID = re.compile(r"_id$", re.I)
_PREFIX_ID = re.compile(r"^id_", re.I)
_EXACT_ID  = re.compile(r"^id$", re.I)
_NUM_CODE  = re.compile(r"(numero|num_|n_|code_|matricule|numero_|ref_)", re.I)
_UNIQUE_ID = re.compile(r"(uuid|guid|ssn|nss|iban|cin|passport|national.?id)", re.I)
_REF_ID_KW = re.compile(
    r"(identifier|identifiant|identity|identite|id_card|numéro|numero|passport|matricule)",
    re.I,
)


def _score_as_identifier(col: SignalScanColumnResult) -> float:
    """Heuristic score ∈ [0, 1] — how likely this column is the primary
    identifier of the dataset."""

    score = 0.0
    name = col.raw_column

    # Structural patterns in column name
    if _EXACT_ID.match(name):
        score += 0.50
    if _SUFFIX_ID.search(name):
        score += 0.45
    if _PREFIX_ID.match(name):
        score += 0.45
    if _NUM_CODE.search(name):
        score += 0.30
    if _UNIQUE_ID.search(name):
        score += 0.50

    # Scan signal: identifiers are always PII
    if col.signal == "S_pii":
        score += 0.15
    elif col.signal is not None:
        score -= 0.30  # sensitive/protected columns are never the ID

    # Taxonomy keywords
    searchable = f"{col.normalized} {col.ref_entry or ''} {col.comment}"
    if _REF_ID_KW.search(searchable):
        score += 0.20

    # MIT domain
    mit = (col.mit_domain or "").lower()
    if "identit" in mit:
        score += 0.15
    if "privacy" in mit:
        score += 0.10

    return min(score, 1.0)


def _detect_id_column(scan_result: SignalScanResponse) -> Optional[str]:
    """Pick the highest-scoring column above threshold as the ID column."""

    best_col: Optional[str] = None
    best_score = 0.0

    for col in scan_result.columns:
        s = _score_as_identifier(col)
        if s > best_score and s >= 0.25:
            best_score = s
            best_col = col.raw_column

    return best_col


# ───────────────────────────────────────────────────────────────────
# 3. Auto-detect PRIMARY SENSITIVE ATTRIBUTE
# ───────────────────────────────────────────────────────────────────

def _detect_sensitive_attribute(scan_result: SignalScanResponse) -> Optional[str]:
    """Return the most sensitive column (S_sens > S_dec > S_prot),
    breaking ties by confidence."""

    candidates = [
        col for col in scan_result.columns
        if col.signal and col.signal != "S_pii"
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda c: (
        SENSITIVE_PRIORITY.get(c.signal or "", 99),
        -c.confidence,
    ))
    return candidates[0].raw_column


# ───────────────────────────────────────────────────────────────────
# 4. Auto-detect SENSITIVE HEALTH COLUMNS (medical/health signals)
# ───────────────────────────────────────────────────────────────────

_HEALTH_KEYWORDS = re.compile(
    r"(medical|health|diagnost|medicament|pharma|symptom|maladie|traitement|patholog|blood|sang|allergi|vaccin|ordonnance|prescription|hopital|hospital|clinic)",
    re.I,
)


def _detect_sensitive_health_columns(scan_result: SignalScanResponse) -> List[str]:
    """Identify columns related to sensitive health data using both
    signal type (S_sens) and domain/naming heuristics."""

    health_cols = []

    for col in scan_result.columns:
        searchable = " ".join(filter(None, [
            col.raw_column,
            col.normalized,
            col.ref_entry,
            col.mit_domain,
            col.comment,
        ]))

        is_health = False

        # Signal-based: S_sens in a health-related domain
        if col.signal == "S_sens":
            is_health = True

        # Domain / keyword heuristics
        if _HEALTH_KEYWORDS.search(searchable):
            is_health = True

        if is_health:
            health_cols.append(col.raw_column)

    return health_cols


# ───────────────────────────────────────────────────────────────────
# 5. Auto-assign ROLES per column
# ───────────────────────────────────────────────────────────────────

def _derive_roles(
    col: SignalScanColumnResult,
    id_column: Optional[str],
    sensitive_attr: Optional[str],
) -> List[str]:
    """Assign semantic roles to a column based on its signal and
    its relationship to the detected id/sensitive columns."""

    name = col.raw_column

    if name == id_column:
        return ["identifier"]

    if name == sensitive_attr:
        return ["sensitive_attribute"]

    if col.signal == "S_pii":
        return ["quasi_identifier", "pii"]

    if col.signal == "S_prot":
        return ["protected", "quasi_identifier"]

    if col.signal == "S_sens":
        return ["sensitive"]

    if col.signal == "S_dec":
        return ["decision_variable"]

    return ["feature"]


# ───────────────────────────────────────────────────────────────────
# 6. Auto-detect CORRELATION COLUMNS (pairs likely correlated)
# ───────────────────────────────────────────────────────────────────

_CORRELATED_DOMAINS = {
    ("demographic", "demographic"),
    ("geographic", "geographic"),
    ("contact", "contact"),
    ("identite", "identite"),
    ("medical", "medical"),
}


def _detect_correlation_columns(
    scan_result: SignalScanResponse,
    id_column: Optional[str],
) -> List[str]:
    """Auto-detect columns likely correlated based on shared MIT domains
    or shared signal types.  Returns a flat list of unique column names."""

    qi_cols = [
        col for col in scan_result.columns
        if col.signal == "S_pii" and col.raw_column != id_column
    ]

    correlated: set = set()
    for a, b in combinations(qi_cols, 2):
        # Same MIT domain → likely correlated
        if a.mit_domain and b.mit_domain:
            combo = (a.mit_domain.lower().strip(), b.mit_domain.lower().strip())
            if combo[0] == combo[1]:
                correlated.add(a.raw_column)
                correlated.add(b.raw_column)
                continue
            if tuple(sorted(combo)) in _CORRELATED_DOMAINS:
                correlated.add(a.raw_column)
                correlated.add(b.raw_column)

    return sorted(correlated)


# ───────────────────────────────────────────────────────────────────
# 7. Auto-detect IMBALANCE COLUMNS (risk of class imbalance)
# ───────────────────────────────────────────────────────────────────

def _detect_imbalance_columns(
    scan_result: SignalScanResponse,
    id_column: Optional[str],
) -> List[str]:
    """Columns useful for imbalance analysis are quasi-identifiers
    (excluding the direct ID column) — these are the columns an
    attacker would use to try to re-identify records."""

    return [
        col.raw_column
        for col in scan_result.columns
        if col.signal == "S_pii" and col.raw_column != id_column
    ]


# ───────────────────────────────────────────────────────────────────
# 8. Auto-detect SAMPLING FRACTION
# ───────────────────────────────────────────────────────────────────

def _detect_sample_frac(scan_result: SignalScanResponse) -> float:
    """Higher PII density → lower sampling fraction (more conservative).
    This is a simple heuristic based on the ratio of PII columns."""

    total = len(scan_result.columns)
    if total == 0:
        return 0.15

    pii_count = sum(1 for c in scan_result.columns if c.signal == "S_pii")
    sens_count = sum(1 for c in scan_result.columns if c.signal in ("S_sens", "S_dec"))

    risk_ratio = (pii_count + sens_count * 2) / total

    if risk_ratio > 0.6:
        return 0.05   # very sensitive dataset
    if risk_ratio > 0.4:
        return 0.10
    if risk_ratio > 0.2:
        return 0.15
    return 0.20


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def build_analysis_profile_from_scan(
    scan_result: SignalScanResponse,
    dataset_id: str,
    dataset_name: str,
    secteur: str = "",
) -> dict:
    """Build a complete analysis profile from scan results.
    Every field is auto-detected from the scan metadata."""

    # ── Auto-detect all derived fields ──
    detected_secteur = secteur or _detect_secteur(scan_result)
    id_column = _detect_id_column(scan_result)
    sensitive_attr = _detect_sensitive_attribute(scan_result)
    health_columns = _detect_sensitive_health_columns(scan_result)
    imbalance_columns = _detect_imbalance_columns(scan_result, id_column)
    correlation_columns = _detect_correlation_columns(scan_result, id_column)
    sample_frac = _detect_sample_frac(scan_result)

    # ── Build column mappings with auto-assigned roles ──
    columns: List[ColumnMapping] = []
    for col in scan_result.columns:
        columns.append(ColumnMapping(
            name=col.raw_column,
            roles=_derive_roles(col, id_column, sensitive_attr),
            type="string",
            description=col.comment or col.ref_entry or col.raw_column,
        ))

    # ── Derive summary lists from roles ──
    qi_columns = [c.name for c in columns if "quasi_identifier" in (c.roles or [])]
    pii_columns = [c.name for c in columns if "pii" in (c.roles or [])]

    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "description": f"Profil d'analyse généré automatiquement pour {dataset_name}",
        "secteur": detected_secteur,
        "public_sample_frac": sample_frac,
        "columns": columns,
        "imbalance_columns": imbalance_columns,
        "correlation_columns": correlation_columns,
        "id_column": id_column,
        "sensitive_health_columns": health_columns,
        "scan_result": scan_result,
        "derived_summary": {
            "quasi_identifiers": qi_columns,
            "pii_columns": pii_columns,
            "sensitive_attribute": sensitive_attr,
            "id_column": id_column,
            "sensitive_health_columns": health_columns,
        },
    }

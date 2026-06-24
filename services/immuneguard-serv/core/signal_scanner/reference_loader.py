import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from core.signal_scanner.normalization import normalize_header


SIGNAL_CODE_PATTERN = re.compile(r"\bS_(?:pii|prot|sens|dec)\b", re.IGNORECASE)


DEFAULT_REFERENCE_CANDIDATES = (
    os.getenv("SIGNAL_REFERENCE_PATH"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "Ref_Signaux_Sprint7.xlsx"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Ref_Signaux_Sprint7.xlsx"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "Template_Ref_Signaux.xlsx"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "Template_Ref_Signaux.json"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Template_Ref_Signaux.xlsx"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Template_Ref_Signaux.json"),
)


def _clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _split_aliases(value: str) -> List[str]:
    if not value:
        return []
    aliases: List[str] = []
    for raw_part in value.replace("|", ",").replace(";", ",").split(","):
        part = raw_part.strip()
        if part:
            aliases.append(part)
    return aliases


def _first_non_empty(row: Dict[str, object], *keys: str) -> str:
    for key in keys:
        cleaned = _clean_text(row.get(key))
        if cleaned:
            return cleaned
    return ""


def _extract_signal_code(value: str) -> str:
    if not value:
        return ""
    match = SIGNAL_CODE_PATTERN.search(value)
    if match:
        return match.group(0)
    return value


def _safe_float(value: Any) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0.0
        text = str(value).strip().replace(",", ".")
        if not text:
            return 0.0
        return float(text)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class SignalReferenceEntry:
    ref_entry: str
    nom_colonne: str
    column_name: str
    aliases: List[str]
    signal: Optional[str]
    mit_domain: str
    legal_source: str
    p: float = 0.0
    sev_column_read: str = ""
    xai_template_fr: str = ""
    action_corrective: str = ""
    severity_columns: Optional[Dict[str, float]] = None


class SignalReferenceRepository:
    def __init__(self, entries: List[SignalReferenceEntry]):
        self.entries = entries
        self.by_exact_fr: Dict[str, SignalReferenceEntry] = {}
        self.by_exact_en: Dict[str, SignalReferenceEntry] = {}
        self.by_alias: Dict[str, SignalReferenceEntry] = {}
        self.search_space: Dict[str, SignalReferenceEntry] = {}
        for entry in entries:
            self._register(self.by_exact_fr, entry.nom_colonne, entry)
            self._register(self.by_exact_en, entry.column_name, entry)
            for alias in entry.aliases:
                self._register(self.by_alias, alias, entry)

    def _register(
        self,
        mapping: Dict[str, SignalReferenceEntry],
        raw_values: Iterable[str] | str,
        entry: SignalReferenceEntry,
    ) -> None:
        values = [raw_values] if isinstance(raw_values, str) else list(raw_values)
        for value in values:
            cleaned = _clean_text(value)
            if not cleaned:
                continue
            normalized = normalize_header(cleaned)
            if not normalized:
                continue
            mapping.setdefault(normalized, entry)
            self.search_space.setdefault(normalized, entry)

    @classmethod
    def from_path(cls, path: str) -> "SignalReferenceRepository":
        if path.lower().endswith(".json"):
            with open(path, "r", encoding="utf-8") as handle:
                raw_entries = json.load(handle)
            if not isinstance(raw_entries, list):
                raise ValueError("JSON reference file must contain a list of entries.")
        else:
            raw_entries = _read_excel_reference_records(path)
        entries = [cls._row_to_entry(index, row) for index, row in enumerate(raw_entries, start=1)]
        return cls(entries)

    @classmethod
    def load_default(cls) -> "SignalReferenceRepository":
        for candidate in DEFAULT_REFERENCE_CANDIDATES:
            if candidate and os.path.exists(candidate):
                return cls.from_path(candidate)
        raise FileNotFoundError(
            "Template_Ref_Signaux reference file not found. "
            "Set SIGNAL_REFERENCE_PATH or add Template_Ref_Signaux.xlsx/json under the service directory."
        )

    @staticmethod
    def _row_to_entry(index: int, row: Dict[str, object]) -> SignalReferenceEntry:
        nom_colonne = _first_non_empty(
            row,
            "nom_colonne",
            "nom colonne",
            "nom_colonne (FR)",
            "nom colonne (FR)",
        )
        column_name = _first_non_empty(
            row,
            "column_name",
            "column name",
            "column_name (EN)",
            "column name (EN)",
        )
        ref_entry = (
            _first_non_empty(row, "ref_entry", "reference", "id")
            or column_name
            or nom_colonne
            or f"ref_{index}"
        )
        aliases = _split_aliases(
            _first_non_empty(
                row,
                "synonyms / aliases",
                "synonymes / aliases",
                "synonyms",
                "synonymes",
                "aliases",
                "alias",
            )
        )
        severity_columns = {
            str(key): _safe_float(value)
            for key, value in row.items()
            if str(key).strip().lower().startswith("sev_") and _clean_text(value)
        }
        signal_code = _extract_signal_code(_first_non_empty(row, "signal_code", "signal code", "signal_code (v5)"))
        return SignalReferenceEntry(
            ref_entry=ref_entry,
            nom_colonne=nom_colonne,
            column_name=column_name,
            aliases=aliases,
            signal=signal_code or _extract_signal_code(_first_non_empty(row, "signal", "signal (EN)", "signal (FR)")) or None,
            mit_domain=_first_non_empty(row, "mit_domain", "mit domain", "mit_domain (EN)", "domaine_mit (FR)"),
            legal_source=_first_non_empty(
                row,
                "legal_source",
                "legal source",
                "source_reglementaire",
                "source_reglementaire (FR/EN)",
                "source réglementaire (FR/EN)",
            ),
            p=_safe_float(_first_non_empty(row, "p", "poids p", "poids_p", "weight", "signal_weight"))
            or _safe_float(_first_non_empty(row, "p_weight", "p weight", "poids_signal"))
            or _default_p_from_signal_code(signal_code),
            sev_column_read=_first_non_empty(row, "sev_column_read", "sev column read", "sev_column"),
            xai_template_fr=_first_non_empty(
                row,
                "xai_template_fr",
                "template_xai_fr",
                "xai template fr",
                "template explication fr",
            ),
            action_corrective=_first_non_empty(row, "action_corrective", "action corrective", "corrective_action"),
            severity_columns=severity_columns,
        )


def _read_excel_reference_records(path: str) -> List[Dict[str, object]]:
    """
    Support both "clean table" Excels and the Sprint-6 Ref Signaux layout
    where the actual header row is embedded in the sheet (titles + Unnamed columns).
    """
    raw = pd.read_excel(path, header=None)
    header_row_idx: Optional[int] = None
    for i in range(min(len(raw), 50)):
        row_values = [str(v).strip() for v in raw.iloc[i].tolist() if _clean_text(v)]
        if "nom_colonne (FR)" in row_values and "signal_code" in row_values:
            header_row_idx = i
            break
    if header_row_idx is None:
        # Fallback: standard read
        dataframe = pd.read_excel(path)
        return dataframe.to_dict(orient="records")

    headers = [str(v).strip() if _clean_text(v) else f"unnamed_{j}" for j, v in enumerate(raw.iloc[header_row_idx].tolist())]
    # Make headers unique
    seen: Dict[str, int] = {}
    uniq_headers: List[str] = []
    for h in headers:
        key = h
        if key in seen:
            seen[key] += 1
            key = f"{key}__{seen[key]}"
        else:
            seen[key] = 0
        uniq_headers.append(key)

    data = raw.iloc[header_row_idx + 1 :].copy()
    data.columns = uniq_headers
    # Keep only rows that look like actual reference entries
    data = data[data.get("nom_colonne (FR)").apply(lambda v: bool(_clean_text(v)))]
    return data.to_dict(orient="records")


def _default_p_from_signal_code(signal_code: str) -> float:
    """
    CDC risk analysis: If 'p' not present in the reference, derive it from signal_code.
    (Ideally 'p' should be provided by the reference; this is a safe fallback.)
    """
    code = (signal_code or "").strip().lower()
    if code == "s_prot":
        return 1.0
    if code == "s_sens":
        return 0.8
    if code == "s_dec":
        return 0.6
    if code == "s_pii":
        return 0.4
    return 0.0

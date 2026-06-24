from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from core.signal_scanner.fuzzy import AUTO_MATCH_THRESHOLD, fuzzy_lookup
from core.signal_scanner.lookup import deterministic_lookup
from core.signal_scanner.normalization import normalize_header
from core.signal_scanner.profiling import profile_column
from core.signal_scanner.reference_loader import SignalReferenceRepository


DEFAULT_COMMENT_FUZZY_REVIEW = "Fuzzy match requires human validation."


@dataclass
class ScanColumnResult:
    raw_column: str
    normalized: str
    match_method: str
    ref_entry: Optional[str]
    signal: Optional[str]
    mit_domain: str
    legal_source: str
    p: float
    xai_template_fr: str
    action_corrective: str
    severity_columns: Dict[str, float]
    confidence: float
    human_validated: bool
    comment: str


class SignalScannerService:
    def __init__(self, repository: SignalReferenceRepository):
        self.repository = repository

    @classmethod
    def from_path(cls, path: str) -> "SignalScannerService":
        return cls(SignalReferenceRepository.from_path(path))

    @classmethod
    def load_default(cls) -> "SignalScannerService":
        return cls(SignalReferenceRepository.load_default())

    def scan_dataframe(self, dataframe: pd.DataFrame) -> Dict[str, object]:
        results: List[Dict[str, object]] = []
        metrics = Counter({"exact": 0, "alias": 0, "fuzzy": 0, "profiling": 0, "none": 0})

        for column in dataframe.columns:
            result = self.scan_column(column, dataframe[column])
            results.append(result.__dict__)
            if result.match_method in {"exact_fr", "exact_en"}:
                metrics["exact"] += 1
            elif result.match_method == "alias":
                metrics["alias"] += 1
            elif result.match_method == "fuzzy":
                metrics["fuzzy"] += 1
            elif result.match_method == "profiling":
                metrics["profiling"] += 1
            else:
                metrics["none"] += 1

        metrics["total_columns"] = len(dataframe.columns)
        return {"columns": results, "metrics": dict(metrics)}

    def scan_column(self, raw_column: str, series: pd.Series) -> ScanColumnResult:
        normalized = normalize_header(raw_column)

        deterministic = deterministic_lookup(normalized, self.repository)
        if deterministic:
            return self._build_reference_result(
                raw_column=raw_column,
                normalized=normalized,
                match_method=deterministic.match_method,
                confidence=deterministic.confidence,
                human_validated=True,
                comment="",
                entry=deterministic.entry,
            )

        fuzzy_result = fuzzy_lookup(normalized, self.repository)
        if fuzzy_result:
            needs_review = fuzzy_result.confidence < AUTO_MATCH_THRESHOLD
            return self._build_reference_result(
                raw_column=raw_column,
                normalized=normalized,
                match_method="fuzzy",
                confidence=fuzzy_result.confidence,
                human_validated=not needs_review,
                comment=DEFAULT_COMMENT_FUZZY_REVIEW if needs_review else "",
                entry=fuzzy_result.entry,
            )

        profiling = profile_column(series.tolist())
        if profiling:
            return ScanColumnResult(
                raw_column=raw_column,
                normalized=normalized,
                match_method=profiling.match_method,
                ref_entry=None,
                signal=profiling.signal,
                mit_domain=profiling.mit_domain,
                legal_source=profiling.legal_source,
                p=0.0,
                xai_template_fr="",
                action_corrective="",
                severity_columns={},
                confidence=profiling.confidence,
                human_validated=False,
                comment=profiling.comment,
            )

        return ScanColumnResult(
            raw_column=raw_column,
            normalized=normalized,
            match_method="none",
            ref_entry=None,
            signal=None,
            mit_domain="",
            legal_source="",
            p=0.0,
            xai_template_fr="",
            action_corrective="",
            severity_columns={},
            confidence=0.0,
            human_validated=False,
            comment="No reference or profiling match found.",
        )

    def _build_reference_result(
        self,
        raw_column: str,
        normalized: str,
        match_method: str,
        confidence: float,
        human_validated: bool,
        comment: str,
        entry,
    ) -> ScanColumnResult:
        # If the reference does not provide explicit sev_* values, keep sev_column_read
        # name available through severity_columns as a placeholder key.
        severity_columns = entry.severity_columns or {}
        if not severity_columns and getattr(entry, "sev_column_read", ""):
            severity_columns = {str(getattr(entry, "sev_column_read")): 0.0}
        return ScanColumnResult(
            raw_column=raw_column,
            normalized=normalized,
            match_method=match_method,
            ref_entry=entry.ref_entry,
            signal=entry.signal,
            mit_domain=entry.mit_domain,
            legal_source=entry.legal_source,
            p=entry.p,
            xai_template_fr=entry.xai_template_fr,
            action_corrective=getattr(entry, "action_corrective", ""),
            severity_columns=severity_columns,
            confidence=round(confidence, 4),
            human_validated=human_validated,
            comment=comment,
        )

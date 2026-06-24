from typing import Optional

from core.signal_scanner.reference_loader import SignalReferenceEntry, SignalReferenceRepository


class LookupResult:
    def __init__(self, match_method: str, entry: SignalReferenceEntry, confidence: float):
        self.match_method = match_method
        self.entry = entry
        self.confidence = confidence


def deterministic_lookup(
    normalized_column: str,
    repository: SignalReferenceRepository,
) -> Optional[LookupResult]:
    if normalized_column in repository.by_exact_fr:
        return LookupResult("exact_fr", repository.by_exact_fr[normalized_column], 1.0)
    if normalized_column in repository.by_exact_en:
        return LookupResult("exact_en", repository.by_exact_en[normalized_column], 1.0)
    if normalized_column in repository.by_alias:
        return LookupResult("alias", repository.by_alias[normalized_column], 0.95)
    return None

from difflib import SequenceMatcher
from typing import Optional

from core.signal_scanner.lookup import LookupResult
from core.signal_scanner.reference_loader import SignalReferenceRepository


AUTO_MATCH_THRESHOLD = 0.80
HUMAN_VALIDATION_THRESHOLD = 0.60


def similarity_score(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def fuzzy_lookup(
    normalized_column: str,
    repository: SignalReferenceRepository,
) -> Optional[LookupResult]:
    best_key = None
    best_score = 0.0

    for candidate in repository.search_space:
        score = similarity_score(normalized_column, candidate)
        if score > best_score:
            best_key = candidate
            best_score = score

    if best_key is None or best_score < HUMAN_VALIDATION_THRESHOLD:
        return None

    return LookupResult(
        match_method="fuzzy",
        entry=repository.search_space[best_key],
        confidence=round(best_score, 4),
    )

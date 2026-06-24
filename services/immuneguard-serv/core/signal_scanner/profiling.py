import ipaddress
import re
from dataclasses import dataclass
from typing import Iterable, Optional


EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
CIN_PATTERN = re.compile(r"^[A-Z]{1,2}\d{4,8}$", re.IGNORECASE)
BLOOD_TYPE_PATTERN = re.compile(r"^(A|B|AB|O)[+-]$", re.IGNORECASE)
GENDER_PATTERN = re.compile(r"^(m|f|h|homme|femme|male|female)$", re.IGNORECASE)
CIM10_PATTERN = re.compile(r"^[A-Z]\d{2}(?:\.\d{1,2})?$", re.IGNORECASE)


@dataclass(frozen=True)
class ProfilingResult:
    match_method: str
    signal: str
    mit_domain: str
    legal_source: str
    confidence: float
    comment: str


def _is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _clean_values(values: Iterable[object]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text.lower() == "nan":
            continue
        cleaned.append(text)
    return cleaned


def _ratio_matching(values: list[str], predicate) -> float:
    if not values:
        return 0.0
    matched = sum(1 for value in values if predicate(value))
    return matched / len(values)


def profile_column(values: Iterable[object]) -> Optional[ProfilingResult]:
    cleaned = _clean_values(values)
    if not cleaned:
        return None

    detectors = (
        (
            "email",
            lambda value: bool(EMAIL_PATTERN.match(value)),
            ProfilingResult("profiling", "S_pii", "contact", "value_profiling:email", 0.92, "Email pattern detected in sampled values."),
            0.92
        ),
        (
            "ip",
            _is_ip_address,
            ProfilingResult("profiling", "S_pii", "network", "value_profiling:ip_address", 0.90, "IP address pattern detected in sampled values."),
            0.90
        ),
        (
            "cin",
            lambda value: bool(CIN_PATTERN.match(value)),
            ProfilingResult("profiling", "S_pii", "identite", "value_profiling:moroccan_cin", 0.90, "Moroccan CIN-like pattern detected in sampled values."),
            0.90
        ),
        (
            "blood_type",
            lambda value: bool(BLOOD_TYPE_PATTERN.match(value.upper())),
            ProfilingResult("profiling", "S_sens", "medical", "value_profiling:blood_type", 0.90, "Blood type pattern detected in sampled values."),
            0.90
        ),
        (
            "cim10",
            lambda value: bool(CIM10_PATTERN.match(value)),
            ProfilingResult("profiling", "S_sens", "medical", "value_profiling:cim10_code", 0.80, "CIM-10 diagnosis code pattern detected."),
            0.80
        ),
        (
            "gender",
            lambda value: bool(GENDER_PATTERN.match(value.lower())),
            ProfilingResult("profiling", "S_prot", "demographic", "value_profiling:gender", 0.90, "Gender-like values detected in sampled values."),
            0.90
        ),
    )

    for _, predicate, result, threshold in detectors:
        ratio = _ratio_matching(cleaned, predicate)
        if ratio >= threshold:
            return ProfilingResult(
                match_method=result.match_method,
                signal=result.signal,
                mit_domain=result.mit_domain,
                legal_source=result.legal_source,
                confidence=max(result.confidence, round(ratio, 4)),
                comment=result.comment,
            )
    return None

import re
import unicodedata


CAMEL_CASE_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
SEPARATOR_PATTERN = re.compile(r"[\s\-.\/]+")
NON_WORD_PATTERN = re.compile(r"[^a-z0-9_]+")
UNDERSCORE_PATTERN = re.compile(r"_+")


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def singularize_token(token: str) -> str:
    if token == "allergies":
        return "allergie"
    if token == "salaries":
        return "salary"
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("sses"):
        return token[:-2]
    if token.endswith("es") and not token.endswith(("aes", "ees", "oes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalize_header(raw_column: str) -> str:
    value = raw_column.strip()
    value = CAMEL_CASE_BOUNDARY.sub(r"\1_\2", value)
    value = strip_accents(value).lower()
    value = SEPARATOR_PATTERN.sub("", value)  # Suppression espaces, tirets, points
    value = NON_WORD_PATTERN.sub("_", value)
    value = UNDERSCORE_PATTERN.sub("_", value).strip("_")
    tokens = [singularize_token(token) for token in value.split("_") if token]
    return "_".join(tokens)

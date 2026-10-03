from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any


EMPTY_MARKERS = {"", "-", "—", "_"}
TRUE_MARKERS = {"true", "yes", "oui", "1", "checked", "x"}
FALSE_MARKERS = {"false", "no", "non", "0", "unchecked"}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return " ".join(text.split())


def parse_number(text: str) -> tuple[float | None, float]:
    normalized = normalize_text(text).replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", normalized)
    if not match:
        return None, 0.0
    token = match.group(0)
    score = 1.0 if normalized == token else 0.92
    try:
        return float(token), score
    except ValueError:
        return None, 0.0


def parse_integer(text: str) -> tuple[int | None, float]:
    number, score = parse_number(text)
    if number is None:
        return None, 0.0
    if not float(number).is_integer():
        return None, 0.2
    return int(number), score


def parse_boolean(text: str) -> tuple[bool | None, float]:
    normalized = normalize_text(text)
    if normalized in TRUE_MARKERS:
        return True, 1.0
    if normalized in FALSE_MARKERS:
        return False, 1.0
    return None, 0.0


def parse_date(text: str) -> tuple[str | None, float]:
    normalized = normalize_text(text)
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(normalized, pattern).date()
            return parsed.isoformat(), 1.0
        except ValueError:
            continue
    return None, 0.0


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, lchar in enumerate(left, 1):
        current = [i]
        for j, rchar in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (lchar != rchar)))
        previous = current
    return previous[-1]


def parse_enum(text: str, values: list[str], aliases: dict[str, str] | None = None) -> tuple[str | None, float]:
    normalized = normalize_text(text)
    normalized_aliases = {normalize_text(key): value for key, value in (aliases or {}).items()}
    if normalized in normalized_aliases:
        return normalized_aliases[normalized], 1.0

    normalized_values = {normalize_text(value).replace("_", " "): value for value in values}
    if normalized in normalized_values:
        return normalized_values[normalized], 1.0

    if not normalized:
        return None, 0.0
    distances = []
    for candidate, original in normalized_values.items():
        distance = edit_distance(normalized, candidate)
        similarity = 1.0 - distance / max(len(normalized), len(candidate), 1)
        distances.append((similarity, original))
    similarity, best = max(distances)
    return (best, similarity) if similarity >= 0.65 else (None, similarity)


def parse_value(text: str, spec: dict[str, Any]) -> tuple[Any, float, float]:
    field_type = spec.get("type", "string")
    if field_type == "double":
        value, parse_score = parse_number(text)
        return value, parse_score, 1.0
    if field_type == "integer":
        value, parse_score = parse_integer(text)
        return value, parse_score, 1.0
    if field_type == "boolean":
        value, parse_score = parse_boolean(text)
        return value, parse_score, 1.0
    if field_type == "date":
        value, parse_score = parse_date(text)
        return value, parse_score, 1.0
    if field_type == "enum":
        value, allowed_score = parse_enum(text, spec.get("values", []), spec.get("aliases"))
        return value, 1.0 if value is not None else 0.0, allowed_score
    if field_type == "string":
        normalized = text.strip()
        return normalized or None, 1.0 if normalized else 0.0, 1.0
    return text, 0.75, 1.0


def is_blank(text: str | None) -> bool:
    return text is None or normalize_text(text) in EMPTY_MARKERS


def iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


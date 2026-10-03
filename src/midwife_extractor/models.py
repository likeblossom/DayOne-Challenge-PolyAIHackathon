from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class FieldStatus(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    NOT_PROVIDED = "NOT_PROVIDED"
    ILLEGIBLE = "ILLEGIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(slots=True)
class RawCandidate:
    text: str | None
    ocr_score: float = 0.0
    image_quality: float = 1.0
    second_choice_score: float | None = None
    second_choice_text: str | None = None
    # 0.5 is neutral when only one recognizer was run; 1.0 means independent agreement.
    model_agreement: float = 0.5
    source: str = "unknown"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RawCandidate":
        return cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value})


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class FieldEvidence:
    raw_text: str | None
    source: str
    ocr_score: float
    image_quality: float
    parse_score: float
    allowed_value_score: float
    model_agreement: float
    recognition_margin: float | None = None
    validation_issues: list[ValidationIssue] = field(default_factory=list)


@dataclass(slots=True)
class FieldResult:
    value: Any
    status: FieldStatus
    confidence: float
    evidence: FieldEvidence

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result

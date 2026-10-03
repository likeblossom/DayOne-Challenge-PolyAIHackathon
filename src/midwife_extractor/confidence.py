from __future__ import annotations

from .models import FieldEvidence


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def recognition_margin(best: float, second: float | None) -> float | None:
    if second is None:
        return None
    return clamp(best - second)


def calculate_confidence(evidence: FieldEvidence) -> float:
    """Heuristic score; calibrate it against held-out labeled patients before calling it a probability."""
    margin = evidence.recognition_margin if evidence.recognition_margin is not None else 0.5
    score = (
        0.40 * clamp(evidence.ocr_score)
        + 0.15 * clamp(evidence.image_quality)
        + 0.15 * clamp(evidence.parse_score)
        + 0.10 * clamp(evidence.allowed_value_score)
        + 0.10 * clamp(evidence.model_agreement)
        + 0.10 * clamp(margin)
    )
    for issue in evidence.validation_issues:
        score -= 0.40 if issue.severity == "error" else 0.20
    return round(clamp(score), 4)


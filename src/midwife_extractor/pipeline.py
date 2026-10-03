from __future__ import annotations

from typing import Any

from .confidence import calculate_confidence, recognition_margin
from .models import FieldEvidence, FieldResult, FieldStatus, RawCandidate, ValidationIssue
from .parsing import is_blank, parse_value
from .schemas import load_form
from .validation import validate_field, validate_record


class ExtractionPipeline:
    def __init__(self, known_threshold: float = 0.85, illegible_threshold: float = 0.30):
        self.known_threshold = known_threshold
        self.illegible_threshold = illegible_threshold

    def extract(self, form_id: str, candidates: dict[str, RawCandidate | dict[str, Any]]) -> dict[str, Any]:
        schema = load_form(form_id)
        specs = schema["fields"]
        results: dict[str, FieldResult] = {}

        for field_name, raw in candidates.items():
            if field_name not in specs:
                raise KeyError(f"{field_name!r} is not a top-level field in form {form_id!r}")
            candidate = raw if isinstance(raw, RawCandidate) else RawCandidate.from_dict(raw)
            results[field_name] = self._extract_field(field_name, specs[field_name], candidate)

        values = {name: result.value for name, result in results.items()}
        record_issues = validate_record(values)
        for name, issues in record_issues.items():
            if name not in results:
                continue
            results[name].evidence.validation_issues.extend(issues)
            results[name].confidence = calculate_confidence(results[name].evidence)
            results[name].status = FieldStatus.NEEDS_REVIEW

        return {
            "form_id": form_id,
            "title_en": schema["title_en"],
            "fields": {name: result.to_dict() for name, result in results.items()},
            "summary": self._summary(results),
        }

    def _extract_field(self, name: str, spec: dict[str, Any], candidate: RawCandidate) -> FieldResult:
        if is_blank(candidate.text):
            evidence = FieldEvidence(
                raw_text=candidate.text,
                source=candidate.source,
                ocr_score=candidate.ocr_score,
                image_quality=candidate.image_quality,
                parse_score=1.0,
                allowed_value_score=1.0,
                model_agreement=candidate.model_agreement,
            )
            return FieldResult(None, FieldStatus.NOT_PROVIDED, calculate_confidence(evidence), evidence)

        assert candidate.text is not None
        value, parse_score, allowed_score = parse_value(candidate.text, spec)
        issues = validate_field(name, value, spec)
        if value is None:
            issues.append(ValidationIssue("PARSE_FAILED", f"Could not parse {candidate.text!r} as {spec.get('type')}", "error"))

        evidence = FieldEvidence(
            raw_text=candidate.text,
            source=candidate.source,
            ocr_score=candidate.ocr_score,
            image_quality=candidate.image_quality,
            parse_score=parse_score,
            allowed_value_score=allowed_score,
            model_agreement=candidate.model_agreement,
            recognition_margin=recognition_margin(candidate.ocr_score, candidate.second_choice_score),
            validation_issues=issues,
        )
        confidence = calculate_confidence(evidence)

        if candidate.image_quality < self.illegible_threshold:
            status = FieldStatus.ILLEGIBLE
        elif issues or confidence < self.known_threshold:
            status = FieldStatus.NEEDS_REVIEW
        else:
            status = FieldStatus.KNOWN
        return FieldResult(value, status, confidence, evidence)

    @staticmethod
    def _summary(results: dict[str, FieldResult]) -> dict[str, int]:
        return {
            status.value: sum(result.status == status for result in results.values())
            for status in FieldStatus
        }

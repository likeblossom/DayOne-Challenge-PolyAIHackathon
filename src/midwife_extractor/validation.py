from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .models import ValidationIssue
from .parsing import iso_date


PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "age_years": (10, 60),
    "temperature_c": (25, 45),
    "weight_kg": (0.5, 250),
    "weight_g": (300, 15000),
    "birth_weight_g": (300, 7000),
    "length_cm": (20, 100),
    "height_cm": (80, 220),
    "head_circumference_cm": (20, 65),
    "gestational_age_weeks": (15, 45),
    "systolic_bp_mmhg": (40, 260),
    "diastolic_bp_mmhg": (20, 180),
    "pulse_bpm": (25, 240),
    "fetal_heart_rate_bpm": (50, 240),
    "gravidity": (0, 30),
    "parity": (0, 30),
    "living_children": (0, 30),
    "age_days": (0, 365),
}


def validate_field(name: str, value: Any, spec: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if value is None:
        return issues

    if isinstance(value, (int, float)):
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        if minimum is not None and value < minimum:
            issues.append(ValidationIssue("BELOW_SCHEMA_MINIMUM", f"{value} is below {minimum}", "error"))
        if maximum is not None and value > maximum:
            issues.append(ValidationIssue("ABOVE_SCHEMA_MAXIMUM", f"{value} is above {maximum}", "error"))
        if name in PLAUSIBLE_RANGES:
            low, high = PLAUSIBLE_RANGES[name]
            if not low <= value <= high:
                issues.append(
                    ValidationIssue("OUTSIDE_PLAUSIBLE_RANGE", f"{name}={value} is outside {low}..{high}", "error")
                )
    return issues


def validate_record(values: dict[str, Any]) -> dict[str, list[ValidationIssue]]:
    issues: dict[str, list[ValidationIssue]] = {}

    def add(field: str, code: str, message: str, severity: str = "error") -> None:
        issues.setdefault(field, []).append(ValidationIssue(code, message, severity))

    systolic = values.get("systolic_bp_mmhg")
    diastolic = values.get("diastolic_bp_mmhg")
    if isinstance(systolic, (int, float)) and isinstance(diastolic, (int, float)) and systolic <= diastolic:
        add("systolic_bp_mmhg", "BP_ORDER_INVALID", "Systolic pressure must exceed diastolic pressure")
        add("diastolic_bp_mmhg", "BP_ORDER_INVALID", "Diastolic pressure must be below systolic pressure")

    gravidity, parity, living = values.get("gravidity"), values.get("parity"), values.get("living_children")
    if isinstance(gravidity, int) and isinstance(parity, int) and parity > gravidity:
        add("parity", "PARITY_EXCEEDS_GRAVIDITY", "Parity cannot exceed gravidity")
    if isinstance(parity, int) and isinstance(living, int) and living > parity:
        add("living_children", "LIVING_CHILDREN_EXCEED_PARITY", "Living children cannot exceed parity")

    delivery = iso_date(values.get("delivery_date"))
    consultation = iso_date(values.get("consultation_date"))
    follow_up = iso_date(values.get("follow_up_date"))
    next_appointment = iso_date(values.get("next_appointment_date"))
    if delivery and consultation and consultation < delivery:
        add("consultation_date", "CONSULTATION_BEFORE_DELIVERY", "Postpartum consultation precedes delivery")
    if consultation and follow_up and follow_up < consultation:
        add("follow_up_date", "FOLLOW_UP_BEFORE_CONSULTATION", "Follow-up precedes consultation")
    if consultation and next_appointment and next_appointment < consultation:
        add("next_appointment_date", "APPOINTMENT_BEFORE_CONSULTATION", "Next appointment precedes consultation")

    mode = values.get("delivery_mode")
    indication = values.get("cesarean_indication")
    if indication and mode not in {"PLANNED_CESAREAN", "EMERGENCY_CESAREAN"}:
        add("cesarean_indication", "CESAREAN_INDICATION_NOT_APPLICABLE", "Indication supplied for non-cesarean delivery")

    transferred = values.get("transferred")
    referral = values.get("referral_facility")
    if transferred is False and referral:
        add("referral_facility", "REFERRAL_NOT_APPLICABLE", "Referral facility supplied without transfer")

    return issues


def validate_cross_page(records: list[dict[str, Any]]) -> dict[str, list[ValidationIssue]]:
    """Compare repeated values across pages. Input records must contain form_id and fields."""
    occurrences: dict[str, list[tuple[str, Any]]] = {}
    for record in records:
        form_id = str(record.get("form_id", "unknown"))
        fields = record.get("fields", {})
        for name in ("birth_weight_g", "newborn_sex", "head_circumference_cm", "delivery_date"):
            if name in fields and fields[name] is not None:
                occurrences.setdefault(name, []).append((form_id, fields[name]))

    result: dict[str, list[ValidationIssue]] = {}
    for name, entries in occurrences.items():
        distinct = {str(value) for _, value in entries}
        if len(distinct) > 1:
            result[name] = [
                ValidationIssue(
                    "CROSS_PAGE_CONFLICT",
                    f"Conflicting {name} values: " + ", ".join(f"{form}={value}" for form, value in entries),
                    "error",
                )
            ]
    return result


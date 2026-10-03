from midwife_extractor.pipeline import ExtractionPipeline


def test_valid_numeric_fields_become_known():
    result = ExtractionPipeline().extract(
        "late_postnatal_newborn",
        {
            "temperature_c": {"text": "36.8 °C", "ocr_score": 0.98, "image_quality": 0.95},
            "weight_g": {"text": "5218 g", "ocr_score": 0.97, "image_quality": 0.93},
        },
    )
    assert result["fields"]["temperature_c"]["value"] == 36.8
    assert result["fields"]["temperature_c"]["status"] == "KNOWN"
    assert result["fields"]["weight_g"]["value"] == 5218


def test_implausible_temperature_needs_review_despite_high_ocr_score():
    result = ExtractionPipeline().extract(
        "late_postnatal_newborn",
        {"temperature_c": {"text": "87.2", "ocr_score": 0.99, "image_quality": 0.99}},
    )
    field = result["fields"]["temperature_c"]
    assert field["status"] == "NEEDS_REVIEW"
    assert field["confidence"] < 0.7
    assert field["evidence"]["validation_issues"][0]["code"] == "OUTSIDE_PLAUSIBLE_RANGE"


def test_blank_is_not_provided():
    result = ExtractionPipeline().extract(
        "late_postnatal_newborn",
        {"treatment": {"text": "", "ocr_score": 0.0, "image_quality": 0.9}},
    )
    assert result["fields"]["treatment"]["status"] == "NOT_PROVIDED"


def test_invalid_blood_pressure_order_flags_both_fields():
    result = ExtractionPipeline().extract(
        "early_postpartum_mother",
        {
            "systolic_bp_mmhg": {"text": "71", "ocr_score": 0.99, "image_quality": 0.99},
            "diastolic_bp_mmhg": {"text": "110", "ocr_score": 0.99, "image_quality": 0.99},
        },
    )
    assert result["fields"]["systolic_bp_mmhg"]["status"] == "NEEDS_REVIEW"
    assert result["fields"]["diastolic_bp_mmhg"]["status"] == "NEEDS_REVIEW"

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .backends import OCRBackend
from .imaging import assess_quality, checkbox_ink_score, crop_normalized, load_rgb
from .models import RawCandidate


def load_template(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def extract_candidates(
    image_path: str | Path,
    template: dict[str, Any],
    backend: OCRBackend,
) -> dict[str, RawCandidate]:
    image = load_rgb(image_path)
    expected_ratio = template.get("aspect_ratio")
    if expected_ratio and abs(image.width / image.height - expected_ratio) > 0.08:
        raise ValueError("Image must be perspective-aligned to the selected template before extraction")

    candidates: dict[str, RawCandidate] = {}
    for name, config in template["fields"].items():
        kind = config.get("kind", "ocr")
        if kind == "ocr":
            crop = crop_normalized(image, config["bbox"], config.get("padding_px", 3))
            candidate = backend.recognize(crop, name, config)
            candidate.image_quality = assess_quality(crop).overall
            candidates[name] = candidate
        elif kind == "checkbox":
            crop = crop_normalized(image, config["bbox"])
            ink = checkbox_ink_score(crop)
            threshold = config.get("checked_threshold", 0.15)
            distance = min(1.0, abs(ink - threshold) / max(threshold, 0.01))
            candidates[name] = RawCandidate(
                text="true" if ink >= threshold else "false",
                ocr_score=0.5 + 0.5 * distance,
                # A correctly empty checkbox has deliberately little visual detail;
                # generic OCR sharpness is therefore not meaningful for this extractor.
                image_quality=1.0,
                source="checkbox_ink",
            )
        elif kind == "checkbox_enum":
            scores = {
                option: checkbox_ink_score(crop_normalized(image, box))
                for option, box in config["options"].items()
            }
            ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            best_name, best_score = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0.0
            minimum = config.get("checked_threshold", 0.15)
            candidates[name] = RawCandidate(
                text=best_name if best_score >= minimum else None,
                ocr_score=min(1.0, 0.5 + max(0.0, best_score - second_score) * 2),
                second_choice_score=min(1.0, 0.5 + second_score * 2),
                image_quality=1.0,
                source="checkbox_enum",
            )
        else:
            raise ValueError(f"Unsupported extraction kind {kind!r} for {name}")
    return candidates

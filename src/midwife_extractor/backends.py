from __future__ import annotations

from typing import Any, Protocol

from PIL import Image

from .models import RawCandidate


class OCRBackend(Protocol):
    def recognize(self, image: Image.Image, field_name: str, spec: dict[str, Any]) -> RawCandidate: ...


class PaddleOCRBackend:
    """Optional PaddleOCR adapter. The dependency and model weights are loaded lazily."""

    def __init__(self, lang: str = "fr") -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError("Install the OCR extra: uv sync --extra ocr") from exc
        self.engine = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            enable_mkldnn=False,
        )

    def recognize(self, image: Image.Image, field_name: str, spec: dict[str, Any]) -> RawCandidate:
        import numpy as np

        predictions = list(self.engine.predict(np.asarray(image)))
        texts: list[str] = []
        scores: list[float] = []
        for prediction in predictions:
            data = getattr(prediction, "json", prediction)
            if callable(data):
                data = data()
            if isinstance(data, dict) and "res" in data:
                data = data["res"]
            if isinstance(data, dict):
                texts.extend(str(value) for value in data.get("rec_texts", []))
                scores.extend(float(value) for value in data.get("rec_scores", []))
        text = " ".join(texts).strip() or None
        score = sum(scores) / len(scores) if scores else 0.0
        # Paddle's per-detection scores are not alternate hypotheses for the same text,
        # so they must not be used as a best-vs-second recognition margin.
        return RawCandidate(text=text, ocr_score=score, source="paddleocr")

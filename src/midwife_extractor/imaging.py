from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps


@dataclass(slots=True)
class ImageQuality:
    sharpness: float
    contrast: float
    brightness: float
    overall: float


def load_rgb(path: str | Path) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def normalized_box(box: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    if len(box) != 4 or not all(0.0 <= value <= 1.0 for value in box):
        raise ValueError(f"Expected normalized [x1,y1,x2,y2], got {box}")
    x1, y1, x2, y2 = box
    if x1 >= x2 or y1 >= y2:
        raise ValueError(f"Invalid bounding box {box}")
    return round(x1 * width), round(y1 * height), round(x2 * width), round(y2 * height)


def crop_normalized(image: Image.Image, box: list[float], padding: int = 0) -> Image.Image:
    x1, y1, x2, y2 = normalized_box(box, *image.size)
    x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
    x2, y2 = min(image.width, x2 + padding), min(image.height, y2 + padding)
    return image.crop((x1, y1, x2, y2))


def assess_quality(image: Image.Image) -> ImageQuality:
    gray = np.asarray(ImageOps.grayscale(image).resize((min(image.width, 512), min(image.height, 512))))
    gray_float = gray.astype(np.float32)
    gx = np.diff(gray_float, axis=1)
    gy = np.diff(gray_float, axis=0)
    gradient_energy = float((gx.var() + gy.var()) / 2.0)
    sharpness = min(1.0, gradient_energy / 500.0)
    p05, p95 = np.percentile(gray_float, [5, 95])
    contrast = min(1.0, float(p95 - p05) / 100.0)
    mean = float(gray_float.mean()) / 255.0
    brightness = max(0.0, 1.0 - abs(mean - 0.65) / 0.65)
    overall = round(0.45 * sharpness + 0.35 * contrast + 0.20 * brightness, 4)
    return ImageQuality(round(sharpness, 4), round(contrast, 4), round(brightness, 4), overall)


def checkbox_ink_score(image: Image.Image) -> float:
    """Estimate handwritten ink while discounting the checkbox's printed black border."""
    rgb = np.asarray(image.convert("RGB")).astype(np.int16)
    if rgb.size == 0:
        return 0.0
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    blue_pen = (blue - red > 10) & (blue - green > 5)
    dark = rgb.mean(axis=2) < 140

    # An empty printed box in the supplied forms occupies about 8–11% dark pixels.
    # A check adds colored pixels or substantially more dark pixels across the interior.
    blue_signal = float(blue_pen.mean()) * 3.0
    black_pen_signal = max(0.0, float(dark.mean()) - 0.11) * 4.0
    return round(min(1.0, max(blue_signal, black_pen_signal)), 4)


def export_template_crops(image_path: str | Path, template: dict[str, Any], output_dir: Path) -> int:
    image = load_rgb(image_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for name, config in template["fields"].items():
        if "bbox" in config:
            crop_normalized(image, config["bbox"], config.get("padding_px", 3)).save(output_dir / f"{name}.png")
            count += 1
        for option, box in config.get("options", {}).items():
            crop_normalized(image, box, 2).save(output_dir / f"{name}__{option}.png")
            count += 1
    return count

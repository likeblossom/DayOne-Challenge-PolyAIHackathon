from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_result_bundle(result: dict[str, Any], source_image: str | Path, output_json: str | Path) -> tuple[Path, Path]:
    """Save result JSON and an unmodified, content-addressed image copy beside it."""
    source = Path(source_image).resolve()
    output = Path(output_json).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    digest = file_sha256(source)
    suffix = source.suffix.lower() or ".img"
    stored_image = output.with_name(f"{output.stem}.source.{digest[:12]}{suffix}")
    if not stored_image.exists():
        shutil.copy2(source, stored_image)
    elif file_sha256(stored_image) != digest:
        raise FileExistsError(f"Refusing to replace a different image at {stored_image}")

    result["source_image"] = {
        "filename": stored_image.name,
        "sha256": digest,
        "original_filename": source.name,
        "modified": False,
    }
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output, stored_image


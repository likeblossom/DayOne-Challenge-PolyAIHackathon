from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "form_structures"


def available_forms() -> dict[str, Path]:
    forms = {}
    for path in sorted(SCHEMA_DIR.glob("[0-9][0-9]_*.schema.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        forms[data["form_id"]] = path
    return forms


def load_form(form_id: str) -> dict[str, Any]:
    forms = available_forms()
    if form_id not in forms:
        raise KeyError(f"Unknown form_id {form_id!r}; choices: {', '.join(forms)}")
    return json.loads(forms[form_id].read_text(encoding="utf-8"))


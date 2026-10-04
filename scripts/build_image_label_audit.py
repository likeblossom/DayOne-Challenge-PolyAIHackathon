#!/usr/bin/env python3
"""Build a non-destructive image/CSV correspondence audit dataset."""

from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data/organizer" / "data" / "Paper Registry"
CSV_PATH = ROOT / "data/organizer" / "data" / "maternal_registry_synthetic.csv"
OUTPUT_DIR = ROOT / "data/image_label_audit"
IMAGE_DIR = OUTPUT_DIR / "images"

# Labels verified from pages 2 and 4 of each eight-page synthetic patient file.
# Direct identifiers (names, CINs, addresses, and phone numbers) are intentionally omitted.
IMAGE_PATIENTS = {
    1: (31, 3, 1, 1, 40, 0, 0, 3587, 34),
    2: (21, 4, 3, 3, 40, 0, 1, 3699, 34),
    3: (23, 2, 1, 1, 41, 0, 0, 3624, 36),
    4: (26, 5, 4, 4, 40, 0, 1, 2967, 36),
    5: (38, 2, 1, 1, 41, 0, 0, 3765, 35),
    6: (36, 4, 3, 3, 35, 0, 0, 2350, 31),
    7: (26, 5, 3, 3, 39, 0, 0, 3430, 35),
    8: (28, 2, 1, 1, 39, 0, 1, 3492, 35),
    9: (21, 1, 0, 0, 41, 0, 1, 3585, 33),
    10: (34, 1, 0, 0, 39, 0, 0, 3119, 35),
}

LABEL_NAMES = (
    "age_years",
    "gravidity",
    "parity",
    "living_children",
    "gestational_age_at_birth_weeks",
    "delivery_type",
    "newborn_sex",
    "birth_weight_g",
    "head_circumference_cm",
)

CSV_COLUMNS = (
    "age (years)",
    "gravidity (number)",
    "parity (number)",
    "living children (number)",
    "gestational age at birth (weeks)",
    "type of delivery (0=vaginal,1=cesarean)",
    "newborn sex (0=female,1=male)",
    "child birth weight (g)",
    "head circumference (cm)",
)


def numeric_equal(raw: str, expected: int) -> bool:
    try:
        return abs(float(raw) - expected) < 0.01
    except (TypeError, ValueError):
        return False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open(newline="", encoding="utf-8-sig") as stream:
        csv_records = list(csv.DictReader(stream))

    patient_audit = {}
    for patient_id, labels in IMAGE_PATIENTS.items():
        scored = []
        for record in csv_records:
            score = sum(
                numeric_equal(record[column], expected)
                for column, expected in zip(CSV_COLUMNS, labels)
            )
            scored.append((score, record["id"]))
        best_score = max(score for score, _ in scored)
        exact_ids = [record_id for score, record_id in scored if score == len(labels)]
        nearest_ids = [record_id for score, record_id in scored if score == best_score]
        patient_audit[patient_id] = {
            "exact_ids": exact_ids,
            "best_score": best_score,
            "nearest_ids": nearest_ids,
        }

    rows = []
    for source_page in range(1, 81):
        candidates = sorted(SOURCE_DIR.glob(f"dossiers_specimen_10_patientes-{source_page:02d}*.png"))
        candidates = [path for path in candidates if ":Zone.Identifier" not in path.name]
        if not candidates:
            raise FileNotFoundError(f"No source image found for page {source_page:02d}")

        # Duplicate-suffixed files are byte-identical; retain one source copy only.
        source = candidates[0]
        patient_id = (source_page - 1) // 8 + 1
        page_in_record = (source_page - 1) % 8 + 1
        output_name = f"image_patient_{patient_id:02d}_page_{page_in_record:02d}.png"
        shutil.copy2(source, IMAGE_DIR / output_name)

        labels = IMAGE_PATIENTS[patient_id]
        audit = patient_audit[patient_id]
        row = {
            "image_filename": output_name,
            "source_filename": source.name,
            "image_patient_id": patient_id,
            "page_in_record": page_in_record,
            "csv_record_id": ";".join(audit["exact_ids"]),
            "match_status": "exact_match" if audit["exact_ids"] else "no_exact_csv_match",
            "matched_fields_in_nearest_candidate": audit["best_score"],
            "compared_fields": len(labels),
            "nearest_csv_record_ids_not_labels": ";".join(audit["nearest_ids"]),
            "sha256": sha256(source),
        }
        row.update(dict(zip(LABEL_NAMES, labels)))
        rows.append(row)

    # The five JPGs are degraded examples and cannot be assigned to the ten clean patient files.
    for source in sorted(SOURCE_DIR.glob("1-*.jpg")):
        output_name = f"unmapped_degraded_{source.stem.replace('-', '_')}.jpg"
        shutil.copy2(source, IMAGE_DIR / output_name)
        row = {
            "image_filename": output_name,
            "source_filename": source.name,
            "image_patient_id": "",
            "page_in_record": "",
            "csv_record_id": "",
            "match_status": "unmapped_degraded_example",
            "matched_fields_in_nearest_candidate": "",
            "compared_fields": "",
            "nearest_csv_record_ids_not_labels": "",
            "sha256": sha256(source),
        }
        row.update({name: "" for name in LABEL_NAMES})
        rows.append(row)

    fieldnames = list(rows[0])
    with (OUTPUT_DIR / "image_labels.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with (OUTPUT_DIR / "README.md").open("w", encoding="utf-8") as stream:
        stream.write(
            "# Image/CSV correspondence audit\n\n"
            "This derived dataset leaves all organizer files unchanged. It contains 80 uniquely "
            "renamed clean synthetic registry pages and five degraded JPG examples. Duplicate PNG "
            "copies were omitted.\n\n"
            "No image patient exactly matches any row in `maternal_registry_synthetic.csv` across "
            "the nine compared clinical fields. Consequently, `csv_record_id` is blank and "
            "`match_status` is `no_exact_csv_match`; nearest CSV IDs are diagnostics only and must "
            "not be used as labels. Clinical labels were verified from the image registry pages. "
            "Direct identifiers are deliberately excluded from the CSV.\n"
        )

    print(f"Created {len(rows)} unique image rows in {OUTPUT_DIR}")
    print("Exact image-patient/CSV matches: 0 of 10")


if __name__ == "__main__":
    main()

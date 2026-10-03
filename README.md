# Online Midwife

This project converts a photographed maternal form into validated JSON.

## How prediction works

```text
Form image
  → crop each field
  → read text with OCR and detect checkboxes
  → convert values to numbers, dates, booleans, or categories
  → validate the values
  → save the JSON and original image together
```

## Confidence

Each field receives a score from 0 to 1:

```text
40% OCR confidence
15% image quality
15% parsing success
10% allowed-value match
10% agreement between models
10% gap between the best and second prediction
```

A validation error subtracts `0.40`; a warning subtracts `0.20`.

- Score `≥ 0.85` and valid → `KNOWN`
- Invalid or lower confidence → `NEEDS_REVIEW`
- Blank → `NOT_PROVIDED`
- Unreadable image → `ILLEGIBLE`

## Validation

Validation checks simple rules:

- Correct type: number, date, boolean, or category
- Plausible range: for example, temperature cannot be `87°C`
- Relationships: systolic pressure must exceed diastolic pressure
- Dates: a postpartum visit cannot occur before delivery
- Form logic: a cesarean indication requires a cesarean delivery

Validation does not diagnose patients. It only detects likely extraction mistakes.

## Run

```bash
uv sync --extra ocr --extra dev
uv run pytest -q

uv run python -m midwife_extractor image \
  dayone-participants/data/Paper\ Registry/dossiers_specimen_10_patientes-08.png \
  templates/08_late_postnatal_newborn.template.json \
  --lang fr \
  --output output/patient_01_page_08.json
```

The command saves the JSON and an unchanged copy of the form image side by side.

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backends import PaddleOCRBackend
from .imaging import export_template_crops
from .pipeline import ExtractionPipeline
from .schemas import available_forms
from .storage import save_result_bundle
from .template_extraction import extract_candidates, load_template


def command_forms(_: argparse.Namespace) -> int:
    for form_id, path in available_forms().items():
        print(f"{form_id}\t{path.name}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    form_id = args.form or payload.get("form_id")
    if not form_id:
        raise SystemExit("Supply --form or form_id in the prediction file")
    candidates = payload.get("candidates", payload)
    result = ExtractionPipeline(args.known_threshold).extract(form_id, candidates)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


def command_crops(args: argparse.Namespace) -> int:
    template = load_template(args.template)
    count = export_template_crops(args.image, template, Path(args.output_dir))
    print(f"Exported {count} field crops to {args.output_dir}")
    return 0


def command_image(args: argparse.Namespace) -> int:
    template = load_template(args.template)
    backend = PaddleOCRBackend(lang=args.lang)
    candidates = extract_candidates(args.image, template, backend)
    result = ExtractionPipeline(args.known_threshold).extract(template["form_id"], candidates)
    if args.output:
        output, stored_image = save_result_bundle(result, args.image, args.output)
        print(f"Saved JSON: {output}")
        print(f"Saved source image: {stored_image}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Warning: use --output to save the source image alongside the JSON")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="midwife-extract")
    subparsers = parser.add_subparsers(dest="command", required=True)

    forms = subparsers.add_parser("forms", help="List supported form schemas")
    forms.set_defaults(func=command_forms)

    validate = subparsers.add_parser("validate", help="Parse, score, and validate OCR candidates")
    validate.add_argument("predictions", help="JSON file containing raw OCR candidates")
    validate.add_argument("--form", help="Form ID; defaults to form_id in the JSON")
    validate.add_argument("--known-threshold", type=float, default=0.85)
    validate.add_argument("--output", help="Write result JSON to this path")
    validate.set_defaults(func=command_validate)

    crops = subparsers.add_parser("crops", help="Export configured field crops for inspection or annotation")
    crops.add_argument("image")
    crops.add_argument("template")
    crops.add_argument("output_dir")
    crops.set_defaults(func=command_crops)

    image = subparsers.add_parser("image", help="Extract an aligned form image with PaddleOCR")
    image.add_argument("image")
    image.add_argument("template")
    image.add_argument("--lang", default="fr", help="PaddleOCR language code")
    image.add_argument("--known-threshold", type=float, default=0.85)
    image.add_argument("--output", help="JSON path; an unchanged source-image copy is saved beside it")
    image.set_defaults(func=command_image)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

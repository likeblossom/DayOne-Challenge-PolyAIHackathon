SANAD TRAINING AND EXPORT

Android runtime: ../android-app. This folder keeps model preparation, training,
evaluation helpers, schema grammar and ONNX export used by that app.

Setup: use a CUDA-compatible torch/torchvision environment, then install
requirements.txt. Do not run parallel training jobs on the same GPU.

Entry points (run from repository root):
  python scripts/generate_diverse_forms.py --help
  python -m vision_pipeline.prepare --help
  python -m vision_pipeline.train --help
  python -m vision_pipeline.all_forms.prepare --help
  python -m vision_pipeline.all_forms.train --help
  python -m vision_pipeline.date_ocr.generate --help
  python -m vision_pipeline.numeric_ocr.generate --help
  python -m vision_pipeline.date_ocr.train --help
The date trainer also trains the numeric reader with --dataset, --initial,
--output and --reports. Keep existing checkpoints; choose new output paths.

Exports/install: ../android-app/MODEL_INTEGRATION.txt.
Tests: python -m pytest tests vision_pipeline/tests -q
Slides: python -m vision_pipeline.build_pitch

All datasets live in ../data/: forms/, dates/, numbers/, organizer/,
processed/, handwriting_fonts/ and image_label_audit/. This entire directory
is Git-ignored. models/, outputs/, mobile_bundle/, mobile_install/ and
mobile_install_all_forms/ also remain local Git-ignored artifacts.
Training reports supply the pitch charts. Organizer references are provisional;
training metrics and export agreement are not Android accuracy measurements.

label_anchor_pilot/ retains shared spatial-assignment, crop and evaluation code
imported by all_forms/. Its old single-form training/pitch entry points are gone.

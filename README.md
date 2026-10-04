# Sanad

**Note: YOU NEED THE 2.8 GB MODEL FILES TO RUN THIS APP, UPLOAD IN PROGRESS**

Android app that reads eight maternal/newborn paper forms offline and saves structured records with the original image, field status and confidence.

![Android architecture](vision_pipeline/presentation/architecture.png)

We removed handwriting objects from the supplied PDF, rendered new English/French/Arabic values in 18 handwriting fonts, and added rotation, blur, noise and JPEG degradation. Labels are saved as CSV/JSONL.

We trained form/script classifiers and YOLO label/handwriting detectors, fine-tuned TrOCR for dates and numbers, and exported the models to ONNX. Android runs one OCR reader at a time. Field rules validate units, dates, ranges and consistency. Records are encrypted locally and can sync over USB.

[Build/install](android-app/README.md) · [Slides](vision_pipeline/presentation/Sanad_pitch.pptx) · [Demo](demo/form01/Sanad-form-1-demo-with-form.mp4)

All datasets are in `data/`: `forms`, `dates`, `numbers`, `organizer`, `processed`, `handwriting_fonts` and `image_label_audit`. Data, checkpoints and model packs stay local and Git-ignored.

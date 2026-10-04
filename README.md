# Sanad

## Install and run

**The APK alone is not enough. You must import the model pack once before using OCR.**

1. Download `Sanad-v0.2.0-judge-kit.zip` (about 3 GB). The download link will be added here after upload.
2. Extract **this outer ZIP**. It contains `Sanad-v0.2.0.apk`, `Sanad-models-v1.zip`, and `README.txt`.
3. On a **64-bit Android phone (Android 8 or newer)**, open the APK and allow installation from your browser/file manager if Android asks. Install Sanad.
4. Copy/download `Sanad-models-v1.zip` to the phone's **Downloads** folder. Open **Sanad → Settings (top right) → Import model pack** and select that ZIP.
5. Keep Sanad open until it says **Models ready**. Import happens once; no computer, account, Wi-Fi or USB connection is needed for OCR afterward.
6. Choose a registry when prompted. Tap the **paperclip** to select a form image, or the **camera** to photograph one. Wait for extraction, check/edit the fields, then submit. Tap the attached image to zoom; use **Saved records** to reopen saved results.

## Results

**Organizer benchmark:** 80 supplied pages (10 per form), 4,705 eligible fields. These are organizer-provided synthetic specimens, separate from our generated training data.
[Results](vision_pipeline/reports/all_forms/organizer_results.json) · [Scoring code](vision_pipeline/all_forms/evaluate.py)

| Extraction metric | Result |
|---|---:|
| Form classification | 97.5% (78/80 pages) |
| Field value exact match | 73.5% (3,458/4,705) |
| Field value match ignoring case, accents, punctuation and spacing | 80.1% (3,770/4,705) |

Form accuracy.

| Form | Normalized field match |
|---|---:|
| Pregnancy/postpartum monitoring | 70.5% |
| Identification and history | 84.5% |
| Current pregnancy | 78.1% |
| Labor and delivery | 87.4% |
| Early postpartum — mother | 83.2% |
| Early postnatal — newborn | 90.0% |
| Late postpartum — mother | 66.9% |
| Late postnatal — newborn | 87.3% |

**Generated held-out OCR crops:** date reader **94.8% exact match / 1.03% character error rate** on 600 crops; numeric reader **78.4% / 4.74%** on 900 crops.
[Date report](vision_pipeline/reports/date_ocr/training.json) · [Numeric report](vision_pipeline/reports/numeric_ocr/training.json)

**Android measurements:** one complete organizer specimen took **37.016 seconds**, sampled process memory reached **~0.91 GB**, and model storage is **2.94 GB**. [Phone measurements](android-app/MODEL_INTEGRATION.txt)

## What we built

Android app that reads eight maternal/newborn paper forms offline and saves structured records with the original image, field status and confidence.

![Android architecture](vision_pipeline/presentation/architecture.png)

We removed handwriting objects from the supplied PDF, rendered new English/French/Arabic values in 18 handwriting fonts, and added rotation, blur, noise and JPEG degradation. Labels are saved as CSV/JSONL.

We trained form/script classifiers and YOLO label/handwriting detectors, fine-tuned TrOCR for dates and numbers, and exported the models to ONNX. Android runs one OCR reader at a time. Field rules validate units, dates, ranges and consistency. Records are encrypted locally and can sync over USB.

[Build/install](android-app/README.md) · [Slides](vision_pipeline/presentation/Sanad_pitch.pptx) · [Demo](demo/form01/Sanad-form-1-demo-with-form.mp4)

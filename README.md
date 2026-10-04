# Sanad

## Install and run

**The APK alone is not enough. You must import the model pack once before using OCR.**

1. Download `Sanad-v0.2.0-judge-kit.zip` (about 3 GB). The download link will be added here after upload.
2. Extract **this outer ZIP**. It contains `Sanad-v0.2.0.apk`, `Sanad-models-v1.zip`, and `README.txt`.
3. On a **64-bit Android phone (Android 8 or newer)**, open the APK and allow installation from your browser/file manager if Android asks. Install Sanad.
4. Copy/download `Sanad-models-v1.zip` to the phone's **Downloads** folder. Open **Sanad → Settings (top right) → Import model pack** and select that ZIP.
5. Keep Sanad open until it says **Models ready**. Import happens once; no computer, account, Wi-Fi or USB connection is needed for OCR afterward.
6. Choose a registry when prompted. Tap the **paperclip** to select a form image, or the **camera** to photograph one. Wait for extraction, check/edit the fields, then submit. Tap the attached image to zoom; use **Saved records** to reopen saved results.

## What we built

Android app that reads eight maternal/newborn paper forms offline and saves structured records with the original image, field status and confidence.

![Android architecture](vision_pipeline/presentation/architecture.png)

We removed handwriting objects from the supplied PDF, rendered new English/French/Arabic values in 18 handwriting fonts, and added rotation, blur, noise and JPEG degradation. Labels are saved as CSV/JSONL.

We trained form/script classifiers and YOLO label/handwriting detectors, fine-tuned TrOCR for dates and numbers, and exported the models to ONNX. Android runs one OCR reader at a time. Field rules validate units, dates, ranges and consistency. Records are encrypted locally and can sync over USB.

[Build/install](android-app/README.md) · [Slides](vision_pipeline/presentation/Sanad_pitch.pptx) · [Demo](demo/form01/Sanad-form-1-demo-with-form.mp4)

## Results

**Organizer benchmark:** 80 supplied pages (10 per form), 4,705 eligible fields. These are organizer-provided synthetic specimens, separate from our generated training data. References were extracted from PDF vectors and are provisional, not independently human-adjudicated. This is an inspected development benchmark run on PC, **not aggregate Android accuracy or a sealed test**. [Results](vision_pipeline/reports/all_forms/organizer_results.json) · [Scoring code](vision_pipeline/all_forms/evaluate.py)

| Extraction metric | Result |
|---|---:|
| Form classification | 97.5% (78/80 pages) |
| Field value exact match | 73.5% (3,458/4,705) |
| Field value match ignoring case, accents, punctuation and spacing | 80.1% (3,770/4,705) |
| Filled text only, exact / normalized | 42.1% / 59.1% (774 / 1,086 of 1,839) |
| Blank text fields given a spurious value | 0.66% (14/2,137) |
| Fields flagged for review in this benchmark snapshot | 41.1% (1,932/4,705) |

All-field scores include blank fields and selections, so they are not handwriting-only accuracy. Normalization is a permissive formatting comparison, not a clinical-equivalence check; it can hide punctuation differences. Review rate is not status accuracy, and the current Android review policy differs from this earlier benchmark snapshot.

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

**Generated held-out OCR crops:** date reader **94.8% exact match / 1.03% character error rate** on 600 crops; numeric reader **78.4% / 4.74%** on 900 crops. These test the specialist readers on our generated data, not the whole app. [Date report](vision_pipeline/reports/date_ocr/training.json) · [Numeric report](vision_pipeline/reports/numeric_ocr/training.json)

**Android measurements:** one complete organizer specimen took **37.016 seconds** on a DOOGEE S200 Plus (Android 15); sampled process memory reached **~0.91 GB**, and model storage is **2.94 GB**. This is a single-page timing and sampled memory, not average latency, continuous peak RAM, or a minimum device requirement. The model-pack import and numeric record-ID reader were also checked on the phone. [Phone measurements](android-app/MODEL_INTEGRATION.txt)

**Offline/review checks:** eight on-device workflow tests covered encrypted persistence, retry, queue and review. A USB sync smoke test committed a record, kept exactly one database row after repeat upload, and reported offline after the USB reverse connection was removed. These are bounded functional checks, not a claim of zero loss under every failure. [Test log](android-app/docs/USB_UPDATE_RESULTS.txt) · [Review policy](android-app/docs/CONFIDENCE_POLICY.txt)

## Record lifecycle and limits

`CAPTURED → PENDING_AI → AI_PROCESSED → NEEDS_REVIEW → VALIDATED → PATIENT_MATCHED → REGISTERED → SYNCED`. Failed extraction/sync can be retried; replacing a photo preserves the previous version. Review offers edits, photo retakes and manual entry. Submitted records link to the user-selected registry code; repeated forms prompt for a new visit or correction.

Field values retain explicit statuses and confidence. Confidence is heuristic, not calibrated; aggregate status accuracy and per-language organizer accuracy have not been measured. Arabic handwriting, longer text and degraded photos remain limitations. This is a native Android conversational prototype, not a WhatsApp integration. Local records/images are encrypted; complete production role-based access and automatic redaction of identifiers in attached images are not implemented. Use only the supplied/generated non-patient examples. No diagnosis or treatment recommendations.

All datasets are in `data/`: `forms`, `dates`, `numbers`, `organizer`, `processed`, `handwriting_fonts` and `image_label_audit`. Data, checkpoints and model packs stay local and Git-ignored.

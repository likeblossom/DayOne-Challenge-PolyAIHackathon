# Sanad Android

Native Java app with offline ONNX inference for eight forms. Photos and records are encrypted with Android Keystore. Results retain values, statuses, confidence and raw OCR; tap the attached image to zoom.

## Build and install

For judges: install `Sanad-v0.2.0.apk`, download `Sanad-models-v1.zip` to the
phone, then tap **Import model pack** in Sanad (also available in Settings).
Do not unzip it. Wait for **Models ready**; OCR then works offline.
Allow about 6 GB free for the downloaded ZIP plus installed models.
Use a 64-bit Android phone. The APK accepts only its matching verified pack.

Requires JDK 17, Android SDK 35 and an authorized Android device. From this folder:

```sh
./gradlew --no-daemon --max-workers=2 :app:assembleDebug :app:testDebugUnitTest
adb install -r app/build/outputs/apk/debug/app-debug.apk
python tools/install_model_pack.py --serial DEVICE_SERIAL
adb shell am start -n org.dayone.midwife/.MainActivity
```

The ~2.94 GB model pack is installed separately from `../vision_pipeline/mobile_install_all_forms/`. It is not included in Git. Original checkpoints and datasets remain local and ignored.

Build judge artifacts from repository root:

```sh
python android-app/tools/package_models.py
python android-app/tools/build_release.py
```

Keep `android-app/.signing/` private and backed up; it is needed to sign updates.
Release APKs use a different signing key from debug builds. Do not uninstall an
existing debug app with saved records just to install a release; use another device.

## Use

Select a registry, upload or photograph a page, inspect the result and submit. Valid fields at 70%+ pass; unresolved grammar or recognition issues require review. Confidence is uncalibrated. Submitted records remain available offline.

For USB sync, run on the connected computer:

```sh
python tools/usb_database.py --serial DEVICE_SERIAL
```

Uses `adb reverse` and a local socket, not Wi-Fi. [USB details](USB_SYNC.txt) · [Model export](MODEL_INTEGRATION.txt) · [Review policy](docs/CONFIDENCE_POLICY.txt).

Normal builds block screenshots. `:app:assembleDemo` enables capture for specimen demos; reinstall the normal debug build afterward. Do not uninstall or clear app data: that removes local records and keys.

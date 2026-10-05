"""Compare PC-trained preprocessing with the exact RGB input captured on Android."""
import argparse
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(ROOT / 'vision_pipeline/mobile_install_all_forms/forms.onnx'),
                                   sess_options=options, providers=['CPUExecutionProvider'])
    refs = [json.loads(line) for line in (ROOT / 'data/processed/organizer_test/labels.jsonl').read_text().splitlines()]
    results = []
    for ref in refs:
        folder = args.capture / f"page_{ref['pdf_page']:02d}"
        if not (folder / 'classifier.png').exists():
            continue
        expected = ImageOps.pad(Image.open(ROOT / ref['image']).convert('RGB'), (320, 320),
                                color='white', method=Image.Resampling.BILINEAR)
        captured = Image.open(folder / 'classifier.png').convert('RGB')
        outputs = {}
        for name, image in [('pc_pixels', expected), ('android_pixels', captured)]:
            pixels = np.asarray(image, dtype=np.float32) / 255
            pixels = (pixels - np.array([.485, .456, .406], dtype=np.float32)) / np.array([.229, .224, .225], dtype=np.float32)
            logits = session.run(None, {'pixels': pixels.transpose(2, 0, 1)[None]})[0][0]
            prob = np.exp(logits - logits.max()); prob /= prob.sum()
            outputs[name] = dict(label=int(prob.argmax()), confidence=float(prob.max()))
        expected.save(folder / 'classifier_pc.png')
        row = dict(page=ref['pdf_page'], expected=int(ref['form_id'].split('_')[0])-1,
                   pixel_mae=float(np.abs(np.asarray(expected, dtype=float)-np.asarray(captured, dtype=float)).mean()),
                   phone=json.loads((folder / 'result.json').read_text()), **outputs)
        results.append(row)
        print(json.dumps(row), flush=True)
    (args.capture / 'parity.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

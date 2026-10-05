"""CPU ONNX classifier diagnostic on an explicit, fingerprinted page manifest."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

from .common import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((args.pack / 'forms.json').read_text())
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(args.pack / 'forms.onnx'), options,
                                   providers=['CPUExecutionProvider'])
    rows = []
    for truth in map(json.loads, args.labels.read_text().splitlines()):
        with Image.open(ROOT / truth['image']) as source:
            image = ImageOps.pad(source.convert('RGB'), (config['size'], config['size']),
                                 method=Image.Resampling.BILINEAR, color='white')
        pixels = np.asarray(image, dtype=np.float32) / 255
        pixels = (pixels - np.array([.485, .456, .406], dtype=np.float32)) / np.array([.229, .224, .225], dtype=np.float32)
        logits = session.run(None, {'pixels': pixels.transpose(2, 0, 1)[None]})[0][0]
        probs = np.exp(logits - logits.max()); probs /= probs.sum()
        predicted = int(config['classes'][int(probs.argmax())]) + 1
        rows.append(dict(case=truth.get('case_id', truth['pdf_page']),
                         expected=int(truth['form_id'].split('_')[0]), predicted=predicted,
                         confidence=float(probs.max())))
    report = dict(scope='PC ONNX development classifier diagnostic, not Android end-to-end accuracy',
                  model_sha256=hashlib.sha256((args.pack / 'forms.onnx').read_bytes()).hexdigest(),
                  labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),
                  n=len(rows), correct=sum(r['expected']==r['predicted'] for r in rows),
                  accepted_correct=sum(r['expected']==r['predicted'] and r['confidence']>=.75 for r in rows),
                  confident_wrong=sum(r['expected']!=r['predicted'] and r['confidence']>=.75 for r in rows), rows=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))


if __name__ == '__main__':
    main()

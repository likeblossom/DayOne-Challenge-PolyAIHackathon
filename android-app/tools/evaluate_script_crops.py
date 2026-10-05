"""Classifier-only replay of exact phone text crops against independent references."""
import argparse
import collections
import hashlib
import io
import json
import re
import sys
import tarfile
import unicodedata
from pathlib import Path
import torch
from PIL import Image

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from vision_pipeline.train import classifier,preprocessing
from diagnose_edge_rules import leaves


def script(text):
    found=set()
    for letter in str(text):
        if not letter.isalpha():continue
        name=unicodedata.name(letter,'')
        found.add('arabic' if 'ARABIC' in name else 'latin' if 'LATIN' in name else 'other')
    return next(iter(found)) if len(found)==1 and 'other' not in found else None


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True)
    ap.add_argument('--labels',type=Path,required=True);ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Use a new result path')
    torch.set_num_threads(2);state=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    model=classifier(len(state['classes']));model.load_state_dict(state['state_dict']);model.eval()
    transform=preprocessing(state['size']);rows=[]
    refs={r.get('case_id',f"page_{r['pdf_page']:02d}"):r for r in map(json.loads,args.labels.read_text().splitlines())}
    summary=json.loads((args.capture/'summary.json').read_text())
    for case in summary['cases']:
        if case['status']!='ok':continue
        folder=args.capture/case['case_id'];result=json.loads((folder/'result.json').read_text());truth=refs[case['case_id']]
        with tarfile.open(folder/'crops.tar') as archive:
            for key,field in leaves(result['fields']):
                reference=truth['fields'].get(key,{})
                if not reference.get('score_eligible') or reference.get('status')!='KNOWN' or not field.get('script_prediction'):continue
                expected=script(reference.get('raw_text') or reference.get('value'))
                if expected is None:continue
                member='./'+re.sub('[^A-Za-z0-9_-]','_',key)+'.png'
                with Image.open(io.BytesIO(archive.extractfile(member).read())) as image:pixels=transform(image.convert('RGB'))
                with torch.inference_mode():probabilities=model(pixels[None]).softmax(-1)[0];label=int(probabilities.argmax())
                prediction=state['classes'][label];confidence=float(probabilities[label]);previous=field['script_prediction']
                rows.append(dict(case=case['case_id'],field=key,expected=expected,
                    phone=previous['label'],phone_confidence=previous['confidence'],
                    candidate=prediction,candidate_confidence=confidence))
    report=dict(scope='PC classifier-only replay of exact phone crops; Latin-only organizer references do not validate Arabic accuracy',
        checkpoint=str(args.checkpoint.resolve()),checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),n=len(rows),
        classes=dict(collections.Counter(r['expected'] for r in rows)),
        phone_correct=sum(r['phone']==r['expected'] for r in rows),candidate_correct=sum(r['candidate']==r['expected'] for r in rows),
        candidate_confident_wrong=sum(r['candidate']!=r['expected'] and r['candidate_confidence']>=.8 for r in rows),
        improvements=sum(r['phone']!=r['expected'] and r['candidate']==r['expected'] for r in rows),
        regressions=sum(r['phone']==r['expected'] and r['candidate']!=r['expected'] for r in rows),rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print({k:v for k,v in report.items() if k!='rows'},flush=True)


if __name__=='__main__':main()

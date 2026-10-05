"""Isolate handwriting detection/pairing changes with frozen printed anchors."""
import argparse
import json
from pathlib import Path
import torch
from PIL import Image
from ultralytics import YOLO
from .common import ROOT,DATA,BASE
from .label_anchor_pilot.infer import pair_text
from .label_anchor_pilot.evaluate import overlap,horizontal_coverage


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Preserve earlier diagnostics')
    torch.set_num_threads(2);model=YOLO(str(args.checkpoint))
    report=dict(scope='PC CPU handwriting/pairing development diagnostic with frozen original printed anchors; no OCR or Android claim',
                checkpoint=str(args.checkpoint.resolve()),pages=[])
    for truth in map(json.loads,(DATA/'organizer_test_v3/labels.jsonl').read_text().splitlines()):
        number=truth['pdf_page'];cached=json.loads((BASE/'outputs/all_forms'/f'page_{number:02d}'/'prediction.json').read_text())
        spec=json.loads((DATA/'all_forms'/truth['form_id']/'spec.json').read_text())
        priors=json.loads((DATA/'all_forms'/truth['form_id']/'pairing_priors.json').read_text())
        with Image.open(ROOT/truth['image']) as source:
            image=source.convert('RGB');size=image.size
            result=model.predict(image,imgsz=1280,rect=False,conf=.15,iou=.45,max_det=600,device='cpu',verbose=False)[0]
        candidate=[dict(quad=b.xyxyxyxy[0].numpy().tolist(),confidence=float(b.conf[0])) for b in result.obb]
        variants={}
        for name,hands in [('baseline',cached['handwriting_detections']),('candidate',candidate)]:
            pairs,_=pair_text(cached['label_detections'],hands,spec,priors);fields=[]
            for key,label in truth['fields'].items():
                if not(label.get('score_eligible') and label['kind']=='text'):continue
                glyph=label.get('glyph_bbox');pair=pairs.get(key)
                fields.append(dict(field=key,filled=label['status']=='KNOWN',matched=pair is not None,
                    covered=bool(label['status']=='KNOWN' and glyph and pair and overlap(pair,glyph,size)>=.5 and horizontal_coverage(pair,glyph,size)>=.85)))
            variants[name]=dict(detections=len(hands),filled=sum(f['filled'] for f in fields),
                covered=sum(f['covered'] for f in fields),blank_matched=sum(f['matched'] and not f['filled'] for f in fields),fields=fields)
        report['pages'].append(dict(page=number,form=truth['form_id'],variants=variants,candidate_detections=candidate))
        print(number,{name:{k:v for k,v in value.items() if k!='fields'} for name,value in variants.items()},flush=True)
    report['totals']={name:{key:sum(p['variants'][name][key] for p in report['pages']) for key in ['filled','covered','blank_matched']} for name in ['baseline','candidate']}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print(report['totals'],flush=True)


if __name__=='__main__':main()

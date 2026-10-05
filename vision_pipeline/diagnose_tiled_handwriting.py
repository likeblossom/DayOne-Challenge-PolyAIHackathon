"""CPU-only detection diagnostic; no OCR, training, or reference-guided crops."""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from ultralytics import YOLO
from .common import ROOT, DATA, BASE
from .all_forms.checkpoints import anchor_checkpoint
from .label_anchor_pilot.infer import pair_text
from .label_anchor_pilot.evaluate import overlap, horizontal_coverage


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pages',type=int,nargs='+',default=[2,10,18,26])
    ap.add_argument('--filter-only',action='store_true',help='Use cached detections only; no model inference')
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    torch.set_num_threads(2);model=None if args.filter_only else YOLO(str(anchor_checkpoint('handwriting')))
    truths={r['pdf_page']:r for r in map(json.loads,(DATA/'organizer_test_v3/labels.jsonl').read_text().splitlines())}
    report=dict(scope='PC CPU tiled handwriting development diagnostic; cached printed anchors; no OCR rerun',pages=[])
    for number in args.pages:
        truth=truths[number];image=Image.open(ROOT/truth['image']).convert('RGB');w,h=image.size
        cached=json.loads((BASE/'outputs/all_forms'/f'page_{number:02d}'/'prediction.json').read_text())
        spec=json.loads((DATA/'all_forms'/truth['form_id']/'spec.json').read_text())
        priors=json.loads((DATA/'all_forms'/truth['form_id']/'pairing_priors.json').read_text())
        started=time.monotonic();hands=[]
        # Two overlapping full-width bands increase character pixels without page registration.
        for top,bottom in ([] if args.filter_only else [(0,round(h*.60)),(round(h*.40),h)]):
            result=model.predict(image.crop((0,top,w,bottom)),imgsz=1280,rect=False,conf=.15,iou=.45,max_det=600,device='cpu',verbose=False)[0]
            for box in result.obb:
                quad=box.xyxyxyxy[0].numpy();quad[:,1]+=top
                # Do not retain a word cut at a tile's internal boundary.
                if (top>0 and quad[:,1].min()<top+3) or (bottom<h and quad[:,1].max()>bottom-3):continue
                hands.append(dict(quad=quad.tolist(),confidence=float(box.conf[0])))
        hands+=cached['handwriting_detections']
        kept=[]
        for hand in sorted(hands,key=lambda x:-x['confidence']):
            q=np.asarray(hand['quad'],np.float32);area=cv2.contourArea(q)
            if any(cv2.intersectConvexConvex(q,np.asarray(old['quad'],np.float32))[0]/max(1,min(area,cv2.contourArea(np.asarray(old['quad'],np.float32))))>.7 for old in kept):continue
            kept.append(hand)
        def not_printed(hand):
            center=tuple(map(float,np.asarray(hand['quad']).mean(0)))
            return not any(a['confidence']>=.65 and cv2.pointPolygonTest(np.asarray(a['quad'],np.float32),center,False)>=0 for a in cached['label_detections'].values())
        clean=[h for h in cached['handwriting_detections'] if not_printed(h)]
        base_pairs,_=pair_text(cached['label_detections'],clean,spec,priors)
        free=[]
        for hand in kept:
            q=np.asarray(hand['quad'],np.float32);area=cv2.contourArea(q)
            if not not_printed(hand):continue
            if any(cv2.intersectConvexConvex(q,np.asarray(old['quad'],np.float32))[0]/max(1,min(area,cv2.contourArea(np.asarray(old['quad'],np.float32))))>.3 for old in base_pairs.values()):continue
            free.append(hand)
        missing=dict(spec,bindings={k:b for k,b in spec['bindings'].items() if k not in base_pairs and k+'::note' not in base_pairs})
        extra,_=pair_text(cached['label_detections'],free,missing,priors)
        variants={}
        for name,detections in [('full',cached['handwriting_detections']),('filtered',clean),('bands',kept),('fallback',kept)]:
            pairs,_=pair_text(cached['label_detections'],detections,spec,priors)
            if name=='fallback':pairs=dict(base_pairs,**extra)
            rows=[]
            for key,field in truth['fields'].items():
                if not(field['kind']=='text' and field.get('score_eligible')):continue
                glyph=field.get('glyph_bbox');pair=pairs.get(key)
                rows.append(dict(field=key,filled=field['status']=='KNOWN',matched=pair is not None,
                    covered=bool(glyph and pair and overlap(pair,glyph,image.size)>=.5 and horizontal_coverage(pair,glyph,image.size)>=.85)))
            variants[name]=dict(detections=len(detections),filled=sum(r['filled'] for r in rows),
                covered=sum(r['covered'] for r in rows),blank_matched=sum(r['matched'] and not r['filled'] for r in rows),fields=rows)
        report['pages'].append(dict(page=number,seconds=round(time.monotonic()-started,2),variants=variants))
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
        print(number,{k:{x:y for x,y in v.items() if x!='fields'} for k,v in variants.items()},flush=True)


if __name__=='__main__':main()

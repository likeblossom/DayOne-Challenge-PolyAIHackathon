"""Refine all printed-label detectors on generated pages, preserving old weights."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from ultralytics import YOLO, settings
from .common import DATA, FORMS
from .all_forms.checkpoints import anchor_checkpoint


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--forms',type=int,nargs='+',default=list(range(1,9)))
    parser.add_argument('--epochs',type=int,default=20)
    parser.add_argument('--resume',action='store_true',help='Resume interrupted runs in this experimental output only')
    args=parser.parse_args()
    torch.set_num_threads(2)
    torch.cuda.set_per_process_memory_fraction(.25)
    settings.update({'sync':False,'wandb':False,'mlflow':False,'comet':False,'clearml':False})
    for number in args.forms:
        form=FORMS[number-1];folder=args.output/form
        if folder.exists() and not args.resume:raise FileExistsError('Refusing to overwrite '+str(folder))
        if args.resume and (folder/'audit.json').is_file():continue
        source=Path(anchor_checkpoint(form));before=hashlib.sha256(source.read_bytes()).hexdigest()
        last=folder/'weights/last.pt'
        if folder.exists() and not last.is_file():raise FileNotFoundError('No resumable checkpoint in '+str(folder))
        started=time.time();model=YOLO(str(last if last.is_file() else source))
        options=dict(data=str(DATA/'all_forms'/form/'anchors/dataset.yaml'),
            project=str(args.output),name=form,exist_ok=False,epochs=args.epochs,
            imgsz=1280,batch=2,device=0,workers=2,cache=False,amp=True,
            optimizer='AdamW',lr0=.0003,lrf=.1,patience=6,seed=20261004,
            deterministic=True,plots=False,max_det=600,fliplr=0,flipud=0,
            mosaic=0,mixup=0,degrees=15,translate=.03,scale=.15,
            hsv_h=0,hsv_s=.15,hsv_v=.2)
        metrics=model.train(resume=True) if last.is_file() else model.train(**options)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
        report=dict(form=form,initial_checkpoint=str(source),initial_sha256=before,
            dataset='Existing generated pages only; inherited font/page-disjoint splits',
            organizer_used_for_training=False,selection='Synthetic validation mAP50-95',
            seconds=round(time.time()-started),validation=metrics.results_dict)
        (folder/'audit.json').write_text(json.dumps(report,indent=2))
        del model;torch.cuda.empty_cache()


if __name__=='__main__':main()

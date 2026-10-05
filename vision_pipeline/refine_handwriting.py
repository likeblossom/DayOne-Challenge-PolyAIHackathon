"""Bounded CUDA refinement of the shared handwriting detector on synthetic pages."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from ultralytics import YOLO, settings
from .common import DATA, MODELS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--epochs',type=int,default=20)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Never overwrite an existing training run')
    torch.set_num_threads(2)
    torch.cuda.set_per_process_memory_fraction(.25)
    settings.update({'sync':False,'wandb':False,'mlflow':False,'comet':False,'clearml':False})
    source=MODELS/'all_forms_final/handwriting/weights/best.pt'
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    started=time.monotonic()
    model=YOLO(str(source))
    metrics=model.train(data=str(DATA/'all_forms/universal/handwriting/dataset.yaml'),
        project=str(args.output.parent),name=args.output.name,exist_ok=False,
        epochs=args.epochs,imgsz=1280,batch=2,device=0,workers=2,cache=False,
        amp=True,optimizer='AdamW',lr0=.0003,lrf=.1,patience=6,seed=20261005,
        deterministic=True,plots=False,max_det=600,fliplr=0,flipud=0,
        mosaic=0,mixup=0,degrees=15,translate=.03,scale=.2,
        hsv_h=0,hsv_s=.15,hsv_v=.2)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    report=dict(initial_checkpoint=str(source),initial_sha256=before,
        dataset='Existing generated pages from all eight forms plus synthetic long-line pages',
        organizer_used_for_training=False,selection='Synthetic validation mAP50-95',
        seconds=round(time.monotonic()-started),validation=metrics.results_dict)
    (args.output/'audit.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()

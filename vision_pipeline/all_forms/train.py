"""CUDA training in new directories; never overwrite the form-06 pilot."""
import argparse,time,fcntl
import torch
from ultralytics import YOLO,settings
from ..common import *

def main():
    p=argparse.ArgumentParser();p.add_argument('--forms',type=int,nargs='+',default=list(range(1,9)));p.add_argument('--epochs',type=int,default=24);p.add_argument('--handwriting',action='store_true');p.add_argument('--batch',type=int,default=4);p.add_argument('--refine',action='store_true');p.add_argument('--finish-all',action='store_true');a=p.parse_args()
    lock=open(BASE/'.training.lock','w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Another training job is active; refusing concurrent GPU training.')
    assert torch.cuda.is_available(),'CUDA required';torch.set_num_threads(4)
    settings.update({'sync':False,'wandb':False,'mlflow':False,'comet':False,'clearml':False})
    jobs=[('handwriting',DATA/'all_forms/universal/handwriting/dataset.yaml',MODELS/'long_handwriting/handwriting/weights/best.pt')] if a.handwriting else [(FORMS[n-1],DATA/'all_forms'/FORMS[n-1]/'anchors/dataset.yaml',MODELS/'yolo11n-obb.pt') for n in a.forms]
    if a.finish_all:jobs.append(('handwriting',DATA/'all_forms/universal/handwriting/dataset.yaml',MODELS/'long_handwriting/handwriting/weights/best.pt'))
    for name,dataset,initial in jobs:
        if a.finish_all and (REPORTS/'all_forms'/(name+'_final_training.json')).exists():continue
        free,total=torch.cuda.mem_get_info()
        if free<6*1024**3:raise SystemExit('Less than 6 GiB free GPU memory; training not started.')
        if a.refine:initial=MODELS/'all_forms'/name/'weights/best.pt'
        if a.finish_all:
            for parent in ['all_forms','all_forms_refined']:
                candidate=MODELS/parent/name/'weights/best.pt'
                if candidate.exists():initial=candidate
        folder=MODELS/('all_forms_final' if a.finish_all else 'all_forms_refined' if a.refine else 'all_forms')/name
        if folder.exists():raise RuntimeError(f'Refusing to overwrite training run: {folder}')
        started=time.time();model=YOLO(str(initial))
        epochs=6 if a.finish_all and name=='handwriting' else a.epochs
        metrics=model.train(data=str(dataset),epochs=epochs,imgsz=1280,batch=a.batch,device=0,workers=2,project=str(folder.parent),name=name,exist_ok=False,seed=42,deterministic=True,amp=True,plots=False,cache=False,patience=8,max_det=600,fliplr=0,flipud=0,mosaic=0,mixup=0,degrees=0,translate=.02,scale=.10,hsv_h=0,hsv_s=.1,hsv_v=.1)
        report=dict(form=name,epochs=a.epochs,seconds=round(time.time()-started),initial_weights=str(initial),best_checkpoint=str(folder/'weights/best.pt'),validation_metrics={k:float(v) for k,v in metrics.results_dict.items()},training_source='data/forms only',organizer_test_used_for_training=False)
        report['epochs']=epochs
        if name=='handwriting' and (DATA/'all_forms/universal/long_line_mix.json').exists():report['training_source']='data/forms plus existing synthetic long_handwriting pages';report['data_mix']=read_json(DATA/'all_forms/universal/long_line_mix.json')
        write_json(REPORTS/'all_forms'/(name+('_final' if a.finish_all else '_refined' if a.refine else '')+'_training.json'),report)
        del model;torch.cuda.empty_cache()
if __name__=='__main__':main()

"""Full-resolution synthetic-only form classifier refinement into a new checkpoint."""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset,DataLoader
from torchvision import transforms
from .common import ROOT,MODELS,letterbox
from .train import classifier,preprocessing,evaluate


class Pages(Dataset):
    def __init__(self,split,size,augment_geometry=False):
        self.classes=[str(i) for i in range(8)];self.rows=[]
        for manifest in sorted((ROOT/'data/forms').glob('*/annotations.jsonl')):
            for line in manifest.read_text().splitlines():
                row=json.loads(line)
                if row['split']==split:self.rows.append((manifest.parent/'images'/row['image_filename'],int(manifest.parent.name[:2])-1))
        pipeline=[transforms.Lambda(lambda im: im.convert('RGB'))]
        if split=='train':
            pipeline.extend([transforms.Lambda(lambda im:letterbox(im,size)),transforms.ColorJitter(brightness=.12,contrast=.12,saturation=.12)])
            if augment_geometry:pipeline.append(transforms.RandomRotation(20,interpolation=transforms.InterpolationMode.BILINEAR,expand=True,fill=255))
        pipeline.append(preprocessing(size))
        if split=='train':pipeline.append(transforms.RandomErasing(p=.2,scale=(.005,.035),ratio=(.3,3.3),value='random'))
        self.transform=transforms.Compose(pipeline)
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        path,label=self.rows[index]
        with Image.open(path) as image:return self.transform(image),label


class Scripts(Dataset):
    def __init__(self,split,size,sources=None,augment=False):
        self.classes=['arabic','latin'];self.rows=[]
        sources=sources or [ROOT/'data/processed'/folder for folder in ['arabic_ocr_tight_v2','latin_ocr_tight_v3']]
        for label,base in enumerate(sources):
            for line in (base/'labels.jsonl').read_text().splitlines():
                row=json.loads(line)
                if row['split']==split:self.rows.append((base/row['image'],label))
        self.transform=transforms.Compose([
            transforms.RandomRotation(5,interpolation=transforms.InterpolationMode.BILINEAR,expand=True,fill=255),
            transforms.ColorJitter(brightness=.15,contrast=.15,saturation=.1),preprocessing(size)
        ]) if split=='train' and augment else preprocessing(size)
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        path,label=self.rows[index]
        with Image.open(path) as image:return self.transform(image.convert('RGB')),label


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--task',choices=['forms','script'],default='forms')
    parser.add_argument('--size',type=int);parser.add_argument('--epochs',type=int,default=10)
    parser.add_argument('--cuda-memory-fraction',type=float,default=.23)
    parser.add_argument('--initial',type=Path)
    parser.add_argument('--augment-geometry',action='store_true')
    parser.add_argument('--arabic-script-data',type=Path)
    parser.add_argument('--latin-script-data',type=Path)
    parser.add_argument('--batch',type=int,default=16);args=parser.parse_args()
    args.size=args.size or (512 if args.task=='forms' else 160)
    if args.output.exists():raise FileExistsError('Use a new checkpoint path')
    torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(args.cuda_memory_fraction)
    torch.manual_seed(20261004);random.seed(20261004);np.random.seed(20261004)
    source=args.initial or MODELS/f'{args.task}.pt';state=torch.load(source,map_location='cpu',weights_only=True)
    classes=len(state['classes']);model=classifier(classes).cuda();model.load_state_dict(state['state_dict'])
    script_sources=[args.arabic_script_data or ROOT/'data/processed/arabic_ocr_tight_v2',args.latin_script_data or ROOT/'data/processed/latin_ocr_tight_v3']
    sets={name:(Pages(split,args.size,args.augment_geometry) if args.task=='forms' else Scripts(name,args.size,script_sources,args.augment_geometry)) for name,split in [('train','train'),('val','validation'),('test','synthetic_test')]}
    assert all(ds.classes==state['classes'] for ds in sets.values())
    loaders={name:DataLoader(ds,batch_size=args.batch,shuffle=name=='train',num_workers=2,pin_memory=True,persistent_workers=True) for name,ds in sets.items()}
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=.01)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,args.epochs)
    report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),size=args.size,task=args.task,
                source='Generated pages / exact synthetic ink crops only; inherited font-disjoint splits',
                organizer_used=False,augment_geometry=args.augment_geometry,selection='Validation accuracy, loss tie-break',history=[])
    if args.task=='script':report['datasets']=[dict(path=str(path.resolve()),labels_sha256=hashlib.sha256((path/'labels.jsonl').read_bytes()).hexdigest()) for path in script_sources]
    report['samples']={name:len(ds) for name,ds in sets.items()}
    best=(-1.,-float('inf'));started=time.time();args.output.parent.mkdir(parents=True,exist_ok=True)
    for epoch in range(1,args.epochs+1):
        model.train();total=0;seen=0
        for images,labels in loaders['train']:
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                loss=torch.nn.functional.cross_entropy(model(images.cuda()),labels.cuda(),label_smoothing=.03)
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1);optimizer.step()
            total+=float(loss.detach())*len(labels);seen+=len(labels)
        scheduler.step();validation=evaluate(model,loaders['val'],'cuda',classes)
        row=dict(epoch=epoch,loss=total/seen,validation=validation,seconds=round(time.time()-started))
        report['history'].append(row);rank=(validation['accuracy'],-validation['loss'])
        if rank>best:
            best=rank;report['best_epoch']=epoch
            torch.save(dict(state_dict=model.state_dict(),classes=state['classes'],size=args.size,
                            architecture='mobilenet_v3_small',training_source='data/forms',epoch=epoch),args.output)
        args.output.with_suffix('.training.json').write_text(json.dumps(report,indent=2));print(json.dumps(row),flush=True)
    model.load_state_dict(torch.load(args.output,map_location='cpu',weights_only=True)['state_dict'])
    report['synthetic_test']=evaluate(model,loaders['test'],'cuda',classes)
    report['seconds']=round(time.time()-started)
    args.output.with_suffix('.training.json').write_text(json.dumps(report,indent=2));print('DONE',report['synthetic_test'],flush=True)


if __name__=='__main__':main()

"""Fast CUDA baselines. Validation is synthetic only; organizer set is never opened."""
import argparse
import copy
import json
import random
import time
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets,models,transforms
from .common import *

def classifier(classes,pretrained=False):
    model=models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None)
    model.classifier[-1]=nn.Linear(model.classifier[-1].in_features,classes)
    return model

def preprocessing(size):
    return transforms.Compose([transforms.Lambda(lambda im:letterbox(im,size)),transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])

@torch.inference_mode()
def evaluate(model,loader,device,classes):
    model.eval();cm=torch.zeros((classes,classes),dtype=torch.long);loss=0.;count=0
    for x,y in loader:
        logits=model(x.to(device));loss+=nn.functional.cross_entropy(logits,y.to(device),reduction='sum').item();count+=len(y)
        for a,b in zip(y,logits.argmax(1).cpu()):cm[a,b]+=1
    return dict(accuracy=cm.diag().sum().item()/max(1,count),loss=loss/max(1,count),n=count,confusion_matrix=cm.tolist())

def train_classifier(args):
    size=320 if args.task=='forms' else 160;folder=DATA/args.task
    sets={s:datasets.ImageFolder(folder/s,transform=preprocessing(size)) for s in ['train','val','test']}
    assert all(ds.classes==sets['train'].classes for ds in sets.values())
    loaders={s:DataLoader(ds,batch_size=args.batch,shuffle=s=='train',num_workers=4,pin_memory=True,persistent_workers=True) for s,ds in sets.items()}
    model=classifier(len(sets['train'].classes),True).cuda();opt=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=.01)
    scaler=torch.amp.GradScaler('cuda');best=-1;history=[];start=time.time();MODELS.mkdir(exist_ok=True)
    for epoch in range(args.epochs):
        model.train();total=correct=n=0
        for x,y in loaders['train']:
            x=x.cuda(non_blocking=True);y=y.cuda(non_blocking=True);opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.float16):logits=model(x);loss=nn.functional.cross_entropy(logits,y)
            scaler.scale(loss).backward();scaler.step(opt);scaler.update();total+=loss.item()*len(y);correct+=(logits.argmax(1)==y).sum().item();n+=len(y)
        val=evaluate(model,loaders['val'],'cuda',len(sets['train'].classes));row=dict(epoch=epoch+1,train_loss=total/n,train_accuracy=correct/n,validation=val,seconds=round(time.time()-start))
        history.append(row);print(json.dumps(row),flush=True)
        if val['accuracy']>best:
            best=val['accuracy'];torch.save(dict(state_dict=model.state_dict(),classes=sets['train'].classes,size=size,architecture='mobilenet_v3_small',training_source='data/forms',epoch=epoch+1),MODELS/f'{args.task}.pt')
    state=torch.load(MODELS/f'{args.task}.pt',map_location='cpu',weights_only=True);model.load_state_dict(state['state_dict'])
    result=dict(task=args.task,history=history,synthetic_test=evaluate(model,loaders['test'],'cuda',len(sets['train'].classes)),classes=sets['train'].classes,seconds=round(time.time()-start),external_test_not_used=True)
    write_json(REPORTS/f'{args.task}_training.json',result);print(json.dumps(result['synthetic_test']),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('task',choices=['forms','script']);ap.add_argument('--epochs',type=int,default=6);ap.add_argument('--batch',type=int,default=32);args=ap.parse_args()
    assert torch.cuda.is_available(),'CUDA is required for this training command'
    random.seed(42);np.random.seed(42);torch.manual_seed(42);torch.set_num_threads(6)
    REPORTS.mkdir(exist_ok=True);MODELS.mkdir(exist_ok=True)
    train_classifier(args)

if __name__=='__main__':main()

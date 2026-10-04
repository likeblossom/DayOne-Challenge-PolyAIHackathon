"""Shared classifier and schema nesting for all-form model validation."""
import re
import numpy as np
import torch
from .train import classifier,preprocessing

class Predictor:
    def __init__(self,path):
        torch.set_num_threads(6)
        state=torch.load(path,map_location='cpu',weights_only=True)
        self.classes=state['classes'];self.transform=preprocessing(state['size'])
        self.model=classifier(len(self.classes)).cuda().eval();self.model.load_state_dict(state['state_dict'])
    @torch.inference_mode()
    def __call__(self,image):
        p=self.model(self.transform(image).unsqueeze(0).cuda()).softmax(1)[0].cpu().numpy();order=np.argsort(p)[::-1]
        return dict(label=self.classes[order[0]],confidence=float(p[order[0]]),margin=float(p[order[0]]-p[order[1]]),probabilities={k:float(v) for k,v in zip(self.classes,p)})

def nest_fields(fields):
    result={}
    for path,entry in fields.items():
        parts=re.findall(r'([^\.\[\]]+)|\[(\d+)\]',path)
        tokens=[int(index) if index else name for name,index in parts]
        target=result
        for i,token in enumerate(tokens):
            last=i==len(tokens)-1
            value=entry.get('value') if last else ([] if isinstance(tokens[i+1],int) else {})
            if isinstance(target,list):
                while len(target)<=token:target.append(None)
                if last or target[token] is None:target[token]=value
            elif last or token not in target:target[token]=value
            target=target[token]
    return result

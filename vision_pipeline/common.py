from pathlib import Path
import json
import re
import numpy as np
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[1]
BASE=Path(__file__).resolve().parent
DATA=ROOT/'data/processed'
MODELS=BASE/'models'
REPORTS=BASE/'reports'
FORMS=[p.stem.replace('.schema','') for p in sorted((ROOT/'data/form_structures').glob('[0-9]*.json'))]
KINDS={'text':0,'checkbox':1,'choice':2}

def read_json(path):return json.loads(Path(path).read_text())
def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def leaves(number):
    fields=read_json(ROOT/'data/form_structures'/f'{FORMS[number-1]}.schema.json')['fields'];out={}
    def walk(items,prefix=''):
        for k,s in items.items():
            key=prefix+k
            if s['type']=='object':walk(s['fields'],key+'.')
            elif s['type']=='array' and s['items']['type']=='object':walk(s['items']['fields'],key+'[].')
            else:out[key]=s
    walk(fields);return out
def wildcard(path):return re.sub(r'\[\d+\]','[]',path)
def letterbox(image,size=320):return ImageOps.pad(image.convert('RGB'),(size,size),color='white',method=Image.Resampling.BILINEAR)
def crop(image,box,margin=.16):
    w,h=image.size;x1,y1,x2,y2=box;dx=max((x2-x1)*.04,2/w);dy=max((y2-y1)*margin,2/h)
    rect=(max(0,int((x1-dx)*w)),max(0,int((y1-dy)*h)),min(w,int(np.ceil((x2+dx)*w))),min(h,int(np.ceil((y2+dy)*h))))
    if rect[2]<=rect[0] or rect[3]<=rect[1]:raise ValueError('Degenerate crop')
    return image.crop(rect),[rect[0]/w,rect[1]/h,rect[2]/w,rect[3]/h]

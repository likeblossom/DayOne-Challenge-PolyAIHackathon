"""Training preparation reads ONLY generated data; organizer test data is separate."""
import argparse
import csv
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from PIL import Image
from .common import *

def script_of(text):
    ar=bool(re.search(r'[\u0621-\u064a\u066e-\u06d3]',text));latin=bool(re.search(r'[A-Za-zÀ-ÿ]',text))
    return 'arabic' if ar and not latin else 'latin' if latin and not ar else None

def process(item):
    folder,r=item;split={'synthetic_test':'test','validation':'val','train':'train'}[r['split']]
    name=r['image_filename'];src=folder/'images'/name;im=Image.open(src).convert('RGB')
    thumbnail=DATA/'forms'/split/f'{int(folder.name[:2])-1}'/name;thumbnail.parent.mkdir(parents=True,exist_ok=True)
    letterbox(im,320).save(thumbnail,quality=92)
    ocr=[];language=[];rng=random.Random(r['random_seed'])
    textfields=[(k,f) for k,f in r['fields'].items() if f['kind']=='text' and f['status']=='KNOWN']
    rng.shuffle(textfields)
    # At most eight script examples per page: do not let dense visit tables dominate.
    for key,f in textfields[:16]:
        script=script_of(f['rendered_text'])
        if not script:continue
        if len(language)>=8:break
        path=DATA/'script'/split/script/f'{Path(name).stem}_{len(language):02d}.jpg';path.parent.mkdir(parents=True,exist_ok=True)
        patch,_=crop(im,f['bbox']);patch.thumbnail((512,128));patch.save(path,quality=95)
        language.append(str(path))
        ocr.append(dict(image=str(path.relative_to(ROOT)),text=f['rendered_text'],field=key,form=folder.name,script=script,split=split,source_image=str(src.relative_to(ROOT))))
    return split,ocr

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dataset',type=Path,default=ROOT/'data/forms');args=ap.parse_args()
    root=args.dataset.resolve()
    if root!= (ROOT/'data/forms').resolve():raise SystemExit('Training is intentionally restricted to data/forms.')
    items=[]
    for name in FORMS:
        folder=root/name
        for line in (folder/'annotations.jsonl').open():items.append((folder,json.loads(line)))
    DATA.mkdir(parents=True,exist_ok=True);counts=Counter();ocr=[]
    with ThreadPoolExecutor(8) as pool:
        for i,(split,entries) in enumerate(pool.map(process,items),1):
            counts[split]+=1;ocr.extend(entries)
            if i%400==0:print(f'prepared {i}/{len(items)}',flush=True)
    with (DATA/'ocr_crops.jsonl').open('w') as out:
        for row in ocr:out.write(json.dumps(row,ensure_ascii=False)+'\n')
    write_json(DATA/'preparation.json',dict(training_source=str(root),organizer_used_for_training=False,pages=dict(counts),script_crops=len(ocr),split_policy='Inherited font-disjoint page splits; crops never cross page splits.'))
    print(counts,len(ocr),flush=True)

if __name__=='__main__':main()

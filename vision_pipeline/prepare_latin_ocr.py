"""Tight synthetic ink crops matching detector-to-OCR geometry; no organizer data."""
import argparse
import collections
import json
import random
import re
from pathlib import Path
import numpy as np
from PIL import Image

from .common import ROOT, DATA
from .label_anchor_pilot.common import line_crop


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--per-page',type=int,default=12)
    parser.add_argument('--script',choices=['latin','arabic','numeric','date'],default='latin')
    args=parser.parse_args()
    if (args.output/'labels.jsonl').exists():
        raise FileExistsError('Choose a new dataset directory; existing labels are preserved')
    args.output.mkdir(parents=True,exist_ok=True)
    rows=[];rng=random.Random(20261004)
    for manifest in sorted((DATA/'all_forms').glob('*/ink_labels.jsonl')):
        form=manifest.parent.name
        bindings=json.loads((manifest.parent/'spec.json').read_text())['bindings']
        for line in manifest.read_text().splitlines():
            page=json.loads(line)
            source=(ROOT/'data/forms'/form/'images'/page['image']).resolve()
            if not source.is_relative_to((ROOT/'data/forms').resolve()):
                raise ValueError('Organizer/source data are not permitted for training')
            def eligible(region):
                if args.script in ('numeric','date'):
                    kind=bindings[region['field']]['schema']['type']
                    return kind=='date' if args.script=='date' else kind in ('integer','double') or region['field']=='record_code'
                own='[A-Za-zÀ-ÿ]' if args.script=='latin' else '[\u0621-\u064a]'
                other='[\u0621-\u064a]' if args.script=='latin' else '[A-Za-zÀ-ÿ]'
                return re.search(own,region['text']) and not re.search(other,region['text'])
            candidates=[region for region in page['ink'] if eligible(region)
                        and np.all(np.asarray(region['quad'])>=0) and np.all(np.asarray(region['quad'])<=1)]
            rng.shuffle(candidates)
            if not candidates:continue
            with Image.open(source) as image:
                image=image.convert('RGB')
                for region in candidates[:args.per_page]:
                    patch=line_crop(image,np.asarray(region['quad'])*np.asarray(image.size))
                    relative=Path('images')/page['split']/f'{source.stem}_{len(rows):06d}.jpg'
                    destination=args.output/relative;destination.parent.mkdir(parents=True,exist_ok=True)
                    patch.save(destination,quality=95)
                    rows.append(dict(image=str(relative),text=region['text'],split=page['split'],format=form,
                                     language=args.script,field=region['field'],source_image=str(source),quad=region['quad']))
        print(form,len(rows),flush=True)
    (args.output/'labels.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    summary=dict(counts=dict(collections.Counter(row['split'] for row in rows)),
                 source='Exact synthetic ink replay quads; production line_crop geometry; inherited page/font-disjoint splits',
                 organizer_used=False,per_page_limit=args.per_page,script=args.script)
    (args.output/'dataset.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary))


if __name__=='__main__':main()

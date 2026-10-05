"""Small, explicit visual/PDF annotation corrections; never reads model outputs."""
import argparse
import hashlib
import json
from pathlib import Path
from .common import ROOT

# Both page images were visually inspected, then independently checked against
# PDF text in (285, 470, 355, 495) points. The old annotation missed glyphs
# just above its rectangle. No other fields are claimed to have been reviewed.
CORRECTIONS={
    37:{'medications_taken':'Fer 2 cp/j'},
    39:{'medications_taken':'Fer 2 cp/j'},
}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Use a new reference directory')
    raw=args.source.read_bytes();rows=list(map(json.loads,raw.splitlines()));changes=[]
    for row in rows:
        for key,text in CORRECTIONS.get(row['pdf_page'],{}).items():
            image=ROOT/row['image']
            if hashlib.sha256(image.read_bytes()).hexdigest()!=row['image_sha256']:raise ValueError('Image changed')
            field=row['fields'][key]
            if field['value'] is not None or field['raw_text']!='':raise ValueError('Unexpected source reference')
            changes.append(dict(page=row['pdf_page'],field=key,before=dict(field),after_text=text))
            field.update(value=text,raw_text=text,status='KNOWN',issues=[],score_eligible=True,
                         reviewed=True,reviewer='assistant visual inspection + independent PDF text',
                         source='Page image and source PDF, manually adjudicated annotation',
                         review_reason='Writing above the original annotation rectangle; not blank')
            row['provenance']+='; selected field corrections independently adjudicated'
    if len(changes)!=2:raise ValueError('Expected both adjudicated pages')
    args.output.mkdir(parents=True)
    (args.output/'labels.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    (args.output/'adjudication.json').write_text(json.dumps(dict(
        source=str(args.source.resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),
        scope='Two visually adjudicated fields only; remaining references are provisional; no model-derived labels',
        changes=changes),ensure_ascii=False,indent=2))
    print(f'{len(rows)} pages retained; {len(changes)} corrected fields; original labels unchanged')


if __name__=='__main__':main()

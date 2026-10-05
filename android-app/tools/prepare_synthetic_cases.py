"""Frozen English/French/Arabic full-page probes from existing synthetic test splits."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Keep benchmark manifests immutable')
    rows=[]
    for source in sorted((ROOT/'data/forms').glob('*/annotations.jsonl')):
        labels=[json.loads(line) for line in source.read_text().splitlines()]
        for language in ['en','fr','ar']:
            candidates=[r for r in labels if r['split']=='synthetic_test' and r['language']==language]
            if not candidates:raise ValueError('No held-out '+language+' page for '+source.parent.name)
            # Fixed ordering, independent of model predictions.
            selected=min(candidates,key=lambda r:(r['profile']!='clean',r['image_filename']))
            image=source.parent/'images'/selected['image_filename']
            fields={key:dict(value=value['canonical_value'],raw_text=value['rendered_text'],
                status=value['status'],kind=value['kind'],score_eligible=True,source='Generator labels, not OCR pseudo-labels')
                for key,value in selected['fields'].items()}
            rows.append(dict(case_id='synthetic_'+image.stem+'_'+language,pdf_page=len(rows)+1,
                image=str(image.relative_to(ROOT)),image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                form_id=selected['form_id'],fields=fields,language=language,font=selected['font_family'],
                profile=selected['profile'],synthetic=True,source_split='synthetic_test',
                provenance='Generated full pages; held-out font families, not independent real handwriting'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    print(len(rows),args.output)


if __name__=='__main__':main()

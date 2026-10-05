"""Adapt the existing incomplete photo references without inventing transcriptions."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Keep evaluation references immutable')
    source=ROOT/'data/processed/organizer_test/photo_labels.jsonl'
    rows=[]
    for number,line in enumerate(source.read_text().splitlines(),1):
        row=json.loads(line);image=ROOT/row['image']
        if hashlib.sha256(image.read_bytes()).hexdigest()!=row['image_sha256']:raise ValueError('Original image changed')
        row.update(pdf_page=number,case_id='camera_'+image.stem.replace('-','_'),
            evaluation_scope='Alternate-layout organizer camera photo; incomplete field references, no aggregate OCR accuracy claim')
        for field in row['fields'].values():
            # Only the existing eligible value is a text/numeric field.
            if field.get('score_eligible'):field['kind']='text'
        rows.append(row)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    print({'photos':len(rows),'eligible_fields':sum(f.get('score_eligible',False) for row in rows for f in row['fields'].values())})


if __name__=='__main__':main()

"""Deterministic organizer-image perturbations; labels are retained, never used for training."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image,ImageFilter

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--labels',type=Path,default=ROOT/'data/processed/organizer_test_v3/labels.jsonl');args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Use a new test-set destination')
    args.output.mkdir(parents=True);seen=set();cases=[]
    rows=[json.loads(line) for line in args.labels.read_text().splitlines()]
    for row in sorted(rows,key=lambda r:r['pdf_page']):
        if row['form_id'] in seen:continue
        seen.add(row['form_id'])
        with Image.open(ROOT/row['image']) as original:
            original=original.convert('RGB')
            for profile in ['rotated_12deg','zoomed_out','jpeg_blur','high_resolution']:
                if profile=='rotated_12deg':image=original.rotate(12,Image.Resampling.BICUBIC,expand=True,fillcolor='white')
                elif profile=='zoomed_out':
                    image=Image.new('RGB',original.size,(155,155,155))
                    small=original.resize((round(original.width*.78),round(original.height*.78)),Image.Resampling.LANCZOS)
                    image.paste(small,((image.width-small.width)//2,(image.height-small.height)//2))
                elif profile=='jpeg_blur':image=original.filter(ImageFilter.GaussianBlur(.55))
                else:image=original.resize((round(original.width*1.3),round(original.height*1.3)),Image.Resampling.BICUBIC)
                case_id=f'page_{row["pdf_page"]:02d}_{profile}';path=args.output/(case_id+'.jpg')
                image.save(path,quality=40 if profile=='jpeg_blur' else 95)
                case=dict(row,case_id=case_id,image=str(path.resolve()),image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                          perturbation=profile,source_image=row['image'],reference_geometry_valid=False,
                          source_labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest())
                # Glyph geometry belongs to the source image; do not accidentally score it after a transform.
                case['fields']={key:{k:v for k,v in field.items() if k not in ('glyph_bbox','bbox')} for key,field in row['fields'].items()}
                cases.append(case)
    (args.output/'labels.jsonl').write_text(''.join(json.dumps(case,ensure_ascii=False)+'\n' for case in cases))
    print(len(cases),'stress cases',args.output,flush=True)


if __name__=='__main__':main()

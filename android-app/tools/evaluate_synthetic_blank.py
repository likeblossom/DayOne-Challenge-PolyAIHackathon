"""High-precision blank evidence probe using held-out generator field regions."""
import argparse
import collections
import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--per-form',type=int,default=10);args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Keep reports immutable')
    rows=[];commands=[];pages=collections.Counter()
    with tempfile.TemporaryDirectory(prefix='sanad-synthetic-blank-') as temporary:
        scratch=Path(temporary)
        for source in sorted((ROOT/'data/forms').glob('*/annotations.jsonl')):
            seen=collections.Counter()
            for page in map(json.loads,source.read_text().splitlines()):
                split=page['split']
                if split not in ('validation','synthetic_test') or seen[split]>=args.per_form:continue
                seen[split]+=1;pages[split]+=1
                with Image.open(source.parent/'images'/page['image_filename']) as original:
                    image=original.convert('RGB');width,height=image.size
                    for key,field in page['fields'].items():
                        if field['kind']!='text':continue
                        x0,y0,x1,y1=field['bbox']
                        if key.endswith(('systolic_bp_mmhg','diastolic_bp_mmhg')):
                            sister=key.replace('systolic_bp_mmhg','diastolic_bp_mmhg') if key.endswith('systolic_bp_mmhg') else key.replace('diastolic_bp_mmhg','systolic_bp_mmhg')
                            other=page['fields'].get(sister)
                            if not other:continue
                            a,b,c,d=other['bbox'];x0,y0,x1,y1=min(x0,a),min(y0,b),max(x1,c),max(y1,d)
                        cx=(x0+x1)*width/2;cy=(y0+y1)*height/2;w=(x1-x0)*width;h=(y1-y0)*height
                        box=(round(cx-.6*w-4),round(cy-.6*h-3),round(cx+.6*w+4),round(cy+.6*h+3))
                        if min(box[:2])<0 or box[2]>width or box[3]>height:continue
                        path=scratch/(str(len(rows))+'.png');image.crop(box).save(path);commands.append(str(path))
                        rows.append(dict(image=page['image_filename'],form=page['form_id'],split=split,profile=page['profile'],field=key,
                            reference_status=field['status'],expected=field['canonical_value'],visible_mark=field['visible_mark']))
        java=ROOT/'android-app/app/src/main/java/org/dayone/midwife'
        blank_source=ROOT/'android-app/app/src/test/java/org/dayone/midwife/BlankEvidence.java'
        subprocess.run(['javac','-d',temporary,str(blank_source),str(java/'EdgeRuleCrop.java'),str(ROOT/'android-app/tools/BlankDiagnostic.java')],check=True)
        result=subprocess.run(['java','-cp',temporary,'BlankDiagnostic'],input='\n'.join(commands)+'\n',text=True,capture_output=True,check=True)
        answers=result.stdout.splitlines()
        if len(answers)!=len(rows):raise ValueError('Missing observations')
        for row,answer in zip(rows,answers):row['observed_blank']=answer=='true'
    counts={}
    for split in pages:
        subset=[r for r in rows if r['split']==split]
        counts[split]=dict(n=len(subset),confirmed_empty=sum(r['observed_blank'] and not r['visible_mark'] for r in subset),
            visible_mark_reported_blank=sum(r['observed_blank'] and r['visible_mark'] for r in subset))
    report=dict(scope='Pure-Java synthetic field-region replay, oracle geometry with inherited held-out font/page splits; not Android detected-region accuracy',pages=dict(pages),counts=counts,rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2));print(counts,flush=True)


if __name__=='__main__':main()

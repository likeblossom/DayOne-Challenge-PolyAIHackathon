"""Checkbox thresholds on held-out synthetic clean pages with oracle box geometry."""
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
    ap.add_argument('--per-form',type=int,default=5);args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Preserve prior results')
    rows=[];commands=[];pages=collections.Counter()
    with tempfile.TemporaryDirectory(prefix='sanad-synthetic-marks-') as temporary:
        scratch=Path(temporary)
        for source in sorted((ROOT/'data/forms').glob('*/annotations.jsonl')):
            selected=collections.Counter()
            for row in map(json.loads,source.read_text().splitlines()):
                split=row['split']
                if split not in ('validation','synthetic_test') or row['profile']!='clean' or selected[split]>=args.per_form:continue
                selected[split]+=1;pages[split]+=1
                with Image.open(source.parent/'images'/row['image_filename']) as original:
                    image=original.convert('RGB');width,height=image.size
                    for key,field in row['fields'].items():
                        components=field.get('components',[]) if field['kind']=='choice' else [dict(bbox=field['bbox'],checked=field['canonical_value'])] if field['kind']=='checkbox' else []
                        for component in components:
                            if isinstance(component.get('value'),list) or not isinstance(component.get('checked'),bool):continue
                            x0,y0,x1,y1=component['bbox'];w=(x1-x0)*width;h=(y1-y0)*height
                            cx=(x0+x1)*width/2;cy=(y0+y1)*height/2
                            box=(round(cx-.9*w-3),round(cy-.9*h-3),round(cx+.9*w+3),round(cy+.9*h+3))
                            if min(box[:2])<0 or box[2]>width or box[3]>height:continue
                            path=scratch/(str(len(rows))+'.png');image.crop(box).save(path)
                            commands.append(f'{path}\t{w}\t{h}')
                            rows.append(dict(image=row['image_filename'],form=row['form_id'],split=split,field=key,option=component.get('value'),expected=component['checked']))
        java=ROOT/'android-app/app/src/main/java/org/dayone/midwife'
        subprocess.run(['javac','-d',temporary,str(java/'CheckboxReader.java'),str(java/'EdgeRuleCrop.java'),str(ROOT/'android-app/tools/CheckboxDiagnostic.java')],check=True)
        result=subprocess.run(['java','-cp',temporary,'CheckboxDiagnostic'],input='\n'.join(commands)+'\n',text=True,capture_output=True,check=True)
        answers=result.stdout.splitlines()
        if len(answers)!=len(rows):raise ValueError('Missing checkbox observations')
        for row,answer in zip(rows,answers):row['observation']=json.loads(answer)
    summaries={}
    for split in ('validation','synthetic_test'):
        subset=[r for r in rows if r['split']==split];summaries[split]={}
        for threshold in [.04,.06,.07,.08,.10,.15,.19]:
            correct=wrong=abstained=0
            for row in subset:
                observation=row['observation'];ink=observation['ink']
                value=(True if ink>threshold else False if ink<.04 else None) if observation['located'] else None
                correct+=value is row['expected'];wrong+=value is not None and value is not row['expected'];abstained+=value is None
            summaries[split][str(threshold)]=dict(n=len(subset),correct=correct,wrong=wrong,abstained=abstained)
    report=dict(scope='Pure-Java checkbox replay on synthetic clean held-out pages with oracle box coordinates; not detected-geometry or Android accuracy',pages=dict(pages),thresholds=summaries,rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2));print(summaries,flush=True)


if __name__=='__main__':main()

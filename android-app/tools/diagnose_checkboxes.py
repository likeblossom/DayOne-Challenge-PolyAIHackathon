"""Replay phone-detected checkbox regions through the shared Java border finder."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from vision_pipeline.label_anchor_pilot.common import frame,line_crop


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--labels',type=Path,default=ROOT/'data/processed/organizer_test_v2/labels.jsonl')
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    refs={r['pdf_page']:r for r in map(json.loads,args.labels.read_text().splitlines())}
    rows=[];commands=[]
    for path in sorted(args.capture.glob('page_*/result.json')):
        page=int(path.parent.name.split('_')[1]);result=json.loads(path.read_text());truth=refs[page]
        if result.get('status')!='ok':continue
        image=Image.open(ROOT/truth['image']).convert('RGB')
        for key,mark in result['metadata'].get('mark_observations',{}).items():
            field,_,option=key.partition('::');label=truth['fields'].get(field,{})
            if 'quad' not in mark or not label.get('score_eligible') or label.get('value') is None:continue
            expected=label['value']
            if option:expected=option in expected if isinstance(expected,list) else option==str(expected)
            if not isinstance(expected,bool):continue
            quad=np.asarray(mark['quad']);center=quad.mean(0);expanded=center+(quad-center)*1.8
            _,_,_,width,height=frame(quad)
            crop=line_crop(image,expanded,pad=0);target=args.output/f'{page}_{len(rows)}.png';crop.save(target)
            commands.append(f'{target.resolve()}\t{width}\t{height}')
            rows.append(dict(page=page,field=key,expected=expected,baseline=mark['value'],crop=str(target)))
    with tempfile.TemporaryDirectory(prefix='sanad-checkbox-') as temporary:
        subprocess.run(['javac','-d',temporary,str(ROOT/'android-app/app/src/main/java/org/dayone/midwife/CheckboxReader.java'),str(ROOT/'android-app/app/src/main/java/org/dayone/midwife/EdgeRuleCrop.java'),str(ROOT/'android-app/tools/CheckboxDiagnostic.java')],check=True)
        output=subprocess.run(['java','-cp',temporary,'CheckboxDiagnostic'],input='\n'.join(commands)+'\n',text=True,capture_output=True,check=True).stdout
    for row,answer in zip(rows,map(json.loads,output.splitlines())):row.update(candidate=answer)
    report=dict(scope='PC crop replay of phone label geometry; not an Android pipeline test',n=len(rows),
        baseline_correct=sum(row['baseline']==row['expected'] for row in rows),
        candidate_correct=sum(row['candidate']['value']==row['expected'] for row in rows),
        candidate_wrong=sum(row['candidate']['value'] is not None and row['candidate']['value']!=row['expected'] for row in rows),rows=rows)
    (args.output/'summary.json').write_text(json.dumps(report,indent=2));print({k:v for k,v in report.items() if k!='rows'})


if __name__=='__main__':main()

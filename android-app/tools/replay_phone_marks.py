"""Replay exact phone checkbox PNGs, preserving original full-pipeline results."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from vision_pipeline.label_anchor_pilot.common import frame


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True)
    ap.add_argument('--labels',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Keep prior reports immutable')
    refs={r['pdf_page']:r for r in map(json.loads,args.labels.read_text().splitlines())}
    rows=[];commands=[];case_hashes={}
    with tempfile.TemporaryDirectory(prefix='sanad-exact-phone-marks-') as temporary:
        scratch=Path(temporary)
        for source in sorted(args.capture.glob('page_*/result.json')):
            number=int(source.parent.name.split('_')[1]);result=json.loads(source.read_text());truth=refs[number]
            if result.get('status')!='ok':continue
            case_hashes[source.parent.name]=hashlib.sha256(source.read_bytes()).hexdigest()
            with tarfile.open(source.parent/'crops.tar') as archive:
                for key,mark in result['metadata'].get('mark_observations',{}).items():
                    field,_,option=key.partition('::');label=truth['fields'].get(field,{})
                    if 'quad' not in mark or not label.get('score_eligible') or label.get('value') is None:continue
                    expected=label['value']
                    if option:expected=option in expected if isinstance(expected,list) else option==str(expected)
                    if not isinstance(expected,bool):continue
                    name='./mark_'+re.sub('[^A-Za-z0-9_-]','_',key)+'.png'
                    path=scratch/(str(len(rows))+'.png');path.write_bytes(archive.extractfile(name).read())
                    _,_,_,width,height=frame(np.asarray(mark['quad']))
                    commands.append(f'{path}\t{width/1.8}\t{height/1.8}')
                    rows.append(dict(page=number,field=key,expected=expected,baseline=mark['value'],baseline_ink=mark['ink_fraction'],baseline_located=mark['outline_located']))
        java=ROOT/'android-app/app/src/main/java/org/dayone/midwife'
        subprocess.run(['javac','-d',temporary,str(java/'CheckboxReader.java'),str(java/'EdgeRuleCrop.java'),str(ROOT/'android-app/tools/CheckboxDiagnostic.java')],check=True)
        result=subprocess.run(['java','-cp',temporary,'CheckboxDiagnostic'],input='\n'.join(commands)+'\n',text=True,capture_output=True,check=True)
        answers=result.stdout.splitlines()
        if len(answers)!=len(rows):raise ValueError('Missing observations')
        for row,answer in zip(rows,answers):row['candidate']=json.loads(answer)
    report=dict(scope='Pure-Java replay of exact captured Android checkbox PNGs; per-mark values, not full selection-field or Android end-to-end accuracy',
        case_result_sha256=case_hashes,labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),
        checkbox_source_sha256=hashlib.sha256((java/'CheckboxReader.java').read_bytes()).hexdigest(),n=len(rows),
        baseline_correct=sum(r['baseline'] is r['expected'] for r in rows),
        candidate_correct=sum(r['candidate']['value'] is r['expected'] for r in rows),
        candidate_wrong=sum(r['candidate']['value'] is not None and r['candidate']['value'] is not r['expected'] for r in rows),
        regressions=sum(r['baseline'] is r['expected'] and r['candidate']['value'] is not r['expected'] for r in rows),
        geometry_differences=sum(r['baseline_located']!=r['candidate']['located'] or abs(r['baseline_ink']-r['candidate']['ink'])>1e-10 for r in rows),rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print({k:v for k,v in report.items() if k not in ('rows','case_result_sha256')},flush=True)


if __name__=='__main__':main()

"""Replay conservative blank evidence using frozen PC anchors; no model training."""
import argparse
import collections
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from .common import ROOT,BASE,DATA
from .label_anchor_pilot.common import world,line_crop
from .label_anchor_pilot.infer import unit_anchor


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    rows=[];commands=[];counts=collections.Counter()
    with tempfile.TemporaryDirectory(prefix='sanad-blank-evidence-') as scratch:
        scratch=Path(scratch)
        for truth in map(json.loads,(DATA/'organizer_test_v3/labels.jsonl').read_text().splitlines()):
            number=truth['pdf_page'];pred=json.loads((BASE/'outputs/all_forms'/f'page_{number:02d}'/'prediction.json').read_text())
            spec=json.loads((DATA/'all_forms'/truth['form_id']/'spec.json').read_text())
            with Image.open(ROOT/truth['image']) as image:
                for key,field in truth['fields'].items():
                    if not(field.get('score_eligible') and field['kind']=='text'):continue
                    anchor=unit_anchor(spec['bindings'][key],pred['label_detections'])
                    if not anchor or anchor['confidence']<.85:continue
                    region=world(spec['bindings'][key]['relative_region'],anchor['quad'])
                    if key.endswith(('systolic_bp_mmhg','diastolic_bp_mmhg')):
                        sister=key.replace('systolic_bp_mmhg','diastolic_bp_mmhg') if key.endswith('systolic_bp_mmhg') else key.replace('diastolic_bp_mmhg','systolic_bp_mmhg')
                        other=unit_anchor(spec['bindings'][sister],pred['label_detections'])
                        if not other or other['confidence']<.85:continue
                        points=np.concatenate([region,world(spec['bindings'][sister]['relative_region'],other['quad'])])
                        lo=points.min(0);hi=points.max(0)
                        region=np.array([lo,[hi[0],lo[1]],hi,[lo[0],hi[1]]])
                    center=region.mean(0)
                    region=center+(region-center)*1.2
                    if np.any(region<2) or np.any(region>np.array(image.size)-2):continue
                    patch=line_crop(image,region,0);path=scratch/(str(len(rows))+'.png');patch.save(path)
                    commands.append(str(path));rows.append(dict(page=number,field=key,reference_status=field['status'],expected=field['value']))
        java=ROOT/'android-app/app/src/main/java/org/dayone/midwife'
        blank_source=ROOT/'android-app/app/src/test/java/org/dayone/midwife/BlankEvidence.java'
        subprocess.run(['javac','-d',str(scratch),str(blank_source),str(java/'EdgeRuleCrop.java'),str(ROOT/'android-app/tools/BlankDiagnostic.java')],check=True)
        result=subprocess.run(['java','-cp',str(scratch),'BlankDiagnostic'],input='\n'.join(commands)+'\n',text=True,capture_output=True,check=True)
        blank=result.stdout.splitlines();assert len(blank)==len(rows)
        for row,value,path in zip(rows,blank,commands):
            row['blank_observed']=value=='true';counts['evaluated']+=1
            expected_blank=row['reference_status']=='NOT_PROVIDED';counts['reference_blank']+=expected_blank
            counts['confirmed_blank']+=expected_blank and row['blank_observed']
            if row['blank_observed'] and not expected_blank:
                counts['false_blank']+=1
                Image.open(path).save(args.output/(str(row['page'])+'_'+Path(path).name))
        report=dict(scope='PC crop replay of pure-Java blank evidence; frozen old anchors, provisional source-PDF references; no Android claim',counts=dict(counts),rows=rows)
        (args.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(dict(counts),flush=True)


if __name__=='__main__':main()

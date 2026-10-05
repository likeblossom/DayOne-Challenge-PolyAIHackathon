"""Exact phone boundary decisions with paired PC reader outputs; not a phone accuracy claim."""
import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path
from benchmark_android import normalized
from compare_reader_reports import value

ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--capture',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Choose a new report')
    base=json.loads(args.baseline.read_text());candidate=json.loads(args.candidate.read_text())
    index=lambda report:{(r['page'],r['field']):r for r in report['rows']}
    aa,bb=index(base),index(candidate)
    if aa.keys()!=bb.keys():raise ValueError('Different case sets')
    rows=[];paths=[]
    with tempfile.TemporaryDirectory(prefix='sanad-boundary-replay-') as temporary:
        for ordinal,(key,a) in enumerate(aa.items()):
            member='./'+re.sub('[^A-Za-z0-9_-]','_',key[1])+'.png'
            with tarfile.open(args.capture/f'page_{key[0]:02d}'/'crops.tar') as archive:raw=archive.extractfile(member).read()
            path=Path(temporary)/f'{ordinal}.png';path.write_bytes(raw);paths.append(str(path))
        java=ROOT/'android-app/app/src/main/java/org/dayone/midwife'
        subprocess.run(['javac','-d',temporary,str(java/'EdgeRuleCrop.java'),str(java/'CropBoundaryEvidence.java'),str(ROOT/'android-app/tools/CropBoundaryDiagnostic.java')],check=True)
        result=subprocess.run(['java','-cp',temporary,'CropBoundaryDiagnostic'],input='\n'.join(paths)+'\n',text=True,capture_output=True,check=True)
        flags=list(map(json.loads,result.stdout.splitlines()))
        if len(flags)!=len(aa):raise ValueError('Incomplete boundary decisions')
    for (key,a),use in zip(aa.items(),flags):
        b=bb[key]
        if a['expected']!=b['expected']:raise ValueError('Reference mismatch')
        av=value(a);bv=value(b) if use else av;expected=normalized(a['expected'])
        rows.append(dict(page=key[0],field=key[1],expanded=use,expected=a['expected'],
            baseline_raw=a['candidate_raw'],candidate_raw=b['candidate_raw'] if use else a['candidate_raw'],
            baseline_value=av,candidate_value=bv,baseline_correct=normalized(av)==expected,candidate_correct=normalized(bv)==expected))
    report=dict(scope='Exact captured phone PNGs decide expansion using production Java; recognition compared using paired PC reconstructed crops, not an Android end-to-end score',
        baseline=str(args.baseline.resolve()),candidate=str(args.candidate.resolve()),
        boundary_source_sha256=hashlib.sha256((java/'CropBoundaryEvidence.java').read_bytes()).hexdigest(),n=len(rows),
        expanded=sum(r['expanded'] for r in rows),baseline_correct=sum(r['baseline_correct'] for r in rows),
        candidate_correct=sum(r['candidate_correct'] for r in rows),
        improvements=sum(not r['baseline_correct'] and r['candidate_correct'] for r in rows),
        regressions=sum(r['baseline_correct'] and not r['candidate_correct'] for r in rows),rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print({k:v for k,v in report.items() if k!='rows'},flush=True)


if __name__=='__main__':main()

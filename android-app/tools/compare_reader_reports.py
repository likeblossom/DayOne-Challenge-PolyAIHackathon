"""Paired, isolated-crop comparison; explicitly not an end-to-end Android score."""
import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from vision_pipeline.grammar import parse,normalize
from benchmark_android import normalized


def value(row):
    text=row['candidate_raw']
    if row['field'].endswith(('systolic_bp_mmhg','diastolic_bp_mmhg')):
        pair=re.fullmatch(r'(\d{1,3}(?:[.,]\d+)?)\s*/\s*(\d{1,3}(?:[.,]\d+)?)\s*(mm\s*hg|cm\s*hg|kpa)?',normalize(text),re.I)
        if pair:
            text=pair.group(1 if row['field'].endswith('systolic_bp_mmhg') else 2)+' '+(pair.group(3) or '')
    return parse(row['form'],row['field'],text)['value']


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Preserve previous comparison')
    base=json.loads(args.baseline.read_text());candidate=json.loads(args.candidate.read_text())
    def index(report):return {(r['page'],r['field']):r for r in report['rows']}
    aa,bb=index(base),index(candidate)
    if aa.keys()!=bb.keys():raise ValueError('Different crop sets')
    rows=[]
    for key,a in aa.items():
        b=bb[key]
        if a['expected']!=b['expected']:raise ValueError('Reference mismatch')
        av,bv=value(a),value(b);expected=normalized(a['expected'])
        rows.append(dict(page=key[0],field=key[1],expected=a['expected'],baseline_raw=a['candidate_raw'],candidate_raw=b['candidate_raw'],
            baseline_value=av,candidate_value=bv,baseline_correct=normalized(av)==expected,candidate_correct=normalized(bv)==expected))
    report=dict(scope='Paired PC ONNX isolated-crop diagnostic; explicit BP-pair components parsed, no cross-field conflicts/status calibration; not Android pipeline accuracy',
        baseline=str(args.baseline.resolve()),candidate=str(args.candidate.resolve()),n=len(rows),
        baseline_correct=sum(r['baseline_correct'] for r in rows),candidate_correct=sum(r['candidate_correct'] for r in rows),
        improvements=sum(not r['baseline_correct'] and r['candidate_correct'] for r in rows),
        regressions=sum(r['baseline_correct'] and not r['candidate_correct'] for r in rows),rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print({k:v for k,v in report.items() if k!='rows'})


if __name__=='__main__':main()

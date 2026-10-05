"""Rescore immutable phone outputs against a versioned reference annotation."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics
from benchmark_android import score


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True)
    ap.add_argument('--labels',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    refs={r.get('case_id',f"page_{r['pdf_page']:02d}"):r for r in map(json.loads,args.labels.read_text().splitlines())}
    provenance=json.loads((args.capture/'summary.json').read_text());cases=[];counts=collections.Counter();by_form={}
    for case in provenance['cases']:
        name=case['case_id'];result=json.loads((args.capture/name/'result.json').read_text());truth=refs[name]
        scored=score(result,truth);counts.update(scored['counts'])
        by_form.setdefault(truth['form_id'],collections.Counter()).update(scored['counts'])
        (args.output/(name+'.json')).write_text(json.dumps(scored,ensure_ascii=False,indent=2))
        cases.append(dict(case,form_correct=scored['form_correct'],counts=scored['counts']))
    report={k:v for k,v in provenance.items() if k not in ('cases','counts','labels_sha256','labels_path')}
    report.update(scope='Rescored real-phone development outputs; revised independent PDF-vector references, not a sealed or fully human-reviewed test',
        labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),labels_path=str(args.labels.resolve()),
        original_labels_sha256=provenance.get('labels_sha256'),capture=str(args.capture.resolve()),cases=cases,counts=dict(counts),
        by_form={k:dict(v) for k,v in by_form.items()},pages=len(cases),form_correct=sum(case['form_correct'] for case in cases))
    if cases:
        report['median_wall_seconds']=statistics.median(case['wall_seconds'] for case in cases)
        memory=[case['sampled_peak_pss_kb'] for case in cases if case.get('sampled_peak_pss_kb')]
        report['maximum_sampled_pss_kb']=max(memory,default=None)
    (args.output/'summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ['pages','form_correct','counts','by_form']},indent=2))


if __name__=='__main__':main()

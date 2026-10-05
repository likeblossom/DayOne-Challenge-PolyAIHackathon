"""Compare saved phone runs on matching pages, rescoring both with one reference version."""
import argparse
import hashlib
import json
from pathlib import Path
from benchmark_android import score


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--labels',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Keep prior comparisons immutable')
    refs={r.get('case_id',f"page_{r['pdf_page']:02d}"):r for r in map(json.loads,args.labels.read_text().splitlines())}
    runs=[json.loads((path/'summary.json').read_text()) for path in [args.baseline,args.candidate]]
    cases=[{row['case_id'] for row in run['cases']} for run in runs];common=sorted(cases[0]&cases[1])
    changes=[];counts=dict(pages=len(common),fields=0,improvements=0,regressions=0,unchanged_correct=0,both_wrong=0)
    for case in common:
        reference=refs[case]
        results=[json.loads((path/case/'result.json').read_text()) for path in [args.baseline,args.candidate]]
        scores=[{r['field']:r for r in score(result,reference)['fields']} for result in results]
        if scores[0].keys()!=scores[1].keys():raise ValueError('Scored field sets differ')
        for key,a in scores[0].items():
            b=scores[1][key];counts['fields']+=1
            category=('unchanged_correct' if b['normalized'] else 'regressions') if a['normalized'] else ('improvements' if b['normalized'] else 'both_wrong')
            counts[category]+=1
            if category in ('improvements','regressions'):
                field=reference['fields'][key]
                changes.append(dict(case=case,form=reference['form_id'],field=key,kind=field['kind'],
                    reference_status=field['status'],category=category,expected=a['expected'],
                    baseline=a['actual'],candidate=b['actual']))
    report=dict(scope='Paired on-phone development comparison; normalized canonical values, not clinical equivalence',
        baseline={k:runs[0][k] for k in ['apk_sha256','model_manifest_sha256']},
        candidate={k:runs[1][k] for k in ['apk_sha256','model_manifest_sha256']},
        labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),counts=counts,
        compared_cases=common,unpaired_candidate_cases=sorted(cases[1]-cases[0]),changes=changes)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(counts,indent=2),flush=True)


if __name__=='__main__':main()

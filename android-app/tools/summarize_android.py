"""Per-form phone metrics from saved outputs; no inference or reference mutation."""
import argparse
import collections
import csv
import hashlib
import json
import re
import statistics
from pathlib import Path
from benchmark_android import score


def envelope(fields,path):
    try:
        for part in re.findall(r'[^.\[\]]+',path):fields=fields[int(part)] if isinstance(fields,list) else fields[part]
        return fields if isinstance(fields,dict) else {}
    except (KeyError,IndexError,TypeError):return {}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--capture',type=Path,required=True)
    ap.add_argument('--labels',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Use a new report destination')
    refs={r.get('case_id',f"page_{r['pdf_page']:02d}"):r for r in map(json.loads,args.labels.read_text().splitlines())}
    provenance=json.loads((args.capture/'summary.json').read_text());groups={};errors=[];processing_errors=[];slices={}
    for case in provenance['cases']:
        truth=refs[case['case_id']];result=json.loads((args.capture/case['case_id']/'result.json').read_text())
        if result.get('status')!='ok':processing_errors.append(dict(case=case['case_id'],status=result.get('status'),
            error_type=result.get('error_type'),message=result.get('error_message',result.get('error'))))
        scored=score(result,truth);group=groups.setdefault(truth['form_id'],dict(counts=collections.Counter(),times=[],memory=[]))
        counts=group['counts'];counts.update(scored['counts']);counts['pages']+=1
        counts['successful_pages']+=result.get('status')=='ok';counts['correct_form']+=scored['form_correct']
        for dimension in ['language','perturbation']:
            if truth.get(dimension):
                bucket=slices.setdefault(dimension,{}).setdefault(truth[dimension],collections.Counter())
                bucket.update(scored['counts']);bucket['pages']+=1
                bucket['successful_pages']+=result.get('status')=='ok';bucket['correct_form']+=scored['form_correct']
        group['times'].append(case['wall_seconds'])
        if case.get('sampled_peak_pss_kb'):group['memory'].append(case['sampled_peak_pss_kb'])
        for row in scored['fields']:
            reference=truth['fields'][row['field']];field=envelope(result.get('fields',{}),row['field'])
            if reference['kind']=='text' and reference['status']=='KNOWN':
                counts['filled_text_with_ocr']+=bool(field.get('ocr'))
            if reference['kind']=='text' and reference['status']=='NOT_PROVIDED':
                counts['blank_text']+=1;counts['blank_text_false_value']+=row['actual'] is not None
            if reference['kind'] in ('choice','checkbox'):
                counts['selection_fields']+=1;counts['selection_correct']+=row['normalized']
            if not row['normalized']:
                if result.get('status')!='ok':stage='pipeline_error'
                elif not scored['form_correct']:stage='form_classifier'
                elif 'PRINTED_LABEL_NOT_DETECTED' in field.get('issues',[]):stage='printed_label_detection'
                elif 'NO_HANDWRITING_MATCH_NOT_PROOF_OF_BLANK' in field.get('issues',[]):stage='handwriting_detection_or_pairing'
                elif field.get('source')=='observed_empty_region':stage='blank_evidence_or_region'
                elif field.get('ocr'):stage='crop_ocr_or_grammar'
                elif reference['kind'] in ('choice','checkbox'):stage='selection_detection_or_reference'
                else:stage='structure_or_reference'
                errors.append(dict(case=case['case_id'],form=truth['form_id'],field=row['field'],stage=stage,
                    expected=row['expected'],actual=row['actual'],raw_text=field.get('raw_text'),
                    confidence=field.get('confidence'),issues=field.get('issues'),ocr=field.get('ocr')))
    rows=[];total=collections.Counter()
    for form,group in sorted(groups.items()):
        c=group['counts'];total.update(c)
        rows.append(dict(form=form,**c,
            filled_text_normalized_accuracy=c['filled_text_normalized']/max(1,c['filled_text']),
            all_field_normalized_accuracy=c['normalized']/max(1,c['fields']),
            known_prediction_accuracy=c['known_predictions_correct']/max(1,c['known_predictions']),
            median_seconds=statistics.median(group['times']),max_seconds=max(group['times']),
            peak_sampled_pss_mib=max(group['memory'],default=0)/1024))
    report=dict(scope=provenance['scope'],capture=str(args.capture.resolve()),
        apk_sha256=provenance['apk_sha256'],model_manifest_sha256=provenance['model_manifest_sha256'],
        labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),
        normalization=provenance.get('normalization'),counts=dict(total),forms=rows,slices=slices,
        error_triage=dict(collections.Counter(e['stage'] for e in errors)),errors=errors,processing_errors=processing_errors,
        limitations=['Development data, not a sealed evaluation.',
            'All-field scores include blank fields; filled-text scores do not.',
            'References are generator/PDF-derived and not fully human-adjudicated.',
            'Error-stage buckets are triage, not causal attribution.',
            'Confidence scores are uncalibrated; sampled PSS can miss memory peaks.'])
    args.output.mkdir(parents=True)
    (args.output/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if rows:
        with (args.output/'per_form.csv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
            writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:report[k] for k in ['counts','error_triage']},indent=2))


if __name__=='__main__':main()

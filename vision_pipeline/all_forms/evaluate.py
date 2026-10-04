"""Organizer development benchmark, not a sealed test or a mobile benchmark."""
import argparse,csv,json,html,os
from collections import Counter,defaultdict
from .infer import AllForms
from ..common import *
from ..label_anchor_pilot.evaluate import normalized,same,score,stages

def main():
    p=argparse.ArgumentParser();p.add_argument('--reuse',action='store_true');p.add_argument('--limit-per-form',type=int,default=10);a=p.parse_args()
    truths=[json.loads(s) for s in (DATA/'organizer_test/labels.jsonl').read_text().splitlines()]
    truths=sorted(truths,key=lambda t:(t['form_id'],t['pdf_page']))
    logs=REPORTS/'all_forms';logs.mkdir(exist_ok=True);output=BASE/'outputs/all_forms';counts=defaultdict(Counter);stage=Counter();rows=[];seen=Counter();cards=[];pipeline=None
    for t in truths:
        form=t['form_id'];seen[form]+=1
        if seen[form]>a.limit_per_form:continue
        out=output/f'page_{t["pdf_page"]:02d}';source=ROOT/t['image']
        if a.reuse and (out/'prediction.json').exists():r=read_json(out/'prediction.json')
        else:
            if pipeline is None:pipeline=AllForms()
            r=pipeline.extract(source,out)
        c=score(r,t);c['normalized']=sum(same(normalized(r['fields'].get(k,{}).get('value')),normalized(v['value'])) for k,v in t['fields'].items() if v.get('score_eligible') and v['kind']!='printed')
        c['pages']=1;c['form_correct']=r['form_id']==form
        if r['form_id']!=form:
            # Wrong template is a failure, even for coincidentally matching blanks.
            for k in ['exact','normalized','known_exact','known_text_exact','known_text_normalized']:c[k]=0
            stage['form_classification']+=1
        else:
            sc,sr=stages(r,t,read_json(DATA/'all_forms'/form/'spec.json'),Image.open(source).size);stage.update(sc);rows.extend(sr)
        counts[form].update(c)
        for k,f in r['fields'].items():
            for candidate in f.get('raw_candidates',[]):
                d=candidate['debug'];crop=os.path.relpath(Path(d['directory'])/'crop_before_processor.png',logs);model_input=os.path.relpath(Path(d['directory'])/'model_input.png',logs)
                cards.append(f'<section><h3>Page {t["pdf_page"]} / {html.escape(k)} / {candidate["script"]}</h3><img src="{crop}"><img src="{model_input}"><p>Raw: {html.escape(candidate["text"])} | Value: {html.escape(str(f["value"]))} | Reference: {html.escape(str(t["fields"].get(k,{}).get("value")))}</p></section>')
        total=Counter();[total.update(v) for v in counts.values()]
        report=dict(pages=total['pages'],counts=dict(total),per_form={k:dict(v) for k,v in counts.items()},stage_counts=dict(stage),normalized_accuracy=total['normalized']/max(1,total['fields']),reference_quality='Provisional PDF-vector labels; already inspected organizer development set; not independently human-adjudicated',routing='Predicted eight-class form, no ground-truth form supplied; wrong forms scored incorrect',training_source='Synthetic only, font-disjoint validation; no organizer checkpoint selection',mobile_accuracy=False)
        write_json(logs/'organizer_results.json',report);print(form,t['pdf_page'],dict(c),flush=True)
    if rows:
        with (logs/'stage_failures.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (logs/'ocr_inputs_outputs.html').write_text('<!doctype html><meta charset="utf-8"><title>Sanad all forms: OCR evidence</title><style>body{font:16px sans-serif;margin:30px}section{border:1px solid #ddd;padding:12px;margin:12px}img{max-width:45%;max-height:230px;margin-right:20px}</style><h1>All-form OCR crops and raw outputs</h1><p>Left: actual crop. Right: rounded visualization of model input. Raw outputs and provisional references; not mobile runtime results.</p>'+''.join(cards))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()

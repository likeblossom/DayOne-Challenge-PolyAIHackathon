"""One-form development benchmark; never trains or selects checkpoints on originals."""
import argparse,csv,hashlib,html,json,os,re,unicodedata
from collections import Counter
from datetime import datetime,timezone
from .common import *
from .infer import Pilot

def normalized(value):
    if not isinstance(value,str):return value
    value=unicodedata.normalize('NFKD',value.casefold())
    return ''.join(c for c in value if c.isalnum())

def same(a,b):
    if isinstance(b,list):return isinstance(a,list) and set(a)==set(b)
    return a==b

def overlap(hand,box,size):
    """Fraction of reference PDF glyph rectangle covered; approximate ink coverage."""
    if hand is None:return 0.
    q=quad(box)*size;q=q.astype(np.float32)
    area,_=cv2.intersectConvexConvex(q,np.asarray(hand['quad'],np.float32))
    return float(area/max(cv2.contourArea(q),1))

def horizontal_coverage(hand,box,size):
    if hand is None:return 0.
    q=np.asarray(hand['quad']);left,right=box[0]*size[0],box[2]*size[0]
    return float(max(0,min(right,q[:,0].max())-max(left,q[:,0].min()))/max(right-left,1))

def score(record,truth):
    c=Counter()
    for key,label in truth['fields'].items():
        if not label.get('score_eligible') or label['kind']=='printed':continue
        f=record['fields'].get(key,{});equal=same(f.get('value'),label['value'])
        c['fields']+=1;c['exact']+=equal;c['review']+=f.get('status')=='NEEDS_REVIEW'
        if label['status']=='KNOWN':c['known']+=1;c['known_exact']+=equal
        if label['kind']=='text':
            c['text_fields']+=1;c['text_exact']+=equal
            if label['status']=='KNOWN':
                c['known_text']+=1;c['known_text_exact']+=equal
                c['known_text_normalized']+=same(normalized(f.get('value')),normalized(label['value']))
                c['known_text_with_ocr']+=bool(f.get('raw_candidates'))
            if label['status']=='NOT_PROVIDED':
                c['blank_text']+=1;c['blank_false_value']+=f.get('value') is not None
                c['blank_confirmed']+=f.get('status')=='NOT_PROVIDED'
    return c

def stages(record,truth,spec,size):
    c=Counter();rows=[]
    for key,label in truth['fields'].items():
        if not(label['kind']=='text' and label['status']=='KNOWN' and label.get('score_eligible')):continue
        f=record['fields'][key];a=spec['bindings'][key]['anchor'];glyph=label.get('glyph_bbox')
        column=spec['bindings'][key].get('column_anchor')
        anchor_missing=a not in record['label_detections'] or bool(column and column not in record['label_detections'])
        if not glyph:continue
        best_hand=max(record['handwriting_detections'],key=lambda h:overlap(h,glyph,size),default=None)
        coverage=overlap(best_hand,glyph,size);width_coverage=horizontal_coverage(best_hand,glyph,size)
        paired_coverage=overlap(f.get('handwriting_detection'),glyph,size)
        paired_width_coverage=horizontal_coverage(f.get('handwriting_detection'),glyph,size)
        candidates=f.get('raw_candidates',[]);raw=candidates[0]['text'] if candidates else ''
        numeric=isinstance(label['value'],(int,float)) or spec['bindings'][key]['schema'].get('type')=='date'
        script_wrong=bool(f.get('script_prediction')) and not numeric and f['script_prediction']['label']!='latin'
        if same(f.get('value'),label['value']):failure='exact_value'
        elif anchor_missing:failure='printed_label_missing'
        elif coverage<.5 or width_coverage<.85:failure='handwriting_detection_miss_or_truncation'
        elif not candidates:failure='no_spatial_assignment'
        elif paired_coverage<.5 or paired_width_coverage<.85:failure='incorrect_or_truncated_pair'
        elif script_wrong and not any(c.get('script')=='latin' for c in candidates):failure='script_route'
        elif normalized(raw)!=normalized(label['raw_text']):failure='ocr_transcription'
        elif normalized(f.get('value'))==normalized(label['value']):failure='case_punctuation_or_accent_only'
        else:failure='grammar_or_reference'
        c['known_text_fields']+=1;c[failure]+=1
        c['label_detected']+=not anchor_missing;c['handwriting_coverage_ge_50pct']+=coverage>=.5
        c['paired_coverage_ge_50pct']+=paired_coverage>=.5;c['script_wrong_observed']+=script_wrong
        rows.append(dict(page=truth['pdf_page'],field=key,expected=label['value'],raw=raw,predicted=f.get('value'),first_failure=failure,best_handwriting_glyph_coverage=round(coverage,3),assigned_glyph_coverage=round(paired_coverage,3),best_horizontal_coverage=round(width_coverage,3),assigned_horizontal_coverage=round(paired_width_coverage,3)))
    return c,rows

def gallery(truths,output_root=OUTPUT,report_dir=LOGS):
    rows=[];cards=[]
    def esc(value):return html.escape(str(value))
    def rel(path):return os.path.relpath(path,report_dir)
    for truth in truths:
        out=output_root/f'page_{truth["pdf_page"]:02d}'/'relative'
        if not(out/'prediction.json').exists():continue
        record=read_json(out/'prediction.json')
        cards.append(f'<h2>Page {truth["pdf_page"]}</h2><a href="{rel(out/"detections_and_pairs.jpg")}">Full-page detections and pairing overlay</a>')
        for key,f in record['fields'].items():
            label=truth['fields'][key]
            for rank,c in enumerate(f.get('raw_candidates',[])):
                folder=Path(c['debug']['directory'])
                row=dict(page=truth['pdf_page'],field=key,rank=rank,model=c['model'],reference=label['raw_text'],raw_output=c['text'],parsed_value=c['parsed']['value'],final_value=f['value'],status=f['status'],token_confidence=c['token_confidence'],input_shape=c['debug']['input_shape'],crop=rel(folder/'crop_before_processor.png'),model_input=rel(folder/'model_input.png'),tensor=rel(folder/'exact_pixel_values.pt'),output_json=rel(folder/'ocr_output.json'))
                rows.append(row)
                unit_info=''
                if 'unit_source' in c['parsed']:
                    p=c['parsed'];row.update(normalized_quantity=p.get('normalized_quantity'),unit_source=p['unit_source'],unit_corrections=json.dumps(p.get('corrections',[]),ensure_ascii=False),numeric_alternatives=json.dumps(p.get('numeric_alternatives',[]),ensure_ascii=False))
                    unit_info=f'<p>Normalized quantity: <code>{esc(p.get("normalized_quantity"))}</code> | Unit source: {esc(p["unit_source"])}</p><p>Corrections: {esc(p.get("corrections",[]))} | Unapplied alternatives: {esc(p.get("numeric_alternatives",[]))}</p>'
                cards.append(f'''<section><h3>{esc(key)} / {esc(c['model'])} {'(selected)' if rank==0 else '(alternative)'}</h3>
                <div class="images"><figure><figcaption>Tight crop before processor</figcaption><img src="{row['crop']}"></figure>
                <figure><figcaption>Actual model input visualization {esc(row['input_shape'])}</figcaption><img src="{row['model_input']}"></figure></div>
                <p>Raw output: <code dir="auto">{esc(c['text'])}</code></p><p>Parsed candidate: <code>{esc(c['parsed']['value'])}</code> | Final value: {esc(f['value'])} | Status: {esc(f['status'])}</p>
                {unit_info}
                <p>Draft reference: <code>{esc(label['raw_text'])}</code> | Token confidence (uncalibrated): {c['token_confidence']:.3f}</p>
                <a href="{row['tensor']}">Exact normalized input tensor (.pt)</a> · <a href="{row['output_json']}">Output, special tokens and token IDs</a></section>''')
            if not f.get('raw_candidates'):
                cards.append(f'<p><b>{esc(key)}</b>: no OCR call; {esc(f["status"])}; {esc(", ".join(f["issues"]))}. Reference: {esc(label["raw_text"])}.</p>')
    with (report_dir/'ocr_inputs_outputs.csv').open('w') as stream:
        if rows:
            writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for row in rows for k in row)));writer.writeheader();writer.writerows(rows)
    (report_dir/'ocr_inputs_outputs.html').write_text('''<!doctype html><meta charset="utf-8"><title>Exact OCR inputs and outputs — one-form pilot</title>
    <style>body{font:16px system-ui;max-width:1200px;margin:35px auto;background:#f5f7fb;color:#182234}section{padding:20px;margin:18px 0;background:white;border:1px solid #ccd4de}.images{display:flex;gap:24px;align-items:flex-start}figure{margin:0;flex:1}img{max-width:100%;max-height:430px;border:1px solid #ddd}code{white-space:pre-wrap;background:#eef1f5;padding:4px}h2{margin-top:45px}</style>
    <h1>What the OCR actually sees and returns</h1><p>Form 06 only. The PNG is a rounded, de-normalized visualization of the actual FP16 tensor after the model processor. The .pt file preserves the exact numerical input. Raw outputs precede grammar correction; all alternatives and skipped fields are shown, not only successes. References are provisional PDF-vector labels, not fully human-adjudicated. No page registration or fixed page-coordinate inference.</p>'''+''.join(cards))
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=10);ap.add_argument('--reuse',action='store_true');args=ap.parse_args()
    truths=[json.loads(s) for s in (DATA/'organizer_test'/'labels.jsonl').read_text().splitlines()]
    truths=[r for r in truths if r['form_id']==FORM][:args.limit]
    totals={k:Counter() for k in ['baseline','nearest','relative']};stage=Counter();field_rows=[];pilot=None
    LOGS.mkdir(parents=True,exist_ok=True)
    for truth in truths:
        page=truth['pdf_page'];source=ROOT/truth['image'];out=OUTPUT/f'page_{page:02d}'
        baseline=read_json(BASE/'outputs'/'organizer'/f'page_{page:02d}'/'prediction.json');totals['baseline'].update(score(baseline,truth))
        detections=None
        for mode in ['relative','nearest']:
            path=out/mode/'prediction.json'
            if args.reuse and path.exists():record=read_json(path)
            else:
                if pilot is None:pilot=Pilot()
                if detections is None:detections=pilot.detect(Image.open(source).convert('RGB'))
                record=pilot.extract(source,out/mode,mode,detections)
            totals[mode].update(score(record,truth))
            if mode=='relative':
                counts,rows=stages(record,truth,read_json(WORK/'spec.json'),Image.open(source).size);stage.update(counts);field_rows.extend(rows)
            print('evaluated',page,mode,dict(score(record,truth)),flush=True)
        report=dict(form=FORM,pages=len([r for r in truths if r['pdf_page']<=page]),requested_pages=len(truths),counts={k:dict(v) for k,v in totals.items()},stage_counts=dict(stage),stage_definition='First failing stage for known text fields. Coverage uses approximate PDF glyph rectangles, threshold 50%; not manually drawn handwriting boxes. Conditional checks do not establish independent causal effects.',reference_quality='Provisional PDF-vector draft; not fully human adjudicated',benchmark_scope='Organizer development benchmark already inspected; not a sealed unbiased test. Same 10 pages and eligible fields across rows. No organizer handwriting used for training or checkpoint selection.',ablation_scope='Baseline changes several stages together (registered full-field dual crop vs label-relative tight crop). Nearest vs relative changes only assignment; detectors, OCR and grammar identical. Form type is given for this one-form pilot. Cached OCR outputs reused for identical crops, so timings are not latency benchmarks.',utc=datetime.now(timezone.utc).isoformat(),code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},reference_sha256=hashlib.sha256((DATA/'organizer_test'/'labels.jsonl').read_bytes()).hexdigest())
        write_json(LOGS/'ablation.json',report)
    if field_rows:
        with (LOGS/'stage_failures.csv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(field_rows[0]));writer.writeheader();writer.writerows(field_rows)
    report['stage_definition']='First failing stage for known text fields. Approximate PDF glyph rectangles: at least 50% area AND 85% horizontal extent required before attributing an error downstream of cropping. Organizer pages are near-upright. These checks are triage, not proof of independent causal effects.'
    report['model_sha256']={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'models/label_anchor_pilot/anchors/weights/best.pt',BASE/'models/label_anchor_pilot/handwriting/weights/best.pt',BASE/'models/script.pt']}
    report['training_preparation']=read_json(WORK/'preparation.json')
    write_json(LOGS/'ablation.json',report)
    gallery(truths)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()

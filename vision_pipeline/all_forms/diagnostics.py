"""Post-hoc stage/assignment ablations on frozen detections; no model training."""
import json,copy,unicodedata
from collections import Counter
from ..common import *
from ..label_anchor_pilot.infer import pair_text
from ..label_anchor_pilot.evaluate import overlap,horizontal_coverage
from ..pitch_metrics import distance

def main():
    truths=[json.loads(s) for s in (DATA/'organizer_test/labels.jsonl').read_text().splitlines()]
    totals={name:Counter() for name in ['nearest','row_relative','row_and_column_relative']};ocr=Counter()
    for t in truths:
        path=BASE/'outputs/all_forms'/f'page_{t["pdf_page"]:02d}'/'prediction.json'
        if not path.exists():continue
        r=read_json(path);correct=r['form_id']==t['form_id']
        for k,f in t['fields'].items():
            if not(f.get('score_eligible') and f['status']=='KNOWN' and f['kind']=='text'):continue
            candidates=r['fields'].get(k,{}).get('raw_candidates',[]) if correct else []
            raw=unicodedata.normalize('NFC',candidates[0]['text'] if candidates else '').strip();ref=unicodedata.normalize('NFC',f['raw_text']).strip()
            ocr['characters']+=len(ref);ocr['character_edits']+=distance(raw,ref);ocr['words']+=len(ref.split());ocr['word_edits']+=distance(raw.split(),ref.split());ocr['fields']+=1
        if not correct:continue
        spec=read_json(DATA/'all_forms'/t['form_id']/'spec.json');priors=read_json(DATA/'all_forms'/t['form_id']/'pairing_priors.json');size=Image.open(ROOT/t['image']).size
        for name in totals:
            config=copy.deepcopy(spec)
            if name=='row_relative':
                for b in config['bindings'].values():b.pop('column_anchor',None);b.pop('column_relative_region',None)
            pairs,_=pair_text(r['label_detections'],r['handwriting_detections'],config,priors,'nearest' if name=='nearest' else 'relative')
            totals[name]['pages']+=1
            for key,label in t['fields'].items():
                if not(label['kind']=='text' and label['status']=='KNOWN' and label.get('score_eligible') and label.get('glyph_bbox')):continue
                hand=pairs.get(key);totals[name]['known_text_fields']+=1
                totals[name]['assigned']+=hand is not None
                totals[name]['adequate_coverage']+=overlap(hand,label['glyph_bbox'],size)>=.5 and horizontal_coverage(hand,label['glyph_bbox'],size)>=.85
    write_json(REPORTS/'all_forms/assignment_ablation.json',dict(variants={k:dict(v) for k,v in totals.items()},scope='Same frozen detections on correctly classified organizer pages. Change assignment only; no OCR rerun. Approximate PDF glyph coverage >=50% area and >=85% width. Not independent causal proof.',raw_ocr=dict(ocr),raw_cer=ocr['character_edits']/max(1,ocr['characters']),raw_wer=ocr['word_edits']/max(1,ocr['words'])))
if __name__=='__main__':main()

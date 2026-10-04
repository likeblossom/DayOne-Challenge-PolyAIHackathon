"""Two detectors -> label-relative assignment -> tight handwriting crops -> OCR.

No reference page, page homography, fixed pixel coordinates or ground truth are
read by inference. Relative regions describe relationships to detected labels.
"""
import argparse,json,re,time,hashlib,copy,shutil
from scipy.optimize import linear_sum_assignment
from PIL import ImageDraw
from ultralytics import YOLO,settings
from .common import *
from ..infer import Predictor,nest_fields
from ..ocr import TransformerOCR
from ..grammar import parse,relations,confidence
from ..unit_grammar import evidence as unit_evidence

def text_units(spec):
    out={}
    for key,b in spec['bindings'].items():
        if b['kind']=='text':out[key]=b
        elif b.get('note'):out[key+'::note']=b['note']
    return out

def ocr_routes(route, schema_type, date_expert=False, numeric_expert=False, field_key=None):
    if date_expert and schema_type=='date':return ['date']
    if numeric_expert and (schema_type in ['double','integer'] or field_key=='record_code'):return ['numeric']
    return ['latin','arabic'] if route['confidence']<.8 or schema_type in ['double','integer','date'] else [route['label']]

def unit_anchor(unit,anchors):
    """Row label supplies y/orientation; column header supplies x for tables."""
    row=anchors.get(unit['anchor'])
    if row is None:return None
    if not unit.get('column_anchor'):return row
    column=anchors.get(unit['column_anchor'])
    if column is None:return None
    c,u,v,w,h=frame(row['quad'])
    target=world(unit['column_relative_region'],column['quad']).mean(0)
    expected=world(unit['relative_region'],row['quad']).mean(0)
    shift=u*float((target-expected)@u)
    return dict(row,quad=(np.asarray(row['quad'])+shift).tolist(),confidence=min(row['confidence'],column['confidence']))

def pair_text(anchors,hands,spec,priors,mode='relative'):
    units=text_units(spec);keys=[k for k,u in units.items() if unit_anchor(u,anchors) is not None]
    costs=np.full((len(keys),len(hands)+len(keys)),2.5)
    for i,key in enumerate(keys):
        unit=units[key];anchor=unit_anchor(unit,anchors)['quad'];ac,_,_,_,ah=frame(anchor)
        reg=np.asarray(unit['relative_region']);lo=reg.min(0);hi=reg.max(0)
        for j,hand in enumerate(hands):
            if mode=='nearest':
                distance=np.linalg.norm(np.asarray(hand['quad']).mean(0)-ac)/max(ah,1)
                costs[i,j]=min(10.,distance/8.)
            else:
                center=local(hand['quad'],anchor).mean(0);height=max(hi[1]-lo[1],.5)
                outside=np.maximum(lo-center,0)+np.maximum(center-hi,0)
                outside_score=np.linalg.norm(outside/np.array([max(hi[0]-lo[0],.2),height]))
                prior=priors.get(key.split('::')[0]);prior_score=0.
                if prior:prior_score=float(np.linalg.norm((center-prior['mean'])/np.asarray(prior['std'])))
                costs[i,j]=min(10.,outside_score*3+prior_score*.12+(1-hand['confidence'])*.15)
                if outside_score>.65:costs[i,j]=10.
    assigned={};diagnostics={}
    if not keys:return assigned,diagnostics
    rows,cols=linear_sum_assignment(costs)
    for i,j in zip(rows,cols):
        if j<len(hands) and costs[i,j]<2.5:
            assigned[keys[i]]=hands[j]
            alternatives=sorted(float(v) for v in costs[i,:len(hands)])
            gap=alternatives[1]-alternatives[0] if len(alternatives)>1 else 2.5
            diagnostics[keys[i]]=dict(cost=float(costs[i,j]),alternative_cost_gap=gap,ambiguous=gap<.12)
    return assigned,diagnostics

class Pilot:
    def __init__(self,date_expert=False,numeric_expert=False,handwriting_weights=None,work=None,anchor_weights=None,save_tensors=True,square_input=False):
        import torch
        torch.set_num_threads(6);settings.update({'sync':False})
        work=Path(work or WORK);self.spec=read_json(work/'spec.json');self.priors=read_json(work/'pairing_priors.json');self.form=self.spec['form'];self.save_tensors=save_tensors
        self.label_model=YOLO(str(anchor_weights or WEIGHTS/'anchors'/'weights'/'best.pt'))
        self.handwriting_weights=Path(handwriting_weights or WEIGHTS/'handwriting'/'weights'/'best.pt')
        self.hand_model=YOLO(str(self.handwriting_weights))
        self.script=Predictor(MODELS/'script.pt');self.ocr=TransformerOCR();self.cache={};self.date_expert=date_expert
        self.numeric_expert=numeric_expert;self.square_input=square_input
    def detect(self,image):
        anchors={};hands=[]
        for task,model in [('anchors',self.label_model),('handwriting',self.hand_model)]:
            result=model.predict(image,imgsz=1280,rect=not self.square_input,conf=.15,iou=.45,max_det=600 if self.square_input or len(self.spec['bindings'])>150 else 150,device=0,verbose=False)[0]
            if result.obb is None:continue
            for i,obb in enumerate(result.obb):
                d=dict(quad=obb.xyxyxyxy[0].cpu().numpy().tolist(),confidence=float(obb.conf[0]),class_id=int(obb.cls[0]),id=i)
                if task=='anchors':
                    name=self.spec['classes'][d['class_id']]
                    if name not in anchors or anchors[name]['confidence']<d['confidence']:anchors[name]=d
                else:hands.append(d)
        return anchors,hands
    def read(self,image,hand,unit,key,out):
        patch=line_crop(image,hand['quad']);route=self.script(patch)
        # Numeric IDs retain their string representation, hyphens and leading zeroes.
        routes=ocr_routes(route,unit.get('schema',{}).get('type'),self.date_expert,self.numeric_expert,key)
        candidates=[]
        for language in routes:
            folder=out/'ocr'/re.sub(r'[^A-Za-z0-9_-]','_',key)/language
            cache_key=(hashlib.sha256(patch.tobytes()).hexdigest(),patch.size,language)
            if cache_key in self.cache:
                candidate=copy.deepcopy(self.cache[cache_key]);source=Path(candidate['debug']['directory'])
                folder.mkdir(parents=True,exist_ok=True)
                for name in ['crop_before_processor.png','model_input.png']+(['exact_pixel_values.pt'] if self.save_tensors else []):
                    if source/name!=folder/name:shutil.copyfile(source/name,folder/name)
                candidate['debug']['directory']=str(folder)
                write_json(folder/'ocr_output.json',candidate)
            else:
                candidate=self.ocr.read(patch,language,debug_dir=folder)
                if not self.save_tensors:
                    (folder/'exact_pixel_values.pt').unlink() # Only this just-created debug artifact.
                    candidate['debug']['tensor_saved']=False
                self.cache[cache_key]=copy.deepcopy(candidate)
            if language=='date':
                from ..date_ocr.normalize import parse_date
                parsed=parse_date(candidate['text'],date_order='DMY')
            else:parsed=parse(self.form,key.split('::')[0],candidate['text'])
            candidate.update(script=language,parsed=parsed,view='detected_handwriting')
            candidates.append(candidate)
        candidates.sort(key=lambda c:(c['parsed']['status']=='KNOWN',c['parsed']['grammar_score']*c['token_confidence']),reverse=True)
        return candidates,route
    def extract(self,path,out,mode='relative',detections=None):
        start=time.time();out=Path(out);out.mkdir(parents=True,exist_ok=True)
        image=Image.open(path).convert('RGB');anchors,hands=self.detect(image) if detections is None else detections
        pairs,pair_scores=pair_text(anchors,hands,self.spec,self.priors,mode);fields={};units=text_units(self.spec)
        def mark(unit):
            a=unit_anchor(unit,anchors)
            if not a:return None,0.
            patch=line_crop(image,world(unit['relative_region'],a['quad']),pad=0)
            arr=np.asarray(patch.convert('L'));h,w=arr.shape;center=arr[int(h*.3):max(int(h*.7),int(h*.3)+1),int(w*.3):max(int(w*.7),int(w*.3)+1)]
            ink=float((center<140).mean()) if center.size else .1
            return (True,.90) if ink>.19 else (False,.90) if ink<.06 else (None,.35)
        for key,b in self.spec['bindings'].items():
            f=dict(value=None,status='NEEDS_REVIEW',confidence=0.,issues=[],raw_candidates=[],schema_path=key);fields[key]=f
            if b['kind']=='printed':
                a=unit_anchor(b,anchors)
                if a:f.update(value=b['fixed'],status='KNOWN',confidence=a['confidence'],source='detected_preprinted_identifier')
                else:f['issues'].append('PRINTED_IDENTIFIER_ANCHOR_MISSING')
                continue
            if b['kind']=='checkbox':
                val,score=mark(b);f.update(value=val,confidence=score,status='KNOWN' if val is not None else 'NEEDS_REVIEW')
                if val is None:f['issues'].append('MISSING_LABEL_OR_AMBIGUOUS_CHECKBOX')
                continue
            if b['kind']=='choice':
                selected=[];missing=False
                for option in b['options']:
                    val,score=mark(option)
                    if val:selected.append(option['value'])
                    if val is None:missing=True
                if b['schema']['type']=='array':f['value']=selected
                elif len(selected)==1:f['value']=selected[0]
                if len(selected)>1 and b['schema']['type']!='array':f['issues'].append('MULTIPLE_EXCLUSIVE_OPTIONS')
                if missing:f['issues'].append('MISSING_OPTION_ANCHOR_OR_UNCLEAR_MARK')
                note_key=key+'::note'
                if note_key in pairs:
                    cs,route=self.read(image,pairs[note_key],b,key,out);f['raw_candidates']=cs
                    if cs[0]['parsed']['status']=='KNOWN':
                        v=cs[0]['parsed']['value'];more=v if isinstance(v,list) else [v]
                        f['value']=list(dict.fromkeys(selected+more)) if b['schema']['type']=='array' else v
                    else:f['issues'].append('UNRESOLVED_OPTION_NOTE')
                f['confidence']=.45 if f['issues'] else .85;f['status']='NEEDS_REVIEW' if f['issues'] else 'KNOWN' if f['value'] is not None else 'NOT_PROVIDED'
                continue
            a=unit_anchor(b,anchors)
            if not a:f['issues'].append('PRINTED_LABEL_NOT_DETECTED');continue
            f['label_detection']=a
            if key not in pairs:
                region=world(b['relative_region'],a['quad']);patch=line_crop(image,region,pad=0);ink=ink_evidence(patch)
                f['unmatched_ink_pixels']=ink;f['issues'].append('NO_HANDWRITING_MATCH')
                # A missing detection is not proof of blank. Require low residual ink.
                if ink<6:f.update(status='NOT_PROVIDED',confidence=.65,blank_observed=True)
                continue
            hand=pairs[key];f['handwriting_detection']=hand;f['pairing']=pair_scores[key]
            cs,route=self.read(image,hand,b,key,out);best=cs[0];parsed=best['parsed']
            f.update(value=parsed['value'],status=parsed['status'],raw_candidates=cs,script_prediction=route,normalizations=parsed['normalizations'])
            f.update(unit_evidence(parsed))
            if best['script']=='date':f.update(date_components=parsed['components'],date_order_context='DMY',ocr_route='schema_date_specialist')
            if best['script']=='numeric':f['ocr_route']='schema_numeric_specialist'
            f['issues'].extend(parsed['issues']+best.get('warnings',[]))
            if pair_scores[key]['ambiguous']:f['issues'].append('AMBIGUOUS_SPATIAL_PAIR')
            if best['script']=='arabic':f['issues'].append('ARABIC_OCR_REQUIRES_REVIEW')
            if len({json.dumps(c['parsed']['value'],ensure_ascii=False) for c in cs if c['parsed']['status']=='KNOWN'})>1:f['issues'].append('SCRIPT_OCR_DISAGREEMENT')
            comp=dict(form=1.,localization=min(a['confidence'],hand['confidence']),script=route['confidence'],ocr=best['token_confidence'],grammar=parsed['grammar_score'],image_quality=1.)
            f['confidence_components']=comp;f['confidence']=confidence(comp,f['issues'])
            if f['status']=='KNOWN' and (f['issues'] or f['confidence']<.85):f['status']='NEEDS_REVIEW'
        for key,codes in relations(fields).items():
            fields[key]['issues'].extend(codes);fields[key]['status']='NEEDS_REVIEW';fields[key]['confidence']=min(.49,fields[key]['confidence'])
        record=dict(form_id=self.form,mode=mode,fields=fields,structured_values=nest_fields(fields),label_detections=anchors,handwriting_detections=hands,seconds=round(time.time()-start,3),image_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),confidence_calibrated=False,lifecycle_state='NEEDS_REVIEW',requires_human_confirmation=True,page_alignment_used=False,fixed_page_coordinates_used=False,orientation_scope='Upright +/-45 degrees only; inverted pages are not reliably detected. No 180-degree robustness claim.')
        record['date_specialist_used']=self.date_expert
        record['numeric_specialist_used']=self.numeric_expert
        record['handwriting_weights']=str(self.handwriting_weights)
        write_json(out/'prediction.json',record)
        overlay=image.copy();draw=ImageDraw.Draw(overlay)
        for name,a in anchors.items():draw.line([tuple(p) for p in a['quad']+[a['quad'][0]]],fill='green',width=3)
        for h in hands:draw.line([tuple(p) for p in h['quad']+[h['quad'][0]]],fill='blue',width=3)
        for key,h in pairs.items():
            a=anchors[units[key]['anchor']];draw.line([tuple(np.mean(a['quad'],axis=0)),tuple(np.mean(h['quad'],axis=0))],fill='orange',width=2)
            column=anchors.get(units[key].get('column_anchor'))
            if column:draw.line([tuple(np.mean(column['quad'],axis=0)),tuple(np.mean(h['quad'],axis=0))],fill='cyan',width=1)
        overlay.save(out/'detections_and_pairs.jpg',quality=93)
        return record

def main():
    ap=argparse.ArgumentParser();ap.add_argument('image',type=Path);ap.add_argument('--output',type=Path,default=OUTPUT/'demo');ap.add_argument('--mode',choices=['relative','nearest'],default='relative');ap.add_argument('--date-expert',action='store_true');ap.add_argument('--numeric-expert',action='store_true');ap.add_argument('--handwriting-weights',type=Path);a=ap.parse_args()
    result=Pilot(date_expert=a.date_expert,numeric_expert=a.numeric_expert,handwriting_weights=a.handwriting_weights).extract(a.image,a.output,a.mode);print(result['seconds'],a.output/'prediction.json')

if __name__=='__main__':main()

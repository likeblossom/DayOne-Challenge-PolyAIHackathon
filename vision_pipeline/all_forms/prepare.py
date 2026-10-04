"""Printed-label supervision and exact synthetic ink replay for all eight forms."""
import argparse, json, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import fitz
import yaml
from ..common import FORMS, wildcard, leaves
from ..label_anchor_pilot.common import *
sys.path.insert(0,str(ROOT/'scripts'))
from generate_diverse_forms import PDF, printed_spans, blank_template, render, W, H

WORK=DATA/'all_forms'
LOGS=REPORTS/'all_forms'

def template_spec(number):
    form=FORMS[number-1];source=ROOT/'data/forms'/form
    doc=fitz.open(PDF);page=doc[number-1];slots=read_json(source/'field_layout.json')
    spans=[s for s in printed_spans(page) if not s['text'].startswith(('Patiente','MÈRE —','SPÉCIMEN','Document synthétique'))]
    for s in spans:s['box']=[v/z for v,z in zip(s['bbox'],[page.rect.width,page.rect.height]*2)]
    anchors={};bindings={};audit=[]
    def bind(name, hint, box, row=False):
        center=quad(box).mean(0)
        matches=[s for s in spans if s['text'].strip()==hint.strip()]
        method='exact_printed_label'
        if not matches:
            method='nearest_printed_indicator'
            matches=[s for s in spans if s['box'][2]<.255] if row else spans
        s=min(matches,key=lambda s:abs(quad(s['box']).mean(0)[1]-center[1])* (8 if row else 2)+abs(quad(s['box']).mean(0)[0]-center[0]))
        anchor=next((k for k,a in anchors.items() if a['box']==s['box']),name)
        anchors.setdefault(anchor,dict(text=s['text'].strip(),box=s['box']))
        audit.append(dict(field=name,hint=hint,label=s['text'].strip(),method=method))
        return anchor
    def unit(name,hint,box,row=False,column=None):
        anchor=bind(name,hint,box,row)
        u=dict(anchor=anchor,relative_region=local(quad(box)*[W,H],quad(anchors[anchor]['box'])*[W,H]).tolist())
        if column is not None:
            col_hint,col_box=column;col=bind(name+'__column',col_hint,col_box)
            u.update(column_anchor=col,column_relative_region=local(quad(box)*[W,H],quad(anchors[col]['box'])*[W,H]).tolist())
        return u
    for slot in slots:
        key=slot['key'];kind=slot['kind'];b=dict(kind=kind,schema=slot['spec'])
        if kind=='choice':
            b['options']=[dict(value=o['value'],**unit(key+'__'+str(o['value']),o['label'],o['box'])) for o in slot['options']]
            if slot.get('note_box'):b['note']=unit(key+'__note','',slot['note_box'])
        else:
            hint=slot['hint'];row=False;column=None
            if key.startswith('visits['):
                i=int(key.split('[')[1].split(']')[0]);row=True
                col_hint=['Visite 1','Visite 2','Visite 3','Visite 1','Visite 2','Visite 3','7ème mois','8ème mois','9ème mois'][i]
                column=(col_hint,[(153+44.8*i)/595.2756,125/841.8898,(193+44.8*i)/595.2756,136/841.8898])
            elif key.startswith('previous_deliveries['):
                i=int(key.split('[')[1].split(']')[0]);row=True
                column=(f'Accouch. {i+1}',[(153+81*i)/595.2756,489/841.8898,(185+81*i)/595.2756,500/841.8898])
            elif key.startswith('previous_pregnancy_anomalies['):
                i=int(key.split('[')[1].split(']')[0]);row=True
                hint=['Avortement','Accouchement prématuré','Mort fœtale in utéro','Autres à préciser :'][i]
                cols={'count':'Nombre','date':'Date','place':'Lieu','gestational_age_weeks':'Age gestationnel (SA)'}
                if key.split('.')[-1] in cols:column=(cols[key.split('.')[-1]],[slot['box'][0],364/841.8898,slot['box'][2],374/841.8898])
            elif key.startswith('family_history.'):
                row=True;hint={'hypertension':'HTA','diabetes':'Diabète','hereditary_diseases':'Maladies héréditaires','malformations':'Malformations','allergies':'Allergie(s)'}[key.split('.')[-1]]
                column=('Famille de la femme' if '.woman_' in key else 'Mari/famille',[slot['box'][0],216/841.8898,slot['box'][2],226/841.8898])
            b.update(unit(key,hint,slot['box'],row,column))
            if kind=='printed':b['fixed']=slot['fixed']
        bindings[key]=b
    assert {wildcard(k) for k in bindings}==set(leaves(number))
    spec=dict(form=form,classes=list(anchors),bindings=bindings,orientation_scope='upright +/-45 degrees; detected row/column anchors; no page registration')
    return spec,anchors,slots,blank_template(doc,number),audit

def prepare(number,ink=True):
    form=FORMS[number-1];work=WORK/form;source=ROOT/'data/forms'/form
    spec,anchors,slots,template,audit=template_spec(number)
    write_json(work/'spec.json',spec);write_json(work/'anchor_binding_audit.json',audit)
    write_json(work/'training_anchor_boxes.json',anchors)
    records=[json.loads(line) for line in (source/'annotations.jsonl').open()]
    def process(r):
        split={'train':'train','validation':'val','synthetic_test':'test'}[r['split']];matrix=np.asarray(r['distortions']['homography'])
        def transform(box):return cv2.perspectiveTransform((quad(box)*[W,H]).astype(np.float32)[None],matrix)[0]/[W,H]
        regions=[]
        if ink:
            index=int(Path(r['image_filename']).stem.split('_')[-1])
            _,fields,*_=render(template,slots,number,index,r['random_seed'],capture_text_boxes=True)
            for key,f in fields.items():
                assert f['rendered_text']==r['fields'][key]['rendered_text'],(form,index,key,'Renderer replay mismatch')
                for t in f.get('text_regions',[]):regions.append(dict(field=key,text=t['text'],canonical_box=t['bbox'],quad=transform(t['bbox']).tolist()))
        for task in ['anchors']+(['handwriting'] if ink else []):
            target=work if task=='anchors' else WORK/'universal'
            image=target/task/'images'/split/r['image_filename'];image.parent.mkdir(parents=True,exist_ok=True)
            if not image.exists():image.symlink_to((source/'images'/r['image_filename']).resolve())
            items=[(i,transform(anchors[k]['box'])) for i,k in enumerate(spec['classes'])] if task=='anchors' else [(0,np.asarray(v['quad'])) for v in regions]
            label=target/task/'labels'/split/(image.stem+'.txt');label.parent.mkdir(parents=True,exist_ok=True)
            assert all((q>=0).all() and (q<=1).all() for _,q in items)
            label.write_text('\n'.join(str(cls)+' '+' '.join(f'{v:.8f}' for v in q.ravel()) for cls,q in items)+'\n')
        return dict(image=r['image_filename'],split=split,ink=regions)
    done=[];started=time.time()
    with ThreadPoolExecutor(6) as pool:
        for i,r in enumerate(pool.map(process,records),1):
            done.append(r)
            if i%50==0:print(form,i,len(records),round(time.time()-started),'seconds',flush=True)
    priors=defaultdict(list)
    for r in done:
        if r['split']!='train':continue
        for region in r['ink']:
            b=spec['bindings'][region['field']];u=b.get('note') if b['kind']=='choice' else b
            if u:priors[region['field']].append(local(quad(region['canonical_box'])*[W,H],quad(anchors[u['anchor']]['box'])*[W,H]).mean(0))
    if ink:
        write_json(work/'pairing_priors.json',{k:dict(mean=np.mean(v,0).tolist(),std=np.maximum(np.std(v,0),[.18,.45]).tolist(),n=len(v)) for k,v in priors.items()})
        (work/'ink_labels.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in done))
    elif not (work/'pairing_priors.json').exists():write_json(work/'pairing_priors.json',{})
    for task in ['anchors']+(['handwriting'] if ink else []):
        target=(work if task=='anchors' else WORK/'universal')/task
        (target/'dataset.yaml').write_text(yaml.safe_dump(dict(path=str(target),train='images/train',val='images/val',test='images/test',names=dict(enumerate(spec['classes'] if task=='anchors' else ['handwriting_line']))),sort_keys=False))
    report=dict(form=form,pages=dict(Counter(r['split'] for r in done)),fields=len(spec['bindings']),schema_leaves=len(leaves(number)),anchor_classes=len(anchors),ink_regions=sum(len(r['ink']) for r in done),exact_ink_replay=ink,organizer_handwriting_used_for_training=False)
    write_json(work/('preparation.json' if ink else 'anchors_preparation.json'),report);print(report,flush=True)

def add_long_lines():
    source=DATA/'long_handwriting';target=WORK/'universal/handwriting';counts=Counter()
    for split in ['train','val','test']:
        for image in (source/'images'/split).glob('*.jpg'):
            dest=target/'images'/split/image.name
            if image.name.startswith('06_'):continue # These 600 base pages already exist.
            if not dest.exists():dest.symlink_to(image.resolve())
            label=source/'labels'/split/(image.stem+'.txt');out=target/'labels'/split/label.name
            if not out.exists():out.symlink_to(label.resolve())
            counts[split]+=1
    assert sum(counts.values())==720,counts
    write_json(WORK/'universal/long_line_mix.json',dict(base_pages=4800,additional_long_line_pages=720,additional_splits=dict(counts),total_pages=5520,organizer_handwriting_used=False))

def main():
    p=argparse.ArgumentParser();p.add_argument('--forms',type=int,nargs='+',default=list(range(1,9)));p.add_argument('--anchors-only',action='store_true');p.add_argument('--add-long-lines',action='store_true');a=p.parse_args()
    if a.add_long_lines:add_long_lines();return
    for n in a.forms:prepare(n,not a.anchors_only)
if __name__=='__main__':main()

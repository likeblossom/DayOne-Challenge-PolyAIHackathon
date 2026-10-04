"""Template-exact multilingual font synthesis with dense coverage and CUDA camera effects.

Labels describe the visible fields, including intentionally blank fields. Synthetic
camera images are for OCR fine-tuning; these records are not clinical simulations.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import random
import re
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, features

from cuda_form_effects import gpu_degrade, transform_bboxes
from schema_form_layout import bind_layout
from schema_form_values import sample_value, localized_enum, nested_labels

ROOT=Path(__file__).resolve().parents[1]
FORM_DIRS=[p.name.removesuffix('.schema.json') for p in sorted((ROOT/'data/form_structures').glob('[0-9][0-9]_*.schema.json'))]
W,H=1654,2339
PDF=ROOT/'data/organizer/data/Paper Registry/dossiers_specimen_10_patientes.pdf'
FONTROOT=ROOT/'data/handwriting_fonts'
LATIN=['allura','dancingscript','caveat','marckscript','badscript','sacramento','kalam','patrickhand','handlee','shadowsintolight','satisfy','parisienne']
ARABIC=['amiri','arefruqaa','lateef','scheherazadenew','reemkufi','mirza']

def slug(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    return re.sub('[^a-z0-9]+','_',s).strip('_')

def printed_spans(page):
    return [s for b in page.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['font'].startswith('Helvetica')]

def blank_template(doc, number):
    page=doc[number-1]
    # Remove handwriting text operators, leaving all graphic transforms balanced.
    stream=page.read_contents().decode('latin1')
    stream=re.sub(r'BT\b.*?\bET', lambda m: '' if '/F3' in m[0] else m[0],stream,flags=re.S)
    lines=stream.splitlines(); result=[]; blue=False
    for line in lines:
        if line.endswith(' RG'):
            rgb=list(map(float,line.split()[:3])); blue=rgb[2]>rgb[0]+.2
        if blue and line.startswith('n ') and line.endswith(' S'): continue
        result.append(line)
    xref=page.get_contents()[0]
    doc.update_stream(xref,'\n'.join(result).encode('latin1'))
    for extra in page.get_contents()[1:]: doc.update_stream(extra,b'')
    # Remove only source patient text in printed headers, not the form artwork.
    for s in printed_spans(page):
        if s['text'].startswith(('MÈRE —','Patiente fictive')):
            page.add_redact_annot(fitz.Rect(s['bbox']),fill=(.97,.74,.8))
    page.apply_redactions(images=0,graphics=0,text=0)
    pix=page.get_pixmap(matrix=fitz.Matrix(W/page.rect.width,H/page.rect.height),alpha=False)
    return Image.frombytes('RGB',(pix.width,pix.height),pix.samples).resize((W,H))

def slots_for(page, number):
    """Use vector coordinates for underlines and checkboxes; enumerate every table cell."""
    spans=printed_spans(page); slots=[]; width,height=page.rect.width,page.rect.height
    def add(key,rect,kind='text',hint='',row=None,col=None):
        x1,y1,x2,y2=rect
        slots.append(dict(key=key,box=[x1/width,y1/height,x2/width,y2/height],kind=kind,hint=hint,row=row,col=col))
    # Inline text: original writing underlines and the printed label immediately left.
    for drawing in page.get_drawings():
        color=drawing.get('color')
        if color and color[2]>color[0]+.2: continue
        rect=drawing['rect']
        if 6<rect.width<10 and 6<rect.height<10 and drawing.get('type')=='s':
            near=[s for s in spans if 0<s['bbox'][0]-rect.x1<22 and abs(s['origin'][1]-rect.y1)<15]
            hint=min(near,key=lambda s:abs(s['origin'][1]-rect.y1))['text'] if near else 'checkbox'
            add(f'check_{slug(hint)}_{round(rect.y0)}_{round(rect.x0)}',list(rect),'checkbox',hint)
        for item in drawing['items']:
            if item[0]!='l': continue
            a,b=item[1:]; length=b.x-a.x
            if length<25 or abs(a.y-b.y)>2 or (drawing.get('width') or 1)>.65: continue
            near=[s for s in spans if 0<=a.x-s['bbox'][2]<20 and abs(s['origin'][1]-a.y)<7]
            if not near: continue
            s=min(near,key=lambda s:abs(a.x-s['bbox'][2])); hint=s['text'].strip()
            if any(t in hint.lower() for t in ['cin','adresse','téléphone','nom du mari','patiente','nom/prénom']): continue
            add(f'{slug(hint)}_{round(a.y)}',[a.x,a.y-12,b.x,a.y-1],hint=hint)
    if number==2:
        for side,x in [('woman',132),('spouse',212)]:
            for row,key in enumerate(['hypertension','diabetes','hereditary','malformations','allergies']):
                add(f'family.{side}.{key}',[x+4,234+row*20,x+77,250+row*20],hint=key)
        for key,x,x2 in [('medical',311,376),('surgical',376,456),('gynecological',456,553)]:
            add(f'history.{key}',[x+5,240,x2-5,266],hint=key)
        for row,key in enumerate(['abortion','preterm','fetal_death','other']):
            for col,(field,x,x2) in enumerate([('count',152,220),('date',220,330),('place',330,420),('weeks',420,553)]):
                add(f'anomalies.{key}.{field}',[x+4,379+20*row,x2-4,395+20*row],hint=field,row=row,col=col)
        for col in range(5):
            for row,field in enumerate(['date','delivery_method','cesarean_indication','complication','weight_g','newborn_complication']):
                add(f'previous_deliveries.{col}.{field}',[152+81*col,530+28*row,227+81*col,553+28*row],hint=field,row=row,col=col)
    if number==3:
        rows=[('appointment_date',141),('attendance_date',159),('contacted',177),('weeks',195),
              ('weight_kg',231),('blood_pressure',249),('skeletal',267),('conjunctiva',285),('breast',303),('edema',321),
              ('fetal_movement',339),('fundal_cm',357),('fetal_heart',375),('speculum',393),('cervix',411),('presentation',429),('pelvis',447),
              ('glycosuria',481),('albuminuria',499),('rubella',517),('toxoplasmosis',535),('syphilis',553),('hepatitis_b',571),('hiv',589),
              ('hemoglobin',607),('platelets',625),('glucose',643),('rai',661),('iron',695),('examiner',731)]
        for col in range(9):
            for row,(key,y) in enumerate(rows):
                add(f'visits.{col}.{key}',[153+44.8*col,y,193+44.8*col,y+14],hint=key,row=row,col=col)
    # Fields printed with dots or no underline are absent from the underline list.
    extras={1:[('other_risk',[355,552,510,568],'complication')],
      4:[('other_facility',[248,176,373,191],'place'),('other_attendant',[248,242,373,257],'examiner'),
         ('cesarean_indication',[295,445,525,461],'cesarean_indication'),('other_complication',[330,631,395,646],'complication')],
      5:[('scar',[258,311,530,327],'scar'),('other_treatment',[114,545,207,559],'treatment'),
         ('other_family_planning',[343,637,402,652],'contraception'),('decline_reason',[48,713,500,734],'declined')],
      7:[('scar',[258,311,530,327],'scar'),('other_treatment',[114,545,207,559],'treatment'),
         ('other_family_planning',[343,637,402,652],'contraception'),('decline_reason',[48,713,500,734],'declined')]}
    for key,box,hint in extras.get(number,[]): add(key,box,hint=hint)
    # Stable unique keys, even where the source repeats exactly the same label.
    unique={s['key']:s for s in slots}
    return list(unique.values())


def render(template,slots,number,index,seed,capture_text_boxes=False,text_overrides=None,text_width_fraction=1.):
    rng=random.Random(seed); lang=['en','fr','ar'][index%3]
    families=ARABIC if lang=='ar' else LATIN; family=families[(index//3)%len(families)]
    paths=sorted((FONTROOT/family).glob('*.ttf'))
    fontpath=next((p for p in paths if 'Regular' in p.name),paths[0])
    # Font families, rather than arbitrary IDs of the same font, define the split.
    holdout={'parisienne','satisfy','mirza','reemkufi'}
    split='synthetic_test' if family in {'parisienne','mirza'} else 'validation' if family in holdout else 'train'
    page=template.copy(); draw=ImageDraw.Draw(page); fields={}; boxes={}
    ink=rng.choice([(18,41,120),(16,65,160),(25,25,30),(45,49,70)])
    occupied=set(rng.sample(range(9),rng.randint(3,9)))
    values={s['key']:sample_value(s,rng,lang,index,number) for s in slots}
    inapplicable=set()
    def depends(detail,parent,expected):
        value=values[parent][0]
        if not (expected in value if isinstance(value,list) else value==expected):inapplicable.add(detail)
    if number==1:depends('other_risk_factor','risk_factors','OTHER')
    if number==2:
        depends('rubella_vaccination_date','rubella_vaccinated',True)
        depends('hepatitis_b_vaccination_date','hepatitis_b_vaccinated',True)
        for i in range(5):
            method=values[f'previous_deliveries[{i}].delivery_method'][0]
            if method not in ['Cesarean','Césarienne','قيصرية']:inapplicable.add(f'previous_deliveries[{i}].cesarean_indication')
    if number==4:
        if values['delivery_setting'][0]=='HOME':values['facility_type']=('NOT_APPLICABLE',localized_enum('NOT_APPLICABLE',lang))
        depends('other_facility_type','facility_type','OTHER');depends('other_attendant','qualified_attendant_present',False)
        if values['delivery_mode'][0]!='INSTRUMENTAL_VAGINAL':values['instrument']=('NONE',localized_enum('NONE',lang))
        if 'CESAREAN' not in values['delivery_mode'][0]:inapplicable.add('cesarean_indication')
        depends('other_complication','complication_types','OTHER')
    if number in [5,7]:
        depends('cesarean_scar_condition','cesarean_performed',True)
        depends('other_family_planning_method','family_planning_method','OTHER')
        depends('reason_declined_family_planning','family_planning_method','NONE')
        wants=values['family_planning_method'][0]!='NONE'
        values['wants_family_planning']=(wants,['Yes','Oui','نعم'][['en','fr','ar'].index(lang)] if wants else ['No','Non','لا'][['en','fr','ar'].index(lang)])
    if number in [6,8]:
        depends('other_danger_sign','danger_signs','OTHER')
        depends('other_trauma_or_malformation','trauma_or_malformations','OTHER')
        depends('referral_facility','transferred',True)
    last_text_box=None
    def handwriting(text,b):
        nonlocal last_text_box
        x1,y1,x2,y2=[round(v*s) for v,s in zip(b,[W,H,W,H])]
        size=max(15,round((y2-y1)*rng.uniform(1.12,1.55)))
        font=ImageFont.truetype(str(fontpath),size)
        kw={'direction':'rtl','language':'ar'} if lang=='ar' else {}
        if lang=='ar':text=text.translate(str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩'))
        bb=font.getbbox(text,**kw);tw,th=bb[2]-bb[0],bb[3]-bb[1]
        patch=Image.new('RGBA',(max(1,tw+8),max(1,th+8)))
        ImageDraw.Draw(patch).text((4-bb[0],4-bb[1]),text,font=font,fill=ink+(255,),**kw)
        patch=patch.rotate(rng.uniform(-2.5,2.5),Image.Resampling.BICUBIC,expand=True)
        ratio=min((x2-x1-3)/patch.width,(y2-y1-2)/patch.height,1.2)
        patch=patch.resize((max(1,int(patch.width*ratio)),max(1,int(patch.height*ratio))),Image.Resampling.LANCZOS)
        px=x2-patch.width if lang=='ar' else x1;py=y1+max(0,(y2-y1-patch.height)//2)
        page.paste(patch,(px,py),patch)
        if capture_text_boxes:
            bounds=patch.getchannel('A').getbbox()
            last_text_box=[(px+bounds[0])/W,(py+bounds[1])/H,(px+bounds[2])/W,(py+bounds[3])/H] if bounds else None
        return text
    def mark(b):
        x1,y1,x2,y2=[round(v*s) for v,s in zip(b,[W,H,W,H])]
        cx=(x1+x2)//2;cy=(y1+y2)//2;d=max(5,(x2-x1)//2-1)
        if rng.random()<.5:draw.line([(cx-d,cy),(cx-2,cy+d),(cx+d,cy-d)],fill=ink,width=3)
        else:
            draw.line((cx-d,cy-d,cx+d,cy+d),fill=ink,width=3)
            draw.line((cx-d,cy+d,cx+d,cy-d),fill=ink,width=3)
    for slot in slots:
        key=slot['key'];b=slot['box'];val,text=values[key]
        if text_overrides and key in text_overrides:
            val=text=text_overrides[key]
            b=list(b);b[2]=b[0]+(b[2]-b[0])*text_width_fraction
        # Every fourth page per language is dense; remaining pages include missing data.
        blank=index//3%4!=0 and (rng.random()<.08 or (key.startswith('visits[') and int(re.search(r'\[(\d+)\]',key)[1]) not in occupied))
        if slot['kind']=='printed':blank=False
        if key in inapplicable:blank=True
        if text_overrides and key in text_overrides:blank=False
        entry={'schema_path':slot['schema_path'],'canonical_value':None if blank else val,'rendered_text':'' if blank else text,'status':'NOT_PROVIDED' if blank else 'KNOWN','kind':slot['kind'],'printed_label':slot['hint'],'visible_mark':False}
        if key in inapplicable:entry['status']='NOT_APPLICABLE'
        boxes[key]=b
        if not blank and slot['kind']=='checkbox':
            if val:mark(b)
            entry['rendered_text']='checked' if val else 'unchecked'
            entry['visible_mark']=bool(val)
        elif not blank and slot['kind']=='choice':
            chosen=val if isinstance(val,list) else [val];parts=[];components=[]
            for opt in slot['options']:
                checked=opt['value'] in chosen
                if checked:mark(opt['box']);parts.append(opt['label']+': checked')
                components.append(dict(value=opt['value'],checked=checked,bbox=opt['box']))
            unmapped=[v for v in chosen if v not in [o['value'] for o in slot['options']]]
            if unmapped:
                assert slot['note_box'],f'No writing space for {key}={unmapped}'
                parts.append(handwriting(', '.join(localized_enum(v,lang) for v in unmapped),slot['note_box']))
                if capture_text_boxes and last_text_box:entry['text_regions']=[dict(bbox=last_text_box,text=parts[-1])]
                components.append(dict(value=unmapped,checked=True,bbox=slot['note_box']))
            entry['components']=components;entry['rendered_text']='; '.join(parts);entry['visible_mark']=True
            allboxes=[c['bbox'] for c in components]
            boxes[key]=[min(v[0] for v in allboxes),min(v[1] for v in allboxes),max(v[2] for v in allboxes),max(v[3] for v in allboxes)]
        elif not blank and slot['kind']=='text':
            if slot.get('bp_part')=='systolic_bp_mmhg':text+='/'
            text=slot.get('text_prefix','')+text
            entry['rendered_text']=handwriting(text,b);entry['visible_mark']=True
            if capture_text_boxes and last_text_box:entry['text_regions']=[dict(bbox=last_text_box,text=entry['rendered_text'])]
        elif slot['kind']=='printed':entry['source']='preprinted row/column identifier; not synthesized handwriting'
        fields[key]=entry
    return page,fields,boxes,lang,family,split

def distort_spec(index,seed):
    rng=random.Random(seed); difficulty=['clean','rotated','low_quality','shadow','heavy','perspective'][index%6]
    angle=0 if difficulty=='clean' else rng.choice([-1,1])*rng.uniform(7,24) if difficulty in ['rotated','heavy'] else rng.uniform(-5,5)
    theta=math.radians(angle); scale=1. if difficulty=='clean' else .69 if abs(angle)>7 else .9
    c,s=math.cos(theta)*scale,math.sin(theta)*scale
    matrix=np.array([[c,-s,(1-c)*W/2+s*H/2],[s,c,(1-c)*H/2-s*W/2],[0,0,1]],dtype=np.float32)
    if difficulty=='perspective': matrix[2,:2]=[rng.uniform(-.1,.1)/W,rng.uniform(-.1,.1)/H]
    # Keep the entire paper inside the camera frame, including lower edge fields.
    corners=matrix@np.array([[0,W,W,0],[0,0,H,H],[1,1,1,1]])
    xy=corners[:2]/corners[2];lo=xy.min(axis=1);hi=xy.max(axis=1)
    if difficulty!='clean' and (lo[0]<.01*W or lo[1]<.01*H or hi[0]>.99*W or hi[1]>.99*H):
        fit=min(1.,.98*W/(hi[0]-lo[0]),.98*H/(hi[1]-lo[1]))
        shift=np.array([W,H])/2-fit*(lo+hi)/2
        matrix=(np.array([[fit,0,shift[0]],[0,fit,shift[1]],[0,0,1]])@matrix).astype(np.float32)
        scale*=fit
    meta=dict(profile=difficulty,rotation_deg=angle,scale=scale,homography=matrix.tolist(),noise=0 if difficulty=='clean' else .008 if difficulty in ['heavy','low_quality'] else .002,blur=5 if difficulty=='heavy' else 0,gpu=True,
              jpeg_quality=rng.randint(18,38) if difficulty in ['heavy','low_quality'] else rng.randint(75,93),
              resolution_scale=rng.uniform(.25,.42) if difficulty=='low_quality' else .6 if difficulty=='heavy' else 1.)
    return matrix,meta

def save_camera(image,path,meta):
    if meta['profile']!='clean':
        matrix=np.asarray(meta['homography']);corners=matrix@np.array([[0,W,W,0],[0,0,H,H],[1,1,1,1]])
        points=list(zip((corners[0]/corners[2]).tolist(),(corners[1]/corners[2]).tolist()))
        mask=Image.new('L',(W,H));ImageDraw.Draw(mask).polygon(points,fill=255)
        background=Image.new('RGB',(W,H),(112,105,91))
        image=Image.composite(image,background,mask)
    if meta['profile'] in ['shadow','heavy']:
        a=np.asarray(image).astype(np.float32);yy,xx=np.mgrid[:H,:W];
        lighting=.36+.64*np.clip((xx/W+.3*yy/H),0,1)
        a*=lighting[...,None];image=Image.fromarray(a.clip(0,255).astype('uint8'))
    factor=meta['resolution_scale']
    if factor<1:
        image=image.resize((int(W*factor),int(H*factor)),Image.Resampling.BILINEAR).resize((W,H),Image.Resampling.BILINEAR)
    image.save(path,quality=meta['jpeg_quality'])
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--per-form',type=int,default=600);ap.add_argument('--output',default='data/forms');ap.add_argument('--forms',type=int,nargs='+',choices=range(1,9),default=list(range(1,9)));args=ap.parse_args()
    out=ROOT/args.output
    if out.exists(): raise SystemExit(f'Choose an unused output folder: {out}')
    assert torch.cuda.is_available() and features.check('raqm')
    out.mkdir();started=time.time();doc=fitz.open(PDF);pool=ThreadPoolExecutor(8)
    manifest=[];coverage={};counts=Counter();fontcounts=Counter();checksums=set();duplicates=0
    print(f'CUDA {torch.cuda.get_device_name(0)}; {args.per_form*len(set(args.forms))} pages; 18 font families',flush=True)
    for number,name in enumerate(FORM_DIRS,1):
        if number not in args.forms:continue
        folder=out/name;(folder/'images').mkdir(parents=True)
        slots=bind_layout(slots_for(doc[number-1],number),number,slug);template=blank_template(doc,number)
        (folder/'field_layout.json').write_text(json.dumps(slots,ensure_ascii=False,indent=2))
        cover=Counter();columnnames=['image_filename','language','font_family','split','profile','random_seed','fields_json','schema_json']
        with (folder/'labels.csv').open('w',newline='') as cf,(folder/'annotations.jsonl').open('w') as jf:
            writer=csv.DictWriter(cf,fieldnames=columnnames);writer.writeheader()
            for start in range(0,args.per_form,6):
                batch=[]
                for index in range(start,min(start+6,args.per_form)):
                    seed=20261004+number*100000+index
                    im,fields,boxes,lang,family,split=render(template,slots,number,index,seed)
                    mat,meta=distort_spec(index//3+index//36,seed)
                    batch.append((im,fields,boxes,lang,family,split,mat,meta,index,seed))
                images=gpu_degrade([b[0] for b in batch],[b[6] for b in batch],[b[7] for b in batch],'cuda',[b[9] for b in batch])
                futures=[]
                for im,b in zip(images,batch):
                    _,fields,boxes,lang,family,split,mat,meta,index,seed=b
                    finalboxes=transform_bboxes(boxes,mat,W,H)
                    for k,f in fields.items():
                        f['bbox']=finalboxes[k];cover[k]+=f['status']=='KNOWN'
                        for component in f.get('components',[]):component['bbox']=transform_bboxes({'c':component['bbox']},mat,W,H)['c']
                    filename=f'{number:02d}_{index:06d}.jpg'
                    futures.append(pool.submit(save_camera,im,folder/'images'/filename,meta))
                    record=dict(image_filename=filename,form_id=name,language=lang,font_family=family,split=split,profile=meta['profile'],random_seed=seed,distortions=meta,fields=fields,schema=nested_labels(fields))
                    jf.write(json.dumps(record,ensure_ascii=False)+'\n')
                    writer.writerow({k:record[k] for k in columnnames if k not in ['fields_json','schema_json']}|{'fields_json':json.dumps(fields,ensure_ascii=False),'schema_json':json.dumps(record['schema'],ensure_ascii=False)})
                    manifest.append({k:record[k] for k in ['image_filename','form_id','language','font_family','split','profile']})
                    counts[meta['profile']]+=1;fontcounts[family]+=1
                for future in futures:
                    checksum=future.result();duplicates+=checksum in checksums;checksums.add(checksum)
                cf.flush();jf.flush()
                if start%60==0: print(f'{name}: {start+len(batch)}/{args.per_form}; {len(manifest)/(time.time()-started):.1f} pages/s',flush=True)
        coverage[name]=dict(cover)
    pool.shutdown()
    with (out/'manifest.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(manifest[0]));writer.writeheader();writer.writerows(manifest)
    report=dict(pages=len(manifest),seconds=round(time.time()-started),cuda=True,profiles=dict(counts),fonts=dict(fontcounts),exact_duplicates=duplicates,
                never_filled={k:[f for f,n in v.items() if n==0] for k,v in coverage.items()},field_coverage=coverage,
                limitations=['Font-based synthesis, not a learned human handwriting model.','Clinical plausibility is not validated; use for OCR, not clinical modeling.','Row and column identifiers already printed on forms are labeled as printed, not handwriting.','Template artwork is shared with organizers; synthetic-test is not an independent layout test.'])
    (out/'report.json').write_text(json.dumps(report,indent=2))
    # Selection spans all languages/profiles; browse exact files via the HTML gallery.
    preview=out/'preview.html';parts=['<meta charset="utf-8"><title>Schema-complete dataset previews</title><style>body{font-family:sans-serif}img{width:31%;vertical-align:top;margin:1%}h2{clear:both}</style>']
    for name in FORM_DIRS:
        if not (out/name).exists():continue
        parts.append(f'<h2>{name}</h2>')
        for i in [0,4,8,9,13,17,36,73,110]:
            if i<args.per_form:parts.append(f'<a href="{name}/images/{int(name[:2]):02d}_{i:06d}.jpg"><img src="{name}/images/{int(name[:2]):02d}_{i:06d}.jpg"></a>')
    preview.write_text('\n'.join(parts))
    print(json.dumps({k:v for k,v in report.items() if k!='field_coverage'},ensure_ascii=False),flush=True)
    if duplicates:raise SystemExit(f'Exact duplicate images: {duplicates}')
    from audit_diverse_forms import audit
    audit(out)

if __name__=='__main__': main()

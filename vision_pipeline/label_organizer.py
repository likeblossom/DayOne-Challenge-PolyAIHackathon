"""Independent PDF-vector reference labels, with provenance and review exclusions.

Never uses the trained OCR/detector. The 200-row registry CSV does not match the
10 PDF patients (e.g. patient 1 age: CSV 24, PDF 31), so no invented join is made.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
import fitz
from .common import *
from .grammar import parse

SOURCE=ROOT/'data/organizer'/'data'/'Paper Registry'

def characters(page):
    result=[]
    for b in page.get_text('rawdict')['blocks']:
        for line in b.get('lines',[]):
            for span in line['spans']:
                if span['font'].startswith('Helvetica'):continue
                for c in span['chars']:result.append(c)
    return result

def text_in(chars,box,page):
    rect=fitz.Rect([v*z for v,z in zip(box,[page.rect.width,page.rect.height]*2)])
    rect=rect+(-1.5,-1.5,1.5,1.5)
    selected=[c for c in chars if rect.contains(fitz.Point((c['bbox'][0]+c['bbox'][2])/2,(c['bbox'][1]+c['bbox'][3])/2))]
    # Preserve the PDF content-stream order, including actual space glyphs.
    return ''.join(c['c'] for c in selected).strip(),selected

def marked(page,box):
    rect=fitz.Rect([v*z for v,z in zip(box,[page.rect.width,page.rect.height]*2)])+(-2,-2,2,2)
    for d in page.get_drawings():
        color=d.get('color')
        if color and color[2]>color[0]+.2:
            center=fitz.Point((d['rect'].x0+d['rect'].x1)/2,(d['rect'].y0+d['rect'].y1)/2)
            if rect.contains(center):return True
    return False

def page_labels(page,number):
    form=FORMS[number-1];slots=read_json(ROOT/'data/forms'/form/'field_layout.json');chars=characters(page);fields={}
    for slot in slots:
        key=slot['key'];kind=slot['kind'];spec=slot['spec'];raw='';entry=dict(schema_path=slot['schema_path'],bbox=slot['box'],kind=kind,source='PDF vector glyphs/checkbox strokes',reviewed=False,score_eligible=False)
        if kind=='printed':
            entry.update(value=slot['fixed'],status='KNOWN',raw_text=str(slot['fixed']),score_eligible=True)
        elif kind=='checkbox':entry.update(value=marked(page,slot['box']),status='KNOWN',raw_text='checked' if marked(page,slot['box']) else 'unchecked',score_eligible=True)
        elif kind=='choice':
            selected=[opt['value'] for opt in slot['options'] if marked(page,opt['box'])]
            if spec['type']=='array':entry.update(value=selected,status='KNOWN',raw_text=';'.join(map(str,selected)),score_eligible=True)
            elif len(selected)==1:entry.update(value=selected[0],status='KNOWN',raw_text=str(selected[0]),score_eligible=True)
            else:entry.update(value=None,status='NOT_PROVIDED' if not selected else 'NEEDS_REVIEW',raw_text='',issues=['No explicit choice or conflicting choices'],score_eligible=not selected)
            if slot.get('note_box'):
                note,_=text_in(chars,slot['note_box'],page)
                if note:entry.update(score_eligible=False,review_reason='Free-text choice note requires independent review',note_text=note)
        else:
            box=slot['box'];raw,selected=text_in(chars,box,page)
            # Read an entire BP pair before taking its systolic/diastolic component.
            if key.endswith(('systolic_bp_mmhg','diastolic_bp_mmhg')):
                sister=key.replace('systolic','diastolic') if key.endswith('systolic_bp_mmhg') else key.replace('diastolic','systolic')
                other=next(s for s in slots if s['key']==sister)['box'];box=[min(box[0],other[0]),min(box[1],other[1]),max(box[2],other[2]),max(box[3],other[3])]
                raw,selected=text_in(chars,box,page)
            parsed=parse(form,key,raw,observed_blank=not selected)
            entry.update(value=parsed['value'],status=parsed['status'],raw_text=raw,issues=parsed['issues'],score_eligible=parsed['status'] in ['KNOWN','NOT_PROVIDED','UNKNOWN','NOT_APPLICABLE'])
            # Source-side parsing is a draft annotation, not a model prediction.
            if selected:
                x1=min(c['bbox'][0] for c in selected);y1=min(c['bbox'][1] for c in selected);x2=max(c['bbox'][2] for c in selected);y2=max(c['bbox'][3] for c in selected)
                entry['glyph_bbox']=[x1/page.rect.width,y1/page.rect.height,x2/page.rect.width,y2/page.rect.height]
        fields[key]=entry
    return fields

def main():
    target=DATA/'organizer_test';target.mkdir(parents=True,exist_ok=True)
    doc=fitz.open(SOURCE/'dossiers_specimen_10_patientes.pdf');seen={};rows=[];pending=[];counts=Counter();known=0
    for image in sorted(SOURCE.glob('*')):
        if image.suffix.lower() not in ['.jpg','.png','.jpeg']:continue
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in seen:
            pending.append(dict(image=str(image.relative_to(ROOT)),reason='EXACT_DUPLICATE',canonical_image=seen[digest]));continue
        seen[digest]=str(image.relative_to(ROOT));m=re.search(r'patientes-(\d+)',image.name)
        if not m:
            pending.append(dict(image=str(image.relative_to(ROOT)),reason='NO_PDF_PAGE_MAPPING: manual annotation required'));continue
        page_no=int(m[1]);number=(page_no-1)%8+1;fields=page_labels(doc[page_no-1],number)
        rows.append(dict(image=str(image.relative_to(ROOT)),image_sha256=digest,form_id=FORMS[number-1],pdf_page=page_no,document_group=f'pdf_document_{(page_no-1)//8+1:02d}',fields=fields,provenance='Independent PDF vector annotation; not model pseudo-labels; manual audit pending',human_review_complete=False))
        for key,f in fields.items():counts[f['status']]+=1;known+=f['score_eligible']
    with (target/'labels.jsonl').open('w') as out:
        for row in rows:out.write(json.dumps(row,ensure_ascii=False)+'\n')
    with (target/'field_labels.csv').open('w',newline='') as out:
        columns=['image','form_id','pdf_page','field','value','raw_text','status','score_eligible','reviewed','source'];writer=csv.DictWriter(out,fieldnames=columns);writer.writeheader()
        for row in rows:
            for key,f in row['fields'].items():writer.writerow(dict(image=row['image'],form_id=row['form_id'],pdf_page=row['pdf_page'],field=key,value=json.dumps(f['value'],ensure_ascii=False),**{k:f.get(k,'') for k in columns[5:]}))
    write_json(target/'exclusions.json',pending)
    write_json(REPORTS/'organizer_label_report.json',dict(unique_pdf_mapped_images=len(rows),excluded=pending,status_counts=dict(counts),score_eligible_fields=known,manually_reviewed_fields=0,csv_join_used=False,csv_join_reason='CSV first row age=24; PDF patient 1 age=31. No verified identifier join.',caveats=['Template geometry shared with synthetic training; this tests handwriting/domain shift, not unseen forms.','PDF-vector labels are draft reference annotations, not a fully human-reviewed benchmark.','Exact duplicate images are counted once.','No direct personal identifiers are extracted or copied.']))
    print(f'{len(rows)} unique PDF-mapped test images; {known} eligible field labels; {dict(counts)}',flush=True)

if __name__=='__main__':main()

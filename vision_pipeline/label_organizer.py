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
import numpy as np
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
    cell=fitz.Rect([v*z for v,z in zip(box,[page.rect.width,page.rect.height]*2)])
    rect=cell+(-2,-2,2,2)
    for d in page.get_drawings():
        if not d.get('color') or not d['rect'].intersects(rect):continue
        items=d['items']
        # Printed squares and surrounding frames are closed four-edge paths.
        # Pen ticks/crosses are open diagonal strokes, regardless of ink color.
        lines=[item for item in items if item[0]=='l']
        if len(lines)>=4 and lines[0][1].distance_to(lines[-1][2])<.1:continue
        if d['rect'].width>cell.width*3 or d['rect'].height>cell.height*3:continue
        for _,a,b in lines:
            dx=abs(a.x-b.x);dy=abs(a.y-b.y)
            if min(dx,dy)<min(cell.width,cell.height)*.18:continue
            if rect.contains(fitz.Point((a.x+b.x)/2,(a.y+b.y)/2)):return True
    return False

def printed_alignment(reference,page):
    """Source-PDF annotation geometry only; never used by app inference."""
    def spans(p):
        out={}
        for block in p.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    if not span['font'].startswith('Helvetica'):continue
                    text=span['text'].strip()
                    if len(text)<2 or text.startswith(('Patiente','MÈRE','SPÉCIMEN','Document synthétique')):continue
                    x1,y1,x2,y2=span['bbox'];out.setdefault(text,[]).append([(x1+x2)/2,(y1+y2)/2])
        return out
    source=spans(reference);target=spans(page);pairs=[]
    for text,points in source.items():
        if text not in target:continue
        for point in points:
            nearest=min(target[text],key=lambda other:np.linalg.norm(np.asarray(other)-point))
            if np.linalg.norm(np.asarray(nearest)-point)<40:pairs.append((point,nearest))
    if len(pairs)<8:return None,dict(accepted=False,reason='too_few_printed_correspondences')
    src=np.array([p[0] for p in pairs]);dst=np.array([p[1] for p in pairs]);x=np.c_[src,np.ones(len(src))];keep=np.ones(len(src),bool)
    for _ in range(5):
        if keep.sum()<8:break
        matrix=np.linalg.lstsq(x[keep],dst[keep],rcond=None)[0]
        residual=np.linalg.norm(x@matrix-dst,axis=1);keep=residual<max(.4,float(np.median(residual))*3)
    accepted=bool(keep.sum()>=8 and np.median(residual)<1 and min(np.ptp(src[keep],axis=0)/[reference.rect.width,reference.rect.height])>.25)
    return matrix if accepted else None,dict(accepted=accepted,inliers=int(keep.sum()),matches=len(src),median_error_points=float(np.median(residual)))


def page_labels(page,number,alignment=None):
    form=FORMS[number-1];slots=read_json(ROOT/'data/forms'/form/'field_layout.json');chars=characters(page);fields={}
    if alignment is not None:
        def transform(box):
            x1,y1,x2,y2=box;points=np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]])*[page.rect.width,page.rect.height]
            projected=np.c_[points,np.ones(4)]@alignment/[page.rect.width,page.rect.height]
            return [*projected.min(0),*projected.max(0)]
        for slot in slots:
            slot['box']=transform(slot['box'])
            if slot.get('note_box'):slot['note_box']=transform(slot['note_box'])
            for option in slot.get('options',[]):option['box']=transform(option['box'])
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
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DATA/'organizer_test')
    parser.add_argument('--align-printed-template',action='store_true',help='Follow each source PDF page transform using printed spans, independently of ML outputs')
    parser.add_argument('--report',type=Path,default=REPORTS/'organizer_label_report.json');args=parser.parse_args()
    target=args.output;target.mkdir(parents=True,exist_ok=True)
    doc=fitz.open(SOURCE/'dossiers_specimen_10_patientes.pdf');seen={};rows=[];pending=[];counts=Counter();known=0
    for image in sorted(SOURCE.glob('*')):
        if image.suffix.lower() not in ['.jpg','.png','.jpeg']:continue
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in seen:
            pending.append(dict(image=str(image.relative_to(ROOT)),reason='EXACT_DUPLICATE',canonical_image=seen[digest]));continue
        seen[digest]=str(image.relative_to(ROOT));m=re.search(r'patientes-(\d+)',image.name)
        if not m:
            pending.append(dict(image=str(image.relative_to(ROOT)),reason='NO_PDF_PAGE_MAPPING: manual annotation required'));continue
        page_no=int(m[1]);number=(page_no-1)%8+1
        alignment,geometry=printed_alignment(doc[number-1],doc[page_no-1]) if args.align_printed_template else (None,dict(accepted=False,reason='legacy_fixed_annotation_regions'))
        fields=page_labels(doc[page_no-1],number,alignment)
        if args.align_printed_template and not geometry['accepted']:
            for field in fields.values():field.update(score_eligible=False,review_reason='Source annotation geometry could not be verified')
        rows.append(dict(image=str(image.relative_to(ROOT)),image_sha256=digest,form_id=FORMS[number-1],pdf_page=page_no,document_group=f'pdf_document_{(page_no-1)//8+1:02d}',fields=fields,annotation_geometry=geometry,provenance='Independent PDF vector annotation; not model pseudo-labels; manual audit pending',human_review_complete=False))
        for key,f in fields.items():counts[f['status']]+=1;known+=f['score_eligible']
    with (target/'labels.jsonl').open('w') as out:
        for row in rows:out.write(json.dumps(row,ensure_ascii=False)+'\n')
    with (target/'field_labels.csv').open('w',newline='') as out:
        columns=['image','form_id','pdf_page','field','value','raw_text','status','score_eligible','reviewed','source'];writer=csv.DictWriter(out,fieldnames=columns);writer.writeheader()
        for row in rows:
            for key,f in row['fields'].items():writer.writerow(dict(image=row['image'],form_id=row['form_id'],pdf_page=row['pdf_page'],field=key,value=json.dumps(f['value'],ensure_ascii=False),**{k:f.get(k,'') for k in columns[5:]}))
    write_json(target/'exclusions.json',pending)
    write_json(args.report,dict(unique_pdf_mapped_images=len(rows),excluded=pending,status_counts=dict(counts),score_eligible_fields=known,manually_reviewed_fields=0,checkbox_annotation='Open diagonal PDF strokes including black ticks and blue crosses; closed printed borders excluded',csv_join_used=False,csv_join_reason='CSV first row age=24; PDF patient 1 age=31. No verified identifier join.',caveats=['Template geometry shared with synthetic training; this tests handwriting/domain shift, not unseen forms.','PDF-vector labels are draft reference annotations, not a fully human-reviewed benchmark.','Exact duplicate images are counted once.','No direct personal identifiers are extracted or copied.']))
    print(f'{len(rows)} unique PDF-mapped test images; {known} eligible field labels; {dict(counts)}',flush=True)

if __name__=='__main__':main()

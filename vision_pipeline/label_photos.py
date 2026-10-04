"""Visual, non-model reference annotations for the five organizer camera photos.

These are alternate split-page layouts, NOT the eight-page PDF geometry. Unknown
transcriptions are deliberately not invented. No direct identifiers are copied.
"""
import csv
import hashlib
import json
from .common import *

PHOTO_FORMS={'1-1.jpg':0,'1-2.jpg':1,'1-3.jpg':1,'1-4.jpg':2,'1-5.jpg':2}
# Independently read from the source photographs. Only unambiguous safe fields.
VISUAL={
 '1-1.jpg':{},
 '1-2.jpg':{},
 '1-3.jpg':{'living_children':dict(value=0,raw_text='00',status='KNOWN')},
 '1-4.jpg':{},'1-5.jpg':{},
}

def main():
    target=DATA/'organizer_test';target.mkdir(parents=True,exist_ok=True);records=[]
    for name,index in PHOTO_FORMS.items():
        path=ROOT/'data/organizer'/'data'/'Paper Registry'/name;form=FORMS[index]
        fields={slot['key']:dict(value=None,status='NEEDS_REVIEW',raw_text='',score_eligible=False,
                   reason='Alternate split-page photograph: visible/absent field and transcription require adjudication',
                   reviewed=False,schema_path=slot['schema_path'])
                for slot in read_json(ROOT/'data/forms'/form/'field_layout.json') if slot['kind']!='printed'}
        for key,value in VISUAL[name].items():
            fields[key].update(value,score_eligible=True,reviewed=True,reason='Assistant visual transcription; independent human confirmation recommended')
        records.append(dict(image=str(path.relative_to(ROOT)),image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            form_id=form,form_type_visually_reviewed=True,layout='ALTERNATE_SPLIT_PAGE',document_group='camera_photo_set_01',
            fields=fields,provenance='Visual inspection, not OCR pseudo-labels',human_review_complete=False))
    with (target/'photo_labels.jsonl').open('w') as f:
        for row in records:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    with (target/'photo_field_labels.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['image','form_id','field','value','raw_text','status','score_eligible','reviewed','reason'])
        for row in records:
            for key,entry in row['fields'].items():w.writerow([row['image'],row['form_id'],key,json.dumps(entry['value'],ensure_ascii=False),*[entry[k] for k in ['raw_text','status','score_eligible','reviewed','reason']]])
    write_json(REPORTS/'camera_photo_label_report.json',dict(images=5,form_labels_visually_reviewed=5,
        score_eligible_value_fields=1,pending_fields=sum(not e['score_eligible'] for row in records for e in row['fields'].values()),
        caveat='Five real camera photos are separate alternate-layout stress cases. Full reliable field ground truth is not yet available.'))

if __name__=='__main__':main()

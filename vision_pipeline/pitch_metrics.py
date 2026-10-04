"""Recompute pitch numbers from frozen predictions; never infer scores from slides."""
import json,re,unicodedata
from collections import Counter
from .common import BASE,DATA,REPORTS,FORMS,read_json,write_json

def format_key(value):
    if not isinstance(value,str):return value
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if c.isalnum())

def equal(a,b,normalized=False,legacy=False):
    if isinstance(b,list):
        if not isinstance(a,list):
            if not legacy:return False
            a=a or []
        return set(a)==set(b)
    if normalized and isinstance(a,str) and isinstance(b,str):return format_key(a)==format_key(b)
    return a==b

def distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1):nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=nxt
    return row[-1]

def score_pages(truths,folder,relative=True,legacy=False):
    c=Counter();characters=errors=words=word_errors=0
    for truth in truths:
        path=folder/f'page_{truth["pdf_page"]:02d}'
        record=read_json(path/('relative/prediction.json' if relative else 'prediction.json'))
        for key,t in truth['fields'].items():
            if not t.get('score_eligible') or t['kind']=='printed':continue
            f=record['fields'].get(key,{});pred=f.get('value');exact=equal(pred,t['value'],legacy=legacy);norm=equal(pred,t['value'],True,legacy)
            c['fields']+=1;c['exact']+=exact;c['format_normalized']+=norm
            c['review']+=f.get('status')=='NEEDS_REVIEW'
            c['machine_known']+=f.get('status')=='KNOWN';c['machine_known_normalized_correct']+=norm and f.get('status')=='KNOWN'
            if t['status']=='KNOWN':c['filled_fields']+=1;c['filled_normalized']+=norm
            if t['kind']=='text' and t['status']=='KNOWN':
                c['filled_text']+=1;c['filled_text_exact']+=exact;c['filled_text_normalized']+=norm
                candidates=f.get('raw_candidates',[]);raw=candidates[0]['text'] if candidates else ''
                # Raw OCR metrics retain punctuation, accents, case and decimal points.
                reference=unicodedata.normalize('NFC',t['raw_text']).strip();raw=unicodedata.normalize('NFC',raw).strip()
                characters+=len(reference);errors+=distance(raw,reference)
                rw=reference.split();pw=raw.split();words+=len(rw);word_errors+=distance(pw,rw)
                c['text_with_ocr']+=bool(candidates)
            if t['kind']=='text' and t['status']=='NOT_PROVIDED':c['blank_text']+=1;c['blank_false_value']+=pred is not None
    return dict(pages=len(truths),counts=dict(c),overall_exact=c['exact']/c['fields'],overall_normalized=c['format_normalized']/c['fields'],filled_text_exact=c['filled_text_exact']/c['filled_text'],filled_text_normalized=c['filled_text_normalized']/c['filled_text'],raw_cer=errors/max(characters,1),raw_wer=word_errors/max(words,1),reference_characters=characters,character_edits=errors,reference_words=words,word_edits=word_errors)

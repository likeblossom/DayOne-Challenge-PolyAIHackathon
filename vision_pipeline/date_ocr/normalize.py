"""Conservative date normalization: no inferred current year or silent century pivot."""
import re,unicodedata
from datetime import date

MONTHS=[
 ('january','janvier','يناير','jan'),('february','fevrier','فبراير','feb','fev'),
 ('march','mars','مارس','mar'),('april','avril','ابريل','أبريل','apr','avr'),
 ('may','mai','مايو'),('june','juin','يونيو','jun'),('july','juillet','يوليو','jul','juil'),
 ('august','aout','اغسطس','أغسطس','aug'),('september','septembre','سبتمبر','sep','sept'),
 ('october','octobre','اكتوبر','أكتوبر','oct'),('november','novembre','نوفمبر','nov'),
 ('december','decembre','ديسمبر','dec')]

def folded(text):
    text=''.join(str(unicodedata.digit(c)) if c.isdigit() else c for c in str(text))
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))

def parse_date(raw,date_order=None):
    if date_order not in [None,'DMY','MDY']:raise ValueError('date_order must be explicit DMY, MDY or None')
    text=' '.join(folded(raw).strip().split())
    result=dict(value=None,status='NEEDS_REVIEW',raw_text=str(raw),normalized_text=text,issues=[],normalizations=[],suggestions=[],grammar_score=0.,components={})
    if not text:result.update(status='ILLEGIBLE');result['issues'].append('NO_DATE_TEXT');return result
    def complete(y,m,d):
        result['components']=dict(year=y,month=m,day=d)
        try:date(y if y is not None and y>=100 else 2000,m,d)
        except ValueError:result['issues'].append('INVALID_CALENDAR_DATE');return result
        if y is None:result['issues'].append('MISSING_YEAR');return result
        if y<100:result['components']={'year_suffix':y,'month':m,'day':d};result['issues'].append('AMBIGUOUS_CENTURY');return result
        try:
            if not 1900<=y<=2100:raise ValueError()
            result.update(value=date(y,m,d).isoformat(),status='KNOWN',grammar_score=1.)
        except ValueError:result['issues'].append('INVALID_CALENDAR_DATE')
        return result
    numeric=re.fullmatch(r'(\d{1,4})\s*([/.-])\s*(\d{1,2})\s*\2\s*(\d{1,4})',text)
    if numeric:
        a,b,c=int(numeric[1]),int(numeric[3]),int(numeric[4])
        if len(numeric[1])==4:return complete(a,b,c)
        if len(numeric[1])>2 or len(numeric[4]) not in [2,4]:result['issues'].append('INVALID_DATE_FORMAT');return result
        options=[]
        for order,month,day in [('DMY',b,a),('MDY',a,b)]:
            try:date(c if c>=100 else 2000+c,month,day);options.append((order,month,day))
            except ValueError:pass
        if not options:result['issues'].append('INVALID_CALENDAR_DATE');return result
        unique={(m,d) for _,m,d in options}
        if len(unique)>1 and date_order is None:
            result['issues'].append('AMBIGUOUS_DATE_ORDER');result['components']={'year':c} if c>=100 else {'year_suffix':c};return result
        chosen=next((o for o in options if o[0]==date_order),options[0])
        if len(unique)>1:result['normalizations'].append('DATE_ORDER_CONTEXT:'+date_order)
        elif date_order and chosen[0]!=date_order:result['normalizations'].append('UNAMBIGUOUS_ALTERNATE_ORDER:'+chosen[0])
        return complete(c,chosen[1],chosen[2])
    # Written month names support EN/FR/AR and ordinals. No fuzzy OCR autocorrection.
    cleaned=re.sub(r'(?<=\d)(?:st|nd|rd|th|er)\b','',text).replace(',',' ')
    tokens=cleaned.split();month_hits=[]
    for i,t in enumerate(tokens):
        for month,aliases in enumerate(MONTHS,1):
            if t.rstrip('.') in [folded(a) for a in aliases]:month_hits.append((i,month))
    if len(month_hits)==1 and len(tokens) in [2,3]:
        i,month=month_hits[0];numbers=[t for j,t in enumerate(tokens) if j!=i]
        if all(re.fullmatch(r'\d{1,4}',t) for t in numbers):
            if len(numbers)==1:return complete(None,month,int(numbers[0]))
            return complete(int(numbers[1]),month,int(numbers[0]))
    result['issues'].append('INVALID_OR_UNSUPPORTED_DATE_FORMAT');return result

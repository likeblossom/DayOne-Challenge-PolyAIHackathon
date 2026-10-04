"""Auditable extraction grammar, not clinical advice or a diagnostic rule engine.

Ranges are deliberately broad OCR sanity checks. Schema-scoped unit corrections
are auditable review proposals, never permission to silently edit numeric digits.
"""
import math
import re
import unicodedata
from datetime import date,datetime
from difflib import get_close_matches
from .common import leaves,wildcard,FORMS,REPORTS,write_json
from .unit_grammar import policy as unit_policy,parse_numeric

RANGES={
 'age_years':(8,70),'age_days':(0,730),'temperature_c':(25,45),
 'weight_kg':(20,300),'weight_g':(200,20000),'birth_weight_g':(200,10000),
 'newborn_weight_g':(200,10000),'height_cm':(90,230),'length_cm':(20,110),
 'head_circumference_cm':(15,70),'gestational_age_weeks':(0,46),
 'systolic_bp_mmhg':(40,300),'diastolic_bp_mmhg':(20,200),'pulse_bpm':(20,250),
 'fetal_heart_rate_bpm':(40,250),'fundal_height_cm':(0,55),'hemoglobin_g_dl':(2,25),
 'platelets_per_ul':(1000,1500000),'blood_glucose_g_l':(.1,10),
 'gravidity':(0,30),'parity':(0,30),'living_children':(0,40),'count':(0,30),
 'tetanus_vaccination_dose':(1,5),'delivery_number':(1,5),
}
UNITS={
 'g':{'g':1,'gr':1,'gram':1,'grams':1,'gramme':1,'grammes':1,'غ':1,'غرام':1,'جم':1,'kg':1000,'كغ':1000,'كجم':1000},
 'kg':{'kg':1,'كغ':1,'كجم':1,'g':.001,'غ':.001},
 'cm':{'cm':1,'سم':1,'m':100,'م':100,'mm':.1},
 'mmHg':{'mmhg':1,'mm hg':1,'cmhg':10,'سم زئبق':10,'ملم زئبق':1},
 '°C':{'°c':1,'c':1,'℃':1,'celsius':1,'degc':1,'درجة':1},'bpm':{'bpm':1,'/min':1,'b/min':1},
 'g/dL':{'g/dl':1,'g/l':.1},'g/L':{'g/l':1,'mg/dl':.01,'mmol/l':.18016},
 'per uL':{'/ul':1,'/µl':1,'per ul':1,'k':1000,'x10^3/ul':1000,'10^3/ul':1000,'10^9/l':1000,'x10^9/l':1000},
 'days':{'day':1,'days':1,'jour':1,'jours':1,'j':1,'يوم':1,'أيام':1},
 'weeks':{'week':1,'weeks':1,'sem':1,'sem.':1,'semaine':1,'semaines':1,'sa':1,'أسبوع':1,'أسابيع':1},
 'years':{'year':1,'years':1,'ans':1,'an':1,'سنة':1,'سنوات':1},
}
TRUE={'yes','oui','true','checked','x','نعم','1'}
FALSE={'no','non','false','unchecked','لا','0'}
UNKNOWN={'unknown','inconnu','inconnue','inconnu(e)','nd','n.d.','غير معروف','غير معلوم'}
NA={'n/a','na','s/o','non applicable','not applicable','لا ينطبق'}
ALIASES={
 'f':'FEMALE','female':'FEMALE','feminin':'FEMALE','fille':'FEMALE','انثى':'FEMALE','أنثى':'FEMALE',
 'm':'MALE','male':'MALE','masculin':'MALE','garcon':'MALE','ذكر':'MALE',
 'indet.':'INDETERMINATE','indetermine':'INDETERMINATE','غير محدد':'INDETERMINATE',
 'negatif':'NEGATIVE','neg':'NEGATIVE','-':'NEGATIVE','سلبي':'NEGATIVE','positif':'POSITIVE','pos':'POSITIVE','+':'POSITIVE','إيجابي':'POSITIVE',
 'aucun':'NONE','neant':'NONE','none':'NONE','لا شيء':'NONE','autre':'OTHER','autres':'OTHER','آخر':'OTHER',
 'fixe':'FIXED','mobile':'MOBILE','vivant':'ALIVE','mort-ne':'STILLBORN','mort ne':'STILLBORN',
 'normal':'NORMAL','normales':'NORMAL','طبيعي':'NORMAL','pale':'PALE','decolorees':'PALE',
 'pilule':'PILL','diu':'IUD','voie basse':'NON_INSTRUMENTAL_VAGINAL',
}

def normalize(text):
    out=[]
    for c in unicodedata.normalize('NFKC',str(text)):
        try:out.append(str(unicodedata.decimal(c)))
        except ValueError:out.append(c)
    return ' '.join(''.join(out).replace('٫','.').replace('٬','').replace('\u200f','').replace('\u200e','').split()).strip()

def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',normalize(text).lower()) if not unicodedata.combining(c))

def catalog():
    result={}
    for number,form in enumerate(FORMS,1):
        rules={}
        for key,spec in leaves(number).items():
            leaf=key.split('.')[-1];typ=spec['type']
            rule=dict(spec,allow_blank=True,raw_text_preserved=True,invalid_action='NEEDS_REVIEW; never silently repair',normalization='Unicode digits, whitespace; explicit units only')
            if typ in ['double','integer']:
                assert leaf in RANGES,(form,key)
                rule['ocr_sanity_range']=list(RANGES[leaf]);rule['unit_aliases']=UNITS.get(spec.get('unit'),{})
                rule['unit_policy']=unit_policy(spec.get('unit'),rule['unit_aliases'])
                rule['normalization']='Unicode digits and typography; explicit unit conversions; schema-scoped OCR unit corrections require review.'
            elif typ=='string':
                rule['max_length']=40 if leaf=='record_code' else 120 if leaf in ['region','province','occupation','spouse_occupation','examiner_role','education_level'] else 500
                rule['allow_multiline']=True
                if leaf=='record_code':rule['pattern']=r'^[A-Za-z0-9][A-Za-z0-9_\-/ ]{0,39}$'
                elif leaf.endswith('_result') or leaf in ['glycosuria','albuminuria']:rule['semantic_note']='May be a qualitative result, titre, numeric result, or narrative; do not force binary.'
                else:rule['semantic_note']='Preserve narrative, negation, accents and Arabic; no medical autocorrection.'
            elif typ=='date':rule.update(formats=['YYYY-MM-DD','DD/MM/YYYY','DD-MM-YYYY','DD.MM.YYYY'],year_range=[1900,2100],ambiguous_two_digit_year='review')
            elif typ=='boolean':rule['allowed_text']=sorted(TRUE|FALSE)
            elif typ in ['enum','array']:rule['matching']='Exact schema values or explicit aliases; fuzzy suggestions require review.'
            rules[key]=rule
        result[form]=rules
    assert sum(map(len,result.values()))==218
    return result

RULES=catalog()

def parse(form,key,raw,*,observed_blank=False):
    rule=RULES[form][wildcard(key)];typ=rule['type'];text=normalize(raw);issues=[];changes=[];value=None;suggestions=[]
    out=dict(value=None,status='NEEDS_REVIEW',raw_text=str(raw),normalized_text=text,issues=issues,normalizations=changes,suggestions=suggestions,grammar_score=0.)
    if not text or text in {'—','_'}:
        out.update(status='NOT_PROVIDED' if observed_blank else 'ILLEGIBLE',grammar_score=1. if observed_blank else 0.);return out
    if folded(text) in UNKNOWN:out.update(status='UNKNOWN',grammar_score=1.);return out
    if folded(text) in NA:out.update(status='NOT_APPLICABLE',grammar_score=1.);return out
    if typ in ['double','integer']:
        numeric=parse_numeric(text,rule,key);out.update(numeric);issues=numeric['issues'];value=numeric['value']
    elif typ=='date':
        for pattern in ['%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y']:
            try:
                dt=datetime.strptime(text,pattern).date()
                if not 1900<=dt.year<=2100:issues.append('DATE_YEAR_OUT_OF_RANGE')
                value=dt.isoformat();break
            except ValueError:pass
        if value is None:issues.append('INVALID_OR_AMBIGUOUS_DATE')
    elif typ=='boolean':
        # Prefixes 1/2/3 label the three newborn advice responses.
        token=folded(re.sub(r'^[123]\s*:\s*','',text))
        if token in TRUE:value=True
        elif token in FALSE:value=False
        else:issues.append('UNRECOGNIZED_BOOLEAN')
    elif typ in ['enum','array']:
        allowed=rule.get('values',rule.get('items',{}).get('values',[]));mapping={folded(v.replace('_',' ')):v for v in allowed}
        mapping.update({k:v for k,v in ALIASES.items() if v in allowed})
        parts=re.split(r'[,;،]',text) if typ=='array' else [text];selected=[]
        for part in parts:
            token=folded(part.replace('_',' '));found=mapping.get(token)
            if found is None:
                issues.append('UNRECOGNIZED_OPTION: '+part);suggestions.extend(mapping[k] for k in get_close_matches(token,mapping,n=2,cutoff=.8))
            elif found not in selected:selected.append(found)
        value=selected if typ=='array' else selected[0] if selected else None
        if typ=='array':
            if 'NONE' in selected and len(selected)>1:issues.append('NONE_WITH_OTHER_OPTIONS')
            if 'NORMAL' in selected and len(selected)>1:issues.append('NORMAL_WITH_ABNORMAL_OPTIONS')
            if {'ODORLESS','FOUL_SMELLING'}<=set(selected):issues.append('CONTRADICTORY_LOCHIA_ODOR')
    else:
        value=text
        if len(value)>rule['max_length']:issues.append('TEXT_TOO_LONG')
        if 'pattern' in rule and not re.fullmatch(rule['pattern'],value):issues.append('INVALID_RECORD_CODE')
        if '\ufffd' in value or any(unicodedata.category(c)=='Cc' for c in value):issues.append('CORRUPTED_TEXT')
    out.update(value=value,status='NEEDS_REVIEW' if issues else 'KNOWN',grammar_score=.1 if issues else 1.)
    return out

def relations(fields,context=None):
    """All cross-field checks report conflicts; none overwrite source values."""
    values={k:v.get('value') if isinstance(v,dict) else v for k,v in fields.items()};context=context or {};issues={}
    def add(key,code):
        if key in values:issues.setdefault(key,[]).append(code)
    prefixes={''}|{k.rsplit('.',1)[0]+'.' for k in values if '.' in k}
    for pre in prefixes:
        a=values.get(pre+'systolic_bp_mmhg');b=values.get(pre+'diastolic_bp_mmhg')
        if isinstance(a,(int,float)) and isinstance(b,(int,float)) and a<=b:
            add(pre+'systolic_bp_mmhg','BP_ORDER_CONFLICT');add(pre+'diastolic_bp_mmhg','BP_ORDER_CONFLICT')
    def ordered(a,b,code):
        x=values.get(a,context.get(a));y=values.get(b,context.get(b))
        if x is not None and y is not None:
            try:
                if x>y:add(a,code);add(b,code)
            except TypeError:pass
    ordered('parity','gravidity','PARITY_EXCEEDS_GRAVIDITY')
    # Multiple births mean living_children may exceed parity: warning, not rejection.
    if isinstance(values.get('living_children'),int) and isinstance(values.get('parity'),int) and values['living_children']>values['parity']:
        add('living_children','REVIEW_MULTIPLE_BIRTHS_OR_COUNT_MISMATCH')
    for a,b in [('last_menstrual_period_date','expected_delivery_date'),('expected_delivery_date','post_term_date'),('delivery_date','consultation_date'),('consultation_date','follow_up_date'),('consultation_date','next_appointment_date')]:ordered(a,b,'DATE_ORDER_CONFLICT')
    for pre in sorted(p for p in prefixes if p.startswith('visits[')):
        # An attendance date can be before an appointment; do not forbid rescheduling.
        for name in ['appointment_date','attendance_date']:
            key=pre+name
            if values.get(key) and values.get('last_menstrual_period_date') and values[key]<values['last_menstrual_period_date']:add(key,'VISIT_BEFORE_LMP')
    conditions=[('other_risk_factor','risk_factors','OTHER'),('other_facility_type','facility_type','OTHER'),
      ('other_complication','complication_types','OTHER'),('cesarean_scar_condition','cesarean_performed',True),
      ('other_family_planning_method','family_planning_method','OTHER'),('referral_facility','transferred',True),
      ('other_danger_sign','danger_signs','OTHER'),('other_trauma_or_malformation','trauma_or_malformations','OTHER'),
      ('rubella_vaccination_date','rubella_vaccinated',True),('hepatitis_b_vaccination_date','hepatitis_b_vaccinated',True)]
    for child,parent,expected in conditions:
        p=values.get(parent);v=values.get(child)
        if p is None or v in [None,'','None','Néant','لا يوجد']:continue
        if not (expected in p if isinstance(p,list) else p==expected):add(child,'CONDITIONAL_FIELD_CONFLICT')
    if values.get('delivery_mode') not in [None,'PLANNED_CESAREAN','EMERGENCY_CESAREAN'] and values.get('cesarean_indication') not in [None,'','None','Néant','لا يوجد']:add('cesarean_indication','NON_CESAREAN_INDICATION_CONFLICT')
    if values.get('delivery_mode') not in [None,'INSTRUMENTAL_VAGINAL'] and values.get('instrument') not in [None,'NONE']:add('instrument','NON_INSTRUMENTAL_DELIVERY_CONFLICT')
    if values.get('delivery_setting')=='HOME' and values.get('facility_type') not in [None,'NOT_APPLICABLE']:add('facility_type','HOME_FACILITY_CONFLICT')
    if values.get('high_risk_pregnancy') is False and values.get('risk_factors'):add('risk_factors','RISK_CHECKBOX_CONFLICT')
    if values.get('wants_family_planning') is False and values.get('family_planning_method') not in [None,'NONE']:add('family_planning_method','FAMILY_PLANNING_CONFLICT')
    for key,v in values.items():
        if key.endswith('birth_weight_g') and isinstance(v,(int,float)) and v>10000:add(key,'VERIFY_NEWBORN_WEIGHT_UNIT')
        if isinstance(v,list):
            if 'NORMAL' in v and len(v)>1:add(key,'NORMAL_WITH_ABNORMAL_OPTIONS')
            if 'NONE' in v and len(v)>1:add(key,'NONE_WITH_OTHER_OPTIONS')
            if {'ODORLESS','FOUL_SMELLING'}<=set(v):add(key,'CONTRADICTORY_LOCHIA_ODOR')
    if values.get('complications_present') is False:
        for key in ['complication_types','complication_timing']:
            if values.get(key):add(key,'COMPLICATION_CHECKBOX_CONFLICT')
    if values.get('wants_family_planning') is True and values.get('reason_declined_family_planning') not in [None,'','None','Néant','لا يوجد']:
        add('reason_declined_family_planning','FAMILY_PLANNING_REASON_CONFLICT')
    for pre in prefixes:
        if pre.startswith('previous_pregnancy_anomalies[') and values.get(pre+'nature') not in [None,'OTHER'] and values.get(pre+'other_description') not in [None,'','None','Néant','لا يوجد']:
            add(pre+'other_description','NON_OTHER_DESCRIPTION_CONFLICT')
        if pre.startswith('previous_deliveries['):
            key=pre+'date'
            if values.get(key) and context.get('delivery_date') and values[key]>context['delivery_date']:add(key,'PREVIOUS_DELIVERY_AFTER_CURRENT')
    # Cross-form context is optional and must be supplied only after human linking.
    birth=context.get('delivery_date');consult=values.get('consultation_date')
    if birth and consult:
        try:
            delta=(date.fromisoformat(consult)-date.fromisoformat(birth)).days
            if delta<0:add('consultation_date','CONSULTATION_BEFORE_BIRTH')
            age=values.get('age_days')
            if isinstance(age,(int,float)) and abs(delta-age)>1:add('age_days','AGE_DATE_MISMATCH')
            timing=values.get('visit_timing')
            if timing=='DAY_7_TO_8' and delta not in [7,8] or timing=='AFTER_DAY_8' and delta<=8 or timing=='DAY_40_TO_50' and not 40<=delta<=50 or timing=='AFTER_DAY_50' and delta<=50:
                add('visit_timing','VISIT_TIMING_DATE_MISMATCH')
        except ValueError:pass
    return issues

def confidence(components,issues=(),agreement=True):
    # Heuristic reliability score, explicitly not a calibrated probability.
    weights={'form':.12,'localization':.20,'script':.08,'ocr':.35,'grammar':.15,'image_quality':.10}
    score=math.exp(sum(w*math.log(max(.001,min(1.,float(components.get(k,0.))))) for k,w in weights.items()))
    if not agreement:score=min(score*.65,.60)
    if issues:score=min(score*.4,.49)
    return round(min(.99,max(0.,score)),4)

if __name__=='__main__':
    write_json(REPORTS/'field_rules.json',RULES)
    print('Exported explicit rules for',sum(map(len,RULES.values())),'schema fields')

"""Typed synthetic OCR values and localized transcriptions (not clinical simulation)."""
import re
from datetime import date, timedelta

TEXT = {
 'region': [('Central','Centre','الوسط'),('North','Nord','الشمال'),('South','Sud','الجنوب')],
 'province': [('Province A','Province A','إقليم أ'),('Province B','Province B','إقليم ب')],
 'health_facility_name': [('Clinic Atlas','Clinique Atlas','عيادة الأطلس'),('Health Centre Noor','Centre de santé Nour','مركز النور الصحي')],
 'education_level': [('Primary','Primaire','ابتدائي'),('Secondary','Secondaire','ثانوي'),('University','Université','جامعي'),('None','Aucun','دون تعليم')],
 'occupation': [('Teacher','Enseignante','معلمة'),('Farmer','Agricultrice','مزارعة'),('Nurse','Infirmière','ممرضة'),('Shopkeeper','Commerçante','تاجرة')],
 'spouse_occupation': [('Driver','Chauffeur','سائق'),('Technician','Technicien','تقني'),('Teacher','Enseignant','معلم')],
 'hypertension': [('Mother','Mère','الأم'),('Father','Père','الأب'),('None','Néant','لا يوجد')],
 'diabetes': [('Mother','Mère','الأم'),('Brother','Frère','الأخ'),('None','Néant','لا يوجد')],
 'hereditary_diseases': [('Thalassemia','Thalassémie','ثلاسيميا'),('None','Néant','لا يوجد')],
 'malformations': [('Heart defect','Cardiopathie','عيب قلبي'),('None','Néant','لا يوجد')],
 'allergies': [('Penicillin','Pénicilline','بنسلين'),('Pollen','Pollen','لقاح'),('None','Néant','لا يوجد')],
 'medical': [('Asthma','Asthme','ربو'),('Anemia','Anémie','فقر دم'),('None','Néant','لا يوجد')],
 'surgical': [('Appendectomy','Appendicectomie','استئصال الزائدة'),('None','Néant','لا يوجد')],
 'gynecological': [('Regular cycles','Cycles réguliers','دورة منتظمة'),('Fibroid','Fibrome','ورم ليفي')],
 'place': [('Hospital A','Hôpital A','مستشفى أ'),('Clinic B','Clinique B','عيادة ب')],
 'other_description': [('Molar pregnancy','Grossesse molaire','حمل عنقودي'),('Ectopic pregnancy','Grossesse extra-utérine','حمل خارج الرحم')],
 'delivery_method': [('Vaginal','Voie basse','طبيعية'),('Cesarean','Césarienne','قيصرية')],
 'cesarean_indication': [('Breech','Siège','مقعدي'),('Fetal distress','Souffrance fœtale','ضائقة جنينية'),('None','Néant','لا يوجد')],
 'maternal_complication': [('Anemia','Anémie','فقر دم'),('Hemorrhage','Hémorragie','نزيف'),('None','Néant','لا يوجد')],
 'newborn_complication': [('Jaundice','Ictère','يرقان'),('None','Néant','لا يوجد')],
 'other_risk_factor': [('Asthma','Asthme','ربو'),('Renal disease','Maladie rénale','مرض كلوي')],
 'skeletal_abnormalities': [('None','Néant','لا يوجد'),('Scoliosis','Scoliose','جنف')],
 'conjunctiva_condition': [('Normal','Normales','طبيعي'),('Pale','Pâles','شاحب')],
 'breast_exam': [('Normal','Normal','طبيعي'),('Tender','Sensible','مؤلم')],
 'speculum_exam': [('Normal','Normal','طبيعي'),('Discharge','Leucorrhées','إفرازات')],
 'cervix_condition': [('Closed','Fermé','مغلق'),('Soft','Souple','لين')],
 'fetal_presentation': [('Cephalic','Céphalique','رأسي'),('Breech','Siège','مقعدي')],
 'pelvis_exam': [('Normal','Normal','طبيعي'),('Narrow','Rétréci','ضيق')],
 'examiner_role': [('Midwife','Sage-femme','قابلة'),('Doctor','Médecin','طبيب'),('Nurse','Infirmière','ممرضة')],
 'other_facility_type': [('Health post','Poste de santé','وحدة صحية')],
 'other_attendant': [('Midwife','Sage-femme','قابلة'),('Relative','Proche','قريبة')],
 'other_complication': [('Retained placenta','Rétention placentaire','احتباس المشيمة')],
 'newborn_abnormality': [('None','Néant','لا يوجد'),('Cleft lip','Fente labiale','شق الشفة')],
 'cesarean_scar_condition': [('Healed','Cicatrisée','ملتئمة'),('Inflamed','Inflammatoire','ملتهبة'),('Healing','En cicatrisation','قيد الالتئام')],
 'medications_taken': [('Paracetamol','Paracétamol','باراسيتامول'),('Iron','Fer','حديد'),('None','Néant','لا يوجد')],
 'other_treatment': [('Folate','Acide folique','حمض الفوليك'),('Local care','Soins locaux','عناية موضعية')],
 'other_family_planning_method': [('Condom','Préservatif','واقي'),('Implant','Implant','غرسة')],
 'reason_declined_family_planning': [('Wants pregnancy','Désir de grossesse','رغبة في الحمل'),('Undecided','Indécise','لم تقرر'),('Discuss later','À discuter plus tard','المناقشة لاحقًا')],
 'other_danger_sign': [('Lethargy','Léthargie','خمول'),('Dehydration','Déshydratation','جفاف')],
 'other_trauma_or_malformation': [('Cleft palate','Fente palatine','شق الحنك'),('Clubfoot','Pied bot','قدم حنفاء')],
 'vaccination_status': [('Up to date','À jour','مكتمل'),('Incomplete','Incomplet','غير مكتمل'),('Not vaccinated','Non vacciné','غير ملقح')],
 'decision': [('Routine follow-up','Suivi habituel','متابعة عادية'),('Refer for assessment','Référer pour bilan','إحالة للفحص')],
 'treatment': [('Local care','Soins locaux','عناية موضعية'),('No treatment','Aucun traitement','دون علاج')],
 'referral_facility': [('Hospital Atlas','Hôpital Atlas','مستشفى الأطلس'),('Clinic Noor','Clinique Nour','عيادة النور')],
}

ENUM_TEXT = {'OTHER':('Other','Autre','آخر'),'NONE':('None','Aucun','لا شيء'),
 'NOT_APPLICABLE':('N/A','S/O','لا ينطبق'),'FEMALE':('F','F','أنثى'),
 'MALE':('M','M','ذكر'),'INDETERMINATE':('Indet.','Indét.','غير محدد')}

def localized_enum(value, lang):
    return ENUM_TEXT.get(value,(str(value),)*3)[['en','fr','ar'].index(lang)]

def sample_value(slot, rng, lang, index, number):
    spec=slot['spec'];typ=spec['type'];key=slot['key'];name=key.split('.')[-1]
    li=['en','fr','ar'].index(lang);cycle=index//3+index//36+sum(map(ord,key))
    if 'fixed' in slot:return slot['fixed'],str(slot['fixed'])
    if typ=='enum':
        value=spec['values'][cycle%len(spec['values'])];return value,localized_enum(value,lang)
    if typ=='array':
        values=spec['items']['values'];value=[values[cycle%len(values)]]
        if rng.random()<.3:
            extra=rng.choice(values)
            if extra not in value:value.append(extra)
        return value,', '.join(localized_enum(v,lang) for v in value)
    if typ=='boolean':
        value=bool(rng.randrange(2))
        return value,(['Yes','Oui','نعم'] if value else ['No','Non','لا'])[li]
    if typ=='date':
        base=date(2024,1,1)+timedelta(days=index*2)
        if key.startswith('visits['):
            col=int(re.search(r'\[(\d+)\]',key)[1]);base+=timedelta(days=45+col*28+(name=='attendance_date'))
        elif key.startswith('previous_deliveries['):base-=timedelta(days=(6-int(re.search(r'\[(\d+)\]',key)[1]))*730)
        elif key.startswith('previous_pregnancy_anomalies['):base-=timedelta(days=1000+int(re.search(r'\[(\d+)\]',key)[1])*400)
        elif name=='expected_delivery_date':base+=timedelta(days=280)
        elif name=='post_term_date':base+=timedelta(days=294)
        elif 'vaccination' in name:base-=timedelta(days=500)
        elif name in ['next_appointment_date','follow_up_date']:base+=timedelta(days=14)
        return base.isoformat(),base.strftime('%d/%m/%Y')
    if typ in ['double','integer']:
        ranges={'age_years':(20,44),'age_days':(7,15) if number==6 else (40,60),
         'temperature_c':(36.2,38.4),'systolic_bp_mmhg':(100,145),'diastolic_bp_mmhg':(60,90),
         'pulse_bpm':(60,105),'weight_kg':(48,88),'weight_g':(2600,5700),'birth_weight_g':(2400,4300),
         'newborn_weight_g':(2400,4300),'length_cm':(47,61),'head_circumference_cm':(32,40),
         'height_cm':(147,178),'gestational_age_weeks':(8,40),'fundal_height_cm':(12,38),
         'fetal_heart_rate_bpm':(115,165),'hemoglobin_g_dl':(9,14),'platelets_per_ul':(150000,350000),
         'blood_glucose_g_l':(.7,1.3),'count':(1,3),'gravidity':(6,9),'parity':(5,5),'living_children':(3,5),
         'tetanus_vaccination_dose':(1,5)}
        lo,hi=ranges[name]
        value=round(rng.uniform(lo,hi),2 if name=='blood_glucose_g_l' else 1) if isinstance(lo,float) or name=='weight_kg' else rng.randint(lo,hi)
        if key.startswith('visits[') and name=='gestational_age_weeks':value=6+int(re.search(r'\[(\d+)\]',key)[1])*4
        if name=='tetanus_vaccination_dose':value=cycle%5+1
        return value,str(value)
    if name=='record_code':return f'S{number}-{index:05d}',f'S{number}-{index:05d}'
    options=TEXT.get(name)
    if options is None:
        assert name.endswith('_result') or name in ['glycosuria','albuminuria'],f'No value generator for {key}'
        options=[('Negative','Négatif','سلبي'),('Positive','Positif','إيجابي')]
    text=options[cycle%len(options)][li]
    return text,text

def nested_labels(fields):
    """Organizer envelope for every leaf; fixed-length arrays preserve column indices."""
    output={}
    for path,entry in fields.items():
        tokens=re.findall(r'([^.[\]]+)|\[(\d+)\]',path)
        parts=[int(i) if i else k for k,i in tokens];obj=output
        for pos,part in enumerate(parts):
            last=pos==len(parts)-1
            value={'value':entry['canonical_value'],'status':entry['status'],'confidence':1.0 if entry['status']=='KNOWN' else 0.0}
            if isinstance(obj,list):
                while len(obj)<=part:obj.append({})
                if last:obj[part]=value
                else:obj=obj[part]
            else:
                if last:obj[part]=value
                else:obj=obj.setdefault(part,[] if isinstance(parts[pos+1],int) else {})
    # Non-OTHER anomaly rows have no description input on the paper form.
    for row in output.get('previous_pregnancy_anomalies',[]):
        row.setdefault('other_description',{'value':None,'status':'NOT_APPLICABLE','confidence':1.0})
    return output

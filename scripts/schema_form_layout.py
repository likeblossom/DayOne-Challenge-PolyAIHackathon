"""Explicit organizer-schema to original PDF field bindings. No fallback auto-layout."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def schema_leaves(number):
    schema = json.loads(next((ROOT/'data/form_structures').glob(f'{number:02d}_*.schema.json')).read_text())
    result = {}
    def walk(fields, prefix=''):
        for key, spec in fields.items():
            path = prefix + key
            if spec['type'] == 'object': walk(spec['fields'], path+'.')
            elif spec['type'] == 'array' and spec['items']['type'] == 'object':
                walk(spec['items']['fields'], path+'[].')
            else: result[path] = spec
    walk(schema['fields'])
    return result

def wildcard(path):
    return re.sub(r'\[\d+\]', '[]', path)

def bind_layout(raw, number, slug):
    leaves = schema_leaves(number)
    result = []
    def get(label, nth=0):
        matches = [s for s in raw if slug(s['hint']) == label or s['key'] == label]
        if len(matches) <= nth: raise ValueError(f'Form {number}: missing physical field {label}/{nth}')
        return dict(matches[nth])
    def box(rect):
        return [rect[0]/595.2756, rect[1]/841.8898, rect[2]/595.2756, rect[3]/841.8898]
    def add(key, source=None, nth=0, rect=None, **extra):
        s = get(source, nth) if source else dict(box=box(rect),kind='text',hint=key,row=None,col=None)
        s.update(key=key,schema_path=wildcard(key),spec=leaves[wildcard(key)],**extra)
        result.append(s)
        return s
    def group(key, labels, rect=None):
        spec=leaves[key]; values=spec.get('values',spec.get('items',{}).get('values',[]))
        if key=='tetanus_vaccination_dose':values=list(range(1,6))
        options=[]
        for value, label in zip(values,labels):
            if label is None:continue
            s=get(*label) if isinstance(label,tuple) else get(label)
            options.append(dict(value=value,box=s['box'],label=s['hint']))
        boxes=[o['box'] for o in options]
        b=[min(v[0] for v in boxes),min(v[1] for v in boxes),max(v[2] for v in boxes),max(v[3] for v in boxes)]
        result.append(dict(key=key,schema_path=key,spec=spec,kind='choice',hint=key,box=b,options=options,
                           note_box=box(rect) if rect else None,row=None,col=None))
    def bp(source,prefix='',nth=0):
        s=get(source,nth);x1,y1,x2,y2=s['box'];mid=(x1+x2)/2
        for key,b in [('systolic_bp_mmhg',[x1,y1,mid-.002,y2]),('diastolic_bp_mmhg',[mid+.002,y1,x2,y2])]:
            t=add(prefix+key,source,nth);t['box']=b;t['bp_part']=key
    if number==1:
        for key,src in [('record_code','n_de_la_fiche'),('region','region'),('province','province'),('health_facility_name','nom_de_l_etablissement_sanitaire'),('high_risk_pregnancy','grossesse_classee_a_risque'),('other_risk_factor','other_risk')]:add(key,src)
        group('health_facility_type',[('checkbox',i) for i in range(5)]+[None],rect=[315,263,505,278])
        group('coverage_mode',['fixe','mobile'])
        group('risk_factors',['anemie','h_t_a','diabete','cardiopathie','metrorragie','infection','pre_eclampsie','eclampsie',None],rect=[300,552,350,568])
    elif number==2:
        for key,src,n in [('age_years','age',0),('education_level','niveau_d_instruction',0),('occupation','profession',0),('spouse_occupation','profession',1),('consanguinity','consanguinite',0),('desired_pregnancy','grossesse_desiree',0),('gravidity','gestation',0),('parity','parite',0),('living_children','nombre_d_enfants_vivants',0),('rubella_vaccinated','vaccinee_contre_la_rubeole',0),('hepatitis_b_vaccinated','vaccinee_contre_l_hepatite_b',0),('rubella_vaccination_date','le',0),('hepatitis_b_vaccination_date','le',1),('cervical_smear_or_via_result','frottis_cervical_iva_moins_de_3_ans',0)]:add(key,src,n)
        group('tetanus_vaccination_dose',['1','2','3','4','5'])
        for side in ['woman','spouse']:
            for old,new in [('hypertension','hypertension'),('diabetes','diabetes'),('hereditary','hereditary_diseases'),('malformations','malformations'),('allergies','allergies')]:add(f'family_history.{side}_family.{new}',f'family.{side}.{old}')
        for key in ['medical','surgical','gynecological']:add('woman_history.'+key,'history.'+key)
        for i,row in enumerate(['abortion','preterm','fetal_death','other']):
            prefix=f'previous_pregnancy_anomalies[{i}].'
            for old,new in [('count','count'),('date','date'),('place','place'),('weeks','gestational_age_weeks')]:add(prefix+new,f'anomalies.{row}.{old}')
            add(prefix+'nature',rect=[40,379+20*i,148,395+20*i],kind='printed',fixed=leaves['previous_pregnancy_anomalies[].nature']['values'][i])
            # The OTHER row has a dedicated description cell; other rows have no such input.
            if i==3:add(prefix+'other_description',rect=[103,440,149,455])
        for i in range(5):
            prefix=f'previous_deliveries[{i}].'
            for old,new in [('date','date'),('delivery_method','delivery_method'),('cesarean_indication','cesarean_indication'),('complication','maternal_complication'),('weight_g','newborn_weight_g'),('newborn_complication','newborn_complication')]:add(prefix+new,f'previous_deliveries.{i}.{old}')
            add(prefix+'delivery_number',rect=[152+81*i,503,227+81*i,527],kind='printed',fixed=i+1)
    elif number==3:
        for key,src in [('last_menstrual_period_date','ddr'),('height_cm','taille'),('expected_delivery_date','date_prevue_d_accouchement'),('post_term_date','date_de_depassement_de_terme')]:add(key,src)
        group('blood_group',['a','b','o','ab']);group('rhesus_factor',[('rh',1),('rh',0)])
        mapping=dict(contacted='follow_up_contacted',weeks='gestational_age_weeks',skeletal='skeletal_abnormalities',conjunctiva='conjunctiva_condition',breast='breast_exam',fetal_movement='active_fetal_movements',fundal_cm='fundal_height_cm',fetal_heart='fetal_heart_rate_bpm',speculum='speculum_exam',cervix='cervix_condition',presentation='fetal_presentation',pelvis='pelvis_exam',rubella='rubella_result',toxoplasmosis='toxoplasmosis_result',syphilis='syphilis_result',hepatitis_b='hepatitis_b_surface_antigen_result',hiv='hiv_result',hemoglobin='hemoglobin_g_dl',platelets='platelets_per_ul',glucose='blood_glucose_g_l',rai='irregular_antibody_screen_result',iron='iron_given',examiner='examiner_role')
        for s in raw:
            if not s['key'].startswith('visits.'):continue
            _,i,old=s['key'].split('.');prefix=f'visits[{i}].'
            if old=='blood_pressure':bp(s['key'],prefix)
            else:add(prefix+mapping.get(old,old),s['key'])
        for i,period in enumerate(leaves['visits[].period']['values']):add(f'visits[{i}].period',rect=[153+44.8*i,109,193+44.8*i,139],kind='printed',fixed=period,col=i)
    elif number==4:
        mapping=dict(qualified_attendant_present='assiste_par_un_personnel_qualifie',other_facility_type='other_facility',other_attendant='other_attendant',delivery_date='date_de_l_accouchement',episiotomy='avec_episiotomie',cesarean_indication='cesarean_indication',complications_present='checkbox',other_complication='other_complication',newborn_sex='sexe',birth_weight_g='poids_a_la_naissance',head_circumference_cm='perimetre_cranien_a_la_naissance',newborn_abnormality='anomalie_a_preciser',gestational_age_weeks='age_gestationnel')
        for key,src in mapping.items():add(key,src)
        group('delivery_setting',['en_milieu_surveille','a_domicile'])
        group('facility_type',['maison_d_accouchement','maternite','clinique_privee',None,None],rect=[420,173,540,189])
        group('delivery_mode',['voie_basse_non_instrumentale','voie_basse_instrumentale','cesarienne_programmee','urgence'])
        group('instrument',['forceps','ventouse',None],rect=[420,376,530,390])
        group('complication_timing',['au_moment_de_l_accouchement','suites_de_couches'])
        group('complication_types',['pre_eclampsie','eclampsie','hemorragie','infection','autres'])
        group('newborn_status',['vivant','mort_ne','deces_24_heures'])
    elif number in [5,7]:
        mapping=dict(consultation_date='date_de_la_consultation',temperature_c='t',pulse_bpm='pouls',weight_kg='poids',uterine_globe_present='presence_du_globe_uterin',cesarean_performed='cesarienne',cesarean_scar_condition='scar',iron_prescribed='fer',vitamin_a_prescribed='vitamine_a',other_treatment='other_treatment',next_appointment_date='prochain_rendez_vous_le',wants_family_planning='desire_utiliser_une_methode',other_family_planning_method='other_family_planning',contraception_prescribed='prescription_faite',family_planning_referral='referee',reason_declined_family_planning='decline_reason')
        for key,src in mapping.items():add(key,src)
        bp('ta');add('medications_taken',rect=[220,490,515,513])
        group('visit_timing',[('checkbox',0),('checkbox',1)])
        group('conjunctiva_condition',['normales','decolorees'])
        group('lochia',['fade','fetide','claires','sanglantes','jaunatres'])
        group('perineum_condition',[('normal',0),'episiotomie','reparee','dechirure'])
        group('sphincter_condition',[('normal',1),'anormal'])
        group('breast_condition',[('normal',2),'lymphangite','mastite_et_abces'])
        group('calf_findings',[('normal',3),'rouges','chauds','douloureux_a_la_dorsiflexion'])
        group('complications',['hemorragie','infection','eclampsie','phlebite','complications_mammaires','anemie','autres'])
        group('family_planning_method',['pilule','diu',None,None],rect=[415,636,531,652])
    else:
        mapping=dict(consultation_date='date_de_la_consultation',age_days='age',temperature_c='temperature',weight_g='poids',length_cm='taille',head_circumference_cm='perimetre_cranien',premature='nouveau_ne_premature',small_for_gestational_age='nouveau_ne_hypotrophe',vitamin_d_supplementation='supplementation_en_vitamine_d',examiner_role='vu_par',transferred='transfert',follow_up_date='revenir_pour_une_visite_de_suivi_necessaire_le')
        for key,src in mapping.items():add(key,src)
        add('other_danger_sign','autres_a_preciser',0);add('other_trauma_or_malformation','autres_a_preciser',1)
        for key,src,rect in [('decision','decision_prise',[106,609,486,620]),('treatment','traitement_prescrit',[122,639,472,650]),('referral_facility','preciser_l_etablissement_de_reference',[261,675,540,686])]:
            if number==6:add(key,src)
            else:add(key,rect=rect)
        add('vaccination_status',rect=[144,422,390,433])
        # Handwritten responses beside the three preprinted advice clauses.
        add('exclusive_breastfeeding_advice_given',rect=[383,728,432,744],text_prefix='1: ')
        add('keep_warm_advice_given',rect=[437,728,486,744],text_prefix='2: ')
        add('return_warning_signs_advice_given',rect=[490,728,539,744],text_prefix='3: ')
        group('feeding_method',['exclusivement_au_sein','artificiel','mixte'])
        group('danger_signs',['convulsions','refus_de_teter','hematemeses','melaenas','diarrhee',('ictere',0),'tirage_sous_costal','toux','rythme_respiratoire_anormal','fievre','hypothermie',None],rect=[340,274,405,285])
        group('trauma_or_malformations',['bosse_serosanguine_ou_cephalohematome','luxation_congenitale_de_la_hanche','diminution_ou_absence_de_la_mobilite_d_un_membre',None],rect=[348,377,410,388])
        group('breastfeeding_evaluation',['normal','a_problemes'])
        group('vaccines_given_today',['bcg','hb',None],rect=[327,440,440,453])
        group('complications_or_malformations',[('ictere',1),'infection','conjonctivite','traumatisme','malformation','autres'])
    bound={s['schema_path'] for s in result}
    assert bound == set(leaves), f'Form {number}: missing={set(leaves)-bound}, extra={bound-set(leaves)}'
    assert len({s['key'] for s in result})==len(result)
    return result

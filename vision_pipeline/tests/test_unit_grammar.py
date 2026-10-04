import pytest
from vision_pipeline.common import FORMS
from vision_pipeline.grammar import RULES,parse

@pytest.mark.parametrize('form,key,raw,value,unit',[
 (5,'temperature_c','37.2 °L',37.2,'°C'),
 (5,'temperature_c','٣٧٫٢ °l',37.2,'°C'),
 (5,'weight_g','5178 9',5178,'g'),
 (5,'weight_g','٥١٧٨ ٩',5178,'g'),
 (5,'weight_g','5178q',5178,'g'),
 (5,'weight_g','5.178 k9',5178,'g'),
 (2,'visits[0].weight_kg','60 k9',60,'kg'),
 (5,'length_cm','52 crn',52,'cm'),
 (5,'head_circumference_cm','34 crn',34,'cm'),
 (2,'visits[0].systolic_bp_mmhg','120/80 mmH9',120,'mmHg'),
 (2,'visits[0].diastolic_bp_mmhg','120/80 mmH9',80,'mmHg'),
 (2,'visits[0].fetal_heart_rate_bpm','140 bprn',140,'bpm'),
 (2,'visits[0].hemoglobin_g_dl','12 9/dL',12,'g/dL'),
 (2,'visits[0].hemoglobin_g_dl','12 g/d1',12,'g/dL'),
 (2,'visits[0].blood_glucose_g_l','90 mg/d1',.9,'g/L'),
 (2,'visits[0].platelets_per_ul','250000 /u1',250000,'per uL'),
 (5,'age_days','8 jour5',8,'days'),
 (2,'visits[0].gestational_age_weeks','32 sern',32,'weeks'),
 (1,'age_years','28 an5',28,'years'),
])
def test_explicit_unit_confusions_are_audited_and_reviewed(form,key,raw,value,unit):
    result=parse(FORMS[form],key,raw)
    assert result['value']==pytest.approx(value),result
    assert result['unit']==unit and result['expected_unit']==unit
    assert result['unit_source']=='SCHEMA_CORRECTED'
    assert result['raw_text']==raw and result['status']=='NEEDS_REVIEW'
    assert result['corrections'][0]['requires_confirmation']
    assert 'INFERRED_UNIT_REQUIRES_REVIEW' in result['issues']

@pytest.mark.parametrize('form,key,raw,value,unit',[
 (5,'temperature_c','37,2  ° C',37.2,'°C'),
 (5,'temperature_c','37.2 ℃',37.2,'°C'),
 (5,'weight_g','5 178 G .',5178,'g'),
 (5,'length_cm','0.52 m',52,'cm'),
 (2,'visits[0].systolic_bp_mmhg','12/8 cm Hg',120,'mmHg'),
 (2,'visits[0].hemoglobin_g_dl','120 g/L',12,'g/dL'),
 (2,'visits[0].blood_glucose_g_l','90 mg/dL',.9,'g/L'),
 (2,'visits[0].platelets_per_ul','250 ×10^9/L',250000,'per uL'),
 (2,'visits[0].platelets_per_ul','250 x10^3/µL',250000,'per uL'),
 (2,'visits[0].platelets_per_ul','250000 /μL',250000,'per uL'),
])
def test_typography_and_explicit_conversions(form,key,raw,value,unit):
    result=parse(FORMS[form],key,raw)
    assert result['status']=='KNOWN',result
    assert result['value']==pytest.approx(value)
    assert result['unit']==unit and result['unit_source']=='EXPLICIT'
    assert not result['corrections']

def test_fused_nine_is_only_an_alternative_not_an_applied_edit():
    result=parse(FORMS[5],'weight_g','51789')
    assert result['value']==51789 and result['status']=='NEEDS_REVIEW'
    assert result['numeric_alternatives'][0]['value']==5178
    assert result['numeric_alternatives'][0]['source_interpretation']=='5178 g'
    assert result['numeric_alternatives'][0]['requires_confirmation']
    assert result['raw_text']=='51789' and not result['corrections']
    for raw in ['5179','5178','999','51789g','51780']:
        assert not parse(FORMS[5],'weight_g',raw)['numeric_alternatives']

@pytest.mark.parametrize('key,raw',[
 ('temperature_c','37.2 L'),('temperature_c','98.6 °F'),
 ('weight_g','5178 mg'),('length_cm','52 kg'),('age_days','8 g'),
 ('weight_g','51x78g'),('weight_g','51 78g'),('weight_g','3O00g'),
 ('weight_g','5178g extra'),('temperature_c','37.2 °L junk'),
])
def test_no_unrestricted_fuzzy_unit_or_digit_replacement(key,raw):
    result=parse(FORMS[5],key,raw)
    assert result['status']=='NEEDS_REVIEW'
    assert not result['corrections']
    assert result['normalized_quantity'] is None

def test_unit_policy_for_every_numeric_schema_leaf():
    samples={'g':'3500 g','kg':'60 kg','cm':'100 cm','mmHg':'100 mmHg','°C':'37 °C','bpm':'100 bpm',
             'g/dL':'12 g/dL','g/L':'1 g/L','per uL':'250000 /uL','days':'8 jours','weeks':'32 semaines','years':'28 ans',None:'2'}
    found=set()
    for form,fields in RULES.items():
        for key,rule in fields.items():
            if rule['type'] not in ['integer','double']:continue
            unit=rule.get('unit');found.add(unit)
            result=parse(form,key.replace('[]','[0]'),samples[unit])
            assert rule['unit_policy']['expected_unit']==unit
            assert result['unit']==unit and result['unit_source'] in ['EXPLICIT','UNITLESS']
            assert not any('UNIT' in i for i in result['issues']),result
    assert found==set(samples)

def test_counts_and_narrative_do_not_gain_unit_corrections():
    result=parse(FORMS[1],'gravidity','2 g')
    assert result['status']=='NEEDS_REVIEW' and result['unit'] is None
    text='37.2 °L / 51789 / 8 jour5'
    assert parse(FORMS[5],'treatment',text)['value']==text

def test_missing_unit_is_declared_schema_context_not_fabricated_ocr():
    result=parse(FORMS[5],'weight_g','5178')
    assert result['normalized_quantity']=='5178 g' and result['unit_source']=='SCHEMA'
    assert result['source_unit'] is None and result['raw_text']=='5178'

def test_normalized_quantity_does_not_round_away_digits():
    result=parse(FORMS[5],'weight_g','5178.123g')
    assert result['normalized_quantity']=='5178.123 g'

def test_numeric_overflow_is_rejected_without_nonstandard_json():
    import json
    result=parse(FORMS[5],'weight_g','9'*400+' g')
    assert result['value'] is None and result['status']=='NEEDS_REVIEW'
    json.dumps(result,allow_nan=False)

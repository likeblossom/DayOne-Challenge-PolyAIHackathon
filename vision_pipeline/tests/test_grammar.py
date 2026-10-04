import pytest
from vision_pipeline.common import FORMS,leaves
from vision_pipeline.grammar import RULES,parse,relations,confidence

def test_every_field_has_a_rule():
    assert sum(map(len,RULES.values()))==218
    for i,f in enumerate(FORMS,1):assert set(RULES[f])==set(leaves(i))

@pytest.mark.parametrize('raw,expected',[('5178g',5178),('٥١٧٨ غ',5178),('5.178 kg',5178),('5 178 g',5178),('5178',5178)])
def test_weight_units_not_digits(raw,expected):
    p=parse(FORMS[5],'weight_g',raw)
    assert p['value']==expected and p['status']=='KNOWN'

def test_never_drop_a_digit_to_make_weight_plausible():
    p=parse(FORMS[5],'weight_g','51789')
    assert p['value']==51789 and p['status']=='NEEDS_REVIEW'
    assert p['raw_text']=='51789' and not p['suggestions']

@pytest.mark.parametrize('raw',['51x78g','5178 mg','51 78g','O5178g'])
def test_ambiguous_or_wrong_unit_requires_review(raw):assert parse(FORMS[5],'weight_g',raw)['status']=='NEEDS_REVIEW'

def test_dates_and_markers():
    assert parse(FORMS[5],'consultation_date','31/02/2026')['status']=='NEEDS_REVIEW'
    assert parse(FORMS[5],'consultation_date','03/02/2026')['value']=='2026-02-03'
    assert parse(FORMS[5],'consultation_date','03/02/26')['status']=='NEEDS_REVIEW'
    assert parse(FORMS[5],'treatment','')['status']=='ILLEGIBLE'
    assert parse(FORMS[5],'treatment','',observed_blank=True)['status']=='NOT_PROVIDED'
    assert parse(FORMS[5],'treatment','غير معروف')['status']=='UNKNOWN'

def test_bp_components_and_nested_relations():
    assert parse(FORMS[2],'visits[0].systolic_bp_mmhg','120/80')['value']==120
    assert parse(FORMS[2],'visits[0].diastolic_bp_mmhg','120/80')['value']==80
    issues=relations({'visits[0].systolic_bp_mmhg':80,'visits[0].diastolic_bp_mmhg':120})
    assert len(issues)==2

def test_twins_not_rejected_as_impossible():
    issues=relations({'parity':1,'gravidity':1,'living_children':2})
    assert issues['living_children']==['REVIEW_MULTIPLE_BIRTHS_OR_COUNT_MISMATCH']

def test_confidence_cannot_hide_invalid_grammar():
    c={k:1. for k in ['form','localization','script','ocr','grammar','image_quality']}
    assert confidence(c,['INVALID'])<.5
    assert confidence(c,agreement=False)<=.6

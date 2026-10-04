"""Regression checks for complete, typed schema-to-paper bindings."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import random
import fitz
import generate_diverse_forms as generator
from schema_form_layout import bind_layout,schema_leaves
from schema_form_values import sample_value,nested_labels
from audit_diverse_forms import valid_value


def test_every_schema_leaf_has_an_explicit_physical_binding():
    with fitz.open(generator.PDF) as doc:
        total=0
        for n in range(1,9):
            slots=bind_layout(generator.slots_for(doc[n-1],n),n,generator.slug)
            assert {s['schema_path'] for s in slots}==set(schema_leaves(n))
            assert len({s['key'] for s in slots})==len(slots)
            total+=len(schema_leaves(n))
            for s in slots:
                x1,y1,x2,y2=s['box']
                assert 0<=x1<x2<=1 and 0<=y1<y2<=1
                if s['kind']=='choice':
                    spec=s['spec'];values=spec.get('values',spec.get('items',{}).get('values',[]))
                    unmapped=set(values)-{o['value'] for o in s['options']}
                    assert not unmapped or s['note_box']
        assert total==218


def test_values_match_declared_types_in_every_language():
    with fitz.open(generator.PDF) as doc:
        for n in range(1,9):
            slots=bind_layout(generator.slots_for(doc[n-1],n),n,generator.slug)
            for index in range(72):
                lang=['en','fr','ar'][index%3]
                for s in slots:
                    value,text=sample_value(s,random.Random(index),lang,index,n)
                    assert valid_value(value,s['spec']),(n,s['key'],value)
                    assert isinstance(text,str) and text


def test_all_nine_visit_columns_and_five_delivery_columns():
    with fitz.open(generator.PDF) as doc:
        visits=bind_layout(generator.slots_for(doc[2],3),3,generator.slug)
        for i in range(9):assert sum(s['key'].startswith(f'visits[{i}].') for s in visits)==32
        history=bind_layout(generator.slots_for(doc[1],2),2,generator.slug)
        for i in range(5):assert sum(s['key'].startswith(f'previous_deliveries[{i}].') for s in history)==7


def test_nested_contract_keeps_array_indices_and_envelopes():
    result=nested_labels({'visits[0].weight_kg':dict(canonical_value=61.5,status='KNOWN'),
                          'visits[1].weight_kg':dict(canonical_value=None,status='NOT_PROVIDED')})
    assert result['visits'][0]['weight_kg']==dict(value=61.5,status='KNOWN',confidence=1.0)
    assert result['visits'][1]['weight_kg']==dict(value=None,status='NOT_PROVIDED',confidence=0.0)


def test_camera_never_clips_the_page():
    import numpy as np
    for n in range(1,9):
        for index in range(600):
            matrix,_=generator.distort_spec(index//3+index//36,20261004+n*100000+index)
            points=matrix@np.array([[0,generator.W,generator.W,0],[0,0,generator.H,generator.H],[1,1,1,1]])
            xy=points[:2]/points[2]
            assert xy.min()>=-.001
            assert xy[0].max()<=generator.W+.001 and xy[1].max()<=generator.H+.001

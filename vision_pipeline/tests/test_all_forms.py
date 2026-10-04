import numpy as np
from vision_pipeline.common import DATA,FORMS,leaves,wildcard,read_json
from vision_pipeline.label_anchor_pilot.common import quad,local,world
from vision_pipeline.label_anchor_pilot.infer import unit_anchor,pair_text

def test_all_schema_fields_bound_without_page_coordinates():
    count=0
    def check(v):
        if isinstance(v,dict):
            assert not {'box','bbox','homography','canonical_box'}&set(v)
            for x in v.values():check(x)
        elif isinstance(v,list):
            for x in v:check(x)
    for number,form in enumerate(FORMS,1):
        spec=read_json(DATA/'all_forms'/form/'spec.json');check(spec)
        assert set(map(wildcard,spec['bindings']))==set(leaves(number))
        count+=len(leaves(number))
        for b in spec['bindings'].values():
            units=b.get('options',[])+([b['note']] if b.get('note') else []) if b['kind']=='choice' else [b]
            for u in units:
                assert u['anchor'] in spec['classes']
                if 'column_anchor' in u:assert u['column_anchor'] in spec['classes']
    assert count==218

def test_table_anchor_geometry_and_missing_column():
    row=quad([10,200,80,215]);column=quad([240,20,270,30]);cell=quad([240,200,280,215])
    unit=dict(anchor='row',column_anchor='col',relative_region=local(cell,row).tolist(),column_relative_region=local(cell,column).tolist(),kind='text')
    theta=np.deg2rad(22);rot=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    transform=lambda p:p@rot.T*.8+[43,72]
    anchors={'row':dict(quad=transform(row).tolist(),confidence=.9),'col':dict(quad=transform(column).tolist(),confidence=.8)}
    a=unit_anchor(unit,anchors)
    np.testing.assert_allclose(world(unit['relative_region'],a['quad']),transform(cell),atol=1e-4)
    assert a['confidence']==.8
    assert unit_anchor(unit,{'row':anchors['row']}) is None
    assert pair_text({'row':anchors['row']},[],{'bindings':{'x':unit}}, {})==({}, {})

def test_exact_replay_all_pages_and_font_disjoint_splits():
    pages=0
    for form in FORMS:
        p=read_json(DATA/'all_forms'/form/'preparation.json')
        assert p['exact_ink_replay'] and not p['organizer_handwriting_used_for_training']
        assert p['ink_regions']>0
        pages+=sum(p['pages'].values())
    assert pages==4800

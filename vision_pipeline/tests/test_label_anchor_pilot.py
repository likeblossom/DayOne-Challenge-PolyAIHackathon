import numpy as np
from PIL import Image
from vision_pipeline.label_anchor_pilot.common import quad,local,world,line_crop,ink_evidence
from vision_pipeline.label_anchor_pilot.infer import pair_text

def test_local_round_trip_with_rotation_scale_translation():
    anchor=quad([20,20,120,35]);points=quad([130,17,190,40])
    angle=np.deg2rad(23);rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    transformed=lambda p:np.asarray(p)@rot.T*1.4+[87,51]
    expected=local(points,anchor);actual=local(transformed(points),transformed(anchor))
    np.testing.assert_allclose(actual,expected,atol=1e-5)
    np.testing.assert_allclose(world(actual,transformed(anchor)),transformed(points),atol=1e-4)

def test_assignment_is_one_to_one_and_can_decline():
    anchor=quad([10,10,60,20]).tolist();near=quad([70,9,100,23]).tolist();far=quad([700,900,750,920]).tolist()
    anchors={'weight':dict(quad=anchor,confidence=.99)}
    unit=dict(kind='text',anchor='weight',relative_region=local(quad([65,8,130,25]),anchor).tolist())
    spec={'bindings':{'weight_g':unit,'duplicate':unit,'missing':dict(unit,anchor='absent')}}
    hands=[dict(quad=near,confidence=.99,id=0),dict(quad=far,confidence=.99,id=1)]
    assigned,_=pair_text(anchors,hands,spec,{})
    assert len(assigned)==1 and next(iter(assigned.values()))['id']==0
    assert 'missing' not in assigned
    assert pair_text({},hands,spec,{})==({}, {})
    assert pair_text(anchors,[],spec,{})==({}, {})

def test_blank_and_crop_padding():
    blank=Image.new('RGB',(200,100),'white')
    assert ink_evidence(blank)==0
    crop=line_crop(blank,quad([30,30,90,45]))
    assert crop.width>60 and crop.height>15
    assert np.asarray(crop).min()==255

def test_single_character_does_not_turn_sideways():
    from vision_pipeline.label_anchor_pilot.common import frame
    _,u,_,w,h=frame(quad([20,20,30,60]))
    np.testing.assert_allclose(u,[1,0])
    assert w==10 and h==40

def test_inference_config_contains_no_absolute_boxes():
    from vision_pipeline.label_anchor_pilot.common import WORK,read_json
    spec=read_json(WORK/'spec.json')
    assert len(spec['bindings'])==27
    def check(value):
        if isinstance(value,dict):
            assert not set(value)&{'box','bbox','canonical_box','homography'}
            for v in value.values():check(v)
        elif isinstance(value,list):
            for v in value:check(v)
    check(spec)

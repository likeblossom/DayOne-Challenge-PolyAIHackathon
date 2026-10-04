import numpy as np
from PIL import Image
from vision_pipeline.geometry import project_box,assign,rectify_crop
from vision_pipeline.common import crop

def test_no_fixed_crop_without_registration():
    matches,priors=assign([dict(key='a',box=[.1,.1,.2,.2],kind='text')],[dict(box=[.1,.1,.2,.2],class_id=0,confidence=.9)],None)
    assert not matches and not priors

def test_detector_assignment_is_one_to_one():
    slots=[dict(key=k,box=[.1,.1,.3,.3],kind='text') for k in ['a','b']]
    matches,_=assign(slots,[dict(box=[.1,.1,.3,.3],class_id=0,confidence=.9)],np.eye(3))
    assert len(matches)==1

def test_margin_clamps_to_image():
    im=Image.new('RGB',(100,200));patch,b=crop(im,[0,0,.5,.5],.3)
    assert b[0]==b[1]==0 and patch.width>50 and patch.height>100

def test_projected_box_and_rectification():
    b,visible=project_box([.1,.1,.2,.2],np.eye(3));assert visible
    im=rectify_crop(Image.new('RGB',(100,200),'white'),b,np.eye(3))
    assert im.width>0 and im.height>0

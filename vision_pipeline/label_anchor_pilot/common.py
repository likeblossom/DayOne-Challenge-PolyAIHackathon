from pathlib import Path
import numpy as np
import cv2
from PIL import Image
from ..common import ROOT,BASE,DATA,MODELS,REPORTS,read_json,write_json

FORM='06_early_postnatal_newborn'
SOURCE=ROOT/'data/forms'/FORM
WORK=DATA/'label_anchor_pilot'
WEIGHTS=MODELS/'label_anchor_pilot'
LOGS=REPORTS/'label_anchor_pilot'
OUTPUT=BASE/'outputs'/'label_anchor_pilot'

def quad(box):
    x1,y1,x2,y2=box
    return np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]],dtype=np.float32)

def frame(points):
    """Local axes from the detected label OBB; no estimated whole-page transform.

    OBBs do not resolve 180-degree reading direction. Pilot capture range is
    upright +/- 45 degrees, matching generated augmentation; inverted pages review.
    """
    p=np.asarray(points,dtype=np.float32);edges=np.roll(p,-1,axis=0)-p
    lengths=np.linalg.norm(edges,axis=1)
    # Within the documented upright +/-45 capture range, the reading axis is
    # the more horizontal edge, NOT necessarily the longest (e.g. a lone digit).
    index=int(np.argmax(np.abs(edges[:,0])/np.maximum(lengths,1e-6)))
    u=edges[index]/max(lengths[index],1e-6)
    if u[0]<0:u=-u
    v=np.array([-u[1],u[0]]);center=p.mean(0)
    return center,u,v,float(lengths[index]),float(lengths[(index+1)%4])

def local(points,anchor):
    c,u,v,w,h=frame(anchor);p=np.asarray(points)-c
    return np.stack([p@u/max(w,1),p@v/max(h,1)],axis=-1)

def world(points,anchor):
    c,u,v,w,h=frame(anchor);p=np.asarray(points)
    return c+p[:,0,None]*w*u+p[:,1,None]*h*v

def line_crop(image,points,pad=.12):
    c,u,v,w,h=frame(points);w+=max(4,h*.15)*2;h+=max(3,h*pad)*2
    src=np.array([c-u*w/2-v*h/2,c+u*w/2-v*h/2,c+u*w/2+v*h/2,c-u*w/2+v*h/2],np.float32)
    width=max(8,min(round(w),image.width*2));height=max(8,min(round(h),image.height*2))
    matrix=cv2.getPerspectiveTransform(src,np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]]))
    return Image.fromarray(cv2.warpPerspective(np.asarray(image.convert('RGB')),matrix,(width,height),borderValue=(255,255,255)))

def ink_evidence(image):
    """Conservative residual-ink check; removes long printed lines, not ink colors."""
    gray=np.asarray(image.convert('L'));threshold=min(170,float(np.median(gray))-35)
    mask=(gray<threshold).astype(np.uint8)
    for kernel in [np.ones((1,max(12,gray.shape[1]//3)),np.uint8),np.ones((max(12,gray.shape[0]//2),1),np.uint8)]:
        mask=cv2.subtract(mask,cv2.morphologyEx(mask,cv2.MORPH_OPEN,kernel))
    if min(mask.shape)>8:mask=mask[3:-3,3:-3]
    return int(mask.sum())

"""Align template priors, match detections one-to-one, and retain both crop views."""
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from PIL import Image
from .common import *
cv2.setNumThreads(4)

def observed_blank(image):
    gray=np.asarray(image.convert('L'));threshold=min(170,float(np.median(gray))-28)
    mask=(gray<threshold).astype(np.uint8)
    horizontal=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((1,max(12,gray.shape[1]//3)),np.uint8))
    mask=cv2.subtract(mask,horizontal)
    if min(mask.shape)>4:mask=mask[1:-1,1:-1]
    return int(mask.sum())<6

def register(reference,image):
    """Return reference→image normalized homography and independently measured support."""
    a=np.asarray(reference.convert('RGB'));b=np.asarray(image.convert('RGB'))
    scale=1000/max(a.shape[:2]);a=cv2.resize(a,None,fx=scale,fy=scale)
    scale_b=1000/max(b.shape[:2]);b=cv2.resize(b,None,fx=scale_b,fy=scale_b)
    orb=cv2.ORB_create(nfeatures=7000,fastThreshold=8)
    ka,da=orb.detectAndCompute(cv2.cvtColor(a,cv2.COLOR_RGB2GRAY),None);kb,db=orb.detectAndCompute(cv2.cvtColor(b,cv2.COLOR_RGB2GRAY),None)
    if da is None or db is None:return None,dict(accepted=False,reason='no_features',confidence=0.)
    pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da,db,k=2)
    matches=[p[0] for p in pairs if len(p)==2 and p[0].distance<.73*p[1].distance]
    if len(matches)<16:return None,dict(accepted=False,reason='too_few_matches',confidence=0.,matches=len(matches))
    src=np.float32([ka[m.queryIdx].pt for m in matches]);dst=np.float32([kb[m.trainIdx].pt for m in matches])
    matrix,mask=cv2.findHomography(src,dst,cv2.RANSAC,3.0)
    if matrix is None:return None,dict(accepted=False,reason='ransac_failed',confidence=0.)
    good=mask.ravel().astype(bool);ratio=float(good.mean());support=int(good.sum())
    spread=np.ptp(src[good],axis=0)/np.array([a.shape[1],a.shape[0]]) if support else [0,0]
    normalized=np.diag([1/b.shape[1],1/b.shape[0],1])@matrix@np.diag([a.shape[1],a.shape[0],1])
    projected=cv2.perspectiveTransform(np.float32([[[0,0],[1,0],[1,1],[0,1]]]),normalized)[0]
    area=abs(cv2.contourArea(projected));finite=np.isfinite(projected).all()
    accepted=bool(support>=14 and ratio>=.22 and min(spread)>.40 and finite and .12<area<2.5 and cv2.isContourConvex(projected))
    confidence=min(.99,ratio*.65+min(support/100,1)*.35) if accepted else 0.
    return (normalized if accepted else None),dict(accepted=accepted,inliers=support,match_count=len(matches),inlier_ratio=ratio,spread=list(map(float,spread)),confidence=confidence)

def project_box(box,matrix):
    x1,y1,x2,y2=box;points=cv2.perspectiveTransform(np.float32([[[x1,y1],[x2,y1],[x2,y2],[x1,y2]]]),matrix)[0]
    lo=points.min(0);hi=points.max(0);visible=bool((lo>=0).all() and (hi<=1).all())
    return np.clip([lo[0],lo[1],hi[0],hi[1]],0,1).tolist(),visible

def iou(a,b):
    w=max(0,min(a[2],b[2])-max(a[0],b[0]));h=max(0,min(a[3],b[3])-max(a[1],b[1]));inter=w*h
    return inter/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)

def assign(slots,detections,matrix):
    priors={s['key']:project_box(s['box'],matrix)[0] for s in slots} if matrix is not None else {}
    # Without a trustworthy geometric frame, assigning generic detections to semantic
    # field names is unsafe. Return no assignments and ask for a retake/manual review.
    if matrix is None or not detections:return {},priors
    eligible=[s for s in slots if s['kind'] in KINDS]
    cost=np.ones((len(eligible),len(detections)),dtype=float)*100
    for i,s in enumerate(eligible):
        for j,d in enumerate(detections):
            if d['class_id']!=KINDS[s['kind']]:continue
            overlap=iou(priors[s['key']],d['box'])
            if overlap>.08:cost[i,j]=1-overlap
    rows,cols=linear_sum_assignment(cost);matches={}
    for i,j in zip(rows,cols):
        if cost[i,j]<.92:matches[eligible[i]['key']]=dict(detections[j],template_iou=1-float(cost[i,j]))
    return matches,priors

def rectify_crop(image,box,matrix,margin=.15):
    x1,y1,x2,y2=box;dx=max(.002,(x2-x1)*.04);dy=max(.001,(y2-y1)*margin)
    points=np.float32([[[x1-dx,y1-dy],[x2+dx,y1-dy],[x2+dx,y2+dy],[x1-dx,y2+dy]]])
    dst=cv2.perspectiveTransform(points,matrix)[0]*np.array(image.size)
    width=max(8,round(np.linalg.norm(dst[1]-dst[0])));height=max(8,round(np.linalg.norm(dst[3]-dst[0])))
    # Avoid pathological projective allocations if a registration ever escapes gates.
    width=min(width,image.width*2);height=min(height,image.height*2)
    warp=cv2.getPerspectiveTransform(dst.astype(np.float32),np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]]))
    return Image.fromarray(cv2.warpPerspective(np.asarray(image),warp,(width,height),borderValue=(255,255,255)))

def checkbox(image,box,matrix):
    im=np.asarray(rectify_crop(image,box,matrix,margin=0).convert('L'));h,w=im.shape
    # Ignore the printed border; measure the central ink inside the square.
    im=im[max(1,int(h*.23)):max(2,int(h*.77)),max(1,int(w*.23)):max(2,int(w*.77))]
    if not im.size:return None,0.,0.
    ink=float((im<140).mean())
    if ink>.19:return True,min(.97,.65+ink),ink
    if ink<.06:return False,min(.97,.90+(0.06-ink)),ink
    return None,.4,ink

def quality(image):
    gray=cv2.cvtColor(np.asarray(image.convert('RGB')),cv2.COLOR_RGB2GRAY)
    sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var());contrast=float(gray.std())
    return float(np.clip((sharp/120)**.3*(contrast/45)**.2,.05,1.))

def save_crop_views(image,key,fixed_box,detector_box,matrix,out):
    """Keep evidence even for blank fields and marks; never fabricate failed crops."""
    target=Path(out)/'crops';target.mkdir(parents=True,exist_ok=True)
    safe=re.sub(r'[^A-Za-z0-9_-]','_',key);paths={}
    if matrix is None:return paths
    fixed=target/f'{safe}_fixed.png';rectify_crop(image,fixed_box,matrix).save(fixed);paths['fixed']=str(fixed.relative_to(out))
    if detector_box:
        detected=target/f'{safe}_detector.png';crop(image,detector_box,margin=.18)[0].save(detected);paths['detector']=str(detected.relative_to(out))
    return paths

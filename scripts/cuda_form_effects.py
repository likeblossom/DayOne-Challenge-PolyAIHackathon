"""Shared CUDA image augmentation and normalized bounding-box transforms."""
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

def transform_bboxes(bboxes, matrix, width, height):
    result={}
    for name,(x1,y1,x2,y2) in bboxes.items():
        pts=np.array([[x1*width,y1*height,1],[x2*width,y1*height,1],
                      [x2*width,y2*height,1],[x1*width,y2*height,1]],dtype=np.float32).T
        out=matrix@pts;out=out[:2]/out[2:]
        result[name]=[round(float(np.clip(out[0].min()/width,0,1)),6),
                      round(float(np.clip(out[1].min()/height,0,1)),6),
                      round(float(np.clip(out[0].max()/width,0,1)),6),
                      round(float(np.clip(out[1].max()/height,0,1)),6)]
    return result

def gpu_degrade(images, homographies, metas, device, seeds):
    arr=np.stack([np.asarray(im,dtype=np.uint8) for im in images])
    x=torch.from_numpy(arr).to(device=device,non_blocking=True).permute(0,3,1,2).float()/255
    n,_,h,w=x.shape;grids=[]
    for matrix in homographies:
        inv=np.linalg.inv(matrix)
        ys,xs=torch.meshgrid(torch.arange(h,device=device),torch.arange(w,device=device),indexing='ij')
        q=torch.stack((xs,ys,torch.ones_like(xs)),-1).float()@torch.tensor(inv.T,device=device)
        q=q[...,:2]/q[...,2:].clamp(min=1e-5)
        q[...,0]=q[...,0]/max(w-1,1)*2-1;q[...,1]=q[...,1]/max(h-1,1)*2-1
        grids.append(q)
    x=F.grid_sample(x,torch.stack(grids),mode='bilinear',padding_mode='border',align_corners=True)
    outputs=[]
    for i in range(n):
        y=x[i:i+1];blur=metas[i]['blur']
        if blur:
            k=int(blur)|1;y=F.avg_pool2d(y,k,stride=1,padding=k//2)
        gen=torch.Generator(device=device).manual_seed(seeds[i])
        noise=torch.randn(y.shape,generator=gen,device=device)*metas[i]['noise']
        ramp=torch.linspace(-1,1,w,device=device).view(1,1,1,w)
        y=(y*(1+ramp*metas[i]['noise']*2.2)+noise).clamp(0,1)
        outputs.append(Image.fromarray((y[0].permute(1,2,0)*255).byte().cpu().numpy(),'RGB'))
    return outputs

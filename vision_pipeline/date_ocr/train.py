"""CUDA fine-tuning of a separate TrOCR date specialist; original model unchanged."""
import argparse,json,os,random,time,hashlib
os.environ.setdefault('USE_TF','0');os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
import numpy as np,torch
from torch.utils.data import Dataset,DataLoader
from PIL import Image,ImageOps
from transformers import TrOCRProcessor,VisionEncoderDecoderModel,get_cosine_schedule_with_warmup
from .common import *

class Dates(Dataset):
    def __init__(self,split,processor,limit=None,dataset_root=DATASET):
        self.dataset_root=Path(dataset_root)
        self.rows=[json.loads(r) for r in (self.dataset_root/'labels.jsonl').read_text().splitlines() if json.loads(r)['split']==split]
        if limit:self.rows=self.rows[:limit]
        self.processor=processor
    def __len__(self):return len(self.rows)
    def __getitem__(self,i):
        r=self.rows[i]
        with Image.open(self.dataset_root/r['image']) as source:
            image=source.convert('RGB')
            if getattr(self.processor.image_processor,'sanad_fit',False):
                size=self.processor.image_processor.size
                image=ImageOps.pad(image,(size['width'],size['height']),color='white',method=Image.Resampling.BILINEAR)
            values=self.processor(images=image,return_tensors='pt').pixel_values[0]
        ids=self.processor.tokenizer(r['text'],add_special_tokens=False).input_ids+[self.processor.tokenizer.eos_token_id]
        if len(ids)>64:raise ValueError('Label would be truncated: '+r['text'])
        return values,torch.tensor(ids,dtype=torch.long),r['text'],r['format'],r['language']

def collate(rows):
    values,labels,texts,kinds,languages=zip(*rows);padded=torch.full((len(rows),max(map(len,labels))),-100,dtype=torch.long)
    for i,ids in enumerate(labels):padded[i,:len(ids)]=ids
    return torch.stack(values),padded,list(texts),list(kinds),list(languages)

def edit_distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        new=[i]
        for j,y in enumerate(b,1):new.append(min(new[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=new
    return row[-1]

@torch.inference_mode()
def evaluate(model,loader,processor,device='cuda'):
    model.eval();correct=n=errors=chars=0;groups={};examples=[]
    for values,labels,texts,kinds,languages in loader:
        with torch.autocast('cuda',dtype=torch.bfloat16):
            geometry={'interpolate_pos_encoding':True} if getattr(model.config.encoder,'interpolate_pos_encoding',False) else {}
            output=model.generate(values.to(device),max_new_tokens=64,num_beams=1,do_sample=False,use_cache=True,**geometry)
        decoded=processor.batch_decode(output,skip_special_tokens=True)
        for pred,truth,kind,lang in zip(decoded,texts,kinds,languages):
            pred=pred.strip();equal=pred==truth;n+=1;correct+=equal;errors+=edit_distance(pred,truth);chars+=len(truth)
            for group in [kind,lang]:
                bucket=groups.setdefault(group,dict(n=0,correct=0));bucket['n']+=1;bucket['correct']+=equal
            if len(examples)<30:examples.append(dict(expected=truth,predicted=pred,format=kind,language=lang))
    return dict(n=n,correct=correct,exact_accuracy=correct/max(n,1),cer=errors/max(chars,1),groups=groups,examples=examples)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--epochs',type=int,default=3);ap.add_argument('--batch',type=int,default=8);ap.add_argument('--lr',type=float,default=2e-5);ap.add_argument('--initial',type=str,default=str(MODELS/'trocr_latin'));ap.add_argument('--train-limit',type=int);ap.add_argument('--val-limit',type=int);ap.add_argument('--dataset',type=Path,default=DATASET);ap.add_argument('--output',type=Path,default=CHECKPOINT);ap.add_argument('--reports',type=Path,default=LOGS)
    ap.add_argument('--workers',type=int,default=2);ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--cuda-memory-fraction',type=float,default=.72)
    ap.add_argument('--baseline',action='store_true',help='Evaluate initialization on validation before training')
    ap.add_argument('--encoder-only',action='store_true',help='Preserve pretrained language decoder; adapt visual encoder only')
    ap.add_argument('--decoder-lr',type=float,help='Optional lower learning rate for language decoder adaptation')
    ap.add_argument('--line-shape',type=int,nargs=2,metavar=('HEIGHT','WIDTH'),help='Experimental aspect-preserving line input; separate checkpoint only')
    a=ap.parse_args()
    if a.encoder_only and a.decoder_lr is not None:ap.error('--decoder-lr cannot be used with --encoder-only')
    task_dataset=a.dataset.resolve();task_checkpoint=a.output.resolve();task_logs=a.reports.resolve()
    if task_checkpoint==Path(a.initial).resolve():raise ValueError('Save to a separate checkpoint; never overwrite initialization weights.')
    if (task_checkpoint/'model.safetensors').exists():raise ValueError('Output checkpoint already exists; choose a new output directory.')
    assert torch.cuda.is_available();torch.set_num_threads(a.threads);torch.cuda.set_per_process_memory_fraction(a.cuda_memory_fraction);torch.manual_seed(42);np.random.seed(42);random.seed(42)
    task_logs.mkdir(parents=True,exist_ok=True)
    processor=TrOCRProcessor.from_pretrained(a.initial,local_files_only=True)
    model=VisionEncoderDecoderModel.from_pretrained(a.initial,local_files_only=True,use_safetensors=True).cuda()
    if a.line_shape:
        height,width=a.line_shape
        if min(height,width)<32 or max(height,width)>768 or height%16 or width%16:ap.error('Line dimensions must be multiples of 16 in [32,768]')
        processor.image_processor.size=dict(height=height,width=width);processor.image_processor.sanad_fit=True
        model.config.encoder.interpolate_pos_encoding=True;model.encoder.config.interpolate_pos_encoding=True
    if a.encoder_only:
        for parameter in model.decoder.parameters():parameter.requires_grad_(False)
    model.config.pad_token_id=processor.tokenizer.pad_token_id
    if model.config.decoder_start_token_id is None:model.config.decoder_start_token_id=2
    train=Dates('train',processor,a.train_limit,task_dataset);val=Dates('val',processor,a.val_limit,task_dataset)
    loader=DataLoader(train,batch_size=a.batch,shuffle=True,num_workers=a.workers,pin_memory=True,collate_fn=collate,persistent_workers=a.workers>0,generator=torch.Generator().manual_seed(42))
    val_loader=DataLoader(val,batch_size=a.batch,shuffle=False,num_workers=a.workers,pin_memory=True,collate_fn=collate,persistent_workers=a.workers>0)
    parameters=[p for p in model.parameters() if p.requires_grad]
    if a.decoder_lr is not None:
        decoder_ids={id(p) for p in model.decoder.parameters()}
        parameters=[dict(params=[p for p in parameters if id(p) not in decoder_ids],lr=a.lr),
                    dict(params=[p for p in model.decoder.parameters() if p.requires_grad],lr=a.decoder_lr)]
    optimizer=torch.optim.AdamW(parameters,lr=a.lr,weight_decay=.01,foreach=False)
    scheduler=get_cosine_schedule_with_warmup(optimizer,num_warmup_steps=max(10,len(loader)//8),num_training_steps=len(loader)*a.epochs)
    report=dict(initial_checkpoint=a.initial,initial_checkpoint_sha256=hashlib.sha256((Path(a.initial)/'model.safetensors').read_bytes()).hexdigest(),dataset=str(task_dataset),label_sha256=hashlib.sha256((task_dataset/'labels.jsonl').read_bytes()).hexdigest(),cuda_device=torch.cuda.get_device_name(0),precision='BF16 autocast, FP32 master weights',trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),train_samples=len(train),validation_samples=len(val),epochs_requested=a.epochs,batch_size=a.batch,learning_rate=a.lr,selection='Synthetic validation exact transcription accuracy, CER tie-break; no organizer images',preprocessing='Unchanged original TrOCR processor; direct resize to 384x384',history=[])
    report.update(encoder_only=a.encoder_only,decoder_learning_rate=a.decoder_lr if a.decoder_lr is not None else (0 if a.encoder_only else a.lr))
    if getattr(processor.image_processor,'sanad_fit',False):report['preprocessing']=dict(mode='Pillow ImageOps.pad bilinear, white; interpolated ViT positions',size=processor.image_processor.size)
    best=(-1.,-float('inf'));started=time.time();step=0
    if a.baseline:
        report['baseline_validation']=evaluate(model,val_loader,processor)
        write_json(task_logs/'training.json',report);print('BASELINE',report['baseline_validation'],flush=True)
    for epoch in range(1,a.epochs+1):
        model.train();loss_sum=0.
        if a.encoder_only:model.decoder.eval()
        for i,(values,labels,*_) in enumerate(loader,1):
            optimizer.zero_grad(set_to_none=True)
            geometry={'interpolate_pos_encoding':True} if getattr(model.config.encoder,'interpolate_pos_encoding',False) else {}
            with torch.autocast('cuda',dtype=torch.bfloat16):loss=model(pixel_values=values.cuda(non_blocking=True),labels=labels.cuda(non_blocking=True),use_cache=False,**geometry).loss
            if not torch.isfinite(loss):raise RuntimeError('Non-finite loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();scheduler.step();step+=1;loss_sum+=float(loss.detach())
            if i==1 or i%50==0:
                progress=dict(epoch=epoch,batch=i,batches=len(loader),loss=round(loss_sum/i,4),seconds=round(time.time()-started),peak_cuda_gb=round(torch.cuda.max_memory_allocated()/1e9,2))
                write_json(task_logs/'progress.json',progress);print(progress,flush=True)
        metrics=evaluate(model,val_loader,processor);entry=dict(epoch=epoch,train_loss=loss_sum/len(loader),validation=metrics,seconds=round(time.time()-started));report['history'].append(entry)
        rank=(metrics['exact_accuracy'],-metrics['cer'])
        if rank>best:
            best=rank;task_checkpoint.mkdir(parents=True,exist_ok=True);model.save_pretrained(task_checkpoint,safe_serialization=True);processor.save_pretrained(task_checkpoint);report['best_epoch']=epoch
        write_json(task_logs/'training.json',report);print('VALIDATION',epoch,metrics,flush=True)
    del model,optimizer;torch.cuda.empty_cache()
    model=VisionEncoderDecoderModel.from_pretrained(task_checkpoint,local_files_only=True).cuda()
    test_loader=DataLoader(Dates('test',processor,dataset_root=task_dataset),batch_size=a.batch,num_workers=a.workers,collate_fn=collate)
    report['synthetic_test']=evaluate(model,test_loader,processor);report['seconds']=round(time.time()-started)
    report['checkpoint_sha256']=hashlib.sha256((task_checkpoint/'model.safetensors').read_bytes()).hexdigest();write_json(task_logs/'training.json',report)
    print('DONE',report['synthetic_test'],flush=True)

if __name__=='__main__':main()

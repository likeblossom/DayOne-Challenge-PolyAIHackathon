"""ADB UI helpers and authentic screenshot capture for the specimen demo."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'demo/form01';SERIAL='S200PLUS20000105738'
def adb(*args):return subprocess.run(['adb','-s',SERIAL,*args],check=True,capture_output=True).stdout
def nodes():
    adb('shell','uiautomator','dump','/sdcard/sanad-demo-ui.xml')
    raw=adb('shell','cat','/sdcard/sanad-demo-ui.xml');(OUT/'ui.xml').write_bytes(raw)
    return ET.fromstring(raw).iter('node')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['ui','click','shot','phone-shot','check-visible','replace']);p.add_argument('value',nargs='?',default='');p.add_argument('--with-text');a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if a.action=='ui':
        for n in nodes():
            t=n.get('text') or n.get('content-desc')
            if t:print(n.get('class'),repr(t),n.get('bounds'), 'checked='+n.get('checked',''))
    elif a.action=='check-visible':
        for n in nodes():
            if n.get('class')=='android.widget.CheckBox' and n.get('text')=='Checked against the paper' and n.get('checked')=='false':
                v=list(map(int,re.findall(r'\d+',n.get('bounds'))))
                if v[3]-v[1]>=80:adb('shell','input','tap',str((v[0]+v[2])//2),str((v[1]+v[3])//2));print('Checked visible reviewed field')
    elif a.action in ('click','replace'):
        for n in nodes():
            if a.value in (n.get('text'),n.get('content-desc')):
                v=list(map(int,re.findall(r'\d+',n.get('bounds'))));adb('shell','input','tap',str((v[0]+v[2])//2),str((v[1]+v[3])//2))
                if a.action=='replace':
                    adb('shell','input','keycombination','113','29');adb('shell','input','text',(a.with_text or '').replace(' ','%s'));adb('shell','input','keyevent','4')
                print(a.action,a.value);break
        else:raise SystemExit('UI item not found: '+a.value)
    else:
        path=OUT/'screenshots';path.mkdir(exist_ok=True)
        capture=adb('exec-out','screencap','-d','4627039422300187648','-p')
        signature=capture.find(b'\x89PNG\r\n\x1a\n')
        if signature<0:raise RuntimeError('Phone did not return a PNG screenshot')
        (path/(a.value+'-phone.png')).write_bytes(capture[signature:])
        if a.action=='phone-shot':
            print(path/(a.value+'-phone.png'));return
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','x11grab','-draw_mouse','0','-video_size','1920x1080','-i',os.environ.get('DISPLAY',':0')+'+1920,0','-frames:v','1','-update','1',str(path/(a.value+'.png'))],check=True)
        with (OUT/'screenshots.jsonl').open('a') as f:f.write(json.dumps({'name':a.value,'at':time.time()})+'\n')
        print(path/(a.value+'.png'))
if __name__=='__main__':main()

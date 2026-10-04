"""Minimal read-only SQLite dashboard for the live phone demo."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
import tkinter as tk
import ctypes
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'demo/form01'
DB=ROOT/'android-app/.usb-database/sanad.sqlite3'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    start=datetime.now(timezone.utc).isoformat()
    (OUT/'dashboard_start.json').write_text(json.dumps({'started_at':start,'database':str(DB),'scope':'New form-01 rows committed since this dashboard started'}))
    root=tk.Tk()
    root.title('Sanad')
    root.geometry('1920x1080+1920+0')
    root.overrideredirect(True)
    c=tk.Canvas(root,width=1920,height=1080,bg='#101b26',highlightthickness=0)
    c.pack()
    # Keep only the demo phone's i3 frame above this borderless canvas.
    x=ctypes.CDLL('libX11.so.6');x.XOpenDisplay.restype=ctypes.c_void_p
    display=x.XOpenDisplay(None)
    x.XQueryTree.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),ctypes.POINTER(ctypes.c_uint)]
    x.XRaiseWindow.argtypes=[ctypes.c_void_p,ctypes.c_ulong];x.XFlush.argtypes=[ctypes.c_void_p];x.XFree.argtypes=[ctypes.c_void_p]
    phone=subprocess.check_output(['xdotool','search','--name','^SANAD_DEMO_PHONE$'],text=True).splitlines()[0]
    parent=ctypes.c_ulong();root_id=ctypes.c_ulong();children=ctypes.POINTER(ctypes.c_ulong)();count=ctypes.c_uint()
    x.XQueryTree(display,int(phone),ctypes.byref(root_id),ctypes.byref(parent),ctypes.byref(children),ctypes.byref(count))
    if children:x.XFree(children)
    def raise_phone():
        x.XRaiseWindow(display,parent.value);x.XFlush(display);root.after(100,raise_phone)
    raise_phone()
    last=None
    def text(x,y,value,size=22,color='#edf5fa',bold=False,width=None):
        c.create_text(x,y,text=value,anchor='nw',fill=color,font=('DejaVu Sans',size,'bold' if bold else 'normal'),width=width)
    def tick():
        nonlocal last
        try:
            with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True,timeout=2) as conn:
                rows=conn.execute('SELECT id,payload,received_at FROM records WHERE form_id=? AND received_at>=? ORDER BY received_at',('pregnancy_postpartum_monitoring',start)).fetchall()
            c.delete('all')
            text(62,30,'Sanad',34,bold=True)
            text(600,140,'PC database',30,bold=True)
            text(600,215,str(len(rows))+' new '+('record' if len(rows)==1 else 'records'),36,color='#65d8b4',bold=True)
            if rows:
                rid,payload,received=rows[-1]
                record=json.loads(payload)
                labels={'record_code':'Record ID','region':'Region','province':'Province','health_facility_name':'Facility','health_facility_type':'Facility type','coverage_mode':'Coverage','high_risk_pregnancy':'High risk','risk_factors':'Risk factors','other_risk_factor':'Other risk'}
                for i,(key,label) in enumerate(labels.items()):
                    value=record['fields'].get(key)
                    if isinstance(value,list):
                        shown=', '.join(str(v.get('value')) for v in value if v.get('value') is not None) or '—'
                    else:
                        v=value.get('value') if value else None
                        shown='—' if v is None else ('Yes' if v is True else 'No' if v is False else str(v))
                    y=340+i*65
                    text(600,y,label,21,color='#9db5c9')
                    text(945,y,shown,23,bold=key=='record_code',width=880)
            signature=tuple(r[0] for r in rows)
            if signature!=last:
                with (OUT/'database_events.jsonl').open('a') as out:
                    out.write(json.dumps({'at':time.time(),'utc':datetime.now(timezone.utc).isoformat(),'new_count':len(rows),'record_ids':list(signature)})+'\n')
                last=signature
        except Exception as e:
            # Never display a stale successful count on a failed query.
            c.delete('all')
            text(62,30,'Sanad',34,bold=True)
            text(600,140,'PC database',30,bold=True)
            text(600,215,'Unavailable',28,color='#ffce7b')
            print(type(e).__name__,flush=True)
        root.after(1000,tick)
    tick()
    root.mainloop()

if __name__=='__main__':main()

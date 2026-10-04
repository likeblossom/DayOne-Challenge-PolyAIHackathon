"""Loopback-only SQLite receiver. No LAN listener, cloud, or third-party dependencies."""
import argparse
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import tarfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / '.usb-database'


def initialize(folder):
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    token_file = folder / 'token'
    if not token_file.exists():
        token_file.write_text(secrets.token_hex(32))
    os.chmod(token_file, 0o600)
    db = folder / 'sanad.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, form_id TEXT NOT NULL, patient_code TEXT NOT NULL, payload TEXT NOT NULL, sha256 TEXT NOT NULL, received_at TEXT NOT NULL)')
    os.chmod(db, 0o600)
    return token_file.read_text().strip(), db


def validate(record):
    if not isinstance(record, dict):
        raise ValueError('Expected record object')
    for key in ('id', 'form_id', 'patient_code', 'confirmed_at'):
        if not isinstance(record.get(key), str) or not record[key] or len(record[key]) > 256:
            raise ValueError('Missing or invalid ' + key)
    if record.get('state') != 'REGISTERED' or not isinstance(record.get('fields'), dict):
        raise ValueError('Only reviewed submitted records are accepted')
    forms = {p.name.split('_', 1)[1].removesuffix('.schema.json') for p in (ROOT / 'app/src/main/assets/forms').glob('*.schema.json')}
    if record['form_id'] not in forms:
        raise ValueError('Unknown form')
    def fields(value):
        if isinstance(value, list):
            for item in value: fields(item)
        elif isinstance(value, dict):
            if 'status' in value:
                if value['status'] not in {'KNOWN','UNKNOWN','NOT_PROVIDED','ILLEGIBLE','NOT_APPLICABLE','NEEDS_REVIEW'} or 'value' not in value:
                    raise ValueError('Invalid field envelope')
                confidence=value.get('confidence')
                if not isinstance(confidence,(float,int)) or isinstance(confidence,bool) or not 0<=confidence<=1:
                    raise ValueError('Invalid confidence')
                if value['status']=='NEEDS_REVIEW' and not value.get('human_reviewed'):
                    raise ValueError('Field still needs review')
            else:
                for item in value.values(): fields(item)
        else:
            raise ValueError('Expected structured fields')
    fields(record['fields'])


def make_server(folder, port=8765):
    token, db = initialize(folder)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass  # Do not log record bodies or credentials.
        def respond(self, status, body):
            data=json.dumps(body).encode();self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)
        def authorized(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+token):
                self.respond(401,{'error':'Unauthorized'});return False
            return True
        def do_GET(self):
            if not self.authorized(): return
            if self.path!='/health':self.respond(404,{'error':'Not found'});return
            self.respond(200,{'service':'sanad-usb-db-v1'})
        def do_POST(self):
            if not self.authorized(): return
            if self.path!='/records':self.respond(404,{'error':'Not found'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=8*1024*1024: self.respond(413,{'error':'Invalid payload size'});return
                self.connection.settimeout(15)
                record=json.loads(self.rfile.read(length));validate(record)
                payload=json.dumps(record,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
                digest=hashlib.sha256(payload.encode()).hexdigest();now=datetime.now(timezone.utc).isoformat()
                with sqlite3.connect(db, timeout=10) as conn:
                    conn.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?,?,?)',(record['id'],record['form_id'],record['patient_code'],payload,digest,now))
                    stored=conn.execute('SELECT sha256,received_at FROM records WHERE id=?',(record['id'],)).fetchone()
                    if stored[0]!=digest:self.respond(409,{'error':'Record ID already has different content; submit a new revision'});return
                self.respond(200,{'id':record['id'],'committed':True,'sha256':stored[0],'received_at':stored[1],'transport':'usb-adb'})
            except (ValueError,TypeError,KeyError):self.respond(400,{'error':'Invalid or unreviewed record'})
            except (sqlite3.Error,OSError):self.respond(503,{'error':'Database temporarily unavailable'})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def pair(folder, serial):
    token, _ = initialize(folder)
    adb=['adb','-s',serial]
    subprocess.run(adb+['reverse','localabstract:sanad-usb-db','tcp:8765'],check=True)
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w') as archive:
        raw=token.encode();info=tarfile.TarInfo('usb-sync-token');info.size=len(raw);info.mode=0o600
        archive.addfile(info,io.BytesIO(raw))
    subprocess.run(adb+['exec-in','run-as','org.dayone.midwife','tar','xf','-','-C','files'],input=data.getvalue(),check=True)
    print('USB paired; Android local socket forwarded to PC localhost:8765. Token installed privately.',flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--serial');ap.add_argument('--data-dir',type=Path,default=DEFAULT_DATA);ap.add_argument('--pair-only',action='store_true');ap.add_argument('--list',action='store_true');args=ap.parse_args()
    os.umask(0o077)
    if args.list:
        _,db=initialize(args.data_dir)
        with sqlite3.connect(db) as conn:
            for row in conn.execute('SELECT id,form_id,received_at FROM records ORDER BY received_at'):print(*row,sep=' | ')
        return
    if args.pair_only:
        if not args.serial:ap.error('--pair-only requires --serial')
        pair(args.data_dir,args.serial);return
    server=make_server(args.data_dir)
    if args.serial:pair(args.data_dir,args.serial)
    print(f'Sanad USB database listening only on 127.0.0.1:8765; database: {args.data_dir / "sanad.sqlite3"}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()

import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

spec=importlib.util.spec_from_file_location('usb_database',Path(__file__).with_name('usb_database.py'))
usb=importlib.util.module_from_spec(spec);spec.loader.exec_module(usb)

class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.server=usb.make_server(self.folder,0);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.token=(self.folder/'token').read_text();self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.record=dict(id='usb-test',form_id='pregnancy_postpartum_monitoring',patient_code='TEST',confirmed_at='2026-10-04T12:00:00Z',state='REGISTERED',fields={'record_code':dict(value='2026-823-001',status='KNOWN',confidence=1,human_reviewed=True)})
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,body=None,token=None):
        req=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+(self.token if token is None else token),'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)
    def test_auth_and_health(self):
        self.assertEqual(401,self.request('/health',token='wrong')[0]);self.assertEqual(200,self.request('/health')[0])
    def test_commit_idempotency_and_preservation(self):
        for _ in range(2):self.assertTrue(self.request('/records',self.record)[1]['committed'])
        with sqlite3.connect(self.folder/'sanad.sqlite3') as db:
            rows=db.execute('SELECT payload FROM records').fetchall();self.assertEqual(1,len(rows));self.assertEqual(self.record,json.loads(rows[0][0]))
    def test_conflicting_id_does_not_overwrite(self):
        self.request('/records',self.record);changed=copy.deepcopy(self.record);changed['fields']['record_code']['value']='other'
        self.assertEqual(409,self.request('/records',changed)[0])
    def test_drafts_rejected(self):
        self.record['state']='NEEDS_REVIEW';self.assertEqual(400,self.request('/records',self.record)[0])
    def test_missing_confirmation_rejected(self):
        del self.record['confirmed_at'];self.assertEqual(400,self.request('/records',self.record)[0])
    def test_unreviewed_field_rejected(self):
        self.record['fields']['record_code'].update(status='NEEDS_REVIEW',human_reviewed=False)
        self.assertEqual(400,self.request('/records',self.record)[0])
    def test_unknown_form_rejected(self):
        self.record['form_id']='unknown';self.assertEqual(400,self.request('/records',self.record)[0])

if __name__=='__main__':unittest.main()

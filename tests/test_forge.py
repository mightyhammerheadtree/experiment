import base64
import json
import struct
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from forge.core import inspect, handoff, strict_settings, validate_launch, build, GEX_REV
from forge.discovery import discover
from forge.planning import plan
from forge.server import Handler


def fixture(path, bits=64):
    """Minimal PE with a branch, a direct call, an indirect call and a return."""
    b = bytearray(1024)
    b[:2] = b'MZ'; struct.pack_into('<I',b,0x3c,0x80)
    b[0x80:0x84] = b'PE\0\0'
    size = 240 if bits == 64 else 224
    struct.pack_into('<HHIIIHH',b,0x84,0x8664 if bits == 64 else 0x14c,1,0,0,0,size,0x22)
    o = 0x98
    struct.pack_into('<H',b,o,0x20b if bits == 64 else 0x10b)
    struct.pack_into('<I',b,o+16,0x1000)
    if bits == 64: struct.pack_into('<Q',b,o+24,0x140000000)
    else: struct.pack_into('<I',b,o+28,0x400000)
    struct.pack_into('<II',b,o+32,0x1000,0x200)
    struct.pack_into('<II',b,o+56,0x2000,0x200)
    struct.pack_into('<H',b,o+68,3)
    struct.pack_into('<I',b,o+(108 if bits == 64 else 92),16)
    struct.pack_into('<8sIIIIIIHHI',b,o+size,b'.text\0\0\0',0x100,0x1000,0x200,0x200,0,0,0,0,0x60000020)
    b[0x200:0x20e] = bytes.fromhex('7505e805000000ffd0c3909090c3')
    path.write_bytes(b)
    return path


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_x64_inspection(self):
        p = fixture(self.root/'game.exe'); (self.root/'data.win').write_bytes(b'FORM')
        r = inspect(p)
        self.assertEqual(r['architecture'],'x64'); self.assertIn('GameMaker',r['engine'])
        self.assertEqual(r['status'],'analysis-only'); self.assertEqual(len(r['sha256']),64)
    def test_x86_inspection(self): self.assertEqual(inspect(fixture(self.root/'game.exe',32))['architecture'],'x86')
    def test_invalid(self):
        p = self.root/'bad.exe'; p.write_bytes(b'bad')
        with self.assertRaises(ValueError): inspect(p)
    def test_truncated_section(self):
        p = fixture(self.root/'game.exe'); p.write_bytes(p.read_bytes()[:700])
        with self.assertRaises(ValueError): inspect(p)
    def test_discovery_both_bitnesses(self):
        for bits in (64,32):
            r = discover(fixture(self.root/f'game{bits}.exe',bits),100)
            self.assertEqual(r['bits'],bits); self.assertGreater(r['instructions'],0)
            self.assertEqual(r['direct_call_targets'],1); self.assertEqual(r['indirect_count'],1)
    def test_discovery_budget(self):
        r = discover(fixture(self.root/'game.exe'),1)
        self.assertEqual(r['instructions'],1); self.assertTrue(r['budget_exhausted'])
    def test_invalid_budget(self):
        with self.assertRaises(ValueError): discover(self.root/'anything',0)
    def test_handoff_honesty(self):
        archive = self.root/'out.zip'; handoff(fixture(self.root/'game.exe'),archive,True)
        with zipfile.ZipFile(archive) as z:
            self.assertIn('NOT A PLAYABLE PORT',z.read('READ-ME-FIRST.txt').decode())
            self.assertIn('discovery',json.loads(z.read('report.json')))
    def test_no_input_overwrite(self):
        p = fixture(self.root/'game.exe')
        with self.assertRaises(ValueError): handoff(p,p)
        self.assertEqual(p.read_bytes()[:2],b'MZ')
    def test_priority(self): self.assertEqual(plan(fixture(self.root/'game.exe'))['target']['priority'],1)
    def test_strict_settings(self):
        r = strict_settings({'features':{'translation':True},'cold':'jit'})
        self.assertFalse(r['features']['translation']); self.assertEqual(r['cold'],'none')
    def test_launch_rejection(self):
        for bad in ({'kind':'wine64','units':[1]}, {'kind':'wine32','units':[1],'features_off':['translation']}, {'kind':'wine64','units':[],'features_off':['translation']}):
            with self.assertRaises(ValueError): validate_launch(bad,'x64')
    def test_build_requires_recording(self):
        with self.assertRaisesRegex(ValueError,'recording'): build(self.root,self.root,self.root/'new')
    def test_build_orchestration_x64(self):
        gex = self.root/'gex'; (gex/'target/x86/release').mkdir(parents=True)
        (gex/'target/x86/release/gexc').touch()
        rec = self.root/'rec'; rec.mkdir(); (rec/'wine32-session.json').write_text('{}')
        out = self.root/'out'
        def fake_run(cmd, **kwargs):
            if 'eject' in cmd:
                self.assertIn('--web-src',cmd)
                project = out/'project'; (project/'user').mkdir(parents=True)
                (project/'gex-project.json').write_text('{"kind":"wine64"}')
                (project/'user/eject.json').write_text('{"features":{"translation":true},"cold":"jit"}')
            elif cmd[0] == 'bash':
                config=json.loads((out/'project/user/eject.json').read_text())
                self.assertFalse(config['features']['translation'])
                web=out/'project/build/web'; web.mkdir(parents=True)
                (web/'wine32.json').write_text(json.dumps({'kind':'wine64','features_off':['translation'],'units':[{'key':'test'}]}))
            else:
                site=out/'site'; site.mkdir(); (site/'index.html').write_text('<html></html>')
                (site/'module.wasm').write_bytes(b'\0asm\x01\0\0\0')
                (site/'site.json').write_text('{"kind":"wine64","features_off":["translation"]}')
        with patch('forge.core.subprocess.check_output',return_value=GEX_REV+'\n'),patch('forge.core.subprocess.run',side_effect=fake_run):
            archive = build(gex,rec,out)
        with zipfile.ZipFile(archive) as z:
            manifest=json.loads(z.read('glassforge-build.json'))
            self.assertTrue(manifest['strict_aot']); self.assertEqual(manifest['status'],'built-not-gameplay-validated')
            self.assertIn('index.html',manifest['files'])


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls): cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
    def post(self,payload):
        req=urllib.request.Request(self.url+'/api/analyze',json.dumps(payload).encode(),{'Content-Type':'application/json'})
        return urllib.request.urlopen(req)
    def test_page(self):
        with urllib.request.urlopen(self.url) as r: self.assertIn(b'glassforge',r.read())
    def test_upload(self):
        with tempfile.TemporaryDirectory() as d:
            data=fixture(Path(d)/'game.exe').read_bytes()
            with self.post({'files':[{'name':'game.exe','data':base64.b64encode(data).decode()}],'discover':True}) as r:
                body=json.load(r); self.assertEqual(body['report']['architecture'],'x64'); self.assertTrue(body['archive'])
    def test_traversal_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post({'files':[{'name':'../game.exe','data':''}]})
        self.assertEqual(cm.exception.code,400)
    def test_duplicate_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post({'files':[{'name':'game.exe','data':''},{'name':'GAME.EXE','data':''}]})
        self.assertEqual(cm.exception.code,400)

if __name__ == '__main__': unittest.main()

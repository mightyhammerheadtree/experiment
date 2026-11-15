import hashlib
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from forge.core import GEX_REV, build
from forge.preflight import preflight, RUNTIME, RUNTIME64
from forge.toolchain import setup_plan, execute_setup
from forge.verify import verify


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def prepared(self, arch='x64'):
        gex = self.root/'gex'; rec = self.root/'rec'; cache = self.root/'units'
        for name in ['target/x86/release/gexc','site/eject-site.mjs','site/build-eject-page.sh','page/package-lock.json']:
            f = gex/name; f.parent.mkdir(parents=True,exist_ok=True); f.touch()
        for name in RUNTIME+RUNTIME64:
            f=gex/'page/public/gex'/name; f.parent.mkdir(parents=True,exist_ok=True); f.touch()
        key = 'a'*64; (cache/key).mkdir(parents=True)
        for name in ['c.wasm','c.entries']: (cache/key/name).touch()
        bundle = self.root/'bundle.tar'; bundle.touch(); rec.mkdir()
        session=dict(format='gex-wine32-session',page={'exe':'/wine/lib/wine/'+('x86_64' if arch=='x64' else 'i386')+'-unix/wine'},bundle=str(bundle),units=[{'key':key,'path':'/g/game.exe'}],unit_misses=[],uncovered=[])
        (rec/'wine32-session.json').write_text(json.dumps(session))
        return gex,rec,cache,session
    def check_preflight(self,gex,rec,cache,arch='x64'):
        with patch('forge.preflight.subprocess.check_output',side_effect=[GEX_REV+'\n','']):
            return preflight(gex,rec,arch,cache)
    def test_valid_x64_preflight(self):
        g,r,c,_=self.prepared(); result=self.check_preflight(g,r,c)
        self.assertEqual(result['status'],'ready-for-eject')
        self.assertTrue(any(x['id']=='trampolines-and-providers' and x['status']=='warning' for x in result['checks']))
    def test_valid_x86_preflight(self):
        g,r,c,_=self.prepared('x86'); self.assertEqual(self.check_preflight(g,r,c,'x86')['failures'],0)
    def test_missing_memory64(self):
        g,r,c,_=self.prepared(); (g/'page/public/gex'/RUNTIME64[0]).unlink()
        self.assertGreater(self.check_preflight(g,r,c)['failures'],0)
    def test_wrong_architecture(self):
        g,r,c,_=self.prepared(); self.assertGreater(self.check_preflight(g,r,c,'x86')['failures'],0)
    def test_bad_unit_key(self):
        g,r,c,s=self.prepared(); s['units'][0]['key']='../../bad'
        (r/'wine32-session.json').write_text(json.dumps(s))
        self.assertGreater(self.check_preflight(g,r,c)['failures'],0)
    def test_relative_bundle_rejected(self):
        g,r,c,s=self.prepared(); s['bundle']='relative.tar'
        (r/'wine32-session.json').write_text(json.dumps(s))
        self.assertGreater(self.check_preflight(g,r,c)['failures'],0)
    def test_malformed_recording(self):
        g,r,c,_=self.prepared(); (r/'wine32-session.json').write_text('[]')
        self.assertGreater(self.check_preflight(g,r,c)['failures'],0)
    def test_missing_unit_pair(self):
        g,r,c,_=self.prepared(); (c/('a'*64)/'c.entries').unlink()
        self.assertGreater(self.check_preflight(g,r,c)['failures'],0)
    def test_failed_preflight_does_not_start_build(self):
        g,r,c,_=self.prepared(); (c/('a'*64)/'c.entries').unlink()
        with patch('forge.core.subprocess.check_output',return_value=GEX_REV+'\n'),patch('forge.core.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError,'preflight blocked'): build(g,r,self.root/'out',unit_cache=c)
            run.assert_not_called()
        self.assertFalse((self.root/'out').exists())
    def archive(self, change=None):
        files={'index.html':b'<html></html>','main.wasm':b'\0asm\x01\0\0\0','site.json':json.dumps({'kind':'wine64','features_off':['translation']}).encode()}
        manifest=dict(schema=1,architecture='x64',strict_aot=True,runtime_translation=False,status='built-not-gameplay-validated',files={n:hashlib.sha256(b).hexdigest() for n,b in files.items()})
        files['glassforge-build.json']=json.dumps(manifest).encode()
        if change: change(files)
        archive=self.root/'site.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for n,b in files.items(): z.writestr(n,b)
        return archive
    def test_verify_good(self): self.assertEqual(verify(self.archive())['status'],'verified-integrity-only')
    def test_verify_modified(self):
        result=verify(self.archive(lambda f:f.update({'main.wasm':b'modified'})))
        self.assertIn('Hash mismatch: main.wasm',result['errors'])
    def test_verify_extra(self): self.assertEqual(verify(self.archive(lambda f:f.update({'extra':b'payload'})))['status'],'invalid')
    def test_verify_missing(self): self.assertEqual(verify(self.archive(lambda f:f.pop('main.wasm')))['status'],'invalid')
    def test_verify_traversal(self): self.assertEqual(verify(self.archive(lambda f:f.update({'../outside':b'x'})))['status'],'invalid')
    def test_verify_symlink(self):
        path=self.archive()
        with zipfile.ZipFile(path,'a') as z:
            i=zipfile.ZipInfo('link'); i.create_system=3; i.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(i,'/etc/passwd')
        self.assertEqual(verify(path)['status'],'invalid')
    def test_verify_limit(self): self.assertEqual(verify(self.archive(),max_bytes=1)['status'],'invalid')
    def test_verify_garbage(self):
        p=self.root/'garbage';p.write_bytes(b'not a zip'); self.assertEqual(verify(p)['status'],'invalid')
    def test_setup_plan_does_not_execute(self):
        with patch('forge.toolchain.subprocess.run') as run:
            result=setup_plan(self.root/'new')
            run.assert_not_called()
        self.assertFalse((self.root/'new').exists())
        self.assertIn('--locked',next(s for s in result['steps'] if s['id']=='driver')['argv'])
        self.assertEqual(next(s for s in result['steps'] if s['id']=='memory64')['env']['GEX_MEM64'],'1')
    def test_setup_rejects_nonrepo(self):
        with self.assertRaises(ValueError): setup_plan(self.root)
    def test_setup_job_bound(self):
        with self.assertRaises(ValueError): setup_plan(self.root/'new',jobs=1000)
    def test_setup_records_failed_step(self):
        plan=setup_plan(self.root/'new',phase='fetch')
        with patch('forge.toolchain.subprocess.run') as run:
            run.return_value.returncode=1
            with self.assertRaisesRegex(ValueError,'clone failed'): execute_setup(plan,self.root/'logs')
        result=json.loads((self.root/'logs/status.json').read_text())
        self.assertEqual(result['failed'],'clone');self.assertEqual(result['status'],'failed')

if __name__ == '__main__': unittest.main()

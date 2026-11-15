import functools
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from windex.staging import stage, ROOT, V86_FILES, GEX_MODULES
from windex.server import Handler


class StageTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_empty_shell_is_honest(self):
        result=stage(self.root/'site'); config=json.loads((self.root/'site/windex.json').read_text())
        self.assertFalse(result['gex_enabled']);self.assertFalse(config['linux']['enabled'])
        self.assertTrue((self.root/'site/index.html').is_file());self.assertTrue((self.root/'site/provenance.json').is_file())
    def test_does_not_overwrite(self):
        with self.assertRaisesRegex(ValueError,'must not exist'):stage(self.root)
    def test_gex_requires_trees(self):
        with self.assertRaisesRegex(ValueError,'together'):stage(self.root/'site',runtime=self.root/'runtime')
    def source(self):
        source=self.root/'linuxontab';(source/'shell').mkdir(parents=True)
        for name in V86_FILES+['linux4.iso']:(source/'shell'/name).write_bytes(b'fixture-not-runtime'*100)
        return source
    def test_stage_linux_with_provenance(self):
        source=self.source(); lock=json.loads((ROOT/'upstreams.lock.json').read_text())
        with patch('windex.staging.subprocess.check_output',side_effect=[lock['linuxontab']['revision']+'\n','']):
            result=stage(self.root/'site',linuxontab=source)
        self.assertTrue(result['linux_enabled']);self.assertFalse(result['gex_enabled'])
        manifest=json.loads((self.root/'site/provenance.json').read_text())
        self.assertEqual(len(manifest['files']['assets/linux/v86.wasm']),64)
    def test_wrong_pin_rejected(self):
        with patch('windex.staging.subprocess.check_output',side_effect=['wrong','']):
            with self.assertRaisesRegex(ValueError,'pinned'):stage(self.root/'site',linuxontab=self.source())
    def test_lfs_pointer_rejected(self):
        source=self.source();(source/'shell/v86.wasm').write_text('version https://git-lfs.github.com/spec/v1\n'+'x'*400)
        lock=json.loads((ROOT/'upstreams.lock.json').read_text())
        with patch('windex.staging.subprocess.check_output',side_effect=[lock['linuxontab']['revision'],'']):
            with self.assertRaisesRegex(ValueError,'LFS'):stage(self.root/'site',linuxontab=source)
    def test_runtime_staging(self):
        package=self.root/'runtime';package.mkdir()
        for n in GEX_MODULES:(package/n).write_text('// fixture, not a compiled runtime')
        (package/'runtime.wasm').write_bytes(b'\0asm\x01\0\0\0');tree=self.root/'base.tar';tree.touch()
        result=stage(self.root/'site',runtime=package,trees=[tree])
        self.assertTrue(result['gex_enabled']);config=json.loads((self.root/'site/windex.json').read_text())
        self.assertEqual(config['gex']['trees'],['/assets/trees/0.tar'])
        self.assertEqual(config['mode'],'runtime-translation')
    def test_symlink_runtime_rejected(self):
        package=self.root/'runtime';package.mkdir()
        for n in GEX_MODULES:(package/n).touch()
        (package/'runtime.wasm').touch();(package/'escape').symlink_to(self.root)
        tree=self.root/'base.tar';tree.touch()
        with self.assertRaisesRegex(ValueError,'symlink'):stage(self.root/'site',runtime=package,trees=[tree])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.site=self.root/'site';self.site.mkdir()
        (self.site/'index.html').write_text('Windex');(self.site/'runtime.wasm').write_bytes(b'0123456789')
        (self.root/'secret').write_text('secret');(self.site/'escape').symlink_to(self.root/'secret')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(self.site)))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def test_isolation_headers(self):
        with urllib.request.urlopen(self.url) as r:
            self.assertEqual(r.headers['Cross-Origin-Opener-Policy'],'same-origin');self.assertEqual(r.headers['Cross-Origin-Embedder-Policy'],'require-corp')
    def test_wasm_range(self):
        req=urllib.request.Request(self.url+'/runtime.wasm',headers={'Range':'bytes=2-4'})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status,206);self.assertEqual(r.read(),b'234');self.assertEqual(r.headers['Content-Range'],'bytes 2-4/10');self.assertEqual(r.headers['Content-Type'],'application/wasm')
    def test_unsatisfiable_range(self):
        req=urllib.request.Request(self.url+'/runtime.wasm',headers={'Range':'bytes=100-'})
        with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code,416)
    def test_symlink_escape(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(self.url+'/escape')
        self.assertEqual(cm.exception.code,403)
    def test_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(self.url+'/%2e%2e/secret')
        self.assertEqual(cm.exception.code,403)
    def test_no_upload_endpoint(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(urllib.request.Request(self.url,data=b'game bytes'))
        self.assertEqual(cm.exception.code,501)

if __name__=='__main__':unittest.main()

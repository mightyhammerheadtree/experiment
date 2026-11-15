"""Build integration checks without pretending to compile or execute Wine."""
import hashlib
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

from windex.wine_bundle import read_build_env, preflight, verify_bundle, package


class WineBuildTests(unittest.TestCase):
    def test_env_is_data_not_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = root/'wine.env'
            env.write_text(f"ignored log\nWINE64_DIST='{root}'\nWINE64_PREFIX='{root}'\n")
            self.assertEqual(read_build_env(env)['WINE64_DIST'], str(root))
            env.write_text('WINE64_DIST=$(touch marker)\n')
            with self.assertRaises(ValueError): read_build_env(env)
            self.assertFalse((root/'marker').exists())

    def test_missing_prefix_fails_packaging_input(self):
        with tempfile.TemporaryDirectory() as temp:
            env = Path(temp)/'wine.env'
            env.write_text(f'WINE64_DIST={temp}\n')
            with self.assertRaisesRegex(ValueError, 'WINE64_PREFIX'): read_build_env(env)

    def test_preflight_reports_missing_tools(self):
        with patch('windex.wine_bundle.shutil.which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'clang.*rustc.*mingw'): preflight()

    def test_bundle_integrity_and_manifest_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = b'archive fixture, not executable Wine'
            (root/'windex-wine.tar').write_bytes(data)
            manifest = dict(schema=1, product='Windex', archive='windex-wine.tar',
                            loader='/wine/lib/wine/x86_64-unix/wine', prefix='/pfx', memory64=False,
                            sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            file = root/'wine-bundle.json'
            file.write_text(json.dumps(manifest))
            self.assertEqual(verify_bundle(root)[0], root/'windex-wine.tar')
            (root/'windex-wine.tar').write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError, 'integrity'): verify_bundle(root)
            manifest['archive'] = '../outside.tar'
            file.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Unsupported'): verify_bundle(root)

    def test_packaging_mounts_wine_and_sanitized_prefix_together(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'upstreams.lock.json').write_text(json.dumps({'wine':{'revision':'fixture'}}))
            source = root/'gex'; (source/'wine').mkdir(parents=True)
            for name in ['wine.pins', 'libs.pins']:
                (source/'wine'/name).write_text('fixture source pins')
            dist = root/'dist'
            for rel in ['x86_64-unix/wine', 'x86_64-unix/wineserver',
                        'x86_64-windows/ntdll.dll', 'x86_64-windows/kernel32.dll',
                        'i386-windows/ntdll.dll']:
                path = dist/'lib/wine'/rel; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'\0asm\x01\0\0\0')
            prefix = root/'prefix'; prefix.mkdir()
            (prefix/'system.reg').write_text('#arch=win64\n')
            (prefix/'user.reg').write_text('fixture')
            env = root/'wine.env'
            env.write_text(f'WINE64_DIST={dist}\nWINE64_PREFIX={prefix}\n')
            def prepare(argv, **kwargs):
                self.assertEqual(kwargs['env']['DIST_MOUNT'], '/wine')
                self.assertEqual(kwargs['env']['GRAPHICS'], 'wayland')
                prepared = Path(argv[-1]); prepared.mkdir()
                (prepared/'system.reg').write_text('#arch=win64\n')
                (prepared/'dosdevices').mkdir()
                (prepared/'dosdevices/z:').symlink_to('/')
            output = root/'work/bundle'
            with patch('windex.wine_bundle.ROOT', root), patch('windex.wine_bundle.verify_source', return_value=(source, 'fixture-gex')), patch('windex.wine_bundle.subprocess.run', side_effect=prepare):
                result = package(source, env, output)
                self.assertEqual(result['status'], 'packaged-not-execution-verified')
                self.assertEqual(verify_bundle(output)[1]['sha256'], result['sha256'])
                with tarfile.open(output/'windex-wine.tar') as archive:
                    self.assertIn('wine/lib/wine/x86_64-unix/wine', archive.getnames())
                    self.assertEqual(archive.getmember('pfx/dosdevices/z:').linkname, '/')
                with self.assertRaisesRegex(ValueError, 'already exists'): package(source, env, output)


if __name__ == '__main__': unittest.main()

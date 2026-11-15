"""Verify a Glassforge site ZIP without extracting or executing its contents."""
import hashlib
import json
import re
import stat
import zipfile
from pathlib import PurePosixPath


def verify(archive, max_bytes=16*1024**3):
    errors = []
    def error(text): errors.append(text)
    try:
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            if len(infos) > 100000: raise ValueError('Too many ZIP members')
            names = [i.filename for i in infos]
            if len(names) != len(set(names)): raise ValueError('Duplicate ZIP members')
            if sum(i.file_size for i in infos) > max_bytes: raise ValueError('ZIP exceeds verification size limit')
            for i in infos:
                p = PurePosixPath(i.filename)
                if not i.filename or '\\' in i.filename or p.is_absolute() or '..' in p.parts or ':' in i.filename or str(p) != i.filename.rstrip('/'):
                    raise ValueError('Unsafe or noncanonical ZIP path: '+i.filename)
                if stat.S_ISLNK(i.external_attr >> 16): raise ValueError('Symlink in ZIP: '+i.filename)
            for required in ['index.html','site.json','glassforge-build.json']:
                if required not in names: error('Missing '+required)
            if errors: return dict(status='invalid', errors=errors)
            def read_json(name):
                if z.getinfo(name).file_size > 8*1024*1024: raise ValueError(name+' too large')
                result = json.loads(z.read(name))
                if not isinstance(result, dict): raise ValueError(name+' must be an object')
                return result
            manifest = read_json('glassforge-build.json')
            site = read_json('site.json')
            if manifest.get('schema') != 1: error('Unsupported manifest schema')
            if manifest.get('strict_aot') is not True or manifest.get('runtime_translation') is not False:
                error('Manifest does not declare strict AOT')
            if manifest.get('status') != 'built-not-gameplay-validated': error('Unexpected validation status')
            arch = manifest.get('architecture')
            if arch not in ('x64','x86'): error('Unsupported architecture')
            if site.get('kind') != {'x64':'wine64','x86':'wine32'}.get(arch): error('Site architecture disagrees with manifest')
            disabled = site.get('features_off')
            if not isinstance(disabled, list) or 'translation' not in disabled: error('Site does not disable runtime translation')
            hashes = manifest.get('files')
            if not isinstance(hashes, dict): raise ValueError('Invalid file hash inventory')
            actual = {i.filename for i in infos if not i.is_dir()} - {'glassforge-build.json'}
            if set(hashes) != actual: error('File inventory differs from ZIP contents')
            for name, expected in hashes.items():
                if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
                    error('Invalid digest: '+name); continue
                if name not in actual: continue
                digest = hashlib.sha256()
                with z.open(name) as f:
                    for block in iter(lambda:f.read(1024*1024), b''): digest.update(block)
                if digest.hexdigest() != expected: error('Hash mismatch: '+name)
            if not any(n.endswith(('.wasm','.wasm.zst')) for n in actual): error('No Wasm artifacts')
            return dict(schema=1, status='invalid' if errors else 'verified-integrity-only', architecture=arch, files=len(actual), errors=errors, scope='Checks archive integrity and declared AOT settings only. Not a signature, Wasm validation, or proof of gameplay.')
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as e:
        return dict(status='invalid', errors=[str(e)])

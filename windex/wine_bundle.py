"""Internal Wine artifact packaging. Never converts or accepts game executables."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def read_build_env(path):
    """Read upstream's KEY=value output as data; never source a shell file."""
    values = {}
    for line in Path(path).read_text().splitlines():
        if not line.startswith('WINE64_') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        words = shlex.split(value)
        if len(words) != 1:
            raise ValueError('Invalid Wine build output: ' + key)
        values[key] = words[0]
    for key in ('WINE64_DIST', 'WINE64_PREFIX'):
        if key not in values or not Path(values[key]).is_dir():
            raise ValueError('Missing Wine build directory: ' + key)
    return values


def verify_source(source):
    source = Path(source).resolve()
    pin = json.loads((ROOT/'upstreams.lock.json').read_text())['gex']['revision']
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()
    if revision != pin or dirty:
        raise ValueError('Wine requires the clean pinned GEX source revision: ' + pin)
    return source, revision


def preflight():
    required = ['make', 'clang', 'clang++', 'wasm-ld', 'llvm-ar', 'llvm-ranlib',
                'llvm-config', 'rustc', 'cargo', 'node', 'pkg-config', 'bison', 'flex',
                'x86_64-w64-mingw32-gcc', 'i686-w64-mingw32-gcc']
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise ValueError('Wasm Wine build prerequisites missing: ' + ', '.join(missing))
    clang = subprocess.check_output(['clang', '--version'], text=True)
    if 'version 22.' not in clang:
        raise ValueError('Pinned GEX Wine requires LLVM/clang 22 (including development headers)')
    for cc in ['x86_64-w64-mingw32-gcc', 'i686-w64-mingw32-gcc']:
        if subprocess.check_output([cc, '-dumpversion'], text=True).strip().split('.')[0] != '12':
            raise ValueError('Pinned GEX Wine requires MinGW GCC 12: ' + cc)
    crt = Path(os.environ.get('GEX_CRT_SRC', str(Path.home()/'emsdk/upstream/emscripten/system/lib/compiler-rt/lib/builtins')))
    if not (crt/'udivti3.c').is_file():
        raise ValueError('Set GEX_CRT_SRC to compiler-rt/lib/builtins sources')



def package(source, env_file, output):
    source, revision = verify_source(source)
    values = read_build_env(env_file)
    dist, prefix = Path(values['WINE64_DIST']).resolve(), Path(values['WINE64_PREFIX']).resolve()
    loader = dist/'lib/wine/x86_64-unix/wine'
    server = dist/'lib/wine/x86_64-unix/wineserver'
    for path in [loader, server, dist/'lib/wine/x86_64-windows/ntdll.dll',
                 dist/'lib/wine/x86_64-windows/kernel32.dll', dist/'lib/wine/i386-windows/ntdll.dll',
                 prefix/'system.reg', prefix/'user.reg']:
        if not path.is_file():
            raise ValueError('Incomplete Wine64/WoW64 artifact: ' + str(path))
    if '#arch=win64' not in (prefix/'system.reg').read_text(errors='replace').splitlines():
        raise ValueError('Wine prefix must be initialized win64')
    with loader.open('rb') as f:
        magic = f.read(8)
    if not (magic.startswith(b'\0asm\x01\0\0\0') or magic.startswith(b'\x7fELF\x02\x01')):
        raise ValueError('Expected upstream GEX Wasm/ELF64 loader')
    output = Path(output).resolve()
    work = (ROOT/'work').resolve()
    if output == work or not output.is_relative_to(work):
        raise ValueError('Wine bundle output must be under work/')
    if output.exists():
        raise ValueError('Wine bundle output already exists; choose a new output directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.wine-bundle-', dir=output.parent) as temp:
        temp = Path(temp)
        # Upstream removes host-profile links, preserves drive links, rewrites registry
        # installation paths, and verifies the prefix matches the distribution.
        subprocess.run(['bash', str(source/'wine/page-prefix.sh'), str(prefix), str(dist), str(temp/'pfx')],
                       env={**os.environ, 'DIST_MOUNT':'/wine', 'GRAPHICS':'wayland'}, check=True)
        for path in dist.rglob('*'):
            if path.is_symlink() and not path.resolve().is_relative_to(dist):
                raise ValueError('Wine distribution links outside its mount: ' + str(path))
        artifact = temp/'bundle'; artifact.mkdir()
        archive = artifact/'windex-wine.tar'
        with tarfile.open(archive, 'w', format=tarfile.PAX_FORMAT) as tar:
            tar.add(dist, arcname='wine')
            tar.add(temp/'pfx', arcname='pfx')
        with archive.open('rb') as stream:
            h = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024*1024), b''): h.update(chunk)
            digest = h.hexdigest()
        manifest = {'schema':1, 'product':'Windex', 'gexRevision':revision,
                    'wineRevision':json.loads((ROOT/'upstreams.lock.json').read_text())['wine']['revision'],
                    'archive':archive.name, 'sha256':digest, 'bytes':archive.stat().st_size,
                    'loader':'/wine/lib/wine/x86_64-unix/wine', 'prefix':'/pfx',
                    'wow64':True, 'memory64':False, 'status':'packaged-not-execution-verified'}
        (artifact/'wine-bundle.json').write_text(json.dumps(manifest, indent=2)+'\n')
        shutil.copyfile(source/'wine/wine.pins', artifact/'wine.pins')
        shutil.copyfile(source/'wine/libs.pins', artifact/'libs.pins')
        artifact.rename(output)
    return manifest


def verify_bundle(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory/'wine-bundle.json').read_text())
    if (manifest.get('schema') != 1 or manifest.get('product') != 'Windex'
            or manifest.get('archive') != 'windex-wine.tar'
            or manifest.get('loader') != '/wine/lib/wine/x86_64-unix/wine'
            or manifest.get('prefix') != '/pfx' or manifest.get('memory64') is not False):
        raise ValueError('Unsupported Wine bundle manifest')
    archive = directory/'windex-wine.tar'
    h = hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''): h.update(chunk)
    if archive.stat().st_size != manifest['bytes'] or h.hexdigest() != manifest['sha256']:
        raise ValueError('Wine bundle integrity mismatch')
    return archive, manifest

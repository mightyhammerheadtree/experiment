"""Stage operator-provided runtime artifacts. No game assets or binaries in Git."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V86_FILES = ['libv86.js', 'v86.wasm', 'seabios.bin', 'vgabios.bin']
GEX_MODULES = ['index.mjs', 'fs.mjs', 'windows-host.mjs', 'gl.mjs', 'audio.mjs', 'input.mjs']


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def stage(output, linuxontab=None, runtime=None, trees=(), iso='linux4.iso'):
    out = Path(output).resolve()
    if out.exists(): raise ValueError('Site output must not exist; stage into a new directory')
    lock = json.loads((ROOT/'upstreams.lock.json').read_text())
    source = Path(linuxontab).resolve() if linuxontab else None
    package = Path(runtime).resolve() if runtime else None
    if source:
        rev = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'], text=True).strip()
        if rev != lock['linuxontab']['revision'] or dirty: raise ValueError('Requires clean pinned linuxontab checkout')
        if Path(iso).name != iso or not iso.endswith('.iso'): raise ValueError('ISO must be a simple .iso filename')
        for name in V86_FILES+[iso]:
            path = source/'shell'/name
            if not path.is_file() or path.stat().st_size < 256: raise ValueError('Missing asset or unresolved LFS pointer: '+str(path))
            with path.open('rb') as stream:
                if stream.read(64).startswith(b'version https://git-lfs'): raise ValueError('Fetch real LFS bytes: '+str(path))
    if bool(package) != bool(trees): raise ValueError('GEX runtime and at least one filesystem tree must be supplied together')
    if package:
        for name in GEX_MODULES:
            if not (package/name).is_file(): raise ValueError('Missing built GEX package module: '+name)
        if not any(package.rglob('*.wasm')): raise ValueError('Runtime package contains no Wasm artifacts')
        for path in package.rglob('*'):
            if path.is_symlink(): raise ValueError('Runtime package must contain real files, not symlinks')
    tree_paths = [Path(t).resolve() for t in trees]
    if any(not t.is_file() for t in tree_paths): raise ValueError('Filesystem tree not found')
    # Never stage into a directory being copied, or recursively consume output.
    for input_dir in [p for p in (source,package) if p]:
        if out.is_relative_to(input_dir): raise ValueError('Site output must be outside input source directories')
    out.mkdir(parents=True)
    shutil.copytree(ROOT/'windex/web', out, dirs_exist_ok=True)
    config = dict(schema=1, product='Windex', mode='runtime-translation', gex=dict(enabled=bool(package), package='/assets/gex/', trees=[], loader='/wine/lib/wine/x86_64-unix/wine', prefix='/pfx', env={'HOME':'/home/user','PATH':'/usr/local/bin:/usr/bin:/bin','WINEDEBUG':'err+all,fixme-all','WINEGEX_WOW64':'1','WINEDLLOVERRIDES':'mshtml=;mscoree='}, memory64=False, persistence=False, store='windex-v1', d3d=True), linux=dict(enabled=bool(source), assets='/assets/linux/', iso=iso, memoryMiB=128))
    if source:
        target=out/'assets/linux'; target.mkdir(parents=True)
        for name in V86_FILES+[iso]: shutil.copyfile(source/'shell'/name,target/name)
    if package:
        shutil.copytree(package,out/'assets/gex')
        target=out/'assets/trees'; target.mkdir(parents=True)
        for i,t in enumerate(tree_paths):
            name=f'{i}.tar'+('.zst' if t.name.endswith('.zst') else '')
            shutil.copyfile(t,target/name)
            config['gex']['trees'].append('/assets/trees/'+name)
    (out/'windex.json').write_text(json.dumps(config,indent=2)+'\n')
    shutil.copyfile(ROOT/'upstreams.lock.json',out/'upstreams.lock.json')
    (out/'_headers').write_text('/*\n  Cross-Origin-Opener-Policy: same-origin\n  Cross-Origin-Embedder-Policy: require-corp\n  Cross-Origin-Resource-Policy: same-origin\n')
    provenance=dict(schema=1, status='staged-not-gameplay-validated', expected_upstreams=lock, runtime_build_attested=False, linuxontab_source_checked=bool(source), files={})
    for p in sorted(out.rglob('*')):
        if p.is_file(): provenance['files'][p.relative_to(out).as_posix()]=digest(p)
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return dict(site=str(out), gex_enabled=bool(package), linux_enabled=bool(source), status=provenance['status'])

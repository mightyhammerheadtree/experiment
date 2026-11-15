"""Early, non-executing checks against the pinned GEX recording contract."""
import json
import re
import subprocess
from pathlib import Path
from .core import GEX_REV

RUNTIME = ['gex_browser.x86.shared.wasm', 'gex_kernel.x86.wasm', 'seed.x86.shared.wasm']
RUNTIME64 = ['gex_browser.x86.m64.shared.wasm', 'seed.x86.m64.shared.wasm']


def preflight(gex, recording, arch='x64', unit_cache=None):
    if arch not in ('x64', 'x86'):
        raise ValueError('Target must be x64 or x86')
    gex, recording = Path(gex).resolve(), Path(recording).resolve()
    checks = []
    def check(name, ok, detail, warning=False):
        checks.append(dict(id=name, status='pass' if ok else ('warning' if warning else 'fail'), detail=detail))
    try:
        revision = subprocess.check_output(['git', '-C', str(gex), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
    except (OSError, subprocess.SubprocessError):
        revision = None
    check('gex-revision', revision == GEX_REV, f'Requires GEX {GEX_REV}; found {revision or "no Git checkout"}')
    try:
        dirty = subprocess.check_output(['git', '-C', str(gex), 'status', '--porcelain', '--untracked-files=no'], text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
        clean = not dirty
    except (OSError, subprocess.SubprocessError):
        clean = False
    check('gex-source-clean', clean, 'Tracked GEX source must be unmodified; untracked build outputs are allowed')
    for name in ['target/x86/release/gexc', 'site/eject-site.mjs', 'site/build-eject-page.sh', 'page/package-lock.json']:
        check('artifact:'+name, (gex/name).is_file(), str(gex/name))
    for name in RUNTIME + (RUNTIME64 if arch == 'x64' else []):
        check('runtime:'+name, (gex/'page/public/gex'/name).is_file(), f'Build upstream runtime artifact {name}')
    path = recording/'wine32-session.json'
    session = None
    try:
        if path.stat().st_size > 64*1024*1024:
            raise ValueError('Session exceeds 64 MiB limit')
        session = json.loads(path.read_text())
        if not isinstance(session, dict): raise ValueError('Session must be an object')
        check('recording-json', True, str(path))
    except (OSError, ValueError) as e:
        session = None
        check('recording-json', False, str(e))
    if session is not None:
        check('recording-format', session.get('format') in ('gex-wine32-session', 'gex-w3-session'), 'Use the upstream page recorder; do not rename the legacy session filename')
        page = session.get('page')
        loader = page.get('exe') if isinstance(page, dict) else None
        expected = '/x86_64-unix/' if arch == 'x64' else '/i386-unix/'
        check('recording-architecture', isinstance(loader, str) and expected in loader, f'Expected {expected} Wine loader, found {loader!r}; x86-on-WoW64 uses a wine64 model and is not a wine32 target')
        bundle = session.get('bundle')
        # Upstream reads this path relative to its own cwd. Require absolute paths
        # instead of guessing, silently rebasing, or rewriting source recordings.
        absolute = isinstance(bundle, str) and Path(bundle).is_absolute()
        check('bundle-path', absolute and Path(bundle).is_file(), 'Recording bundle must be an existing absolute path; record with --bundle /absolute/file.tar')
        cache = Path(unit_cache).resolve() if unit_cache else None
        check('unit-cache', cache is not None and cache.is_dir(), 'Pass --unit-cache explicitly so validation and GEX use the same cache')
        units = session.get('units')
        valid = isinstance(units, list) and bool(units)
        check('recorded-units', valid, 'At least one recorded function-tier unit is required')
        if valid:
            missing = []; malformed = []
            for i, unit in enumerate(units):
                key = unit.get('key') if isinstance(unit, dict) else None
                if not isinstance(key, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', key) or not isinstance(unit.get('path'), str):
                    malformed.append(i)
                elif cache and not all((cache/key/f).is_file() for f in ['c.wasm', 'c.entries']):
                    missing.append(key)
            check('unit-keys', not malformed, f'Malformed unit entries: {malformed[:20]}')
            check('unit-files', cache is not None and not missing, f'Missing compiled unit pairs: {missing[:20]}')
        for key in ['unit_misses', 'uncovered']:
            entries = session.get(key, [])
            check('coverage:'+key, isinstance(entries, list) and not entries, f'{len(entries) if isinstance(entries, list) else "invalid"} {key}; strict AOT may need more compilation/recording', warning=True)
        check('trampolines-and-providers', False, 'GEX eject must validate content-keyed NT trampoline/provider units; this preflight cannot derive their keys', warning=True)
    failed = sum(c['status'] == 'fail' for c in checks)
    return dict(schema=1, architecture=arch, status='blocked' if failed else 'ready-for-eject', failures=failed, checks=checks, scope='Prerequisite checks only, not game compatibility or complete code coverage')

"""Architecture-first project plans and non-executing toolchain checks."""
import shutil
from pathlib import Path
from .core import GEX_REV, inspect


def plan(path, code=False, budget=100000):
    report = inspect(path)
    arch = report['architecture']
    report['target'] = {'priority': 1 if arch == 'x64' else 2, 'backend': 'gex-wine64' if arch == 'x64' else 'gex-wine32', 'strict_aot': True, 'runtime_translation': False, 'browser_requirements': ['WebAssembly', 'SharedArrayBuffer', 'COOP/COEP isolation', 'WebGPU for accelerated graphics'] + (['WebAssembly memory64 when required by the game'] if arch == 'x64' else [])}
    imports = {i.lower() for i in report['imports']}
    report['compatibility'] = []
    for dlls, feature, message in [({'d3d11.dll','dxgi.dll'}, 'd3d11', 'Validate GEX D3D device and Wine graphics path; import presence does not prove support.'), ({'d3d9.dll'}, 'd3d9', 'Validate Wine graphics translation and browser rendering.'), ({'winmm.dll','xaudio2_7.dll','dsound.dll'}, 'audio', 'Verify browser user-gesture audio unlock and Wine sound output.'), ({'wininet.dll','ws2_32.dll'}, 'network', 'Offline by default. Browser networking is not raw Windows sockets.'), ({'mscoree.dll'}, 'dotnet', 'Wine Mono is not bundled by GEX; managed runtime is a blocker.')]:
        if imports & dlls:
            report['compatibility'].append({'feature':feature, 'status':'needs-validation', 'detail':message})
    report['pipeline'] = [
        {'id':'inspect', 'status':'complete', 'detail':f'{arch} PE parsed without executing guest code'},
        {'id':'discover', 'status':'pending' if not code else 'complete', 'detail':'iced-x86 bounded code discovery'},
        {'id':'toolchain', 'status':'pending', 'detail':f'GEX {GEX_REV}, Wine, runtime, graphics, unit cache'},
        {'id':'record', 'status':'pending', 'detail':'Prepare Wine bundle and record actual gameplay; legacy session filename also handles wine64'},
        {'id':'compile', 'status':'pending', 'detail':'GEX eject with translation=false and cold=none'},
        {'id':'package', 'status':'pending', 'detail':'Validate AOT launch settings and package upstream static site'},
        {'id':'validate', 'status':'pending', 'detail':'Test menus, all gameplay paths, audio, saves and missing-code traps in a browser'}]
    if code:
        from .discovery import discover
        report['discovery'] = discover(path, budget)
    return report


def doctor(gex=None):
    tools = ['git','make','node','rustc','cargo','clang','wasm-ld','emcc','wasm-tools','zstd','x86_64-w64-mingw32-gcc','i686-w64-mingw32-gcc']
    result = {'tools': {t:shutil.which(t) for t in tools}, 'note':'Presence checks only; versions and end-to-end operation are not certified.'}
    if gex:
        root = Path(gex)
        result['artifacts'] = {p:(root/p).is_file() for p in ['target/x86/release/gexc','page/public/gex/gex_browser.x86.shared.wasm','page/public/gex/gex_browser.x86.m64.shared.wasm','page/public/gex/seed.x86.m64.shared.wasm','site/eject-site.mjs']}
    return result

"""Use GEX's existing Wine bundle/probe path; never execute by default."""
import json
import os
import subprocess
from pathlib import Path
from .core import GEX_REV, inspect


def probe_plan(gex, exe, dist, prefix, unit_cache, output, arch='x64', seconds=120, build_units=False):
    if arch not in ('x64','x86'): raise ValueError('Probe target must be x64 or x86')
    if not 1 <= seconds <= 3600: raise ValueError('Probe timeout must be between 1 and 3600 seconds')
    gex, exe, dist, prefix, unit_cache, output = [Path(p).resolve() for p in (gex,exe,dist,prefix,unit_cache,output)]
    report = inspect(exe)
    if report['architecture'] != arch: raise ValueError('EXE architecture disagrees with probe target')
    if output.exists(): raise ValueError('Probe output must not exist')
    if output.is_relative_to(exe.parent):
        raise ValueError('Probe output must be outside the game folder (upstream bundles that entire folder)')
    for path in [gex/'wine/run.sh', prefix/'system.reg', dist/'lib/wine'/('x86_64-unix' if arch=='x64' else 'i386-unix')/'wine']:
        if not path.is_file(): raise ValueError('Missing prerequisite: '+str(path))
    adapter = Path(__file__).resolve().parent.parent/'scripts/local-bench.sh'
    argv=['bash',str(gex/'wine/run.sh'),'--page',str(gex),'--no-make','--dist',str(dist),'--prefix',str(prefix),'--units',str(unit_cache),'--timeout',str(seconds)]
    if build_units: argv.append('--build-units')
    argv += ['--',str(exe)]
    return dict(schema=1, architecture=arch, gex=str(gex), gex_revision=GEX_REV, exe=str(exe), exe_sha256=report['sha256'], output=str(output), argv=argv, env={'BENCH_SH':str(adapter),'WINE32_PAGE_DIR':str(output/'page')}, status='plan-only', warnings=['--execute runs the supplied game and Chromium via upstream tooling; use a disposable VM without secrets.', 'GEX copies the entire EXE parent directory, including unrelated files; use a dedicated clean game folder.', 'This is a runtime-translation probe, NOT a strict-AOT export or a complete gameplay recording.', 'A successful process exit is not proof of rendering or gameplay. --build-units may need repeated probe passes.', 'The local adapter does not provision Chromium, GPU drivers, Wine or the GEX toolchain.'])


def execute_probe(plan):
    root = Path(plan['gex'])
    rev = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    dirty = subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True).strip()
    if rev != GEX_REV or dirty: raise ValueError('Probe requires a clean, pinned GEX source checkout')
    if inspect(plan['exe'])['sha256'] != plan['exe_sha256']: raise ValueError('EXE changed after planning')
    output = Path(plan['output'])
    output.mkdir(parents=True,exist_ok=False)
    (output/'probe-plan.json').write_text(json.dumps(plan,indent=2))
    status = dict(status='failed', scope='Upstream runtime probe only; not a static build or gameplay certification')
    try:
        with (output/'probe.log').open('w') as stream:
            result = subprocess.run(plan['argv'],cwd=root,env=dict(os.environ,**plan['env']),stdout=stream,stderr=subprocess.STDOUT)
        status['returncode'] = result.returncode
        if result.returncode: raise ValueError(f'GEX probe failed ({result.returncode}); see {output / "probe.log"}')
        status['status'] = 'probe-finished-not-gameplay-validated'
    finally:
        (output/'probe-status.json').write_text(json.dumps(status,indent=2))
    return status

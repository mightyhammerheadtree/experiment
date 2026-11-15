"""Reviewed upstream build plans; execution is opt-in and never installs OS packages."""
import json
import os
import subprocess
from pathlib import Path
from .core import GEX_REV


def setup_plan(gex, phase='all', jobs=4):
    if phase not in ('fetch','driver','runtime','wine','all'): raise ValueError('Invalid setup phase')
    if not 1 <= jobs <= 64: raise ValueError('Jobs must be between 1 and 64')
    root = Path(gex).resolve()
    steps = []
    if not root.exists():
        steps += [dict(id='clone', argv=['git','clone','--no-checkout','https://github.com/HeyPuter/gex',str(root)], cwd=str(root.parent)), dict(id='pin', argv=['git','checkout','--detach',GEX_REV], cwd=str(root))]
    elif not (root/'.git').exists():
        raise ValueError('Existing setup destination is not a Git checkout')
    def add(name, argv, env=None):
        steps.append(dict(id=name, argv=argv, cwd=str(root), env=env or {}))
    if phase in ('driver','all'):
        add('driver',['cargo','build','--locked','--release','-p','gexc','--features','x86','--target-dir','target/x86','--jobs',str(jobs)])
    if phase in ('wine','all'):
        add('wine',['make','wine',f'JOBS={jobs}'])
    if phase in ('runtime','all'):
        add('page',['make','page',f'JOBS={jobs}'])
        add('memory64',['sh','hosts/browser/build.sh'], {'GEX_ARCH':'x86','GEX_MEM64':'1'})
    return dict(schema=1, gex=str(root), revision=GEX_REV, phase=phase, steps=steps, prerequisites=['Linux build host with upstream native build dependencies','Rust 1.96.0 plus upstream-required nightly/rust-src components','LLVM/clang 22, Node >=22, Emscripten 6.0.1, wasm-tools','MinGW-w64 GCC 12 for both architectures, make, zstd','Network access to all upstream dependency sources; substantial free RAM/disk'], note='Plan only unless --execute. Builds upstream artifacts, not a game port. OS/toolchain package installation and version provisioning remain operator tasks.')


def execute_setup(plan, log_dir):
    logs = Path(log_dir).resolve()
    if logs.exists(): raise ValueError('Log directory must not exist')
    root = Path(plan['gex'])
    def validate_checkout():
        rev = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'], text=True).strip()
        if rev != GEX_REV or dirty: raise ValueError('Setup requires the pinned checkout with no tracked modifications')
    if root.exists(): validate_checkout()
    logs.mkdir(parents=True)
    (logs/'plan.json').write_text(json.dumps(plan, indent=2))
    status = dict(status='running', completed=[], failed=None)
    try:
        for i, step in enumerate(plan['steps']):
            if step['id'] not in ('clone','pin'): validate_checkout()
            Path(step['cwd']).mkdir(parents=True, exist_ok=True)
            print(f"[{step['id']}] log: {logs / (str(i)+'-'+step['id']+'.log')}", flush=True)
            status['failed'] = step['id']
            with (logs/(str(i)+'-'+step['id']+'.log')).open('w') as stream:
                proc = subprocess.run(step['argv'], cwd=step['cwd'], env=dict(os.environ, **step.get('env',{})), stdout=stream, stderr=subprocess.STDOUT)
            if proc.returncode:
                status['failed'] = step['id']
                raise ValueError(f"Setup step {step['id']} failed ({proc.returncode}); see {logs}")
            status['completed'].append(step['id'])
            status['failed'] = None
            if step['id'] == 'pin': validate_checkout()
        status['status'] = 'completed'
    finally:
        if status['status'] != 'completed': status['status'] = 'failed'
        (logs/'status.json').write_text(json.dumps(status, indent=2))
    return status

import argparse
import json
import subprocess
from .core import inspect, handoff, build
from .planning import plan, doctor

p = argparse.ArgumentParser(description='Glassforge • x64-first EXE → browser port workbench')
s = p.add_subparsers(dest='command', required=True)
a = s.add_parser('inspect'); a.add_argument('exe')
a = s.add_parser('plan'); a.add_argument('exe'); a.add_argument('--discover', action='store_true'); a.add_argument('--budget', type=int, default=100000)
a = s.add_parser('doctor'); a.add_argument('--gex')
a = s.add_parser('handoff'); a.add_argument('exe'); a.add_argument('-o', '--output', required=True); a.add_argument('--discover', action='store_true'); a.add_argument('--budget', type=int, default=100000)
a = s.add_parser('build'); a.add_argument('--gex', required=True); a.add_argument('--recording', required=True); a.add_argument('-o', '--output', required=True); a.add_argument('--arch', choices=['x64','x86'], default='x64'); a.add_argument('--unit-cache')
a = s.add_parser('preflight'); a.add_argument('--gex', required=True); a.add_argument('--recording', required=True); a.add_argument('--arch', choices=['x64','x86'], default='x64'); a.add_argument('--unit-cache', required=True)
a = s.add_parser('verify'); a.add_argument('archive')
a = s.add_parser('probe'); a.add_argument('exe'); a.add_argument('--gex', required=True); a.add_argument('--dist', required=True); a.add_argument('--prefix', required=True); a.add_argument('--unit-cache', required=True); a.add_argument('-o','--output',required=True); a.add_argument('--arch',choices=['x64','x86'],default='x64'); a.add_argument('--seconds',type=int,default=120); a.add_argument('--build-units',action='store_true'); a.add_argument('--execute',action='store_true')
a = s.add_parser('setup'); a.add_argument('--gex', required=True); a.add_argument('--phase', choices=['fetch','driver','runtime','wine','all'], default='all'); a.add_argument('--jobs', type=int, default=4); a.add_argument('--execute', action='store_true'); a.add_argument('--logs', default='work/setup-logs')
a = s.add_parser('serve'); a.add_argument('--port', type=int, default=8080); a.add_argument('--host', default='0.0.0.0')
args = p.parse_args()
try:
    if args.command == 'inspect': print(json.dumps(inspect(args.exe), indent=2))
    elif args.command == 'plan': print(json.dumps(plan(args.exe, args.discover, args.budget), indent=2))
    elif args.command == 'doctor': print(json.dumps(doctor(args.gex), indent=2))
    elif args.command == 'handoff': print(json.dumps(handoff(args.exe, args.output, args.discover, args.budget), indent=2))
    elif args.command == 'build': print(build(args.gex, args.recording, args.output, args.arch, args.unit_cache))
    elif args.command == 'preflight':
        from .preflight import preflight
        result = preflight(args.gex, args.recording, args.arch, args.unit_cache)
        print(json.dumps(result, indent=2))
        if result['failures']: p.exit(1)
    elif args.command == 'verify':
        from .verify import verify
        result = verify(args.archive)
        print(json.dumps(result, indent=2))
        if result['status'] == 'invalid': p.exit(1)
    elif args.command == 'probe':
        from .probe import probe_plan, execute_probe
        result = probe_plan(args.gex,args.exe,args.dist,args.prefix,args.unit_cache,args.output,args.arch,args.seconds,args.build_units)
        print(json.dumps(result, indent=2), flush=True)
        if args.execute: print(json.dumps(execute_probe(result), indent=2))
    elif args.command == 'setup':
        from .toolchain import setup_plan, execute_setup
        result = setup_plan(args.gex, args.phase, args.jobs)
        print(json.dumps(result, indent=2), flush=True)
        if args.execute: print(json.dumps(execute_setup(result, args.logs), indent=2))
    else:
        from .server import serve
        serve(args.host, args.port)
except (ValueError, OSError, subprocess.CalledProcessError) as e:
    p.exit(1, f'glassforge: {e}\n')

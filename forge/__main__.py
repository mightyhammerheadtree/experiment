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
a = s.add_parser('serve'); a.add_argument('--port', type=int, default=8080); a.add_argument('--host', default='0.0.0.0')
args = p.parse_args()
try:
    if args.command == 'inspect': print(json.dumps(inspect(args.exe), indent=2))
    elif args.command == 'plan': print(json.dumps(plan(args.exe, args.discover, args.budget), indent=2))
    elif args.command == 'doctor': print(json.dumps(doctor(args.gex), indent=2))
    elif args.command == 'handoff': print(json.dumps(handoff(args.exe, args.output, args.discover, args.budget), indent=2))
    elif args.command == 'build': print(build(args.gex, args.recording, args.output, args.arch, args.unit_cache))
    else:
        from .server import serve
        serve(args.host, args.port)
except (ValueError, OSError, subprocess.CalledProcessError) as e:
    p.exit(1, f'glassforge: {e}\n')

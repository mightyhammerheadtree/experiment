import argparse
import json
import subprocess
from .staging import stage
from .server import serve

p=argparse.ArgumentParser(description='Windex — direct Windows runtime + Linux console in your browser')
s=p.add_subparsers(dest='command',required=True)
a=s.add_parser('stage');a.add_argument('-o','--output',required=True);a.add_argument('--linuxontab');a.add_argument('--runtime');a.add_argument('--tree',action='append',default=[]);a.add_argument('--iso',default='linux4.iso')
a=s.add_parser('serve');a.add_argument('--site',default='windex/web');a.add_argument('--host',default='0.0.0.0');a.add_argument('--port',type=int,default=8080)
args=p.parse_args()
try:
    if args.command=='stage':print(json.dumps(stage(args.output,args.linuxontab,args.runtime,args.tree,args.iso),indent=2))
    else:serve(args.site,args.host,args.port)
except (ValueError,OSError,subprocess.SubprocessError) as e:p.exit(1,f'windex: {e}\n')

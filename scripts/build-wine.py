"""Internal upstream Wine build driver; the Windex product remains in-browser."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from windex.wine_bundle import package, preflight, verify_source

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', default='.cache/gex', help='Clean pinned GEX checkout')
parser.add_argument('--output', default='work/wine-bundle')
parser.add_argument('--check', action='store_true', help='Check build prerequisites without building')
parser.add_argument('--package-only', action='store_true', help='Package an existing upstream out/wine.env build')
args = parser.parse_args()
try:
    source, revision = verify_source(args.source)
    if not args.package_only:
        preflight()
    if args.check:
        print('Pinned source and Wine build prerequisites OK: ' + revision)
    else:
        if not args.package_only:
            # Upstream owns sysroot, dependency, Wine64/WoW64 and native-prefix builds.
            subprocess.run(['make', '-C', str(source), 'wine'],
                           env={**os.environ, 'WINE64_MEM64':'0', 'WINE64_TWIN':'0'}, check=True)
        print(json.dumps(package(source, source/'out/wine.env', args.output), indent=2))
except (ValueError, subprocess.CalledProcessError) as error:
    print(str(error), file=sys.stderr)
    sys.exit(1)

"""Developer asset assembly, not an end-user runtime or EXE conversion tool."""
import json
import os
import sys
import shutil
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from windex.staging import stage

config_path = Path(os.environ.get('WINDEX_BUILD_CONFIG', 'windex.build.local.json'))
config = json.loads(config_path.read_text()) if config_path.is_file() else {}
output = Path(os.environ.get('WINDEX_OUTPUT', 'work/site')).resolve()
work = (Path(__file__).resolve().parent.parent/'work').resolve()
if output == work or not output.is_relative_to(work):
    raise ValueError('Build output must be a subdirectory of work/')
output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='.windex-build-', dir=output.parent) as temporary:
    staged = Path(temporary)/'site'
    result = stage(staged, linuxontab=config.get('linuxontab'), runtime=config.get('runtime', 'node_modules/@gexemu/runtime'), trees=config.get('trees', ['node_modules/@gexemu/debian/debian-slim.tar.zst']), iso=config.get('iso', 'linux4.iso'))
    if output.exists(): shutil.rmtree(output)
    staged.rename(output)
result['site'] = str(output)
print(json.dumps(result, indent=2))

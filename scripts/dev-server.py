"""Developer hosting only. Windex itself runs in the browser."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from windex.server import serve

site = os.environ.get('WINDEX_SITE', 'work/site' if Path('work/site/index.html').is_file() else 'windex/web')
serve(site, os.environ.get('HOST', '0.0.0.0'), int(os.environ.get('PORT', '8080')))

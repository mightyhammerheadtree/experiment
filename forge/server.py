"""Analysis-only UI. Build execution is deliberately CLI-only."""
import base64
import binascii
import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .core import handoff

WEB = Path(__file__).resolve().parent.parent/'web/index.html'
MAX = 90 * 1024 * 1024

class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, kind='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/': self.reply(200, WEB.read_bytes(), 'text/html; charset=utf-8')
        else: self.reply(404, b'{}')

    def do_POST(self):
        if self.path != '/api/analyze':
            return self.reply(404, b'{}')
        # No ambient authenticated actions, disk persistence, or build execution.
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= MAX: return self.reply(413, b'{"error":"Upload limit: 60 MiB total before encoding"}')
            payload = json.loads(self.rfile.read(n))
            if not isinstance(payload, dict): raise ValueError('Expected a JSON object')
            files = payload['files']
            if not isinstance(files, list) or not 1 <= len(files) <= 128: raise ValueError('Select 1–128 files')
            if any(not isinstance(item, dict) for item in files): raise ValueError('Invalid file entry')
            with tempfile.TemporaryDirectory(prefix='glassforge-') as directory:
                root = Path(directory)
                seen = set()
                total = 0
                for item in files:
                    name = item['name']
                    if not isinstance(name, str) or name in ('', '.', '..') or '/' in name or '\\' in name or '\0' in name:
                        raise ValueError('Unsafe filename')
                    if name.lower() in seen: raise ValueError('Duplicate filename')
                    seen.add(name.lower())
                    decoded = base64.b64decode(item['data'], validate=True)
                    total += len(decoded)
                    if total > 60 * 1024 * 1024: raise ValueError('Files exceed the 60 MiB upload limit')
                    (root/name).write_bytes(decoded)
                exes = list(root.glob('*.[eE][xX][eE]'))
                if len(exes) != 1: raise ValueError('Select exactly one EXE plus companion files')
                archive = root/'glassforge-analysis.zip'
                if archive.exists(): raise ValueError('Reserved output filename')
                report = handoff(exes[0], archive, code=payload.get('discover') is True, budget=20000)
                body = dict(report=report, archive=base64.b64encode(archive.read_bytes()).decode())
                self.reply(200, json.dumps(body).encode())
        except (ValueError, KeyError, TypeError, OSError, binascii.Error) as e:
            self.reply(400, json.dumps({'error': str(e)}).encode())

def serve(host, port):
    print(f'Glassforge listening on {host}:{port}', flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()

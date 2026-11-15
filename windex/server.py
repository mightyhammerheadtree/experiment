"""Development-only static hosting; no upload or executable-execution endpoint."""
import functools
import mimetypes
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

mimetypes.add_type('application/wasm','.wasm')
mimetypes.add_type('text/javascript','.mjs')

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy','same-origin')
        self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        super().end_headers()

    def send_head(self):
        root=Path(self.directory).resolve()
        requested=unquote(urlsplit(self.path).path)
        if '\\' in requested or '..' in requested.split('/'):
            self.send_error(HTTPStatus.FORBIDDEN);return None
        path=Path(self.translate_path(self.path)).resolve()
        if not path.is_relative_to(root):
            self.send_error(HTTPStatus.FORBIDDEN);return None
        if path.is_dir():
            if not (path/'index.html').is_file():
                self.send_error(HTTPStatus.FORBIDDEN,'Directory listing disabled');return None
            path=path/'index.html'
            if not path.resolve().is_relative_to(root):
                self.send_error(HTTPStatus.FORBIDDEN);return None
        try:
            file=path.open('rb'); size=path.stat().st_size
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND);return None
        start,end=0,size-1
        range_header=self.headers.get('Range')
        if range_header:
            import re
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',range_header)
            if not match:
                file.close();self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE);return None
            start=int(match[1]);end=min(int(match[2]) if match[2] else size-1,size-1)
            if start> end or start>=size:
                file.close();self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return None
        self.send_response(206 if range_header else 200)
        self.send_header('Content-Type',self.guess_type(str(path)))
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(max(0,end-start+1)))
        if range_header:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers();file.seek(start);self.remaining=max(0,end-start+1)
        return file

    def copyfile(self,source,outputfile):
        remaining=self.remaining
        while remaining:
            block=source.read(min(1024*1024,remaining))
            if not block:break
            outputfile.write(block);remaining-=len(block)


def serve(site, host='0.0.0.0', port=8080):
    site=Path(site).resolve()
    if not (site/'index.html').is_file(): raise ValueError('Stage a site first, or use windex/web for the unconfigured shell')
    print(f'Windex serving {site} on {host}:{port}',flush=True)
    ThreadingHTTPServer((host,port),functools.partial(Handler,directory=str(site))).serve_forever()

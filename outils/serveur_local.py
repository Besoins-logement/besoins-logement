#!/usr/bin/env python3
"""Tiny static server with HTTP Range support (single range), HEAD, and a request log.

Usage: python3 range_server.py <root_dir> <port> [--prefix /besoins-logement/] [--log file]
Serves <root_dir> under <prefix> to mimic GitHub Pages project sites (https://<account>.github.io/besoins-logement/).
"""
import argparse, email.utils, json, mimetypes, os, re, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TYPES = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.csv': 'text/csv; charset=utf-8',
    '.gz': 'application/gzip', '.parquet': 'application/octet-stream', '.svg': 'image/svg+xml', '.png': 'image/png',
    '.wasm': 'application/wasm', '.txt': 'text/plain; charset=utf-8', '.geojson': 'application/geo+json',
}
RANGE_RE = re.compile(r'^bytes=(\d*)-(\d*)$')
LOCK = threading.Lock()


def make_handler(root, prefix, logfile):
    root = os.path.realpath(root)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):  # quiet console
            pass

        def _log(self, status, nbytes, rng):
            if not logfile:
                return
            with LOCK, open(logfile, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'t': round(time.time(), 3), 'm': self.command, 'p': self.path, 'range': rng,
                                    'status': status, 'bytes': nbytes}) + '\n')

        def _send_error(self, code, msg):
            body = msg.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)
            self._log(code, len(body), None)

        def _resolve(self):
            path = urllib.parse.urlsplit(self.path).path
            path = urllib.parse.unquote(path)
            if prefix and path == prefix.rstrip('/'):
                return 'REDIRECT'
            if prefix:
                if not path.startswith(prefix):
                    return None
                path = path[len(prefix):]
            else:
                path = path.lstrip('/')
            full = os.path.realpath(os.path.join(root, path))
            if not (full == root or full.startswith(root + os.sep)):
                return None
            if os.path.isdir(full):
                full = os.path.join(full, 'index.html')
            return full if os.path.isfile(full) else None

        def do_HEAD(self):
            self._serve(head=True)

        def do_GET(self):
            self._serve(head=False)

        def _serve(self, head):
            full = self._resolve()
            if full == 'REDIRECT':
                self.send_response(301)
                self.send_header('Location', prefix)
                self.send_header('Content-Length', '0')
                self.end_headers()
                self._log(301, 0, None)
                return
            if not full:
                return self._send_error(404, 'Not found')
            size = os.path.getsize(full)
            ext = os.path.splitext(full)[1].lower()
            ctype = TYPES.get(ext) or mimetypes.guess_type(full)[0] or 'application/octet-stream'
            start, end, status = 0, size - 1, 200
            rng = self.headers.get('Range')
            if rng:
                m = RANGE_RE.match(rng.strip())
                if not m or (m.group(1) == '' and m.group(2) == ''):
                    return self._send_error(416, 'Bad range')
                a, b = m.group(1), m.group(2)
                if a == '':  # suffix range
                    n = int(b)
                    start, end = max(0, size - n), size - 1
                else:
                    start = int(a)
                    end = min(int(b), size - 1) if b else size - 1
                if start >= size or start > end:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    self._log(416, 0, rng)
                    return
                status = 206
            length = end - start + 1
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(length))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Last-Modified', email.utils.formatdate(os.path.getmtime(full), usegmt=True))
            self.send_header('Cache-Control', 'max-age=600')
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            sent = 0
            if not head:
                with open(full, 'rb') as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(1 << 16, remaining))
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            break
                        sent += len(chunk)
                        remaining -= len(chunk)
            self._log(status, sent, rng)

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('port', type=int)
    ap.add_argument('--prefix', default='/besoins-logement/')
    ap.add_argument('--log', default=None)
    a = ap.parse_args()
    prefix = a.prefix if a.prefix.endswith('/') else a.prefix + '/'
    if prefix == '/':
        prefix = ''
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(a.root, prefix, a.log))
    srv.daemon_threads = True
    print(f'Serving {a.root} at http://127.0.0.1:{a.port}{prefix or "/"}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()

from __future__ import annotations

"""Minimal live-reload HTTP server using SSE.

Serves files from a build directory and injects a tiny script into HTML
responses that listens on ``/_sse`` for reload events.  Call
``notify_reload()`` after a build completes to push a reload to every
connected browser tab.
"""

import io
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from queue import Queue, Empty

_RELOAD_JS = b"""<script>
(function(){
  var es = new EventSource('/_sse');
  es.onmessage = function(e){ location.reload(); };
  es.onerror = function(){ setTimeout(function(){ es.close(); }, 5000); };
})();
</script>"""


class _SSEClients:
    """Thread-safe registry of SSE client queues."""

    def __init__(self):
        self._lock = threading.Lock()
        self._clients: list[Queue[str]] = []

    def add(self) -> Queue[str]:
        q: Queue[str] = Queue()
        with self._lock:
            self._clients.append(q)
        return q

    def remove(self, q: Queue[str]) -> None:
        with self._lock:
            try:
                self._clients.remove(q)
            except ValueError:
                pass

    def broadcast(self, data: str = 'reload') -> None:
        with self._lock:
            for q in self._clients:
                q.put(data)


_sse_clients = _SSEClients()


def _inject_reload(data: bytes) -> bytes:
    """Insert the reload snippet before </body>, </html>, or at the end."""
    if b'</body>' in data:
        return data.replace(b'</body>', _RELOAD_JS + b'\n</body>', 1)
    if b'</html>' in data:
        return data.replace(b'</html>', _RELOAD_JS + b'\n</html>', 1)
    return data + b'\n' + _RELOAD_JS


def _make_handler(build_dir: Path):
    """Create a request handler class bound to *build_dir*."""

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(build_dir), **kwargs)

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            super().end_headers()

        def do_GET(self):
            if self.path == '/_sse':
                self._handle_sse()
                return

            path = self.translate_path(self.path)
            if path.endswith(('.html', '.htm')) and Path(path).is_file():
                self._serve_html(Path(path))
            else:
                super().do_GET()

        def _serve_html(self, file_path: Path):
            raw = file_path.read_bytes()
            body = _inject_reload(raw)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle_sse(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            q = _sse_clients.add()
            try:
                while True:
                    try:
                        data = q.get(timeout=30)
                        self.wfile.write(f'data: {data}\n\n'.encode())
                        self.wfile.flush()
                    except Empty:
                        self.wfile.write(b': keepalive\n\n')
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                _sse_clients.remove(q)

        def log_message(self, format, *args):
            pass

    return Handler


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class LiveServer:
    """Serves *build_dir* on localhost with SSE live-reload."""

    def __init__(self, build_dir: Path, port: int = 0):
        self._build_dir = build_dir
        handler = _make_handler(build_dir)
        self._httpd = _ThreadingHTTPServer(('127.0.0.1', port), handler)
        self._httpd.timeout = 0.5
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def url(self) -> str:
        return f'http://127.0.0.1:{self.port}'

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def notify_reload(self) -> None:
        _sse_clients.broadcast('reload')

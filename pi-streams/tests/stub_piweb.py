"""In-process PI WEB stand-in for tests.

Routes are (method, path regex, status code, JSON value), matched in order.
The regex is applied with re.fullmatch to the path only; the query is separate.
Unmatched requests get 200 and {"ok": true}. Each recorded request is
(method, path, raw query, parsed JSON body or None).
"""
from __future__ import annotations

import json
import re
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LIVE_PORT = 8504


class StubPiWeb:
    def __init__(self) -> None:
        self.routes: list[tuple[str, str, int, object]] = []
        self.requests: list[tuple[str, str, str, object]] = []
        self._lock = threading.Lock()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def set_routes(self, routes: list[tuple[str, str, int, object]]) -> None:
        with self._lock:
            self.routes = list(routes)

    def start(self) -> None:
        if self._httpd is not None:
            raise RuntimeError("stub already started")
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                stub._serve(self)

            def do_POST(self) -> None:
                stub._serve(self)

            def do_PUT(self) -> None:
                stub._serve(self)

            def do_PATCH(self) -> None:
                stub._serve(self)

            def do_DELETE(self) -> None:
                stub._serve(self)

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        httpd.daemon_threads = True
        port = int(httpd.server_address[1])
        if port == LIVE_PORT:
            httpd.server_close()
            raise RuntimeError("refusing to bind the live PI WEB port")
        self._httpd = httpd
        self._thread = threading.Thread(
            target=httpd.serve_forever,
            kwargs={"poll_interval": 0.05},
            name="stub-piweb",
            daemon=True,
        )
        self._thread.start()
        try:
            self._wait_until_listening()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        httpd = self._httpd
        thread = self._thread
        self._httpd = None
        self._thread = None
        if httpd is not None and thread is not None and thread.is_alive():
            httpd.shutdown()
        if httpd is not None:
            httpd.server_close()
        if thread is not None:
            thread.join(timeout=5)

    @property
    def url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("stub is not started")
        port = int(self._httpd.server_address[1])
        return f"http://127.0.0.1:{port}"

    def _wait_until_listening(self) -> None:
        assert self._httpd is not None
        port = int(self._httpd.server_address[1])
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.01)
        raise RuntimeError("stub PI WEB server did not accept connections")

    def _serve(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urllib.parse.urlsplit(handler.path)
        length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(length) if length else b""
        body: object
        if not raw:
            body = None
        else:
            text = raw.decode("utf-8", "replace")
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                # Keep the request visible when a client sends a non-JSON body.
                body = text
        with self._lock:
            self.requests.append((handler.command, parsed.path, parsed.query, body))
            routes = list(self.routes)
        status, payload = _match(handler.command, parsed.path, routes)
        encoded = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(encoded)))
        handler.end_headers()
        handler.wfile.write(encoded)
        handler.wfile.flush()


def _match(method: str, path: str, routes: list[tuple[str, str, int, object]]) -> tuple[int, object]:
    for route_method, pattern, status, payload in routes:
        if route_method == method and re.fullmatch(pattern, path):
            return status, payload
    return 200, {"ok": True}

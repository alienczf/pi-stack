"""Owned socket fixture for the public protocol. Never connects to a host daemon."""
import json
import socket
import tempfile
import threading
from pathlib import Path


class StubPrime:
    def __init__(self, handler, *, schema=30, protocol=7, path=None):
        self.tmp = tempfile.TemporaryDirectory(prefix="prime-owned-test-")
        self.path = str(path if path is not None else Path(self.tmp.name) / "owned.sock")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen()
        self.server.settimeout(5)
        self.handler, self.schema, self.protocol = handler, schema, protocol
        self.requests, self.errors = [], []
        self.thread = threading.Thread(target=self.serve)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.thread.join(6)
        self.server.close()
        self.tmp.cleanup()
        if self.thread.is_alive():
            raise AssertionError("owned fixture did not settle")
        if self.errors:
            raise AssertionError(self.errors)

    def send(self, connection, frame):
        connection.sendall((json.dumps(frame, ensure_ascii=False) + "\n").encode())

    def response(self, request, data=None, **fields):
        return {"type": "response", "id": request["id"], "command": request["command"]["type"], "success": True, "data": data, **fields}

    def serve(self):
        try:
            connection, _ = self.server.accept()
            with connection:
                connection.settimeout(5)
                self.send(connection, {"type": "daemon_hello", "protocol": {"name": "prime-agent.daemon", "version": self.protocol}, "schemaRevision": self.schema})
                with connection.makefile("rb") as reader:
                    for line in reader:
                        request = json.loads(line)
                        self.requests.append(request)
                        result = self.handler(self, request)
                        if result is None:
                            continue
                        for frame in result if isinstance(result, list) else [result]:
                            self.send(connection, frame)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except BaseException as exc:
            self.errors.append(repr(exc))

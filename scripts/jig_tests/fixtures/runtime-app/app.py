#!/usr/bin/env python3
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

API_VERSION = "fixture-v1"


def load_notes(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_notes(path, notes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes, sort_keys=True) + "\n", encoding="utf-8")


def handler_for(data_file, data_dir):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status, value):
            raw = json.dumps(value, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed = urlparse(self.path)
            notes = load_notes(data_file)
            if parsed.path == "/health":
                self.send_json(200, {"build": API_VERSION, "dataDir": str(data_dir.resolve()), "pid": os.getpid()})
            elif parsed.path == "/notes":
                self.send_json(200, notes)
            elif parsed.path == "/search":
                query = parse_qs(parsed.query).get("q", [""])[0].lower()
                self.send_json(200, [item for item in notes if query in item["title"].lower() or query in item["body"].lower()])
            else:
                self.send_json(404, {"error": "not-found"})

        def do_POST(self):
            if self.path != "/notes":
                self.send_json(404, {"error": "not-found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            value = json.loads(self.rfile.read(length))
            if set(value) != {"title", "body"} or not value["title"]:
                self.send_json(400, {"error": "invalid-note"})
                return
            notes = load_notes(data_file)
            note = {"id": len(notes) + 1, "title": value["title"], "body": value["body"]}
            notes.append(note)
            save_notes(data_file, notes)
            self.send_json(201, note)

        def log_message(self, _format, *_arguments):
            return

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--endpoint-file", required=True)
    arguments = parser.parse_args()
    data_dir = Path(arguments.data_dir)
    endpoint_file = Path(arguments.endpoint_file)
    server = ThreadingHTTPServer(("127.0.0.1", arguments.port), handler_for(data_dir / "notes.json", data_dir))
    endpoint_file.parent.mkdir(parents=True, exist_ok=True)
    endpoint_file.write_text(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "pid": os.getpid()}) + "\n", encoding="utf-8")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

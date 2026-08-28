#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from app import API_VERSION


def endpoint(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))["url"]


def request_json(url, method="GET", value=None):
    raw = None if value is None else json.dumps(value).encode()
    request = Request(url, data=raw, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=3) as response:
        return json.loads(response.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint-file", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    add = commands.add_parser("add")
    add.add_argument("--title", required=True)
    add.add_argument("--body", required=True)
    commands.add_parser("list")
    search = commands.add_parser("search")
    search.add_argument("query")
    arguments = parser.parse_args()
    base = endpoint(arguments.endpoint_file)
    if arguments.command == "doctor":
        value = request_json(base + "/health")
        if value["build"] != API_VERSION:
            raise SystemExit("wrong build")
    elif arguments.command == "add":
        value = request_json(base + "/notes", "POST", {"title": arguments.title, "body": arguments.body})
    elif arguments.command == "list":
        value = request_json(base + "/notes")
    else:
        value = request_json(base + "/search?q=" + quote(arguments.query))
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()

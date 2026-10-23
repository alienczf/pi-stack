"""Throwaway intake observer. Native admission is not transactional with this journal."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import uuid


@dataclass(frozen=True)
class Intake:
    session: str
    source_kind: str
    source_id: str
    lane: str
    body: str

    def __post_init__(self):
        if not all(isinstance(v, str) and v for v in (
                self.session, self.source_kind, self.source_id, self.body)):
            raise ValueError("nonempty source identity, session and body required")
        if self.source_kind not in {"user", "automation"}:
            raise ValueError("unknown source kind")
        if self.lane not in {"prompt", "prompt_and_wait", "steer", "follow_up"}:
            raise ValueError("unknown lane")


class Journal:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS intake (
            session TEXT NOT NULL, source_kind TEXT NOT NULL, source_id TEXT NOT NULL,
            lane TEXT NOT NULL, body TEXT NOT NULL, sha256 TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('dispatch_uncertain', 'admitted', 'rejected')),
            reply TEXT, PRIMARY KEY(session, source_kind, source_id))""")
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.db.close()

    def lookup(self, ask: Intake):
        row = self.db.execute("SELECT * FROM intake WHERE session=? AND source_kind=? AND source_id=?",
                              (ask.session, ask.source_kind, ask.source_id)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["reply"] = json.loads(result["reply"]) if result["reply"] else None
        return result


def dispatch(journal: Journal, ask: Intake, send):
    with journal.db:
        inserted = journal.db.execute("""INSERT OR IGNORE INTO intake
            VALUES (?, ?, ?, ?, ?, ?, 'dispatch_uncertain', NULL)""",
            (ask.session, ask.source_kind, ask.source_id, ask.lane, ask.body,
             hashlib.sha256(ask.body.encode()).hexdigest())).rowcount == 1
        row = journal.lookup(ask)
        if (row["body"], row["lane"]) != (ask.body, ask.lane):
            raise ValueError("source identity conflict")
    if not inserted:
        return row
    reply = send(ask.lane, activeSessionId=ask.session, message=ask.body)
    if not isinstance(reply, dict) or type(reply.get("success")) is not bool:
        raise ValueError("reply success must be boolean")
    state = "admitted" if reply["success"] else "rejected"
    with journal.db:
        journal.db.execute("UPDATE intake SET state=?, reply=? WHERE session=? AND source_kind=? AND source_id=?",
                           (state, json.dumps(reply), ask.session, ask.source_kind, ask.source_id))
    return journal.lookup(ask)


class Wire:
    def __init__(self, path: str, *, timeout: float):
        self.path = path
        self.timeout = timeout
        self.events = []
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(timeout)
        self.reader = None

    def __enter__(self):
        try:
            self.sock.connect(self.path)
            self.reader = self.sock.makefile("rb")
            self.hello = self.read()
            if (self.hello.get("type") != "daemon_hello"
                    or self.hello.get("protocol") != {"name": "prime-agent.daemon", "version": 7}
                    or self.hello.get("schemaRevision") != 30):
                raise ValueError("expected protocol 7 schema 30")
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *_):
        if self.reader is not None:
            self.reader.close()
        self.sock.close()

    def read(self):
        line = self.reader.readline()
        if not line:
            raise ConnectionError("Prime disconnected; dispatch outcome is uncertain")
        frame = json.loads(line)
        if not isinstance(frame, dict):
            raise ValueError("expected object frame")
        return frame

    def request(self, kind, **fields):
        identity = str(uuid.uuid4())
        frame = {"type": "command", "id": identity,
                 "protocol": {"name": "prime-agent.daemon", "version": 7},
                 "command": {"type": kind, **fields}}
        self.sock.sendall((json.dumps(frame) + "\n").encode())
        while True:
            reply = self.read()
            if reply.get("type") != "response":
                self.events.append(reply)
                continue
            if reply.get("id") != identity:
                continue
            if reply.get("command") != kind or type(reply.get("success")) is not bool:
                raise ValueError("invalid correlated response")
            return reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--source-kind", choices=["user", "automation"], required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--lane", choices=["prompt", "steer", "follow_up"], required=True)
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    ask = Intake(args.session, args.source_kind, args.source_id, args.lane, args.message)
    with Journal(args.journal) as journal, Wire(args.socket, timeout=args.timeout) as wire:
        print(json.dumps(dispatch(journal, ask, wire.request)))


if __name__ == "__main__":
    main()

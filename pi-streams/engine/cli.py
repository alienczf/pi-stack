from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine import StreamsError
from engine.doctor import run_doctor
from engine.project import commit_home, create_stream, home_lock, init_project, load_project, resolve_home
from engine.threads import (
    adopt_thread,
    close_stream,
    ensure_coordinator,
    format_status,
    rotate_coordinator,
    spawn_thread,
    status_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pi-streams")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("project_root")
    init.add_argument("--home")
    init.add_argument("-y", action="store_true")
    init.add_argument("--pi-web-url")
    init.add_argument("--remote")
    init.add_argument("--coordinator-model")
    init.add_argument("--coordinator-thinking")

    new = sub.add_parser("new")
    new.add_argument("stream_id", metavar="id")
    new.add_argument("--home")

    status = sub.add_parser("status")
    status.add_argument("stream_id", metavar="id", nargs="?")
    status.add_argument("--json", action="store_true")
    status.add_argument("--home")

    sub.add_parser("doctor")

    thread = sub.add_parser("thread")
    thread_sub = thread.add_subparsers(dest="thread_cmd", required=True)
    spawn = thread_sub.add_parser("spawn")
    spawn.add_argument("stream")
    spawn.add_argument("--repo", required=True)
    spawn.add_argument("--role", required=True)
    spawn.add_argument("--base")
    spawn.add_argument("--branch")
    spawn.add_argument("--model")
    spawn.add_argument("--thinking")
    spawn.add_argument("--note", default="")
    spawn.add_argument("--home")
    adopt = thread_sub.add_parser("adopt")
    adopt.add_argument("stream")
    adopt.add_argument("session_id")
    adopt.add_argument("--worktree", required=True)
    adopt.add_argument("--role", required=True)
    adopt.add_argument("--home")

    rotate = sub.add_parser("rotate")
    rotate.add_argument("stream")
    rotate.add_argument("--home")

    close = sub.add_parser("close")
    close.add_argument("stream")
    close.add_argument("--home")
    return parser


def cmd_init(args: argparse.Namespace) -> int:
    home = init_project(
        Path(args.project_root),
        home=Path(args.home) if args.home else None,
        assume_yes=args.y,
        pi_web_url=args.pi_web_url,
        remote=args.remote,
        coordinator_model=args.coordinator_model,
        coordinator_thinking=args.coordinator_thinking,
    )
    print(home)
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    with home_lock(home):
        project = load_project(home)
        stream_dir = create_stream(home, args.stream_id)
        sid = ensure_coordinator(project, stream_dir)
        commit_home(home, f"pi-streams new {args.stream_id}")
    print(project.info.pi_web_url)
    print(sid)
    return 0


def cmd_thread_spawn(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    with home_lock(home):
        project = load_project(home)
        sid = spawn_thread(
            project,
            args.stream,
            args.repo,
            args.role,
            base=args.base,
            branch=args.branch,
            model=args.model,
            thinking=args.thinking,
            note=args.note,
        )
        commit_home(home, f"pi-streams thread spawn {args.stream} {args.role}")
    print(sid)
    return 0


def cmd_thread_adopt(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    with home_lock(home):
        project = load_project(home)
        sid = adopt_thread(project, args.stream, args.session_id, Path(args.worktree), args.role)
        commit_home(home, f"pi-streams thread adopt {args.stream} {args.session_id}")
    print(sid)
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    with home_lock(home):
        project = load_project(home)
        sid = rotate_coordinator(project, args.stream)
        commit_home(home, f"pi-streams rotate {args.stream}")
    print(project.info.pi_web_url)
    print(sid)
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    with home_lock(home):
        project = load_project(home)
        report = close_stream(project, args.stream)
        commit_home(home, f"pi-streams close {args.stream}")
    sys.stdout.write("".join(f"{line}\n" for line in report))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    project = load_project(home)
    report = status_report(project, args.stream_id)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        sys.stdout.write(format_status(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.cmd == "init":
            return cmd_init(args)
        if args.cmd == "new":
            return cmd_new(args)
        if args.cmd == "status":
            return cmd_status(args)
        if args.cmd == "doctor":
            return run_doctor()
        if args.cmd == "rotate":
            return cmd_rotate(args)
        if args.cmd == "close":
            return cmd_close(args)
        if args.cmd == "thread" and args.thread_cmd == "spawn":
            return cmd_thread_spawn(args)
        if args.cmd == "thread" and args.thread_cmd == "adopt":
            return cmd_thread_adopt(args)
    except StreamsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"unknown command {args.cmd}", file=sys.stderr)
    return 2

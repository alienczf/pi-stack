from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine import StreamsError, artifacts, clock, dcr, delivery, drive, failure, failure_recovery, migration, replacement
from engine.doctor import run_doctor
from engine.project import (
    STATE_SCHEMA,
    commit_repo,
    create_stream,
    ensure_git,
    index_lock,
    init_project,
    load_projects,
    load_stream_config,
    read_homes,
    require_stream,
    resolve_index,
    resolve_project,
    stream_lock,
    stream_locks,
    stream_rows,
    upgrade_stream,
)
from engine.threads import (
    adopt_thread,
    close_stream,
    ensure_coordinator,
    format_status,
    rotate_coordinator,
    resolve_coordinator,
    spawn_thread,
    status_report,
)
from engine.tick import run_tick


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pi-streams")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("project_root")
    init.add_argument("--home")
    init.add_argument("-y", action="store_true")
    init.add_argument("--pi-web-url")
    init.add_argument("--coordinator-model")
    init.add_argument("--coordinator-thinking")

    new = sub.add_parser("new")
    new.add_argument("stream_id", metavar="id")
    new.add_argument("--home")
    new.add_argument("--coordinator-session", help="explicitly adopt this exact owned native session; never chosen by directory")

    status = sub.add_parser("status")
    status.add_argument("stream_id", metavar="id", nargs="?")
    status.add_argument("--json", action="store_true")
    status.add_argument("--home")

    receipts = sub.add_parser("delivery")
    receipt_sub = receipts.add_subparsers(dest="delivery_cmd", required=True)
    for name in ("list", "send", "ack"):
        operation = receipt_sub.add_parser(name)
        operation.add_argument("stream")
        operation.add_argument("--home")
        if name == "send":
            operation.add_argument("--delivery-id", required=True)
            operation.add_argument("--session", required=True)
            operation.add_argument("--body-file", required=True)
            operation.add_argument("--behavior", choices=("steer", "follow-up"))
        if name == "ack":
            operation.add_argument("delivery_id")
            operation.add_argument("--session", required=True)
            operation.add_argument("--state", required=True, choices=("consumed", "applied", "blocked"))
            operation.add_argument("--detail", required=True)
            operation.add_argument("--evidence")

    failures = sub.add_parser("failure")
    failure_sub = failures.add_subparsers(dest="failure_cmd", required=True)
    ratify = failure_sub.add_parser("ratify")
    ratify.add_argument("stream")
    ratify.add_argument("--home")
    ratify.add_argument("--session", required=True)
    ratify.add_argument("--episode", required=True)
    ratify.add_argument("--notice-id", required=True)
    ratify.add_argument("--notice-file", required=True)
    advance = failure_sub.add_parser("advance")
    advance.add_argument("stream")
    advance.add_argument("--home")
    advance.add_argument("--session", required=True)
    advance.add_argument("--episode", required=True)

    maintenance = sub.add_parser("dcr")
    maintenance_sub = maintenance.add_subparsers(dest="dcr_cmd", required=True)
    for name in ("ready", "advance"):
        operation = maintenance_sub.add_parser(name)
        operation.add_argument("stream")
        operation.add_argument("--home")
        operation.add_argument("--session", required=True)
        operation.add_argument("--operation", required=True)

    driving = sub.add_parser("drive")
    driving.add_argument("stream")
    driving.add_argument("mode", nargs="?", default="status", choices=("on", "off", "status"))
    driving.add_argument("--home")

    sub.add_parser("doctor")

    migrate = sub.add_parser("migrate")
    migrate.add_argument("stream")
    migrate.add_argument("--home")
    migration_mode = migrate.add_mutually_exclusive_group(required=True)
    migration_mode.add_argument("--plan", action="store_true", help="show a source-backed migration plan without changing artifacts")
    migration_mode.add_argument("--apply", metavar="PLAN_FILE", help="apply the exact reviewed source-backed plan")
    migration_mode.add_argument("--resume", action="store_true", help="resume only the already recorded migration")
    migrate.add_argument("--mapping", help="explicit JSON byte-span authority/history map")

    upgrade = sub.add_parser("upgrade")
    upgrade.add_argument("stream_id", metavar="id", nargs="?")
    upgrade.add_argument("--home")

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

    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("stream")
    checkpoint.add_argument("--home")
    checkpoint.add_argument("--session", required=True)

    rotate = sub.add_parser("rotate")
    rotate.add_argument("stream")
    rotate.add_argument("--home")

    close = sub.add_parser("close")
    close.add_argument("stream")
    close.add_argument("--home")

    tick = sub.add_parser("tick")
    tick.add_argument("--home")

    state = sub.add_parser("state")
    state_sub = state.add_subparsers(dest="state_cmd", required=True)
    for name in ("append", "ruling", "objective"):
        operation = state_sub.add_parser(name)
        operation.add_argument("stream")
        operation.add_argument("--home")
        operation.add_argument("--body-file", required=True, help="UTF-8 input file, or - for stdin")
        if name != "objective":
            operation.add_argument("--subject", required=True)
            operation.add_argument("--at", help="arrival time with ISO timezone; defaults to now")
        if name == "append":
            operation.add_argument("--request-id", required=True)
        if name == "ruling":
            operation.add_argument("--notice-id", required=True, help="human ruling provenance, not an authentication receipt")
            operation.add_argument("--supersedes-file", help="exact retired Rules text; no automatic classification")
    for name in ("check", "read-entry", "update", "close"):
        command = state_sub.add_parser(name)
        command.add_argument("stream")
        if name == "read-entry":
            command.add_argument("entry")
        if name in {"update", "close"}:
            command.add_argument("--expect", required=True)
    poc = sub.add_parser("poc")
    commands = poc.add_subparsers(dest="poc_cmd", required=True)
    for name in ("init", "doctor", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--stream", required=True)
    return parser


def cmd_init(args: argparse.Namespace) -> int:
    index = init_project(
        Path(args.project_root),
        home=Path(args.home) if args.home else None,
        assume_yes=args.y,
        pi_web_url=args.pi_web_url,
        coordinator_model=args.coordinator_model,
        coordinator_thinking=args.coordinator_thinking,
    )
    print(index)
    return 0


def _open_stream(index: Path, project_name: str, stream_id: str) -> Path:
    stream_dir = require_stream(index, project_name, stream_id)
    ensure_git(stream_dir)
    return stream_dir


def cmd_migrate(args: argparse.Namespace) -> int:
    if args.mapping and not args.plan:
        raise StreamsError("--mapping is only for --plan; application requires the exact reviewed plan file")
    mapping = json.loads(migration.regular_bytes(Path(args.mapping))) if args.mapping else None
    document = json.loads(migration.regular_bytes(Path(args.apply))) if args.apply else None
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream = require_stream(index, project.info.name, args.stream, allow_migration=True)
        with stream_lock(stream):
            result = migration.plan_migration(stream, mapping).public() if args.plan else migration.apply_migration_locked(stream, document)
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = create_stream(index, project, args.stream_id)
        with stream_lock(stream_dir):
            sid = ensure_coordinator(project, stream_dir, coordinator_session=args.coordinator_session)
            commit_repo(stream_dir, f"pi-streams new {args.stream_id}")
    print(project.info.pi_web_url)
    print(sid)
    return 0


def cmd_thread_spawn(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = _open_stream(index, project.info.name, args.stream)
        with stream_lock(stream_dir):
            sid = spawn_thread(
                index,
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
            commit_repo(stream_dir, f"pi-streams thread spawn {args.stream} {args.role}")
    print(sid)
    return 0


def cmd_thread_adopt(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = _open_stream(index, project.info.name, args.stream)
        with stream_lock(stream_dir):
            sid = adopt_thread(index, project, args.stream, args.session_id, Path(args.worktree), args.role)
            commit_repo(stream_dir, f"pi-streams thread adopt {args.stream} {args.session_id}")
    print(sid)
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = _open_stream(index, project.info.name, args.stream)
        with stream_lock(stream_dir):
            sid = rotate_coordinator(index, project, args.stream)
            commit_repo(stream_dir, f"pi-streams rotate {args.stream}")
    print(project.info.pi_web_url)
    print(sid)
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = _open_stream(index, project.info.name, args.stream)
        with stream_lock(stream_dir):
            result = close_stream(index, project, args.stream)
            commit_repo(stream_dir, f"pi-streams close {args.stream}", paths=result.handovers)
    sys.stdout.write("".join(f"{line}\n" for line in result.report))
    return 0


def _state_body(path: str) -> str:
    try:
        data = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
        return data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise StreamsError(f"could not read artifact input: {exc}") from exc


def cmd_state(args: argparse.Namespace) -> int:
    body = _state_body(args.body_file)
    retired = _state_body(args.supersedes_file) if getattr(args, "supersedes_file", None) else None
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = require_stream(index, project.info.name, args.stream)
        if load_stream_config(stream_dir / "stream.toml").state_schema != STATE_SCHEMA:
            raise StreamsError("canonical STATE schema required; explicit migration is needed")
        try:
            if args.state_cmd == "objective":
                result = {"changed": artifacts.update_current_objective(stream_dir, body)}
            else:
                at = args.at or clock.stamp(clock.now())
                if args.state_cmd == "append":
                    occurrence = artifacts.append_log(stream_dir, at, args.subject, body, request_id=args.request_id)
                    request = args.request_id
                else:
                    occurrence = artifacts.record_ruling(stream_dir, at, args.subject, body,
                                                         notice_id=args.notice_id, supersedes=retired)
                    request = "ruling:" + args.notice_id
                result = {"occurrence": occurrence, "request_id": request}
        except OSError as exc:
            raise StreamsError(f"artifact publication failed; reconcile the same request ID: {exc}") from exc
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_delivery(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = require_stream(index, project.info.name, args.stream)
        with stream_lock(stream_dir):
            if args.delivery_cmd == "list":
                result = delivery.receipts(stream_dir)
            elif args.delivery_cmd == "send":
                delivery.prepare_locked(stream_dir, args.delivery_id, args.session, _state_body(args.body_file), behavior=args.behavior)
                result = delivery.send_locked(stream_dir, args.delivery_id)
            else:
                result = delivery.acknowledge_locked(stream_dir, args.delivery_id, args.session, args.state, args.detail, evidence=args.evidence)
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_drive(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = require_stream(index, project.info.name, args.stream)
        with stream_lock(stream_dir):
            if args.mode == "status":
                result = drive.public(stream_dir)
            elif args.mode == "off":
                drive.pause_local(stream_dir)
                try:
                    resolved = resolve_coordinator(stream_dir)
                    if resolved is None:
                        raise StreamsError("no designated exact native coordinator; refusing to guess a stop target")
                    result = drive.confirm_pause(stream_dir, resolved)
                except (StreamsError, OSError) as exc:
                    raise StreamsError(f"Local drive-off intent is saved; native stop/durability confirmation is unconfirmed: {exc}") from exc
            else:
                resolved = resolve_coordinator(stream_dir)
                if resolved is None:
                    raise StreamsError("drive control requires the designated exact native coordinator")
                from engine import piweb
                piweb.require_settings(resolved.native.status, project.coordinator.model, project.coordinator.thinking)
                result = drive.enable(stream_dir, resolved)
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_failure(args: argparse.Namespace) -> int:
    notice = None
    if args.failure_cmd == "ratify":
        try:
            notice = json.loads(_state_body(args.notice_file))
        except ValueError as exc:
            raise StreamsError("Authenticated notice input must be JSON, not a fixed/readiness string") from exc
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = require_stream(index, project.info.name, args.stream)
    with stream_lock(stream_dir):
        if args.failure_cmd == "ratify":
            result = failure.ratify_locked(stream_dir, args.session, args.episode, args.notice_id, notice, clock.stamp(clock.now()))
        else:
            result = failure_recovery.advance_locked(stream_dir, args.session, args.episode, clock.stamp(clock.now()), index=index, project=project)
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_dcr(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = require_stream(index, project.info.name, args.stream)
        with stream_lock(stream_dir):
            op = dcr.load(stream_dir, args.session)
            if op is None or op.id != args.operation:
                raise StreamsError("DCR callback does not match the registered stream/SID/operation")
            recovery = failure_recovery.load(stream_dir, op.recovery_original) if op.recovery_original else None
            if recovery is not None:
                if recovery.id != op.id or recovery.fork != args.session or recovery.cwd != op.cwd or recovery.phase != "dcr":
                    raise StreamsError("DCR callback does not own this held recovery fork")
                resolved = failure_recovery.resolve_fork(stream_dir, recovery)
            else:
                if op.recovery_original or Path(op.cwd).resolve() != stream_dir.resolve():
                    raise StreamsError("DCR callback has no exact recovery owner")
                resolved = resolve_coordinator(stream_dir)
                if resolved is None or resolved.row.session != args.session:
                    raise StreamsError("DCR callback does not own the designated native coordinator")
            if args.dcr_cmd == "ready":
                result = dcr.ready(stream_dir, index, args.stream, resolved, args.operation)
            else:
                if recovery is not None:
                    failure_recovery.advance_locked(stream_dir, recovery.session, recovery.episode, clock.stamp(clock.now()), index=index, project=project)
                else:
                    dcr.step(index, project, args.stream, stream_dir, resolved)
                current = dcr.load(stream_dir, args.session)
                result = {"id": args.operation, "phase": current.phase, "detail": current.detail}
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        project = resolve_project(index)
        stream_dir = _open_stream(index, project.info.name, args.stream)
        with stream_lock(stream_dir):
            result = replacement.prepare_checkpoint_locked(stream_dir, args.session)
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    indexes = [resolve_index(args.home)] if args.home else read_homes()
    return run_tick(indexes)


def cmd_status(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    report = status_report(index, args.stream_id)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        sys.stdout.write(format_status(report))
    return 0


def cmd_upgrade(args: argparse.Namespace) -> int:
    index = resolve_index(args.home)
    with index_lock(index):
        rows = stream_rows(index, args.stream_id)
        projects = {project.info.name: project for project in load_projects(index)}
        repos = [Path(row.path) for row in rows]
        for repo in repos:
            ensure_git(repo)
        ordered = sorted(rows, key=lambda row: str(Path(row.path).resolve()))
        with stream_locks(repos):
            for row in ordered:
                if row.project not in projects:
                    raise StreamsError(f"stream {row.id} names missing project {row.project}")
                upgrade_stream(Path(row.path), row.id)
    return 0


def cmd_prime_state(args):
    from engine import state
    stream = Path(args.stream).absolute()
    try:
        if args.state_cmd == "read-entry":
            sys.stdout.write(state.read_entry(stream, args.entry))
            return 0
        if args.state_cmd == "check":
            current = state.check_state(stream)
            result = {"success": True, "reason": "checked", "state_sha256": current.sha256, "history_files": []}
        else:
            payload = json.loads(sys.stdin.read())
            if args.state_cmd == "close":
                if not hasattr(state, "close_work"):
                    raise StreamsError("computed close is not wired")
                result = state.close_work(stream, expect=args.expect, **payload)
            else:
                result = state.update_state(stream, expect=args.expect, **payload)
    except (StreamsError, OSError, ValueError, TypeError, KeyError) as exc:
        result = {"success": False, "reason": str(exc), "state_sha256": None, "history_files": []}
    result = {key: result[key] for key in ("success", "reason", "state_sha256", "history_files")}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["success"] else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.cmd in {"new", "status", "thread", "rotate", "close"}:
            selected = resolve_index(args.home)
            if any(project.info.backend != "pi" for project in load_projects(selected)):
                raise StreamsError("legacy Pi command is not wired for a Prime project; use the explicit poc/state commands")
        if args.cmd == "state":
            return cmd_prime_state(args) if args.state_cmd in {"check", "read-entry", "update", "close"} else cmd_state(args)
        if args.cmd == "poc":
            import importlib.util
            if importlib.util.find_spec("engine.poc") is None:
                raise StreamsError("merged PoC commands are not wired yet")
            from engine import poc
            result = getattr(poc, args.poc_cmd)(Path(args.root), args.stream)
            print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
            return 0 if result.get("status") == "PASS" else 1
        if args.cmd == "init":
            return cmd_init(args)
        if args.cmd == "new":
            return cmd_new(args)
        if args.cmd == "status":
            return cmd_status(args)
        if args.cmd == "doctor":
            return run_doctor()
        if args.cmd == "upgrade":
            return cmd_upgrade(args)
        if args.cmd == "migrate":
            return cmd_migrate(args)
        if args.cmd == "checkpoint":
            return cmd_checkpoint(args)
        if args.cmd == "rotate":
            return cmd_rotate(args)
        if args.cmd == "close":
            return cmd_close(args)
        if args.cmd == "tick":
            return cmd_tick(args)
        if args.cmd == "failure":
            return cmd_failure(args)
        if args.cmd == "dcr":
            return cmd_dcr(args)
        if args.cmd == "drive":
            return cmd_drive(args)
        if args.cmd == "delivery":
            return cmd_delivery(args)
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

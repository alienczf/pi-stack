"""Confined installation of pinned unchanged stock Prime and the selected checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import StreamsError, repo_root
from engine.project import Project, ProjectSection, ModelSettings, Caps, dump_project, git, DEFAULT_MODEL, DEFAULT_WORKER_MODEL, DEFAULT_THINKING
from engine.prime import LEVELS
from engine.prime_compat import split_model

PRIME_REVISION = "8aac8692456c00c01d4e53e60e6d3347a3506559"
PRIME_URL = "https://github.com/PrimeIntellect-ai/prime-agent.git"
PSTACK_URL = "https://github.com/cursor/plugins.git"
RUNTIME_FILES = ("pyproject.toml", "src/rlm/__init__.py", "src/rlm/repl.py")


def confined(root, path):
    root, path = Path(root), Path(path)
    if ".." in root.parts or ".." in path.parts:
        raise StreamsError("installation path traversal is not allowed")
    if not root.is_absolute() or not path.is_absolute() or not path.is_relative_to(root):
        raise StreamsError("installation path escapes prefix")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise StreamsError("installation path contains a symlink")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(root):
    if root.is_symlink() or not root.is_dir() or any(not (root / name).is_file() for name in RUNTIME_FILES):
        raise StreamsError("Prime runtime sidecar is incomplete")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise StreamsError("runtime sidecar symlink")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = digest(path)
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def install_bytes(root, path, content, mode=0o644, *, replace_from=None, plan=None):
    path = confined(root, path)
    if plan is not None:
        if path.exists() and (not path.is_file() or path.stat().st_mode & 0o777 != mode
                or path.read_bytes() not in (content, replace_from)):
            raise StreamsError(f"conflicting owned file: {path}")
        plan[path] = (content, mode, replace_from)
        return
    if path.exists():
        if not path.is_file() or path.stat().st_mode & 0o777 != mode:
            raise StreamsError(f"conflicting owned file: {path}")
        current = path.read_bytes()
        if current == content:
            return
        if replace_from is None or current != replace_from:
            raise StreamsError(f"conflicting owned file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".install-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
        if replace_from is None:
            os.link(temporary, path)
        else:
            if path.read_bytes() != replace_from:
                raise StreamsError(f"owned file changed during update: {path}")
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if path.read_bytes() != content:
            raise StreamsError("install readback differs")
    finally:
        Path(temporary).unlink(missing_ok=True)


def clean_env(root):
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "RUSTUP_HOME") if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="/bin/false",
               CARGO_HOME=str(root / "build/cargo"), CARGO_TARGET_DIR=str(root / "build/prime"),
               UV_CACHE_DIR=str(root / "cache/uv"), UV_PYTHON_INSTALL_DIR=str(root / "cache/python"))
    return env


def run(argv, *, cwd=None, env=None):
    result = subprocess.run([str(v) for v in argv], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise StreamsError(f"command failed ({result.returncode}): {argv[0]}\n" + result.stderr.decode(errors="replace"))
    return result.stdout.decode("utf-8")


def preflight(root, project, model, thinking, percent):
    if sys.platform != "linux" or sys.version_info < (3, 11):
        raise StreamsError("merged PoC requires Linux and Python 3.11 or newer")
    root, project = Path(root), Path(project)
    confined(root, root)
    confined(root, project)
    if project != root / "project":
        raise StreamsError("project must be exactly <prefix>/project")
    split_model(model)
    if thinking not in LEVELS:
        raise StreamsError("explicit supported thinking level required")
    if isinstance(percent, bool) or not math.isfinite(percent) or not 0 < percent <= 100:
        raise StreamsError("explicit compaction percentage must be finite and in (0,100]")
    missing = [name for name in ("git", "cargo", "rustc", "cc", "uv") if shutil.which(name) is None]
    if missing:
        raise StreamsError("missing prerequisites: " + ", ".join(missing) + "; install them explicitly without sudo or global changes")
    if git(repo_root(), "branch", "--show-current").strip() != "feat/merged-poc":
        raise StreamsError("installer requires the explicitly selected feat/merged-poc checkout")
    return root


def install_prime(root):
    source = confined(root, root / "src/prime-agent")
    env = clean_env(root)
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "-c", "credential.helper=", "clone", "--no-checkout", PRIME_URL, source], env=env)
        run(["git", "-C", source, "checkout", "--detach", PRIME_REVISION], env=env)
    if run(["git", "-C", source, "rev-parse", "HEAD"], env=env).strip() != PRIME_REVISION:
        raise StreamsError("Prime source revision differs from pinned stock")
    if run(["git", "-C", source, "remote", "get-url", "origin"], env=env).strip() != PRIME_URL:
        raise StreamsError("Prime source origin is not the pinned upstream")
    if run(["git", "-C", source, "status", "--porcelain"], env=env).strip():
        raise StreamsError("Prime source has changes; no patches or repairs are allowed")
    runtime = source / "prime-agent-runtime"
    expected_runtime = tree_hash(runtime)
    binary = root / "libexec/prime-agent"
    installed_runtime = root / "libexec/prime-agent-runtime"
    if binary.exists():
        if not installed_runtime.exists() or tree_hash(installed_runtime) != expected_runtime:
            raise StreamsError("installed binary has a missing or mismatched runtime sidecar")
        receipt = confined(root, root / "reports/install.json")
        if not receipt.is_file():
            raise StreamsError("refusing an unrecorded existing Prime binary")
        previous = json.loads(receipt.read_text())
        if (previous.get("prime_source_revision") != PRIME_REVISION or previous.get("prime_binary_sha256") != digest(binary)
                or previous.get("prime_runtime_sha256") != expected_runtime):
            raise StreamsError("installed binary or runtime conflicts with its retained receipt")
    else:
        run(["cargo", "build", "--locked", "--release", "-p", "pa-cli", "--bin", "prime-agent"], cwd=source, env=env)
        built = root / "build/prime/release/prime-agent"
        install_bytes(root, binary, built.read_bytes(), 0o755)
        for path in sorted(runtime.rglob("*")):
            if path.is_file():
                install_bytes(root, installed_runtime / path.relative_to(runtime), path.read_bytes())
    if tree_hash(installed_runtime) != expected_runtime:
        raise StreamsError("installed runtime bytes differ from pinned source")
    version = run([binary, "--version"], env=env).strip()
    if version != "0.10.1":
        raise StreamsError(f"unexpected Prime version: {version}")
    return {"prime_source_revision": PRIME_REVISION, "prime_binary_sha256": digest(binary),
            "prime_runtime_sha256": expected_runtime, "prime_version": version}


def install_poteto(root):
    plugins = confined(root, root / "src/plugins")
    env = clean_env(root)
    if not plugins.exists():
        plugins.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "-c", "credential.helper=", "clone", "--depth", "1", "--filter=blob:none", "--sparse", PSTACK_URL, plugins], env=env)
        run(["git", "-C", plugins, "sparse-checkout", "set", "pstack"], env=env)
    if run(["git", "-C", plugins, "remote", "get-url", "origin"], env=env).strip() != PSTACK_URL:
        raise StreamsError("pstack origin conflicts")
    if run(["git", "-C", plugins, "status", "--porcelain"], env=env).strip():
        raise StreamsError("pstack source has changes")
    poteto = plugins / "pstack/skills/poteto-mode/SKILL.md"
    if not poteto.is_file():
        raise StreamsError("pstack process entry is missing")
    return run(["git", "-C", plugins, "rev-parse", "HEAD"], env=env).strip(), poteto


def write_wrappers(root, checkout):
    import shlex
    q = lambda path: shlex.quote(str(path))
    exports = {"PRIME_AGENT_CODING_AGENT_DIR": root / "prime/agent", "PRIME_AGENT_SESSION_DIR": root / "prime/agent/sessions",
               "PRIME_AGENT_DAEMON_SOCKET": root / "prime/daemon.sock", "PI_PACKAGE_DIR": root / "libexec",
               "PRIME_AGENT_KERNEL_VENV": root / "prime/kernel-venv", "UV_CACHE_DIR": root / "cache/uv",
               "UV_PYTHON_INSTALL_DIR": root / "cache/python", "XDG_CACHE_HOME": root / "xdg/cache",
               "XDG_CONFIG_HOME": root / "xdg/config", "XDG_DATA_HOME": root / "xdg/data"}
    assignments = "PYTHONDONTWRITEBYTECODE=1 DO_NOT_TRACK=1 " + " ".join(f"{key}={q(value)}" for key, value in exports.items())
    prime = '#!/bin/sh\nexec env -i HOME="$HOME" PATH="$PATH" LANG="${LANG-C.UTF-8}" ' + assignments + " " + q(root / "libexec/prime-agent") + ' "$@"\n'
    streams = '#!/bin/sh\nexport PYTHONDONTWRITEBYTECODE=1\nexport XDG_CONFIG_HOME=' + q(root / "xdg/config") + '\nexport PATH=' + q(root / "bin") + ':"$PATH"\nexec ' + q(checkout / "bin/pi-streams") + ' "$@"\n'
    install_bytes(root, root / "bin/prime-agent", prime.encode(), 0o755)
    install_bytes(root, root / "bin/pi-streams", streams.encode(), 0o755)
    return {"prime": str(root / "bin/prime-agent"), "streams": str(root / "bin/pi-streams")}


def model_metadata(model, thinking, *, revision=None):
    relative = "scripts/prime-models/" + model.replace("/", "-") + ".json"
    path = repo_root() / relative
    if revision is None and not path.is_file():
        return {}
    definition = json.loads(git(repo_root(), "show", f"{revision}:{relative}") if revision else path.read_text())
    levels = definition.get("thinkingLevelMap", {})
    supported = thinking in levels and (thinking == "off" or definition.get("reasoning") is True and levels[thinking] is not None)
    if definition.get("provider") + "/" + definition.get("id") != model or not supported:
        raise StreamsError("model metadata does not support the requested thinking level")
    return {definition["provider"]: {"models": [{key: value for key, value in definition.items() if key != "provider"}]}}


def merge_owned(current, expected, desired):
    if isinstance(expected, dict) and isinstance(desired, dict):
        if not isinstance(current, dict):
            raise StreamsError("conflicting owned configuration")
        result = dict(current)
        for key, value in desired.items():
            if key not in expected:
                if key in current and current[key] != value:
                    raise StreamsError("conflicting new owned configuration field: " + key)
                result[key] = value
            else:
                if key not in current:
                    raise StreamsError("missing prior owned configuration field: " + key)
                result[key] = merge_owned(current[key], expected[key], value)
        return result
    if isinstance(expected, list) and expected and all(isinstance(v, dict) and "id" in v for v in expected):
        if not isinstance(current, list) or len({v.get("id") for v in current}) != len(current):
            raise StreamsError("conflicting model definitions")
        old = {v["id"]: v for v in expected}
        new = {v["id"]: v for v in desired}
        result = []
        for item in current:
            ident = item.get("id")
            result.append(merge_owned(item, old[ident], new.get(ident, old[ident])) if ident in old else item)
        if not set(old) <= {v.get("id") for v in current}:
            raise StreamsError("missing prior owned model definition")
        for ident, item in new.items():
            if ident not in old:
                existing = [v for v in current if v.get("id") == ident]
                if existing and existing != [item]:
                    raise StreamsError("conflicting new model definition")
                if not existing:
                    result.append(item)
        return result
    if current != expected:
        raise StreamsError("conflicting prior owned configuration value")
    return desired


def install_json(root, path, desired, *, previous=None, plan=None):
    confined(root, path)
    if not path.exists():
        if previous is not None:
            raise StreamsError("missing prior owned configuration")
        install_bytes(root, path, (json.dumps(desired, sort_keys=True) + "\n").encode(), plan=plan)
        return
    raw = path.read_bytes()
    merged = merge_owned(json.loads(raw), desired if previous is None else previous, desired)
    if json.loads(raw) != merged:
        install_bytes(root, path, (json.dumps(merged, sort_keys=True) + "\n").encode(), replace_from=raw, plan=plan)


def prepare_project(root, project, model, thinking, percent, poteto, *, worker_model=DEFAULT_WORKER_MODEL,
                    worker_thinking=DEFAULT_THINKING, previous=None, plan=None):
    project.mkdir(parents=True, exist_ok=True)
    index = root / "index"
    index.mkdir(exist_ok=True)
    models = ModelSettings(model, thinking)
    info = ProjectSection(project.name, str(project), "", str(root / "worktrees"), git(repo_root(), "rev-parse", "HEAD").strip(),
                          "prime", str(root / "bin/prime-agent"), str(root / "prime/agent"), str(root / "prime/agent/sessions"),
                          str(root / "prime/daemon.sock"), str(poteto))
    config = Project(info, models, ModelSettings(worker_model, worker_thinking), Caps(), [])
    config_path = confined(root, index / "projects" / f"{project.name}.toml")
    if previous is None:
        if config_path.exists():
            import tomllib
            merge_owned(tomllib.loads(config_path.read_text()), tomllib.loads(dump_project(config)), tomllib.loads(dump_project(config)))
        else:
            install_bytes(root, config_path, dump_project(config).encode())
    else:
        import tomllib
        from dataclasses import replace
        old = replace(config, info=replace(info, pi_stack_revision=previous["pi_stack_revision"]),
                      coordinator=ModelSettings(previous["model"], previous["thinking"]),
                      threads=ModelSettings(previous.get("worker_model", previous["model"]), previous.get("worker_thinking", previous["thinking"])))
        raw = config_path.read_bytes()
        merge_owned(tomllib.loads(raw.decode()), tomllib.loads(dump_project(old)), tomllib.loads(dump_project(config)))
        text = raw.decode()
        section = ""
        lines = []
        changes = {"project": {"pi_stack_revision": info.pi_stack_revision}, "coordinator": {"model": model, "thinking": thinking},
                   "threads": {"model": worker_model, "thinking": worker_thinking}}
        for line in text.splitlines(keepends=True):
            if line.strip().startswith("["):
                heading = re.match(r"\s*\[([A-Za-z_]+)\]\s*(?:#.*)?$", line)
                section = heading[1] if heading else ""
            key = line.split("=", 1)[0].strip()
            if key in changes.get(section, {}):
                value = re.fullmatch(r"(\s*\w+\s*=\s*)(\"(?:\\.|[^\"\\])*\"|'[^']*')(.*?)(\n?)", line)
                if not value:
                    raise StreamsError("unsupported owned TOML value spelling")
                line = value[1] + json.dumps(changes[section][key]) + value[3] + value[4]
            lines.append(line)
        updated = "".join(lines)
        merge_owned(tomllib.loads(updated), tomllib.loads(dump_project(config)), tomllib.loads(dump_project(config)))
        install_bytes(root, config_path, updated.encode(), replace_from=raw, plan=plan)
    if not (index / "streams.tsv").exists():
        install_bytes(root, index / "streams.tsv", b"id\tpath\tproject\n")
    if not (index / "ALERTS").exists():
        install_bytes(root, index / "ALERTS", b"")
    settings = {"allowedModels": list(dict.fromkeys((model, worker_model))), "retry": {"enabled": False, "failover": {"enabled": False},
                "provider": {"waitForUsage": {"enabled": False, "pauseUntilReset": False}}}}
    old_settings = {**settings, "allowedModels": list(dict.fromkeys((previous["model"], previous.get("worker_model", previous["model"]))))} if previous else None
    install_json(root, root / "prime/agent/settings.json", settings, previous=old_settings, plan=plan)
    providers = {}
    for selected_model, selected_thinking in ((model, thinking), (worker_model, worker_thinking)):
        for provider, metadata in model_metadata(selected_model, selected_thinking).items():
            rows = providers.setdefault(provider, {"models": []})["models"]
            for item in metadata["models"]:
                if item not in rows:
                    rows.append(item)
    if providers:
        old_providers = {}
        if previous:
            for selected_model, selected_thinking in ((previous["model"], previous["thinking"]),
                    (previous.get("worker_model", previous["model"]), previous.get("worker_thinking", previous["thinking"]))):
                for provider, metadata in model_metadata(selected_model, selected_thinking, revision=previous["pi_stack_revision"]).items():
                    rows = old_providers.setdefault(provider, {"models": []})["models"]
                    rows.extend(item for item in metadata["models"] if item not in rows)
        install_json(root, root / "prime/agent/models.json", {"providers": providers}, previous={"providers": old_providers} if previous else None, plan=plan)
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install the isolated merged PoC; never login or start a session")
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--coordinator-model", default=DEFAULT_MODEL, help="stream model (default: %(default)s)")
    parser.add_argument("--coordinator-thinking", choices=LEVELS, default=DEFAULT_THINKING, help="stream thinking (default: %(default)s)")
    parser.add_argument("--worker-model", default=DEFAULT_WORKER_MODEL, help="worker/reviewer model (default: %(default)s)")
    parser.add_argument("--worker-thinking", choices=LEVELS, default=DEFAULT_THINKING, help="worker thinking (default: %(default)s)")
    parser.add_argument("--update-owned-from", metavar="RECEIPT_SHA256", help="explicitly update verified owned config/provenance; preserve user fields and snapshot prior files")
    parser.add_argument("--compaction-percent", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        root = preflight(args.prefix, args.project, args.coordinator_model, args.coordinator_thinking, args.compaction_percent)
        split_model(args.worker_model)
        root.mkdir(parents=True, exist_ok=True)
        previous = None
        receipt = root / "reports/install.json"
        if args.update_owned_from:
            if digest(confined(root, receipt)) != args.update_owned_from:
                raise StreamsError("prior installation receipt hash differs")
            previous = json.loads(receipt.read_text())
            if previous["root"] != str(root) or previous["project"] != str(args.project) or previous["paths"]["checkout"] != str(repo_root()):
                raise StreamsError("prior installation provenance names foreign paths")
            if git(repo_root(), "status", "--porcelain").strip():
                raise StreamsError("owned update requires committed clean source")
            git(repo_root(), "merge-base", "--is-ancestor", previous["pi_stack_revision"], "HEAD")
            snapshot = root / "reports/install-updates" / args.update_owned_from
            for relative in ("reports/install.json", "index/projects/project.toml", "prime/agent/settings.json", "prime/agent/models.json", "bin/prime-agent", "bin/pi-streams"):
                path = confined(root, root / relative)
                install_bytes(root, snapshot / relative, path.read_bytes(), path.stat().st_mode & 0o777)
        build = install_prime(root)
        pstack_revision, poteto = install_poteto(root)
        wrappers = write_wrappers(root, repo_root())
        plan = {} if previous else None
        prepare_project(root, args.project, args.coordinator_model, args.coordinator_thinking, args.compaction_percent, poteto,
                        worker_model=args.worker_model, worker_thinking=args.worker_thinking, previous=previous, plan=plan)
        report = {"pi_stack_revision": git(repo_root(), "rev-parse", "HEAD").strip(), **build,
                  "pstack_revision": pstack_revision, "root": str(root), "project": str(args.project),
                  "model": args.coordinator_model, "thinking": args.coordinator_thinking,
                  "worker_model": args.worker_model, "worker_thinking": args.worker_thinking,
                  "threshold_percent": args.compaction_percent, "paths": {**wrappers, "poteto": str(poteto), "checkout": str(repo_root())},
                  "checks": {"pinned_stock": True, "runtime_sidecar": True, "explicit_configuration": True}}
        if previous:
            report = {**previous, **report, "previous_receipt_sha256": args.update_owned_from}
            install_bytes(root, receipt, (json.dumps(report, sort_keys=True, indent=2) + "\n").encode(), replace_from=receipt.read_bytes(), plan=plan)
            for path, (content, mode, prior) in plan.items():
                install_bytes(root, path, content, mode, replace_from=prior)
        else:
            install_json(root, receipt, report)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (StreamsError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

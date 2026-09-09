#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

REVISION = re.compile(r"^[0-9a-f]{40,64}$")


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangedPath:
    status: str
    paths: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {"status": self.status, "paths": list(self.paths)}


@dataclass(frozen=True)
class UpdatePlan:
    pi_stack_root: str
    pi_stack_revision: str
    pi_stack_status: tuple[str, ...]
    pstack_path: str
    pstack_git_root: str
    pstack_repository_path: str
    branch: str
    upstream: str
    current_revision: str
    upstream_revision: str
    current_version: str
    upstream_version: str
    changed_paths: tuple[ChangedPath, ...]
    readiness: str

    def as_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "piStack": {
                "root": self.pi_stack_root,
                "revision": self.pi_stack_revision,
                "statusSummary": list(self.pi_stack_status),
            },
            "pstack": {
                "path": self.pstack_path,
                "gitRoot": self.pstack_git_root,
                "repositoryPath": self.pstack_repository_path,
                "branch": self.branch,
                "upstream": self.upstream,
                "currentRevision": self.current_revision,
                "upstreamRevision": self.upstream_revision,
                "currentVersion": self.current_version,
                "upstreamVersion": self.upstream_version,
            },
            "changedPaths": [item.as_json() for item in self.changed_paths],
            "readiness": self.readiness,
        }


@dataclass(frozen=True)
class CheckoutState:
    pi_stack_root: Path
    pi_stack_revision: str
    pi_stack_status: tuple[str, ...]
    pstack_path: Path
    pstack_git_root: Path
    pstack_repository_path: str
    branch: str
    upstream: str
    current_revision: str
    selected_skills: tuple[str, ...]


def run(command: Sequence[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise UpdateError(f"{' '.join(command)}: {message}")
    return result.stdout.rstrip("\n")


def git_root(path: Path, label: str) -> Path:
    if not path.is_dir():
        raise UpdateError(f"{label} path is not a directory: {path}")
    try:
        return Path(run(["git", "rev-parse", "--show-toplevel"], cwd=path)).resolve()
    except UpdateError as error:
        raise UpdateError(f"{label} is not inside a Git checkout: {path}") from error


def git(path: Path, *arguments: str) -> str:
    return run(["git", *arguments], cwd=path)


def plugin_metadata_path(pstack_path: Path, pstack_git_root: Path) -> str:
    try:
        relative = pstack_path.relative_to(pstack_git_root)
    except ValueError as error:
        raise UpdateError(f"pstack path is outside its Git checkout: {pstack_path}") from error
    metadata = relative / ".cursor-plugin" / "plugin.json"
    return metadata.as_posix()


def plugin_version(pstack_git_root: Path, revision: str, metadata_path: str) -> str:
    try:
        payload = json.loads(git(pstack_git_root, "show", f"{revision}:{metadata_path}"))
    except (UpdateError, json.JSONDecodeError) as error:
        raise UpdateError(f"cannot read pstack metadata at {revision}:{metadata_path}") from error
    if not isinstance(payload, dict) or payload.get("name") != "pstack":
        raise UpdateError(f"plugin metadata at {revision}:{metadata_path} is not pstack")
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise UpdateError(f"pstack metadata at {revision}:{metadata_path} has no version")
    return version


def selected_pstack_skills(pi_stack_root: Path) -> tuple[str, ...]:
    install = pi_stack_root / "install.sh"
    if not install.is_file():
        raise UpdateError(f"pi-stack install.sh is missing: {install}")
    output = run(["bash", str(install), "--print-pstack-skills"])
    names = tuple(output.splitlines())
    if not names or len(names) != len(set(names)):
        raise UpdateError("pi-stack returned an invalid selected pstack skill list")
    if any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) for name in names):
        raise UpdateError("pi-stack returned an invalid selected pstack skill name")
    return names


def require_upstream_skills(
    pstack_git_root: Path,
    upstream_revision: str,
    repository_path: str,
    names: tuple[str, ...],
) -> None:
    prefix = "" if repository_path == "." else f"{repository_path}/"
    for name in names:
        path = f"{prefix}skills/{name}/SKILL.md"
        try:
            git(pstack_git_root, "cat-file", "-e", f"{upstream_revision}:{path}")
        except UpdateError as error:
            raise UpdateError(f"upstream pstack is missing selected skill root: {name}") from error


def changed_paths(pstack_git_root: Path, current: str, upstream: str, repository_path: str) -> tuple[ChangedPath, ...]:
    pathspec = repository_path if repository_path != "." else ":/"
    output = git(pstack_git_root, "diff", "--name-status", "-z", f"{current}..{upstream}", "--", pathspec)
    if not output:
        return ()
    fields = output.split("\0")
    if fields[-1] == "":
        fields.pop()
    result: list[ChangedPath] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        path_count = 2 if status.startswith(("R", "C")) else 1
        paths = tuple(fields[index : index + path_count])
        if len(paths) != path_count:
            raise UpdateError("git returned an incomplete changed-path record")
        index += path_count
        result.append(ChangedPath(status=status, paths=paths))
    return tuple(result)


def git_common_dir(git_root_path: Path) -> Path:
    common = Path(git(git_root_path, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = git_root_path / common
    return common.resolve()


def tracked_status(git_root_path: Path) -> tuple[str, ...]:
    return tuple(git(git_root_path, "status", "--short", "--untracked-files=no").splitlines())


def pstack_local_status(git_root_path: Path) -> tuple[str, ...]:
    return tuple(
        git(
            git_root_path,
            "status",
            "--short",
            "--untracked-files=all",
            "--ignored=matching",
        ).splitlines()
    )


def require_clean_pstack(pstack_git_root: Path) -> None:
    if pstack_local_status(pstack_git_root):
        raise UpdateError(
            f"pstack checkout contains tracked, staged, untracked, or ignored content: {pstack_git_root}"
        )


def require_materialized_skills(
    pstack_git_root: Path,
    repository_path: str,
    names: tuple[str, ...],
) -> None:
    prefix = "" if repository_path == "." else f"{repository_path}/"
    roots = tuple(f"{prefix}skills/{name}" for name in names)
    output = git(pstack_git_root, "ls-files", "-z", "-v", "--", *roots)
    records = tuple(record for record in output.split("\0") if record)
    paths: set[str] = set()
    for record in records:
        if len(record) < 3 or record[1] != " ":
            raise UpdateError("git returned an invalid selected-skill index record")
        tag = record[0]
        path = record[2:]
        paths.add(path)
        if tag != "H":
            raise UpdateError(f"selected pstack skill is not fully materialized: {path}")
        source = pstack_git_root / path
        if source.is_symlink():
            raise UpdateError(f"selected pstack skill contains a symlink: {path}")
        if not source.is_file():
            raise UpdateError(f"selected pstack skill file is missing from the working tree: {path}")
    for name in names:
        skill = f"{prefix}skills/{name}/SKILL.md"
        if skill not in paths:
            raise UpdateError(f"selected pstack skill root is missing from the working tree: {name}")


def inspect_checkout(pi_stack_path: Path, pstack_path: Path) -> CheckoutState:
    pi_stack_root = git_root(pi_stack_path.resolve(), "pi-stack")
    pstack_path = pstack_path.resolve()
    pstack_git_root = git_root(pstack_path, "pstack")
    if git_common_dir(pstack_git_root) == git_common_dir(pi_stack_root):
        raise UpdateError("pstack must use an independent Git checkout; refusing to change pi-stack")
    pi_stack_revision = git(pi_stack_root, "rev-parse", "HEAD")
    pi_stack_status = tracked_status(pi_stack_root)
    if pi_stack_status:
        raise UpdateError(f"pi-stack checkout has tracked or staged changes: {pi_stack_root}")
    if not (pstack_path / "skills" / "poteto-mode" / "SKILL.md").is_file():
        raise UpdateError(f"pstack path has no skills/poteto-mode/SKILL.md: {pstack_path}")
    require_clean_pstack(pstack_git_root)
    try:
        branch = git(pstack_git_root, "symbolic-ref", "--quiet", "--short", "HEAD")
    except UpdateError as error:
        raise UpdateError(f"pstack checkout is not on a branch: {pstack_git_root}") from error
    try:
        upstream = git(pstack_git_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    except UpdateError as error:
        raise UpdateError(f"pstack branch {branch} has no upstream: {pstack_git_root}") from error
    repository_path = pstack_path.relative_to(pstack_git_root).as_posix() or "."
    selected_skills = selected_pstack_skills(pi_stack_root)
    require_materialized_skills(pstack_git_root, repository_path, selected_skills)
    if git(pi_stack_root, "rev-parse", "HEAD") != pi_stack_revision or tracked_status(pi_stack_root) != pi_stack_status:
        raise UpdateError("pi-stack changed while its pstack selection was inspected")
    return CheckoutState(
        pi_stack_root=pi_stack_root,
        pi_stack_revision=pi_stack_revision,
        pi_stack_status=pi_stack_status,
        pstack_path=pstack_path,
        pstack_git_root=pstack_git_root,
        pstack_repository_path=repository_path,
        branch=branch,
        upstream=upstream,
        current_revision=git(pstack_git_root, "rev-parse", "HEAD"),
        selected_skills=selected_skills,
    )


def require_unchanged_checkout(state: CheckoutState, expected_pstack_revision: str) -> None:
    if git(state.pi_stack_root, "rev-parse", "HEAD") != state.pi_stack_revision:
        raise UpdateError("pi-stack HEAD changed while pstack was updated")
    if tracked_status(state.pi_stack_root) != state.pi_stack_status:
        raise UpdateError("pi-stack tracked or staged status changed while pstack was updated")
    require_clean_pstack(state.pstack_git_root)
    current_revision = git(state.pstack_git_root, "rev-parse", "HEAD")
    if current_revision != expected_pstack_revision:
        raise UpdateError(f"pstack HEAD changed unexpectedly: {current_revision}")
    require_materialized_skills(
        state.pstack_git_root,
        state.pstack_repository_path,
        state.selected_skills,
    )


def make_plan(
    state: CheckoutState,
    current_revision: str,
    upstream_revision: str,
    readiness: str,
) -> UpdatePlan:
    require_upstream_skills(
        state.pstack_git_root,
        upstream_revision,
        state.pstack_repository_path,
        state.selected_skills,
    )
    metadata_path = plugin_metadata_path(state.pstack_path, state.pstack_git_root)
    return UpdatePlan(
        pi_stack_root=str(state.pi_stack_root),
        pi_stack_revision=state.pi_stack_revision,
        pi_stack_status=state.pi_stack_status,
        pstack_path=str(state.pstack_path),
        pstack_git_root=str(state.pstack_git_root),
        pstack_repository_path=state.pstack_repository_path,
        branch=state.branch,
        upstream=state.upstream,
        current_revision=current_revision,
        upstream_revision=upstream_revision,
        current_version=plugin_version(state.pstack_git_root, current_revision, metadata_path),
        upstream_version=plugin_version(state.pstack_git_root, upstream_revision, metadata_path),
        changed_paths=changed_paths(
            state.pstack_git_root,
            current_revision,
            upstream_revision,
            state.pstack_repository_path,
        ),
        readiness=readiness,
    )


def build_fresh_plan(state: CheckoutState) -> UpdatePlan:
    git(state.pstack_git_root, "fetch", "--prune")
    require_unchanged_checkout(state, state.current_revision)
    upstream_revision = git(state.pstack_git_root, "rev-parse", state.upstream)
    counts = git(
        state.pstack_git_root,
        "rev-list",
        "--left-right",
        "--count",
        f"{state.current_revision}...{upstream_revision}",
    ).split()
    if len(counts) != 2:
        raise UpdateError("git returned invalid ahead and behind counts")
    try:
        ahead, behind = (int(value) for value in counts)
    except ValueError as error:
        raise UpdateError("git returned invalid ahead and behind counts") from error
    if ahead and behind:
        raise UpdateError(f"pstack checkout has diverged from {state.upstream}: {state.pstack_git_root}")
    if ahead:
        raise UpdateError(
            f"pstack checkout has local commits not in {state.upstream}: {state.pstack_git_root}"
        )
    return make_plan(
        state,
        state.current_revision,
        upstream_revision,
        "ready" if behind else "up-to-date",
    )


def build_plan(pi_stack_path: Path, pstack_path: Path) -> UpdatePlan:
    return build_fresh_plan(inspect_checkout(pi_stack_path, pstack_path))


def recovery_plan(
    state: CheckoutState,
    expected_current: str,
    expected_upstream: str,
) -> UpdatePlan:
    try:
        resolved_current = git(state.pstack_git_root, "rev-parse", f"{expected_current}^{{commit}}")
        resolved_upstream = git(state.pstack_git_root, "rev-parse", f"{expected_upstream}^{{commit}}")
    except UpdateError as error:
        raise UpdateError("reviewed pstack endpoint is not available locally") from error
    if resolved_current != expected_current or resolved_upstream != expected_upstream:
        raise UpdateError("reviewed pstack endpoint did not resolve exactly")
    if expected_current != expected_upstream:
        try:
            git(state.pstack_git_root, "merge-base", "--is-ancestor", expected_current, expected_upstream)
        except UpdateError as error:
            raise UpdateError("reviewed current revision is not an ancestor of the reviewed upstream revision") from error
    require_unchanged_checkout(state, expected_upstream)
    return make_plan(state, expected_upstream, expected_upstream, "up-to-date")


def apply_plan(
    pi_stack_path: Path,
    pstack_path: Path,
    expected_pi_stack: str,
    expected_current: str,
    expected_upstream: str,
) -> dict[str, Any]:
    if not REVISION.fullmatch(expected_pi_stack):
        raise UpdateError("--expected-pi-stack must be a full Git revision")
    if not REVISION.fullmatch(expected_current):
        raise UpdateError("--expected-current must be a full Git revision")
    if not REVISION.fullmatch(expected_upstream):
        raise UpdateError("--expected-upstream must be a full Git revision")
    state = inspect_checkout(pi_stack_path, pstack_path)
    if state.pi_stack_revision != expected_pi_stack:
        raise UpdateError(
            f"reviewed pi-stack revision {expected_pi_stack} no longer matches {state.pi_stack_revision}"
        )
    fast_forwarded = False
    if state.current_revision == expected_upstream:
        plan = recovery_plan(state, expected_current, expected_upstream)
    elif state.current_revision == expected_current:
        plan = build_fresh_plan(state)
        if plan.upstream_revision != expected_upstream:
            raise UpdateError(
                f"reviewed upstream revision {expected_upstream} no longer matches {plan.upstream_revision}"
            )
        git(
            state.pstack_git_root,
            "-c",
            "core.hooksPath=/dev/null",
            "merge",
            "--ff-only",
            "--no-edit",
            expected_upstream,
        )
        require_unchanged_checkout(state, expected_upstream)
        fast_forwarded = True
    else:
        raise UpdateError(
            f"pstack HEAD {state.current_revision} is neither the reviewed current revision "
            f"{expected_current} nor the reviewed upstream revision {expected_upstream}"
        )
    current_revision = git(state.pstack_git_root, "rev-parse", "HEAD")
    pi_stack_revision = git(state.pi_stack_root, "rev-parse", "HEAD")
    pi_stack_status = tracked_status(state.pi_stack_root)
    return {
        "plan": plan.as_json(),
        "result": {
            "pstackRevision": current_revision,
            "piStackRevision": pi_stack_revision,
            "piStackStatusSummary": list(pi_stack_status),
            "fastForwarded": fast_forwarded,
        },
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Plan or apply an independent pstack fast-forward")
    result.add_argument("--pi-stack", required=True, type=Path)
    result.add_argument("--pstack", required=True, type=Path)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    apply = commands.add_parser("apply")
    apply.add_argument("--expected-pi-stack", required=True)
    apply.add_argument("--expected-current", required=True)
    apply.add_argument("--expected-upstream", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "plan":
            payload = build_plan(arguments.pi_stack, arguments.pstack).as_json()
        else:
            payload = apply_plan(
                arguments.pi_stack,
                arguments.pstack,
                arguments.expected_pi_stack,
                arguments.expected_current,
                arguments.expected_upstream,
            )
    except UpdateError as error:
        print(f"update-pstack: {error}", file=sys.stderr)
        return 1
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

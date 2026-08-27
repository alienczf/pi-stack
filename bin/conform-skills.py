#!/usr/bin/env python3
"""Rewrite Cursor skill frontmatter so Pi will load it without name warnings.

Does not edit the source tree. Writes SKILL.md copies under --out and
symlinks every other file so playbooks and references keep working.

Pi names must be 1-64 chars, lowercase a-z 0-9 hyphens, no leading or
trailing hyphen, no consecutive hyphens. Cursor allows Title Case names
such as "Poteto Mode".
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

MAX_NAME = 64
MAX_DESCRIPTION = 1024
NAME_OK = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_LINE = re.compile(r"^name:\s*(.*)$")
DESC_LINE = re.compile(r"^description:\s*(.*)$")


def slugify(raw: str, fallback: str = "skill") -> str:
	s = raw.strip().lower()
	s = re.sub(r"[^a-z0-9]+", "-", s)
	s = re.sub(r"-{2,}", "-", s).strip("-")
	if not s:
		s = slugify(fallback, "skill") if fallback != raw else "skill"
	if len(s) > MAX_NAME:
		s = s[:MAX_NAME].rstrip("-") or "skill"
	if not NAME_OK.fullmatch(s):
		s = re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "skill"
	return s


def unquote(value: str) -> str:
	value = value.strip()
	if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
		return value[1:-1]
	return value


def split_frontmatter(text: str) -> tuple[str | None, str]:
	if text.startswith("\ufeff"):
		text = text[1:]
	if not text.startswith("---"):
		return None, text
	rest = text[3:]
	if rest.startswith("\r\n"):
		rest = rest[2:]
	elif rest.startswith("\n"):
		rest = rest[1:]
	else:
		return None, text
	end = rest.find("\n---")
	if end < 0:
		return None, text
	fm = rest[:end]
	body = rest[end + 4 :]
	if body.startswith("\n"):
		body = body[1:]
	return fm, body


def first_match(pattern: re.Pattern[str], fm: str) -> str | None:
	for line in fm.splitlines():
		m = pattern.match(line)
		if m:
			return unquote(m.group(1))
	return None


def replace_first_line(fm: str, pattern: re.Pattern[str], replacement: str) -> str:
	lines = fm.splitlines(keepends=True)
	out: list[str] = []
	found = False
	for line in lines:
		if not found and pattern.match(line.rstrip("\n")):
			nl = "\n" if line.endswith("\n") else ""
			out.append(f"{replacement}{nl}")
			found = True
		else:
			out.append(line)
	if not found:
		prefix = "" if (not fm or fm.endswith("\n")) else "\n"
		return f"{fm}{prefix}{replacement}\n"
	return "".join(out)


def rewrite_skill_text(text: str, dirname: str) -> tuple[str, str, bool]:
	"""Return (new_text, name, name_changed)."""
	fallback = slugify(dirname)
	fm, body = split_frontmatter(text)
	if fm is None:
		name = fallback
		desc = f"Imported skill {dirname}."
		new = f"---\nname: {name}\ndescription: {desc}\n---\n\n{body.lstrip()}"
		return new, name, True

	raw_name = first_match(NAME_LINE, fm)
	name = slugify(raw_name, fallback) if raw_name else fallback
	changed = raw_name != name
	new_fm = replace_first_line(fm, NAME_LINE, f"name: {name}") if raw_name else f"name: {name}\n{fm}"

	raw_desc = first_match(DESC_LINE, new_fm)
	if raw_desc is None:
		new_fm = f"{new_fm.rstrip()}\ndescription: Imported skill {dirname}.\n"
	elif len(raw_desc) > MAX_DESCRIPTION:
		trimmed = raw_desc[:MAX_DESCRIPTION]
		escaped = trimmed.replace("\\", "\\\\").replace('"', '\\"')
		new_fm = replace_first_line(new_fm, DESC_LINE, f'description: "{escaped}"')

	new = f"---\n{new_fm.rstrip()}\n---\n"
	if body:
		new += "\n" + body
		if not new.endswith("\n"):
			new += "\n"
	else:
		new += "\n"
	return new, name, changed


def discover_skill_dirs(root: Path) -> list[Path]:
	found: list[Path] = []

	def walk(dirpath: Path) -> None:
		if not dirpath.is_dir():
			return
		if dirpath.name in {".git", "node_modules"} or dirpath.name.startswith("."):
			return
		skill = dirpath / "SKILL.md"
		if skill.is_file():
			found.append(dirpath)
			return
		try:
			entries = sorted(dirpath.iterdir(), key=lambda p: p.name)
		except OSError:
			return
		for child in entries:
			if child.is_dir():
				walk(child)

	walk(root)
	return found


def link_or_replace(src: Path, dest: Path) -> None:
	target = src.resolve()
	if dest.is_symlink() or dest.exists():
		if dest.is_symlink() and Path(os.readlink(dest)).resolve() == target:
			return
		if dest.is_dir() and not dest.is_symlink():
			raise SystemExit(f"refusing to replace directory {dest}")
		dest.unlink()
	dest.symlink_to(target)


def conform_one(src: Path, out_root: Path, verbose: bool) -> Path:
	src = src.resolve()
	skill_md = src / "SKILL.md"
	if not skill_md.is_file():
		raise SystemExit(f"no SKILL.md in {src}")
	dest_dir = (out_root / src.name).resolve()
	if dest_dir == src:
		raise SystemExit(f"refusing in-place rewrite of {src}. Set --out to a different directory")
	dest_dir.mkdir(parents=True, exist_ok=True)
	text = skill_md.read_text(encoding="utf-8")
	new_text, name, changed = rewrite_skill_text(text, src.name)
	dest_md = dest_dir / "SKILL.md"
	if not dest_md.exists() or dest_md.read_text(encoding="utf-8") != new_text:
		dest_md.write_text(new_text, encoding="utf-8")
	if verbose and changed:
		raw = first_match(NAME_LINE, split_frontmatter(text)[0] or "") or src.name
		print(f"rewrote name: {raw} -> {name} ({src.name})", file=sys.stderr)
	keep = {"SKILL.md"}
	for entry in src.iterdir():
		if entry.name == "SKILL.md":
			continue
		keep.add(entry.name)
		link_or_replace(entry, dest_dir / entry.name)
	for entry in dest_dir.iterdir():
		if entry.name not in keep:
			if entry.is_symlink() or entry.is_file():
				entry.unlink()
	return dest_dir


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		description="Copy skills into a Pi-safe tree. Does not edit the source.",
	)
	parser.add_argument("--out", required=True, type=Path, help="directory that will hold one child per skill")
	parser.add_argument("--tree", type=Path, help="walk this directory for SKILL.md (Pi discovery rules)")
	parser.add_argument("skills", nargs="*", type=Path, help="skill directories that contain SKILL.md")
	parser.add_argument("-v", "--verbose", action="store_true")
	args = parser.parse_args(argv)
	sources: list[Path] = []
	if args.tree:
		sources.extend(discover_skill_dirs(args.tree))
	sources.extend(args.skills)
	if not sources:
		raise SystemExit("pass --tree DIR and/or one or more skill directories")
	out = args.out.resolve()
	out.mkdir(parents=True, exist_ok=True)
	seen: set[Path] = set()
	for src in sources:
		src = src.resolve()
		if src in seen:
			continue
		seen.add(src)
		conform_one(src, out, args.verbose)
	return 0


if __name__ == "__main__":
	sys.exit(main())

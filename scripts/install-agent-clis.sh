#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for name in agent-cli prime-cli prime-cli-remote; do
	[[ -x "$root/bin/$name" ]] || { printf 'Missing executable %s\n' "$root/bin/$name" >&2; exit 1; }
done
[[ -f "$root/bin/prime_cli.py" ]] || { printf 'Missing prime_cli.py\n' >&2; exit 1; }
mkdir -p "$HOME/.local/bin"
for name in agent-cli prime-cli prime-cli-remote; do
	ln -sfn "$root/bin/$name" "$HOME/.local/bin/$name"
done

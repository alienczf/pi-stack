#!/usr/bin/env bash
set -euo pipefail

usage() {
	cat <<'EOF'
usage: install.sh

Copies the pi-stack overlay into $HOME/.pi/agent.
Merges defaultTools and skills into settings.json.
Never writes auth.json, models-store.json, private/, or sessions/.
Does not search for git repositories. Fit a repo later with jig.sh.

Environment
  HOME     install target (default is your home)
  PSTACK   live pstack clone (see README)
EOF
}

case "${1:-}" in
	-h | --help)
		usage
		exit 0
		;;
	"")
		;;
	*)
		usage >&2
		exit 2
		;;
esac

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
overlay="$here/overlay"
if [[ ! -f "$overlay/APPEND_SYSTEM.md" ]]; then
	printf 'install.sh must run from a pi-stack checkout that contains overlay/\n' >&2
	exit 1
fi

pstack="${PSTACK:-}"
if [[ -z "$pstack" ]]; then
	if [[ -f /home/zhanfeng/Projects/plugins/pstack/skills/poteto-mode/SKILL.md ]]; then
		pstack=/home/zhanfeng/Projects/plugins/pstack
	elif [[ -f "${HOME}/src/pstack/skills/poteto-mode/SKILL.md" ]]; then
		pstack="${HOME}/src/pstack"
	else
		printf 'PSTACK is unset and no pstack clone was found at /home/zhanfeng/Projects/plugins/pstack or %s/src/pstack\n' "$HOME" >&2
		exit 1
	fi
fi
if [[ ! -f "$pstack/skills/poteto-mode/SKILL.md" ]]; then
	printf 'PSTACK=%s has no skills/poteto-mode/SKILL.md\n' "$pstack" >&2
	exit 1
fi

agent="${HOME}/.pi/agent"
mkdir -p "$agent/prompts" "$agent/bin"

install_md() {
	local src="$1" dest="$2"
	PSTACK="$pstack" python3 - "$src" "$dest" <<'PY'
import os
import sys
from pathlib import Path

src = Path(sys.argv[1])
dest = Path(sys.argv[2])
text = src.read_text().replace("__PSTACK__", os.environ["PSTACK"])
if dest.exists() and dest.read_text() == text:
	sys.exit(0)
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(text)
PY
}

install_md "$overlay/APPEND_SYSTEM.md" "$agent/APPEND_SYSTEM.md"
install_md "$overlay/AGENTS.md" "$agent/AGENTS.md"
for src in "$here/prompts"/*.md; do
	install_md "$src" "$agent/prompts/$(basename "$src")"
done

if [[ -x "$here/bin/jig.sh" ]]; then
	wrapper="$agent/bin/jig"
	wanted=$'#!/usr/bin/env bash\nexec '"$here/bin/jig.sh"$' "$@"\n'
	if [[ ! -f "$wrapper" ]] || [[ "$(cat "$wrapper")" != "$wanted" ]]; then
		printf '%s' "$wanted" >"$wrapper"
	fi
	chmod +x "$wrapper"
fi

export PI_AGENT_DIR="$agent"
export PSTACK="$pstack"
export PI_STACK_ROOT="$here"
python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

agent = Path(os.environ["PI_AGENT_DIR"])
pstack = Path(os.environ["PSTACK"])
repo = Path(os.environ["PI_STACK_ROOT"])
path = agent / "settings.json"

tools = ["read", "write", "edit", "bash", "grep", "find", "ls"]
wanted = [
	pstack / "skills/poteto-mode",
	pstack / "skills/how",
	pstack / "skills/why",
	pstack / "skills/architect",
	pstack / "skills/interrogate",
	pstack / "skills/tdd",
	pstack / "skills/unslop",
	pstack / "skills/technical-writing",
	pstack / "skills/figure-it-out",
	pstack / "skills/show-me-your-work",
	pstack / "skills/reflect",
	pstack / "skills/create-verification-skill",
	repo / "skills/jig",
	repo / "skills/cross-repo",
]
skills = [str(p.resolve()) for p in wanted if (p / "SKILL.md").is_file()]
if len(skills) > 14:
	sys.exit("skills allowlist grew past 14")

if path.exists():
	data = json.loads(path.read_text())
	if not isinstance(data, dict):
		sys.exit("settings.json is not an object")
else:
	data = {}

data["defaultTools"] = tools
data["skills"] = skills
text = json.dumps(data, indent=2) + "\n"
if path.exists() and path.read_text() == text:
	sys.exit(0)
tmp = path.with_name("settings.json.pi-stack-tmp")
tmp.write_text(text)
tmp.replace(path)
PY

cat <<'EOF'
pi-stack is installed for this user.
Fit a repo with a jig:
  cd /path/to/repo && jig.sh
or inside Pi:
  /skill:jig
EOF

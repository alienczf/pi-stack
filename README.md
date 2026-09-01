# pi-stack

pi-stack installs a user-level Pi overlay and pstack process skills. Jig configures one Git repository with human-ratified repository Principles and a pstack-generated verification skill. It does not change product code.

## Install pi-stack

Install Pi and sign in before you install pi-stack.

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh | bash
```

On a later quickstart run, the piped installer asks before it fast-forwards `$HOME/.pi-stack`. Enter `y`, or pass `-y`:

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh | bash -s -- -y
```

To install from a checkout, run:

```bash
git clone https://github.com/alienczf/pi-stack.git
cd pi-stack
./install.sh
```

The installer prints this layout with your actual home path and skill count:

```text
pi-stack is installed for this user.
  overlay   $HOME/.pi/agent
  agents    $HOME/.pi/agent/agents
  backups   $HOME/.pi/agent/backups/subagents
  skills    <count>
  packages  pi-web-access, pi-hashline-edit, pi-subagents, @narumitw/pi-goal
  jig       $HOME/.local/bin/jig
  controller $HOME/.pi/agent/jig/bin/jigctl.py
Configure one Git repository:
  cd /path/to/repo && jig init
Or use the current trusted Pi session:
  /skill:jig init
  /jig init
```

The installer keeps the Jig launcher, controller, skill, and references under `$HOME/.pi/agent/jig/`. The command at `$HOME/.local/bin/jig` resolves that installed copy. It does not depend on the checkout that ran `install.sh`.

The installer preserves unrelated settings and package rows. It preserves an existing `defaultProjectTrust` value and does not add one to a fresh settings file. The shell command denies project trust for its own Pi process with explicit flags. It does not make every project trusted.

The prompt and `-y` update only when a bootstrap invocation selects the default `$HOME/.pi-stack` checkout. Running that checkout's `install.sh` directly or setting `PI_STACK` uses the selected source as-is. The installer does not update the nested pstack clone or installed package versions. After a source update, it installs each newly required package that is absent.

A second run with the same inputs leaves all owned file bytes unchanged and removes stale files only from the installed Jig resource directory. It never writes `auth.json`, `models-store.json`, `private/`, or `sessions/`.

To use existing source trees, run:

```bash
PI_STACK=/path/to/pi-stack PSTACK=/path/to/pstack ./install.sh
```

Set `PI_STACK_SKIP_PACKAGES=1` only for an offline or fixture install. That option records the package settings but does not install the packages.

## Required packages

Fresh installs get these packages. Existing rows remain unchanged.

- `npm:pi-web-access` adds `web_search` and `fetch_content`. Librarian skills are filtered out.
- `npm:pi-hashline-edit` replaces the built-in `read` and `edit` tools with hash-anchored versions. The overlay keeps the built-in `grep`.
- `npm:pi-subagents` adds the `subagent` and `subagent_wait` tools. A running Pi agent does not start a child with `pi -p`.
- `npm:@narumitw/pi-goal` replaces the prose `/goal` prompt with settled-idle continuation and the `goal_complete`, `goal_blocked`, and `goal_wait` tools.

If `$HOME/.pi/agent/pi-goal.json` is absent, the installer creates it with unlimited automatic turns and a three-run no-progress guard. It preserves an existing file byte for byte.

The overlay does not install an MCP adapter, a todo tool, plan mode, pi-lens, an interactive browser, CDP, or Instant Grep. Those packages duplicate or conflict with its tools.

## Run process commands

- `/poteto` loads poteto-mode.
- `/goal <objective>` starts a session-scoped objective. Give it a checkable exit predicate. Arrange a wake message before you call `goal_wait` for an external wait.
- `/skill:cross-repo` reads the current repository's registry and starts one subagent for each listed path. It stops when no registry exists.

## Configure one repository

Run one command from any directory inside the target Git repository:

```text
jig init
/skill:jig init
/jig init
```

All routes resolve the Git top level. Jig rejects package names, subtree paths, flags, and extra arguments before it writes `.pi/jig`. A monorepo has one repository-wide Jig scope.

### Public routes

[`skills/jig/references/public-routes.json`](skills/jig/references/public-routes.json) owns this table. Run `python3 scripts/render-jig-routes.py --check` to detect drift.

<!-- public-routes:start -->
| Command | Resource loading | Receipt | Controller | Pause and resume | Terminal state |
| --- | --- | --- | --- | --- | --- |
| `jig init` | Starts a fresh Pi process with project context, extensions, prompts, themes, and discovered skills disabled. It explicitly loads only the installed Jig and create-verification-skill procedures. | `isolated-shell` | `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py` | Exit at awaiting-principles when the operator has not supplied a complete response. Resume active work with jig init. Resume with /skill:jig init or /jig init when the manifest records inherited-session. | `configured` |
| `/skill:jig init` | Uses the current trusted Pi session and its installed pstack skills. It never starts a nested Pi process. | `inherited-session` | `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py` | Stop at awaiting-principles when the operator has not supplied a complete response. Resume active work with /skill:jig init. Resume with jig init when the manifest records isolated-shell. | `configured` |
| `/jig init` | Expands to the registered Jig skill in the current trusted Pi session. It never starts a nested Pi process. | `inherited-session` | `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py` | Stop at awaiting-principles when the operator has not supplied a complete response. Resume active work with /jig init. Resume with jig init when the manifest records isolated-shell. | `configured` |
<!-- public-routes:end -->

A manifest keeps its original route. A version 1 manifest is an unsupported legacy campaign. Preserve `.pi/jig` and its worktrees, then archive or migrate it explicitly. Jig version 2 never reinterprets old state.

### What init does

1. Jig surveys one Git root and records cited product entry points and existing policies.
2. It asks one round of repository-specific questions. Generic pstack process rules are not questions.
3. The operator approves the exact digest and marker for `.cursor/skills/principle-repository/SKILL.md`.
4. Jig follows the installed pstack `create-verification-skill` procedure. That procedure owns Launch, Doctor, Drive, Evidence, Cleanup, Helpers, the feature map, and live proof.
5. The controller records the generated `.cursor/skills/verify-*/SKILL.md` path and hash.
6. The controller idempotently adds `../.cursor/skills` to `.pi/settings.json` while preserving unrelated valid settings.
7. Jig reports `configured` and stops.

Jig never selects, edits, verifies, or merges a product-code improvement. Later verification audits belong to `/skill:maintain-verification-skill`.

### Repository artifacts

| Path | Owner | Purpose |
| --- | --- | --- |
| `.pi/jig/manifest.json` | Controller | Version 2 state, route, hashes, transitions, and configured capability paths. |
| `.pi/jig/profile.json` | Jig skill through controller validation | Cited repository survey. |
| `.pi/jig/principles/` | Controller and operator input | Candidate, answers, and decision receipts. |
| `.cursor/skills/principle-repository/SKILL.md` | Target operator through exact ratification | Repository-specific priorities and constraints. |
| `.cursor/skills/verify-*/` | pstack create-verification-skill | Runtime verification skill, feature map, helpers, and named evidence. |
| `.pi/settings.json` | Repository, merged by controller | Loads the canonical `.cursor/skills` tree in Pi. |

Run the owning route again after a crash or clean pause. Preserve the recorded artifacts. Do not copy a manifest from another route.

## Verify the repository

Run these commands from the pi-stack Git root. None starts a nested Pi process.

<!-- readme-checks:start -->
```bash
bash -n bin/jig.sh install.sh scripts/check-jig.sh
python3 -m unittest discover -s scripts/jig_tests -p 'test_*.py'
bash scripts/check-overlay.sh
bash scripts/check-conform-skills.sh
bash scripts/check-subagents.sh
bash scripts/check-jig.sh
bash scripts/check-cross-repo.sh
python3 scripts/render-jig-routes.py --check
```
<!-- readme-checks:end -->

`python3 scripts/check-readme-commands.py --execute` extracts that block and runs each command in order. The integration suite uses a Pi stub for the shell route. It never starts a nested real Pi process.

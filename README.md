# pi-stack

pi-stack installs a user-level Pi overlay and two explicit skills. Jig initializes one whole Git repository through target COMMANDMENTS, runtime verification, and one terminal first improvement result.

## Install pi-stack

Install Pi and sign in before you install pi-stack.

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh | bash
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
Fit one Git repository:
  cd /path/to/repo && jig init
Or use the current trusted Pi session:
  /skill:jig init
  /jig init
```

The installer keeps the Jig launcher, controller, skill, and references under `$HOME/.pi/agent/jig/`. The command at `$HOME/.local/bin/jig` resolves that installed copy. It does not depend on the checkout that ran `install.sh`.

The installer preserves unrelated settings and package rows. It preserves an existing `defaultProjectTrust` value and does not add one to a fresh settings file. The shell command denies project trust for its own Pi process with explicit flags. It does not make every project trusted.

Run the same installer again after you update a checkout. A second run with the same inputs leaves all owned file bytes unchanged and removes stale files only from the installed Jig resource directory. It never writes `auth.json`, `models-store.json`, `private/`, or `sessions/`.

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

## Initialize one repository

Run one of these commands from any directory inside the target Git repository:

```text
jig init
/skill:jig init
/jig init
```

All commands resolve the Git top level. Version 1 rejects package names, subtree paths, flags, and extra arguments before it writes `.pi/jig`. A monorepo is one repository-wide Jig scope.

### Public routes

[`skills/jig/references/public-routes.json`](skills/jig/references/public-routes.json) owns this table. Run `python3 scripts/render-jig-routes.py --check` to detect drift.

<!-- public-routes:start -->
| Command | Resource loading | Receipt | Controller | Pause and resume | Terminal state |
| --- | --- | --- | --- | --- | --- |
| `jig init` | Starts a fresh Pi process with --no-approve, --no-context-files, --no-extensions plus one explicit --extension, --no-skills plus one explicit --skill, --no-prompt-templates, --no-themes, and explicit system prompt overrides. Only the installed Jig skill and installed pi-subagents extension enter the campaign as resources. | `isolated-shell` | `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/jig/bin/jigctl.py` | Exit at awaiting-commandments when the operator has not supplied a complete response. Resume with jig init. A clean exit at another active boundary also resumes with jig init. Resume with /skill:jig init or /jig init when the manifest records inherited-session. | `initialized with kept, reverted, or no-eligible-candidate` |
| `/skill:jig init` | Uses the current trusted Pi session. Resources already loaded into that session remain loaded. It never starts a nested Pi process. | `inherited-session` | `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/jig/bin/jigctl.py` | Stop at awaiting-commandments when the operator has not supplied a complete response. Resume with /skill:jig init in a trusted Pi session. Resume with jig init when the manifest records isolated-shell. | `initialized with kept, reverted, or no-eligible-candidate` |
| `/jig init` | Expands to an instruction to load the registered Jig skill in the current trusted Pi session. Resources already loaded into that session remain loaded. It never starts a nested Pi process. | `inherited-session` | `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/jig/bin/jigctl.py` | Stop at awaiting-commandments when the operator has not supplied a complete response. Resume with /jig init in a trusted Pi session. Resume with jig init when the manifest records isolated-shell. | `initialized with kept, reverted, or no-eligible-candidate` |
<!-- public-routes:end -->

A manifest keeps its original route. If a route mismatch occurs, use the recovery command in the table. Never relabel inherited work as isolated work.

### Ratify target COMMANDMENTS

Jig surveys the repository first. It pauses at `awaiting-commandments` until the target operator supplies one complete response.

1. Jig runs `present-commandments` and shows observed facts, every question, and every recommended default.
2. The target operator answers every key once. A default counts only when the response explicitly selects it.
3. Jig passes `.pi/jig/commandments/answers.input.json` to the emitted `stage-commandments` operation. The operator can provide the same complete JSON in the interactive Pi session.
4. Jig displays the complete candidate bytes, the exact SHA-256 digest, and the intended marker.
5. The operator chooses ratify, amend, or defer. Jig records amend and defer through `record-commandments-decision`.
6. Only `ratify-commandments` publishes root `COMMANDMENTS.md`. Jig continues only after `validate-commandments` succeeds.

Jig preserves an existing `COMMANDMENTS.md`. Agents can propose later amendments under `.pi/jig/commandments/proposals/`, but they do not edit or weaken the ratified file.

### Finish verification and one first step

After ratification, Jig builds `.pi/skills/jig-verification/` from target facts and the canonical installed `create-verification-skill` procedure. The controller accepts it only after the protected public path passes Launch, Doctor, Drive, retained Evidence, and exact Cleanup.

Jig then records every considered candidate in `.pi/jig/steps/0001/selection.json`. It either selects no candidate or exactly one eligible candidate. Selected work runs only in `.pi/jig/worktrees/0001` on the controller-owned branch. The controller pins the output, runs the baseline and required proof, requires an independent verdict when the proposal says so, and writes `.pi/jig/steps/0001/result.json`.

`initialized` has exactly one outcome:

- `kept`
- `reverted`
- `no-eligible-candidate`

Jig leaves a kept candidate branch and worktree for operator review. It does not merge.

## Inspect artifacts and ownership

The target repository stores these durable artifacts:

| Path | Owner | Purpose |
| --- | --- | --- |
| `COMMANDMENTS.md` | Target operator through controller ratification | Target intent, exceptions, proof policy, and authority. |
| `.pi/jig/manifest.json` | Controller | Route, state, hashes, receipts, and terminal pointers. |
| `.pi/jig/profile.json` | Jig skill through the controller | Cited repository survey. |
| `.pi/jig/commandments/` | Controller and target operator input | Interview, staged candidate, decisions, and amendment proposals. |
| `.pi/skills/jig-verification/` | Jig skill inside controller-reserved paths | Target-local verification skill, feature map, and helpers. |
| `.pi/jig/steps/0001/` | Controller | Selection, proposal, worker handoff, pinned output, proof, verdict, and result. |
| `.pi/jig/worktrees/0001` | Controller | Isolated selected-candidate worktree. |

The controller owns locks, transitions, path containment, hashes, proof execution, and terminal results. The Jig skill owns repository interpretation and candidate recommendations. A selected worker owns only the proposal's allowed product paths in the isolated worktree. The target operator owns merge decisions.

## Recover after interruption

Run the same owning route again after a crash or a clean pause. `start` validates the manifest and receipts, reconciles controller-owned interrupted writes, and resumes from the last valid boundary.

Preserve `.pi/jig`, `COMMANDMENTS.md`, the selected branch, and the selected worktree. Do not delete partial evidence or copy a manifest from another route. A source revision change or candidate revision change invalidates stale evidence and fails closed.

## Version 1 limits

Version 1 has no package-only scope, second improvement step, recurring run, scheduler, automatic learning, automatic COMMANDMENTS change, deployment, or automatic merge. It does not provide an operating-system sandbox for hostile repositories.

Program-level behavioral evaluation was deferred. This release makes no claim that Jig improves agent placement, import selection, routing, proof choices, or agent behavior.

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

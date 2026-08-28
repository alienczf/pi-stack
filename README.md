# pi-stack

User-level overlay for [Pi](https://github.com/badlogic/pi-mono) plus two skills. One `install.sh` is the whole user setup. After that, fit each git repo with `jig`.

Install Pi first if you do not have it. `install.sh` does not bootstrap Pi or `/login`.

## Quickstart

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh | bash
```

That curl pipe bash is the quickstart. Same oneshot as `./install.sh` from a checkout.

## How to install

The quickstart above is `install.sh`. It copies the overlay, rewrites Cursor skill names into `$HOME/.pi/agent/skills-pstack`, merges `settings.json`, installs the required packages, rewrites `cursor/*` subagent models to `inherit`, and links `jig` into `$HOME/.local/bin`. You do not run `conform-skills.py` yourself. You do not hand-edit `skills` or the required packages.

If `PI_STACK` is unset, that uses `$HOME/.pi-stack`. The clone is skipped when that tree already has `overlay/`. If `PSTACK` is unset, it sparse-clones [pstack](https://github.com/cursor/plugins/tree/main/pstack) into `$PI_STACK/.plugins` when that tree is missing.

A checkout you already have:

```bash
PI_STACK=/path/to/pi-stack ./install.sh
```

Or run `./install.sh` from the checkout. Same thing when `PI_STACK` is unset.

To read the installer before running it:

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh
```

The installer writes `$HOME/.pi/agent/`. Skill copies get Pi-legal `name` fields. The pstack clone is not edited. `Poteto Mode` becomes `poteto-mode`. Playbooks stay reachable through symlinks. Pointing Pi at `pstack/skills` directly will warn.

Existing `settings.json` keys stay, including extra `packages` rows, `theme`, top-level `defaultModel`, and `enabledModels`. `cursor/*` entries in `subagents.defaultModel` and `subagents.agentOverrides.*.model` become `inherit`. Other pins stay. If `defaultProjectTrust` is missing, it is set to `always` so non-interactive `pi -p` can see a jig. An existing `ask` or `never` is left alone. It never writes `auth.json`, `models-store.json`, `private/`, or `sessions/`.

If `$HOME/.pi/agent/pi-goal.json` is absent, the installer creates it with unlimited automatic turns and the three-run no-progress guard. Existing files are left byte-for-byte unchanged. Start a goal with `/goal --tokens 100k <objective>` when you want a per-run token budget.

The installer writes pstack-aligned user agents into `$HOME/.pi/agent/agents/`. Same-name files override pi-subagents builtins. Dated backups of replaced dest files and of package originals go in `$HOME/.pi/agent/backups/subagents/`.

`pi` is found on `PATH`, at `$HOME/.local/bin/pi`, or under `$HOME/.local/share/pi-node`. If it is missing, overlay files may already be written and the script exits 1. Install Pi from https://pi.dev/install.sh, then rerun. Set `PI_STACK_SKIP_PACKAGES=1` to merge package names without running `pi install`.

A second run with the same inputs leaves owned files unchanged. It does not `git pull` `$HOME/.pi-stack` or `$HOME/.pi-stack/.plugins`. Update those trees yourself, then rerun install:

```bash
git -C ~/.pi-stack pull --ff-only
git -C ~/.pi-stack/.plugins pull --ff-only
./install.sh
```

To reuse trees you already have:

```bash
PI_STACK=/path/to/pi-stack PSTACK=/path/to/pstack ./install.sh
```

Do not vendor pstack skill bodies into this repo. Point at a live clone. A forked copy drifts from upstream.

Dumping the whole pstack tree is optional and not what install does. Install conforms the 14-name allowlist only. `bin/conform-skills.py --tree` is for that dump case.

## How to fit a repo

```bash
cd /path/to/repo
jig
```

Install links `$HOME/.local/bin/jig`. If that directory is not on `PATH`, run `$HOME/.local/bin/jig` or the checkout `bin/jig.sh`.

Inside Pi, run `/skill:jig` or `/jig`.

Drafts land under `.pi/jig/`. Review them. Then `--apply` copies AGENTS, tutorial, and lexicon. It does not run the rename plan.

A coordinator is just another git repo. Jig it the same way. Put target paths in that repo's `registry.md` or `siblings.tsv`. `examples/orchestrator/` is sample output of such a repo. `install.sh` does not copy it.

Do not place `AGENTS.md` in a directory that has multiple domain git repos as children. Pi still loads ancestor files. Starting Pi in a sibling repo must not load the coordinator.

Monorepo. One git repo with `packages/` is a single root. That root `AGENTS.md` is an ancestor of every package. Keep it router-only. Jig packages separately. pi-stack does not know the package names.

## Required packages

Required. Fresh installs get these. Existing rows are kept.

- `npm:pi-web-access`. Pi has no web tools. This adds `web_search` and `fetch_content`. Librarian skills are filtered out.
- `npm:pi-hashline-edit`. Replaces builtin `read` and `edit` with hash-anchored versions. Keep builtin `grep`. Do not switch to `pi-hashline-edit-pro`. That package renames the edit tools.
- `npm:pi-subagents`. Pi has no Task tool. This adds `subagent` and `subagent_wait`. Do not spawn children with bash `pi -p`.
- `npm:@narumitw/pi-goal`. This replaces the prose `/goal` prompt with settled-idle continuation plus explicit `goal_complete`, `goal_blocked`, and `goal_wait` tools. Pi-stack removes the 25-response cap for fresh configurations and keeps the three-run no-progress guard. Existing `pi-goal.json` files keep their settings.

Skip. These packages either duplicate the overlay or conflict with it.

- MCP adapter. Use `gh`, `git`, `curl`.
- Todo tool, plan-mode, pi-lens. Files and hooks, not extra tools.
- Interactive browser or CDP. `fetch_content` is enough.
- Instant Grep. Pi `grep` is ripgrep.

## How to invoke process

- `/poteto` loads poteto-mode.
- `/goal <objective>` starts a session-scoped objective. Give it a checkable exit predicate. For external waits, arrange a wake message before calling `goal_wait` alone.
- `/skill:jig` fits the current git repo.
- `/skill:cross-repo` reads the registry in the current git repo and starts one `subagent` per listed path. If there is no registry, it stops.

## Checks

```bash
bash scripts/check-overlay.sh
bash scripts/check-conform-skills.sh
bash scripts/check-subagents.sh
bash scripts/check-jig.sh
bash scripts/check-cross-repo.sh
PI_STACK_SMOKE=1 bash scripts/check-subagents.sh
```

`PI_STACK_SMOKE=1` runs a live parent `pi -p` that must call the `subagent` tool. Doctor first, then a `delegate` child. It spends tokens. The static check stays free.

Later commits use Conventional Commits such as `feat(overlay):`, `feat(jig):`, `feat(cross-repo):`, and `docs:`.

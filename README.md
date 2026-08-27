# pi-stack

User-level overlay for [Pi](https://github.com/badlogic/pi-mono) plus two skills. After install, Pi loads poteto-mode process. Then you fit each git repo with a jig.

## How to install

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh | bash
```

If `PI_STACK` is unset, that uses `$HOME/.pi-stack`. The clone is skipped when that tree already has `overlay/`. If `PSTACK` is unset, it sparse-clones [pstack](https://github.com/cursor/plugins/tree/main/pstack) into `$HOME/.pistack` when that tree is missing.

A checkout you already have:

```bash
PI_STACK=/path/to/pi-stack ./install.sh
```

Or run `./install.sh` from the checkout. Same thing when `PI_STACK` is unset.

To read the installer before running it:

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh
```

The installer writes `$HOME/.pi/agent/`. It merges `defaultTools` and `skills` into `settings.json`. It never writes `auth.json`, `models-store.json`, `private/`, or `sessions/`. Existing keys stay, including `packages`, `subagents`, `defaultModel`, and `enabledModels`.

A second run with the same inputs leaves owned files unchanged. It does not `git pull` `$HOME/.pi-stack` or `$HOME/.pistack`. Update those trees yourself, then rerun install:

```bash
git -C ~/.pi-stack pull --ff-only
git -C ~/.pistack pull --ff-only
./install.sh
```

To reuse trees you already have:

```bash
PI_STACK=/path/to/pi-stack PSTACK=/path/to/pstack ./install.sh
```

Do not vendor pstack skill bodies into this repo. Point at a live clone. A forked copy drifts from upstream.

## How to fit a repo

```bash
cd /path/to/repo
/path/to/pi-stack/bin/jig.sh
```

Put the pi-stack `bin` directory on `PATH` if you want `jig.sh` as a command. Install also writes `$HOME/.pi/agent/bin/jig` as a wrapper.

Inside Pi, run `/skill:jig` or `/jig`.

Drafts land under `.pi/jig/`. Review them. Then `--apply` copies AGENTS, tutorial, and lexicon. It does not run the rename plan.

A coordinator is just another git repo. Jig it the same way. Put target paths in that repo's `registry.md` or `siblings.tsv`. `examples/orchestrator/` is sample output of such a repo. `install.sh` does not copy it.

Do not place `AGENTS.md` in a directory that has multiple domain git repos as children. Pi still loads ancestor files. Starting Pi in a sibling repo must not load the coordinator.

Monorepo. One git repo with `packages/` is a single root. That root `AGENTS.md` is an ancestor of every package. Keep it router-only. Jig packages separately. pi-stack does not know the package names.

## How to invoke process

- `/poteto` loads poteto-mode.
- `/skill:jig` fits the current git repo.
- `/skill:cross-repo` reads the registry in the current git repo and starts one `pi -p` per listed path. If there is no registry, it stops.

## Checks

```bash
bash scripts/check-overlay.sh
bash scripts/check-jig.sh
bash scripts/check-cross-repo.sh
```

Later commits use Conventional Commits such as `feat(overlay):`, `feat(jig):`, `feat(cross-repo):`, and `docs:`.

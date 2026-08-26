# pi-stack

User-level overlay for [Pi](https://github.com/badlogic/pi-mono) plus two skills. After install, Pi loads poteto-mode process. Then you fit each git repo with a jig.

## How to install

Clone this repo, then run the installer from the checkout.

```bash
git clone https://github.com/alienczf/pi-stack.git
cd pi-stack
./install.sh
```

To read the installer before running it:

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh
```

`curl | bash` only works if the current directory is already a pi-stack checkout. The script copies files that sit next to `install.sh`.

The installer writes `$HOME/.pi/agent/`. It merges `defaultTools` and `skills` into `settings.json`. It never writes `auth.json`, `models-store.json`, `private/`, or `sessions/`. Existing keys stay, including `packages`, `subagents`, `defaultModel`, and `enabledModels`.

Set `PSTACK` if the live pstack clone is not at `/home/zhanfeng/Projects/plugins/pstack` or `$HOME/src/pstack`.

```bash
PSTACK=/path/to/pstack ./install.sh
```

A second run with the same inputs leaves owned files unchanged.

## How to fit a repo

```bash
cd /path/to/repo
/path/to/pi-stack/bin/jig.sh
```

Put `/path/to/pi-stack/bin` on `PATH` if you want `jig.sh` as a command. Install also writes `$HOME/.pi/agent/bin/jig` as a wrapper.

Inside Pi, run `/skill:jig` or `/jig`.

Drafts land under `.pi/jig/`. Review them. Then `--apply` copies AGENTS, tutorial, and lexicon. It does not run the rename plan.

## How to invoke process

- `/poteto` loads poteto-mode.
- `/skill:jig` fits the current git repo.
- `/skill:cross-repo` coordinates across two or more git repos.

## Checks

```bash
bash scripts/check-overlay.sh
bash scripts/check-jig.sh
bash scripts/check-cross-repo.sh
```

Later commits use Conventional Commits such as `feat(overlay):`, `feat(jig):`, `feat(cross-repo):`, and `docs:`.

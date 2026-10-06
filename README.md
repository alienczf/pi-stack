# pi-stack

pi-stack installs a user-level Pi overlay and pstack process skills. Jig was removed; repository principles and repeated mistakes go to pstack's `correct`, verification to `create-verification-skill` and `maintain-verification-skill`, and learning to `reflect`.

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
  packages  pi-web-access, pi-subagents
  pstack    $HOME/.local/bin/update-pstack
```

The pstack updater lives under `$HOME/.pi/agent/update-pstack/`. Its wrapper records the pi-stack checkout that installed it.

The installer preserves unrelated settings and package rows. It preserves an existing `defaultProjectTrust` value and does not add one to a fresh settings file. The shell command denies project trust for its own Pi process with explicit flags. It does not make every project trusted.

The prompt and `-y` update only when a bootstrap invocation selects the default `$HOME/.pi-stack` checkout. Running that checkout's `install.sh` directly or setting `PI_STACK` uses the selected source as-is.

The installer does not update the nested pstack clone or installed package versions. Use `update-pstack` for that independent update. After a source update, the installer installs each newly required package that is absent.

A second run with the same inputs leaves all owned file bytes unchanged. It removes stale files only from the pstack updater resource directory. It never writes `auth.json`, `models-store.json`, `private/`, or `sessions/`.

To use existing source trees, run:

```bash
PI_STACK=/path/to/pi-stack PSTACK=/path/to/pstack ./install.sh
```

Set `PI_STACK_SKIP_PACKAGES=1` only for an offline or fixture install. That option records the package settings but does not install the packages.

## Update pstack without updating pi-stack

Run `/update-pstack` inside Pi after pstack publishes an update. The procedure reviews the exact upstream diff before it changes the checkout. It stops if pstack removes a selected skill or adds a Cursor action that the Pi adapter cannot map.

Use the shell command to inspect the update plan:

```bash
update-pstack status
```

Status refuses tracked or staged pi-stack changes, then records its revision and clean status. The JSON also records both pstack revisions and versions, changed paths, and readiness. After you review one plan, apply only those revisions:

```bash
update-pstack apply \
	--expected-pi-stack <pi-stack-revision> \
	--expected-current <current-pstack-revision> \
	--expected-upstream <upstream-pstack-revision>
```

The command fast-forwards only the independent pstack Git checkout. It then reruns the selected pi-stack `install.sh`. If installation changes pi-stack `HEAD` or tracked state, the command restores the reviewed revision and fails. The same apply command can repair an interrupted installation even when the remote publishes a later revision. Set `PI_STACK` and `PSTACK` to use non-default checkouts.

`/skill:update-pstack` runs the same procedure without the `/update-pstack` prompt alias.

## Required packages

Fresh installs get these packages. Refresh removes retired npm package registrations and uninstalls their copies from Pi's managed npm directory. It preserves unrelated packages and backs up settings before removing registrations. `PI_STACK_SKIP_PACKAGES=1` skips physical package operations until the next normal install.

- `npm:pi-web-access` adds `web_search` and `fetch_content`. Librarian skills are filtered out.
- The overlay uses the built-in `read`, `edit`, and `grep` tools.
- `npm:pi-subagents` adds the `subagent` and `subagent_wait` tools. A running Pi agent does not start a child with `pi -p`.

The overlay does not install an MCP adapter, a todo tool, plan mode, pi-lens, an interactive browser, CDP, or Instant Grep. Those packages duplicate or conflict with its tools.

## Run process commands

- `/poteto` loads poteto-mode.
- `/update-pstack` reviews and installs a pstack update while keeping the pi-stack revision unchanged.

## Repository principles, verification, and learning

Use pstack's `correct` for repository principles and for a mistake that keeps coming back. Rank the fix as architecture, then types, lints, tests, and docs last. Use `create-verification-skill` to build repository verification and `maintain-verification-skill` to keep it current. Use `reflect` to turn later work into approved skill edits.

## Streams

One command installs the harness and prepares a project home:

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh | bash -s -- -y --project ~/Projects/alphalab
```

From a checkout, `./install.sh -y --project ~/Projects/alphalab` does the same thing. `-y` accepts every setup default. Without it, `pi-streams init` asks these questions on the terminal:

| Question | Default |
| --- | --- |
| Which URL do you open pi-web at? | `host` and `port` from `~/.config/pi-web/config.json`, or `http://127.0.0.1:8504` |
| Where should the project home's private remote live? | none |
| Which model should coordinators use? | `openai-codex/gpt-6-astra` |
| Which thinking level should coordinators use? | `xhigh` |

Pass `--pi-web-url`, `--remote`, `--coordinator-model`, or `--coordinator-thinking` to set an answer without the question.

The pi-web URL in `project.toml` is the address you open in a browser, which may be a tunnel. `pi-streams` runs on the pi-web host and calls pi-web at `PI_WEB_URL` when it is set, otherwise at the `host` and `port` in `~/.config/pi-web/config.json`, otherwise at `http://127.0.0.1:8504`.

Every install links `~/.local/bin/pi-streams` to this checkout's `bin/pi-streams` and installs the `stream` and `stream-kickoff` skills and the `stream` prompt. With `--project`, or on a later install once `pi-streams` has a registered home, it also installs:

- `~/.local/bin/pi-web-cli`, leaving an identical file in place and backing up a different one once
- `pi-web` when it is missing, by printing and running `npm install -g @jmfederico/pi-web`. With `PI_STACK_SKIP_PACKAGES=1` it only prints the command.
- `pi-streams-tick.timer`, two minutes after boot and then every five minutes

The timer runs without a login session only when systemd lingering is on for your user. Without `systemctl`, the installer copies the units, prints a note, and leaves scheduling `pi-streams tick` to you. The installer does not change pi-web's config. After `--project`, it runs `pi-streams doctor` and exits 1 on FAIL without removing what it wrote.

## Verify the repository

Run these commands from the pi-stack Git root. None starts a nested Pi process.

<!-- readme-checks:start -->
```bash
bash -n install.sh
bash scripts/check-overlay.sh
bash scripts/check-conform-skills.sh
bash scripts/check-update-pstack.sh
bash scripts/check-subagents.sh
bash scripts/check-cross-repo.sh
python3 -m unittest discover -s pi-streams/tests
```
<!-- readme-checks:end -->

`python3 scripts/check-readme-commands.py --execute` extracts that block and runs each command in order.

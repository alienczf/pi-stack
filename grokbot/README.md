# Watch Grok Bot repository handoffs through scheduled routines

Hand the repository unit to pi, then watch through a short self-deleting Grok Bot scheduled cron routine. Do not use OS cron. Each invocation checks durable evidence once and returns control. Pi owns code, worktrees, checks, commits, pushes, and PRs within the brief. The operator owns merges.

## Roll out the CLI and all four skills

1. Review the checkout on the PI host through the deployment's authorized access route. Keep its provider, model, and stricter host-authorization rules unchanged.
2. If the host needs the reviewed CLI, have an authorized operator install only that executable from the repository root. These are rollout instructions, not an automatic installation.

```bash
install -d "$HOME/.local/bin"
install -m 0755 bin/pi-web-cli "$HOME/.local/bin/pi-web-cli"
pi-web-cli wait --help
```

3. Copy all four directories under `grokbot/skills/` into the bot's skill library through its skill editor or importer. Replace each entire `SKILL.md`.
   - [pi-async-wait](skills/pi-async-wait/SKILL.md) contains the complete routine prompt template.
   - [pi-web-control-plane](skills/pi-web-control-plane/SKILL.md) contains session commands.
   - [orchestrate-with-pi](skills/orchestrate-with-pi/SKILL.md) routes sessions and streams.
   - [principle-hand-off-the-unit](skills/principle-hand-off-the-unit/SKILL.md) assigns repository ownership.
4. Reload the skill library. Confirm that all three routing skills link to `pi-async-wait` through their `sand-workflow:` links instead of instructing the bot to poll.
5. Before relying on scheduled checks, verify that the bot can delete or disable its own Grok Bot routine. If neither operation is available, report the limitation and do not leave an uncontrolled routine running.

The CLI requires Linux and Python 3.10 or later for its signal-based hard deadline. No particular host name, network route, or chat service is assumed.

## Schedule one bounded routine

1. Have pi create or adopt the unit's isolated worktree and session. For a campaign, hand the full brief to the owning stream coordinator.
2. Send the complete work brief and explicit done condition. After the prompt or focused steer returns accepted, create one short scheduled cron routine in Grok Bot's routine panel.
3. Copy the [full routine prompt template](skills/pi-async-wait/SKILL.md#copyable-routine-prompt). Fill the sid, authorized host access, expected artifact, optional stream path, done condition, absolute UTC deadline, routine id, and durable last-state record. Persist the assigned id before the first run.
4. Pick a supported short cadence, such as every five minutes with a deadline 30 minutes away. Return control after scheduling.

Each invocation checks cancellation and deadline first. It reads `pi-web-cli status <sid>` once and, for streams, `STATE.md`, `ALERTS.md`, and `STREAM.md` once each. It verifies the artifact against the done condition, reports only meaningful changes, saves state, and returns without loops, sleep, retries, or repeated wait calls.

A failed API request means unknown, not idle. Idle is not task proof. Delete the routine on verified done, terminal error, usage limit, cancellation, or deadline. If deletion fails, disable it and report the failure. Never extend the deadline or spawn a replacement routine. Compact before 70 percent context. Stop and report usage limits without switching provider or model.

## Use one short CLI check

Outside the routine, use `pi-web-cli wait <sid> --timeout 240` once for a short bounded check. The timeout must be finite and satisfy `0 < seconds <= 300`. Never chain calls into a long wait.

| Exit | Outcome |
| --- | --- |
| `0` | Idle, including a quiescent successful assistant turn. Not task proof. |
| `1` | API, transport, or response-contract failure. |
| `2` | Invalid arguments. Usage goes to stderr. |
| `3` | Current session error or abort. |
| `4` | Usage limit. Stop and report. |
| `124` | Overall hard deadline expired. |

Wait prints one JSON result. Successful observations include `sid`, verified-or-null `cwd`, `event`, `context_percent`, `last_assistant_line`, and UTC `ts`. Only the last nonempty assistant text line is included, capped at 280 characters. Thinking and tool arguments are excluded.

`PI_WEB_URL` selects the API endpoint. `PI_WEB_SESSIONS_DIR` selects the local metadata root, normally `~/.pi/agent/sessions/`. A missing, invalid, or conflicting sid-matching session header yields null cwd, never the CLI process's cwd.

Wait validates status, reads a bounded messages page, then reconciles status. All busy flags and queued work prevent idle. Status responses are capped at 256 KiB and message responses at 4 MiB. The hard deadline also interrupts trickled headers and bodies. Only the current assistant after the latest user contributes error evidence. A newer retry supersedes an older error. A recognized account limit in that assistant's error field takes precedence over busy status. Ordinary quota prose and generic HTTP 429 are not account limits.

Snapshot checks can miss short transitions and daemon-only errors. The routine must verify repository evidence independently of idle. Live routine permissions and scheduling still require an authorized rollout check.

## Verify the repository changes

Run from the repository root.

```bash
python3 -m unittest discover -s grokbot/tests -v
python3 scripts/check-readme-commands.py --execute
git diff --check
```

The subprocess tests use only fake loopback PI WEB servers and temporary session metadata. They do not change the installed CLI or create live routines.

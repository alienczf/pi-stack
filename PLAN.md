# Grok Bot async handoff plan

## Goal

A Grok Bot returns after it hands work to pi. A Grok Bot routine resumes the bot when the host reports a terminal session event. The bot does not wait inside a background worker or shell loop.

## Grounding

The requested worktree is `/home/alphalab/Projects/worktrees/pi-stack-grokbot-async` on `feat/grokbot-async-watch`, based on fetched `origin/main` at `3acf0f0`.

`bin/pi-web-cli` is in the current upstream repository. The installed `/home/alphalab/.local/bin/pi-web-cli` matches its existing stdlib Python command structure. No external repository change is necessary. Existing commands call PI WEB through `PI_WEB_URL`, defaulting to loopback port 8504.

The older complete skill sources are in `/home/alphalab/Projects/worktrees/pi-bot-design-review/skills/`. The current `pi-bot` checkout has a newer handoff policy that no longer contains the requested polling text. Use the older complete files to preserve the named skills' intent, remove deployment-specific assumptions, and replace their polling workflow.

## Data shape and proposed boundaries

Normalize the observed PI WEB contract at one boundary into a session observation with its session id, cwd, activity state, context percent, and latest assistant text or error. Represent terminal outcomes as named events. Both `wait` and `notify` consume that classifier so they agree about idle, error, and usage limit. Do not infer idle from missing fields or classify an API failure as successful completion.

Prefer extending the existing standalone stdlib Python executable over adding a dependency. Compare a status-and-messages watcher with an event-stream watcher before implementation. Choose after tracing the installed server, not by guessing response shapes.

`wait` uses a monotonic deadline of at most 300 seconds and bounds each request by remaining time. It prints one small JSON result and uses distinct documented outcome codes.

`notify` returns promptly with a PID or unit and a private log path. A detached host process owns observation and delivery, not a Grok Bot worker. The watcher delivers one small payload and exits after bounded backoff. A private key file supplies the entire header value so raw keys and prefixed schemes are both possible. Header name is configurable. Do not assume Grok Bot's auth scheme. Reject unsafe file modes and redirects that could leak a key. Keep the webhook URL out of output too.

The default and `--once` must have explicit one-payload semantics. Each spawn or steer requires a new watcher. State the arming behavior for an already-idle session and the limitation that status snapshots can miss short transitions.

## Design rubric

1. Matches real PI WEB status and message shapes, including compaction, bash activity, queued work, and usage-limit errors.
2. Keeps waits and retry lifetimes bounded without provider changes.
3. Does not disclose webhook URL or key in logs, argv, exceptions, or redirects.
4. Tests commands as subprocesses against fake servers, including real detachment.
5. Keeps installation and maintenance simple and all Grok Bot instructions generic.

## Verification plan

Run stdlib unit and integration tests through the actual executable with fake PI WEB and webhook HTTP servers. Assert terminal outcomes, request deadline, error precedence, payload limits, private permissions, retry behavior, process exit, and no secret output. Run existing repository checks that do not mutate host configuration. Review every new SKILL.md for full copyability and actionable routine instructions. No live webhook delivery or deployed skill change is in scope.

## Setup question

ZF must confirm the Grok Bot webhook header name and full header value format from the routine panel on first setup. The operator enters the URL and key directly into private files on the PI host. The bot never reads those values.

## Decision trail

- HTTPS Git uses the existing GitHub credential helper. The repository's existing SSH remote configuration remains untouched.
- No merge is authorized.
- Two scouts independently traced PI WEB status/messages and WebSocket behavior. Both prefer the existing Python executable with status/message reconciliation. WebSocket events have no replay and still require HTTP reconciliation.
- The workflow tool returned launch receipts rather than awaiting its children. The parent halted later phases and recovered the original paused tasks sequentially through their retained run handles. No implementation began before scout findings.
- Baseline `python3 scripts/check-readme-commands.py --execute` passed every documented check, including all 105 pi-streams tests, before implementation.
- Snapshot observation cannot catch daemon errors emitted only as ephemeral `session.error` events. Document this limit. Do not imply that an idle event proves task success.
- Status has no cwd. Resolve cwd only from verified sid-matching local session metadata, with a configurable session root and null for unavailable metadata.
- A newly created empty session is already idle. Register notify after the accepted work prompt or steer. Report an already-terminal first observation rather than wait for a busy transition that may have completed before arming.
- The cross-judge selected candidate A before implementation resumed. The single writer read the final cross-judge report and implemented the reconciled contract. No implementation edits occurred while the design gate was paused.

## Design alternatives and synthesis

| Criterion | A, shared Python snapshots | B, Node WebSocket helper |
| --- | --- | --- |
| API and outcome contract | Validated status plus persisted assistant outcomes. | Live events plus HTTP reconciliation. |
| Lifetimes | One hard observation deadline and one delivery deadline. | Connection, reconnect, reconciliation, and delivery deadlines. |
| Secrets | Descriptor checks, private file logs, and file-only credential arguments. | Additional process and packaging boundary to audit. |
| Verification | Existing executable tested as a subprocess. | Helper and executable each need lifecycle tests. |
| Maintenance | One stdlib executable, unchanged installer integration. | New installed Node helper without durable event replay. |

Choose A. Keep B's warnings about bootstrap gaps and ephemeral daemon errors, not its helper. The host user manager reports `running` and systemd 255 is installed. Use only transient systemd user services, matching existing PI host services. Missing user-manager access is an explicit launch failure rather than a silent nohup fallback.

## Implemented contract

`AssistantOutcome` stores the current assistant's timestamp, stop reason, error evidence, and last text line. `SessionObservation` stores verified sid, nullable cwd, three activity flags, pending count, context percent, and that outcome. A shared classifier serves both commands.

Status, messages, and status reconciliation avoids declaring quiescence across a visible activity or message-count change. It does not compare status counts with projected history lengths. The message response has its own 4 MiB byte cap. Only the latest assistant after the latest user is current. A newer assistant supersedes an earlier retry failure.

A recognized account limit in current error evidence wins over busy activity. Generic errors and aborts become terminal only after streaming, compaction, bash, and queued work stop. A quiescent `stop` becomes `done` when selected, otherwise `idle`. `length` and `toolUse` are not `done`. Errors and usage limits stop observation even when filtered out, without a webhook POST in that case.

Wait accepts a finite timeout greater than zero and at most 300 seconds. Exit codes are 0 for idle, 1 for API or contract failures, 2 for arguments, 3 for error or abort, 4 for usage limit, and 124 for timeout. `SIGALRM` enforces the total monotonic deadline even during trickled HTTP responses.

Notify defaults to one payload, a 24-hour observation deadline, and a separate two-minute delivery deadline. `--once` is an explicit alias. The frozen payload retries at most five times with 1, 2, 4, and 8-second backoffs for transport, 429, and 5xx failures. Redirects and permanent client errors stop delivery. The routine deduplicates by sid, event, and timestamp.

Both credential files use `O_NOFOLLOW`, descriptor checks for regular type, effective-user ownership, and exact 0600 mode, then bounded single-line reads. The key is the complete header value. Header validation rejects framing names. Systemd receives file paths, not credential values. Logs are private and contain only fixed labels or HTTP status codes. Neither HTTP client uses environment proxies or follows redirects.

Cwd comes only from bounded local headers with matching session type and id. `PI_WEB_SESSIONS_DIR` overrides the metadata root. Unknown or conflicting cwd is null. The watcher's process cwd is never substituted.

## Verification record

The initial 26 CLI integration tests passed. The final `python3 -m unittest discover -s grokbot/tests -v` run passed all 29 tests with no skips. The detached tests used the real active systemd user manager and fake HTTP endpoints. They verified survival after launcher exit, private argv, successful exit, cancellation, frozen retry bodies, five-attempt exhaustion, redirect rejection, permanent client failures, secret-file validation, error classification, response-byte caps, and trickled-response deadlines.

`python3 scripts/check-readme-commands.py --execute` passed every documented root check, including all 105 pi-streams tests. `python3 -m py_compile bin/pi-web-cli grokbot/tests/test_pi_web_cli.py` and `git diff --check` passed. An explicit metadata and link check passed for all four skills, including the under-500-line limit and the absence of named-deployment assumptions. Comparing the installed CLI against the unchanged HEAD version confirmed that the live executable was not modified. The staged diff is empty.

Manual cleanup kept the original commands unchanged and added no phase-narrating comments. The installed `control-cli` and `deslop` leaves are unavailable. Direct subprocess tests and manual diff review replace those checks. The independent reviewer passed the complete diff with no actionable correctness, security, documentation, or comment findings. The parent also reran all 29 CLI tests without skips and all documented root checks, including 105 pi-streams tests. No test watcher units remained.

GitHub CLI is the forge because no Origin executable is available. Fetch and push use the explicit HTTPS repository URL and the existing host credential helper. The remote's SSH URL stays unchanged. The initial `remote.origin.url` command override did not replace Git's first configured URL, so the parent repeated the fetch with an explicit HTTPS URL before publication.

## PR handoff

https://github.com/alienczf/pi-stack/pull/31 targets `main` from `feat/grokbot-async-watch`. GitHub reports the PR open and ready, with no merge commit or merge timestamp. The implementation and rollout are separate ordered commits. This decision record and the completed TODO form the final handoff commit. No deployment or merge is authorized by this record.

## Remaining limits

- ZF must confirm the real Grok Bot auth header and format, and the routine's delete or disable permission. No real webhook was provisioned or called.
- Detached tests need a systemd user manager. They skip without one. The host run must report whether they executed.
- Snapshot observation can miss short transitions and ephemeral daemon-only errors. Idle and done do not prove a repository goal or an entire stream completed.
- Reboot, an API failure, or exhausted delivery can prevent the wake. Durable deadlines and the cron fallback provide operator-visible recovery instructions, not an exactly-once delivery guarantee.
- One watcher per unit is an operating rule, not a cross-launch lock. Cancel an obsolete watcher before rearming after a steer.
- Descriptor ownership checks are implemented. A foreign-owned 0600 fixture cannot be created by this unprivileged test user, so that case lacks a direct fixture test.

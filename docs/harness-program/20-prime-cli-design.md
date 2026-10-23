# Prime CLI for pi-stack

Track 2. Written before implementation on 2026-10-23. This file remains uncommitted for Grok Bot to collect. Code belongs only to `feat/prime-cli` in `/home/alphalab/Projects/worktrees/pi-stack-prime-cli`, based on `3acf0f01e6084a317b89cef3a86f4781e60877cf`.

## Goal and boundary

Grok Bot and pi-stack callers can change the selected CLI backend without changing command arguments or the JSON fields they consume. No GUI, new workflow engine, or stream migration is included. Under P2, streams-on-prime waits for track 1 to land and for this branch to rebase onto that main.

The full completion predicate is an offline behavior suite plus real-server command checks using `openai-codex/gpt-6.1-sol`. Control-plane success alone does not prove inference, steering delivery, compaction, or interactive-answer parity. Missing credentials and missing upstream capabilities remain explicit failures.

The marked gap in `00-brief-verbatim.md` stays unknown. The old prime-stack kickoff restrictions and numerical-cap question are historical context, not authority for this separately authorized task. No coordinator or existing stream is changed.

## Evidence and runtime model

The source checkout is `/home/alphalab/Projects/prime-agent`, initially at `71beca9478f552dc6fc898bba9685f9ce00515cf`. The real-server target is upstream stable `v0.10.1`, source revision `8aac8692456c00c01d4e53e60e6d3347a3506559`. Both declare daemon protocol 7, schema 30. The adapter targets the public supervisor socket, not private worker framing or the stdin-only RPC mode.

Prime uses one long-running supervisor and one worker per resident session. Clients disconnect without ending resident sessions. The persistent `sessionId` and runtime `activeSessionId` are distinct. The compatibility `id` is the active selector returned by `create`. The daemon owns rebindings and durable transcripts. The CLI does not create another session registry.

Each connection receives `daemon_hello`. Commands are LF-delimited JSON envelopes with `type`, a unique `id`, `protocol`, and `command`. Replies have `type: response`, matching `id`, `command`, `success`, and optional `data` or `error`. Events may arrive before the reply. The client validates the hello and reply and ignores unrelated events, rather than interpreting the first received line as the result. No operation is automatically retried after a timeout or disconnect because acceptance may be uncertain.

Source anchors under the upstream checkout:

- `crates/pa-types/src/daemon/mod.rs` defines the protocol identity.
- `crates/pa-types/src/daemon/command.rs` defines create, prompt, queues, and lifecycle command shapes.
- `crates/pa-daemon/src/protocol.rs` defines supervisor envelopes and response constructors.
- `crates/pa-daemon/src/supervisor/clients.rs` sends the hello and multiplexes events and responses.
- `crates/pa-daemon/src/worker/create.rs` consumes top-level `cwd`, `provider`, `model`, and `thinking`.
- `crates/pa-daemon/src/worker/summary.rs` builds `get_connection_state`, including context usage.
- `crates/pa-daemon/src/worker/input.rs` distinguishes prompt admission, steering, and follow-up queues.
- `crates/pa-daemon/src/worker/commands.rs` implements messages, queues, abort, and kill. Kill durably records archived state and closes children.
- `crates/pa-daemon/src/session_commands.rs` handles `/compact` before the model loop.
- `crates/pa-core/src/models/` and `crates/pa-core/src/auth/` own catalog resolution and provider credentials.

The installed `~/.local/bin/pi-web-cli` matches the repository's `bin/pi-web-cli`. That client defines the compatibility envelopes below. Its numeric `status` field is retained as an HTTP-style compatibility code even though Prime's wire protocol is not HTTP.

## Required caller contract

The required operations are cwd-scoped list, spawn with cwd, prompt from argv or stdin, explicit steer and follow-up, live status, transcript messages, command discovery, model selection, thinking-level selection, abort, stop, queue clear, archive, and answers to interactive questions.

The status contract includes `id`, `cwd`, `isStreaming`, `pendingMessageCount`, `contextUsage`, `model`, `thinkingLevel`, and numeric `cost`. `pi-streams/engine/threads.py:_coordinator_state` rejects a status without numeric cost. `contextUsage` is Prime's measured or estimated `{tokens, contextWindow, percent}`, or null when unavailable. Null is not zero usage. Pending count comes from authoritative queue arrays, not a local counter. Cost comes from `get_session_stats`. Status spans three daemon requests and is not an atomic snapshot.

The JSON envelopes remain:

```json
{"ok":true,"status":200,"sessions":[]}
{"ok":true,"status":201,"session":{"id":"active-selector","cwd":"/work"}}
{"ok":true,"status":200,"result":{"accepted":true}}
{"ok":true,"status":200,"session":{"id":"active-selector","isStreaming":false,"pendingMessageCount":0,"contextUsage":null}}
{"ok":true,"status":200,"commands":[]}
{"ok":true,"status":200,"result":{"messages":[]}}
```

Other successful verbs use `{ok,status,result}`. Errors use `ok:false`, a nonzero exit, and a stable error code. Unsupported behavior uses compatibility status 501. Transport failure must never return `ok:true`. Command acceptance is not model completion or proof that a steer was acted upon.

## Command mapping

Every row is LAYER 3. The CLI executes the translation on every invocation. A repository schema and tests support the contract, but cannot perform the live protocol operation.

| Command | Pi semantics and JSON | Prime equivalent | Gap | Shim |
| --- | --- | --- | --- | --- |
| `list --cwd PATH` | Cwd-scoped roster in `sessions` | `list` with `cwd` | Different row identifiers | Preserve native row data and add compatible `id` and `cwd`. Exclude archived rows. |
| `spawn PATH` | Resident session in `session`, including `id` | `create` with top-level `cwd`, `lifecycle: resident` | Active and durable IDs differ | Return active ID as `id`. Optional environment model selection is sent during create. |
| `prompt SID [TEXT]` | Accept argv or stdin, `result.accepted` | `prompt` with `activeSessionId` and `message` | Prime can suspend admission after abort | Send an explicit follow-up behavior for ordinary input so a new user prompt resumes a stopped queue without replaying a failed request. |
| `prompt SID --steer` | Steer an active turn | `steer` with `activeSessionId` and `message` | Acknowledgement is queue admission, not completion | Normalize successful admission to `accepted:true`. Keep native acknowledgement fields. |
| `prompt SID --follow-up` | Deliver after the current turn | `follow_up` with `activeSessionId` and `message` | Same acknowledgement distinction | Normalize admission and preserve lane semantics. |
| `status SID` | `session.isStreaming`, pending count, context usage, numeric cost | `get_connection_state`, `get_queue`, and `get_session_stats` | No single Pi-shaped response | Add ID, count both `steering` and `followUp`, and use native stats cost. Preserve unknown context as null. |
| `commands SID` | Array in `commands` | `get_commands` | Prime command discovery differs from Pi extensions | Unwrap `data.commands`. Do not pretend Pi-only tools or skills are installed. |
| `stop SID` | Stop active work and clear pending input while retaining the session | `abort_and_clear_queue` | Native command differs | Keep the resident session. Do not use daemon shutdown. |
| `abort SID` | Abort active work without clearing queued messages | `abort` | Prime suspends queue admission | Preserve suspension. A later explicit prompt resumes it. |
| `queue-clear SID` | Clear pending input | `clear_queue` | Reply uses native lane fields | Preserve those fields under `result`. |
| `archive SID` | Remove the live session while retaining its transcript | `kill` | Kill also cancels session schedules and closes its children | Return explicit archived result after native success. Never delete transcript files. |
| `messages SID` | `result.messages` with role and content blocks | `get_messages` | Saved/windowed history can differ | Preserve message data. Do not manufacture Pi tool rows. |
| `model SID PROVIDER/ID` | Select model, result envelope | `set_model` with provider and modelId | Available catalog and auth govern selection | Validate selector, forward selection, and return upstream errors. No fallback model. |
| `thinking-level SID LEVEL` | Select reasoning level | `set_thinking_level` with `level` | Prime may clamp unsupported levels | Preserve native behavior. Read status to observe effective level. |
| `answer SID ASK_ID QUESTION_ID TEXT` | Submit correlated interactive answer | No equivalent found in public daemon command union | Pi Web's ask registry has no native Prime counterpart | Return explicit unsupported error. Sending arbitrary prompt text is not an answer implementation. |

`prompt SID '/compact ...'` uses Prime's native session slash command. It is not a separate pi-web-cli verb. Future stream integration needs this path and `isCompacting`, without adding an automatic 252k policy here. Track 1 owns that policy.

## Competing designs and chosen data shape

| Candidate | Structure | Benefit | Cost and decision |
| --- | --- | --- | --- |
| A. Direct socket adapter | Small Python standard-library transport plus command adapter and thin executables | No extra daemon, port, dependency, auth database, or duplicated lifecycle state | Tied to a versioned upstream wire protocol. Chosen because the public supervisor protocol already carries the required operations. |
| B. Local HTTP gateway | Persistent process translating Pi-shaped HTTP requests into Prime socket commands | Existing HTTP-only callers could keep their URL client | Adds another service, service auth, request lifecycle, and shared session state without fixing missing interactive questions. Rejected for this track. |

The central data shape is a command envelope and its correlated response. A command registry owns simple verb translations. Explicit functions own the composite list, spawn, prompt, status, and command-discovery projections. `PrimeClient.request(command)` owns the socket connection, hello validation, LF framing, correlation, and errors. CLI parsers validate external arguments. There is no event cache, background polling service, workflow engine, or durable shim state.

Model the Domain shaped this command/response boundary. Build the Lever requires the committed offline and real-server check scripts. Prove It Works means the real-daemon and inference verdicts are separate.

## Network access and authentication

LAYER 3. `prime-cli-remote` runs the host CLI through `options-01-ssh` over the existing userspace Twingate path. It mirrors pi-web-cli-remote's argument and stdin contract. SSH handles transport authentication. Prime retains owner-only Unix socket access. A stronger codebase or test layer cannot authenticate a live remote caller.

The selected route is `Grok Bot -> options-01-ssh -> host prime-cli -> supervisor Unix socket`. This achieves SSH-protected network access without exposing unauthenticated HTTP or raw TCP. An SSH-forwarded Unix socket is possible but creates local socket lifecycle and path issues that remote execution avoids. No TUN, raw scp, sudo, or system service is needed. The wrapper does not restart Twingate on every call, following G15.

LAYER 3. `PRIME_AGENT_DAEMON_SOCKET` selects the local socket, otherwise the upstream per-user `/tmp/prime-agent-UID/daemon.sock` path applies. The client never starts or shuts down a daemon implicitly. Operators must select the intended server. There is no CLI token flag or credential import. Provider auth remains Prime-owned and absent from git, argv, and output.

The stable release archive is checksum-verified against its published manifest and extracted outside git. The live check uses an isolated agent directory and dedicated socket so it cannot attach to or shut down an existing Prime daemon. The same-user trust boundary is explicit. A Unix socket is not a sandbox against that user.

## Backend-neutral CLI and skill contract

LAYER 3. `agent-cli --backend pi|prime <command> ...` selects the backend. `PI_STACK_BACKEND` supplies an opt-in default, with Pi retained as the default for current installations. `prime-cli` is the direct Prime name. The dispatcher forwards argv and stdin, stdout, stderr, and exit status without shell interpolation. Deterministic dispatch belongs in executable code, not an always-on rule or a skill.

LAYER 1. The adjacent CLI reference names stable envelopes, ID rules, command semantics, and unsupported behavior. These data shapes guide both implementations and tests. A stronger layer is not available.

LAYER 2. Subprocess tests exercise every verb against an in-process Unix-socket fixture, including interleaved events, malformed responses, unknown sessions, framing, stdin, quoting, protocol mismatch, errors, and model selector validation. The real-server script exercises only sessions it creates. These checks fail on wrong results rather than trusting source inspection.

LAYER 5. Existing skills can later replace the literal binary name with `agent-cli --backend prime`, while retaining cwd, prompt modes, session identifiers, response keys, and native `/compact`. They must treat null context as unknown, `accepted` as admission only, and unsupported answers as missing capability. A skill cannot repair a missing daemon API. This track documents that contract but does not edit stream, cross-repo, or loop behavior before P2.

LAYER 3. Packaging follows pi-stack's `bin/` tools and installer-managed user links. Installing these small clients does not install Prime, change provider credentials, start a service, or select a different stream backend. Tests cover isolated installation without running the full host installer.

## Caladan, non-blocking

The source is pi-bot `caladan` at `bb39dc0fc61d514b590f5d5de82ba7b603ec06a5`, not a pi-stack branch. It remains read-only. The open question is whether its later Prime adaptation stays in pi-bot or is intentionally transplanted. The default here is to leave it in pi-bot and expose a swappable CLI contract. No backup, rebase, branch mutation, or push is part of track 2.

Detailed caller findings are added after the independent read-only inspection. Nothing in the CLI transport requires a Caladan-specific branch.

## Verification

Not yet complete. This section records actual commands and observations as execution proceeds, not predicted transcripts.

Initial observations on options-01:

```text
prime-agent v0.10.1 archive SHA-256 verified
prime-agent executable SHA-256 1fbb506f54a8e9af1f0d123e521d13a765bce34883707c69656f06d5951b314c
/tmp/prime-t2.3qhjos6h/prime-agent --version -> 0.10.1
stable bundled model catalog contains gpt-6.1-sol -> false
~/.prime/agent/auth.json -> absent, existence checked only
provider environment variable names -> none found
```

No credential file was opened, copied, or changed. Source inspection found that `resolve_cli_model` accepts an unknown model ID within a known provider and keeps that custom ID. Catalog absence is therefore not itself a spawn blocker. Native `set_model` still resolves through the available catalog, so selecting a custom ID may require a model definition.

The owned real supervisor is running in tmux session `prime-cli-t2-01a16656`, PID `3133971`, using `/tmp/prime-t2.3qhjos6h/agent` and `/tmp/prime-t2.3qhjos6h/daemon.sock`. No system service was installed. A raw-protocol baseline check, before exercising the new client, returned:

```text
daemon_hello -> prime-agent.daemon version=7 schemaRevision=30 appVersion=0.10.1
list cwd=/tmp/prime-t2.3qhjos6h/work -> success=true sessions=[]
```

This proves the real server and protocol identity, not the CLI or model. The isolated nonsecret settings disable provider failover and quota parking. Prime enables provider failover by default, so this override is necessary for the program's no-switch rule. Neither credentials nor a resource budget is added.

The host identifies itself as `hpc180-options-01`. Neither `options-01-ssh` nor `pi-web-cli-remote` is on its PATH. Off-host wrapper verification cannot be claimed from this host alone.

## Decisions

1. Use the public supervisor JSONL socket and stable v0.10.1 for verification. The wire is explicit and the release is reproducible.
2. Choose the direct adapter over a new HTTP gateway. The gateway adds a service without closing the real API gaps.
3. Use active session selectors as compatibility IDs. Prime owns the active-to-durable binding.
4. Keep SSH remote execution rather than exposing a network listener. Existing machine access already provides authentication.
5. Keep credentials Prime-owned. This task does not authorize importing Pi or Codex credentials or running a login flow.
6. Preserve unknown context as null and distinguish admission from completion. Fabricated zero usage or delivery success would reproduce corpus F5 and F8.
7. Map archive to native kill and stop to abort-and-clear. These preserve the difference between ending a resident session and stopping its current work.
8. Return unsupported for interactive answers until Prime has a correlated question API or an explicitly scoped question extension. Plain prompt injection would be false parity.
9. Keep Pi as the neutral dispatcher's default. P2 forbids silently porting existing streams now.
10. Leave Caladan in its own repository and defer its migration. Its cross-repository destination is non-blocking for this CLI.
11. Use one parent writer with read-only research lanes. Separate Before Serializing Shared State keeps shared docs and branches free of concurrent writes.
12. Do not switch models for skill-prescribed cross-model review. The program's same-model constraint takes precedence. Independent same-model research and direct verification are the available checks.
13. Reuse the still-running upstream investigator as the single implementation writer after writing this design. Its costly source context is directly needed for the adapter. The parent owns only artifact 20 and isolated live verification during that write phase.
14. Disable Prime provider failover and quota parking in the owned live-check configuration. Upstream otherwise enables failover, which conflicts with the program's stop-and-report rule.
15. Include numeric cost from native session statistics. Actual pi-stack code requires it even though the abbreviated task list did not name it.

## Gaps

- Interactive `answer` has no native correlated-question API in the inspected daemon union. This is a parity gap, not a completed shim.
- The requested model is absent from the stable bundled catalog, but create-time custom-ID resolution can preserve it. Prime credentials are absent on this host. Live checks must determine the exact inference failure without changing provider.
- Remote wrapper execution from the Grok Bot machine requires that machine and its authenticated `options-01-ssh`. Local wrapper quoting tests are not off-host evidence.
- Stream ticks, coordinator compaction policy, skill installation into Prime, and Caladan adaptation are outside this implementation under P2.
- Prime's executable Python skills are not automatically equivalent to Pi's Markdown process skills. Command discovery must report only what the target runtime actually loads.

## Parity checklist

Initial state before implementation. The final revision records tested status rather than intent.

| pi-web-cli command | State | Evidence |
| --- | --- | --- |
| list | missing | Implementation pending. |
| spawn | missing | Implementation pending. |
| prompt, argv and stdin | missing | Implementation pending. |
| prompt --steer | missing | Implementation pending. |
| prompt --follow-up | missing | Implementation pending. |
| status | missing | Implementation pending. |
| commands | missing | Implementation pending. |
| stop | missing | Implementation pending. |
| abort | missing | Implementation pending. |
| queue-clear | missing | Implementation pending. |
| archive | missing | Implementation pending. |
| messages | missing | Implementation pending. |
| model | missing | Implementation pending. |
| thinking-level | missing | Implementation pending. |
| answer | missing | No upstream correlated-question API found. |

# Prime CLI for pi-stack

Track 2. Written before implementation on 2026-10-23. This session leaves its design edits uncommitted for Grok Bot to collect. Code belongs only to `feat/prime-cli` in `/home/alphalab/Projects/worktrees/pi-stack-prime-cli`, based on `3acf0f01e6084a317b89cef3a86f4781e60877cf`.

Final result is **BLOCKED**, not full parity. The CLI implementation is locally committed at `bccf159aed76c121fd9df133cedb515b8bd38dd3`. Real Prime returned `No API key found for openai-codex.` Model attempts stopped at that refusal. No credentials, provider, existing stream, or other branch were changed. No push was made.

## Goal and boundary

Grok Bot and pi-stack callers can change the selected CLI backend without changing command arguments or the JSON fields they consume. No GUI, new workflow engine, or stream migration is included. Under P2, streams-on-prime waits for track 1 to land and for this branch to rebase onto that main.

The full completion predicate is an offline behavior suite plus real-server command checks using `openai-codex/gpt-6.1-sol`. Control-plane success alone does not prove inference, steering delivery, compaction, or interactive-answer parity. Missing credentials and missing upstream capabilities remain explicit failures.

The marked gap in `00-brief-verbatim.md` stays unknown. The old prime-stack kickoff restrictions and numerical-cap question are historical context, not authority for this separately authorized task. No coordinator or existing stream is changed.

## Evidence and runtime model

The source checkout is `/home/alphalab/Projects/prime-agent`, initially at `71beca9478f552dc6fc898bba9685f9ce00515cf`. The real-server target is upstream stable `v0.10.1`, source revision `8aac8692456c00c01d4e53e60e6d3347a3506559`. Both declare daemon protocol 7, schema 30. The adapter targets the public supervisor socket, not private worker framing or the stdin-only RPC mode.

Prime uses one long-running supervisor and one worker per resident session. Clients disconnect without ending resident sessions. The persistent `sessionId` and runtime `activeSessionId` are distinct. The compatibility `id` is the durable `sessionId` returned by `create`. Native `activeSessionId` remains a separate field. The daemon owns rebindings and durable transcripts. The CLI does not create another session registry. This revises the initial active-selector choice after review showed that a fresh CLI connection does not receive the rebind event needed to validate an old active selector.

Each connection receives `daemon_hello`. Commands are LF-delimited JSON envelopes with `type`, a unique `id`, `protocol`, and `command`. Replies have `type: response`, matching `id`, `command`, `success`, and optional `data` or `error`. Events may arrive before the reply. The client validates the hello and reply and ignores unrelated events, rather than interpreting the first received line as the result. No operation is automatically retried after a timeout or disconnect because acceptance may be uncertain.

Source anchors under the upstream checkout:

- `crates/pa-types/src/daemon/mod.rs` defines the protocol identity.
- `crates/pa-types/src/daemon/command.rs` defines create, prompt, queues, and lifecycle command shapes.
- `crates/pa-daemon/src/protocol.rs` defines supervisor envelopes and response constructors.
- `crates/pa-daemon/src/supervisor/clients.rs` sends the hello and multiplexes events and responses.
- `crates/pa-daemon/src/supervisor/worker_lifecycle.rs:105-211` consumes public `create.config.cwd`, `provider`, `model`, and `thinking`. It converts those fields into the top-level worker payload consumed by `worker/create.rs`. The client must not send worker payloads directly to the supervisor.
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
{"ok":true,"status":201,"session":{"id":"durable-session-id","cwd":"/work"}}
{"ok":true,"status":200,"result":{"accepted":true}}
{"ok":true,"status":200,"session":{"id":"durable-session-id","isStreaming":false,"pendingMessageCount":0,"contextUsage":null}}
{"ok":true,"status":200,"commands":[]}
{"ok":true,"status":200,"result":{"messages":[]}}
```

Other successful verbs use `{ok,status,result}`. Errors use `ok:false`, a nonzero exit, and a stable error code. Unsupported behavior uses compatibility status 501. Transport failure must never return `ok:true`. Command acceptance is not model completion or proof that a steer was acted upon.

## Command mapping

Every row is LAYER 3. The CLI executes the translation on every invocation. A repository schema and tests support the contract, but cannot perform the live protocol operation.

| Command | Pi semantics and JSON | Prime equivalent | Gap | Shim |
| --- | --- | --- | --- | --- |
| `list --cwd PATH` | Cwd-scoped roster in `sessions`, including saved and archived rows | `list` with `cwd` and `all:true` | Different row identifiers and path key | Preserve native data, map `sessionFile` to `path`, preserve timestamps and message count, and derive `archived` from lifecycle. |
| `spawn PATH` | Resident session in `session`, including `id` | `create` with `config.cwd` and `lifecycle: resident` | Active and durable IDs differ | Return durable `sessionId` as `id`, retain `activeSessionId` separately, and verify cwd and explicit model identity. Optional model settings go inside `config`. |
| `prompt SID [TEXT]` | Accept argv or stdin, `result.accepted` | `prompt` with `activeSessionId` and `message` | Prime can suspend admission after abort | Send an explicit follow-up behavior for ordinary input so a new user prompt resumes a stopped queue without replaying a failed request. |
| `prompt SID --steer` | Steer an active turn | `steer` with `activeSessionId` and `message` | Acknowledgement is queue admission, not completion | Normalize successful admission to `accepted:true`. Keep native acknowledgement fields. |
| `prompt SID --follow-up` | Deliver after the current turn | `follow_up` with `activeSessionId` and `message` | Same acknowledgement distinction | Normalize admission and preserve lane semantics. |
| `status SID` | `session.isStreaming`, pending count, context usage, numeric cost | `get_connection_state`, `get_queue`, and `get_session_stats` | No single Pi-shaped response | Add ID, count both `steering` and `followUp`, and use native stats cost. Preserve unknown context as null. |
| `commands SID` | Array in `commands` | `get_commands` | Prime command discovery differs from Pi extensions | Unwrap `data.commands`. Do not pretend Pi-only tools or skills are installed. |
| `stop SID` | Close runtime without archival, `{ok,status,result:{stopped:true}}` | `abort_and_clear_queue` is a work-stop approximation | No safe public per-root stop-without-archive equivalent found | Return `{ok,status,result:{accepted:true,runtimeClosed:false,semantics:...}}`. This is an explicit payload and lifecycle difference, not exact parity. |
| `abort SID` | Clear pending input and abort current operations, `{ok,status,result:{aborted:true}}` | `abort_and_clear_queue` | Prime's plain `abort` preserves queues and is not equivalent | Clear queues and return removed native lanes under `result`. A later explicit prompt resumes suspended admission. The result payload differs from Pi's marker. |
| `queue-clear SID` | Clear pending input | `clear_queue` | Reply uses native lane fields | Preserve those fields under `result`. |
| `archive SID` | Reject active work, then retain transcript, `{ok,status,result:{archived:true}}` | Work check followed by `kill` | Native kill does not itself reject busy work and also closes children and cancels schedules | Inspect work and queues while holding a native delivery pause, reject busy state, then kill. Return `archived:true` plus `preflightAtomic:false`. Never delete transcripts. |
| `messages SID` | `result.messages` with role and content blocks | `get_messages` | Saved/windowed history can differ | Preserve message data. Do not manufacture Pi tool rows. |
| `model SID PROVIDER/ID` | Select model, result envelope | `set_model` with provider and modelId | Available catalog and auth govern selection | Validate selector, forward selection, and return upstream errors. No fallback model. |
| `thinking-level SID LEVEL` | Select reasoning level | `set_thinking_level` with `level` | Prime may clamp unsupported levels | Preserve native behavior. Read status to observe effective level. |
| `answer SID ASK_ID QUESTION_ID TEXT` | Submit `{askId,answers:[{id,values:[],otherText}]}`, return `{ok,status,result}` | No equivalent found in public daemon command union | Pi Web's ask registry has no native Prime counterpart | Return `{ok:false,status:501,error:unsupported,...}`. Sending arbitrary prompt text is not an answer implementation. |

`prompt SID '/compact ...'` uses Prime's native session slash command. It is not a separate pi-web-cli verb. Future stream integration needs this path and `isCompacting`, without adding an automatic 252k policy here. Track 1 owns that policy.

The installed PI WEB implementation, not just its thin client, supplies the lifecycle oracle. `dist/server/sessions/piSessionService.js:1767` clears queues during abort. Line 1793 closes the active runtime during stop. Line 1519 rejects active work before archive. `closeActive` at line 1992 disposes runtime without adding archive state. Initial assumptions that abort preserves Pi queues and stop retains the Pi runtime were wrong and are superseded below.

The caller audit also found these required fields and non-CLI dependencies:

- `sessions[].messageCount`, `archived`, `modified`, and `path` drive recovery, coordinator selection, and transcript inspection in `pi-streams/engine/threads.py` and `tick.py`.
- `status.queuedMessages` carries exact `{kind:steer|followUp,text}` records, including duplicate texts. Current tick clears and replays that queue.
- Native `get_queue` can contain display previews for internal Prime input, not replayable raw text. `sessionActions.rlmChildStatus` and `injectedPrompts` identify some internal classes. Ordinary human prompts can retain exact text, but arbitrary internal queue replay remains a gap unless the adapter can prove or reject it.
- `pendingAsk.askId` and question text trigger human-decision events. A null ask alongside an unsupported-answer capability is honest absence, not full question parity.
- `pi-streams/engine/piweb.py:18` runs the checkout's `bin/pi-web-cli` with Python. Changing a PATH executable alone does not port streams.
- `pi-streams/engine/sessionlog.py` expects native JSONL assistant-message entries at the listed host transcript path. A gateway cache is not a replacement transcript.

LAYER 3. Prime's `acquire_session_input_pause` and `release_session_input_pause` offer a native connection-owned delivery-pause lease for archive checks. This belongs in the runtime because code layout and tests cannot pause live queued delivery. The lease does not exclude other producers or already running work, so the client reports `preflightAtomic:false` rather than claim atomic archive-if-idle behavior.

## Competing designs and chosen data shape

| Candidate | Structure | Benefit | Cost and decision |
| --- | --- | --- | --- |
| A. Direct socket adapter | Small Python standard-library transport plus command adapter and thin executables | No extra daemon, port, dependency, auth database, or duplicated lifecycle state | Tied to a versioned upstream wire protocol. Chosen because the public supervisor protocol already carries the required operations. |
| B. Local HTTP gateway | Persistent process translating Pi-shaped HTTP requests into Prime socket commands | Existing HTTP-only callers could keep their URL client | Adds another service, service auth, request lifecycle, and shared session state without fixing missing interactive questions. Rejected for this track. |

The central data shape is a command envelope and its correlated response. A command registry owns simple verb translations. Explicit functions own the composite list, spawn, prompt, status, and command-discovery projections. `PrimeClient.request(kind, **fields)` owns command correlation and errors. Its client object owns the socket, hello validation, and LF framing. CLI parsers validate external arguments. There is no event cache, background polling service, workflow engine, or durable shim state.

Model the Domain shaped this command/response boundary. Build the Lever requires the committed offline and real-server check scripts. Prove It Works means the real-daemon and inference verdicts are separate.

## Network access and authentication

LAYER 3. `prime-cli-remote` runs the host CLI through `options-01-ssh` over the existing userspace Twingate path. It mirrors pi-web-cli-remote's argument and stdin contract. SSH handles transport authentication. Prime retains owner-only Unix socket access. A stronger codebase or test layer cannot authenticate a live remote caller.

The selected route is `Grok Bot -> options-01-ssh -> host prime-cli -> supervisor Unix socket`. This achieves SSH-protected network access without exposing unauthenticated HTTP or raw TCP. An SSH-forwarded Unix socket is possible but creates local socket lifecycle and path issues that remote execution avoids. No TUN, raw scp, sudo, or system service is needed. The wrapper does not restart Twingate on every call, following G15.

LAYER 3. `PRIME_AGENT_DAEMON_SOCKET` selects the local socket, otherwise the upstream per-user `/tmp/prime-agent-UID/daemon.sock` path applies. The client never starts or shuts down a daemon implicitly. Operators must select the intended server. There is no CLI token flag or credential import. Provider auth remains Prime-owned and absent from git, argv, and output.

The stable release archive is checksum-verified against its published manifest and extracted outside git. The live check uses an isolated agent directory and dedicated socket so it cannot attach to or shut down an existing Prime daemon. Default control-only mode must not enqueue runnable prompt text. Prompt admission and model execution require explicit `--inference`. A native input pause can keep queued tests from running on the success path, but cannot guarantee that queued text stays suspended after connection loss. The same-user trust boundary is explicit. A Unix socket is not a sandbox against that user.

## Backend-neutral CLI and skill contract

LAYER 3. `agent-cli --backend pi|prime <command> ...` selects the backend. `PI_STACK_BACKEND` supplies an opt-in default, with Pi retained as the default for current installations. `prime-cli` is the direct Prime name. The dispatcher forwards argv and stdin, stdout, stderr, and exit status without shell interpolation. Deterministic dispatch belongs in executable code, not an always-on rule or a skill.

LAYER 1. The adjacent CLI reference names stable envelopes, ID rules, command semantics, and unsupported behavior. These data shapes guide both implementations and tests. A stronger layer is not available.

LAYER 2. Subprocess tests exercise every verb against an in-process Unix-socket fixture, including interleaved events, malformed responses, unknown sessions, framing, stdin, quoting, protocol mismatch, errors, and model selector validation. The real-server script exercises only sessions it creates. These checks fail on wrong results rather than trusting source inspection.

LAYER 5. Existing skills can later select `agent-cli --backend prime`, retaining cwd, prompt modes, opaque durable session identifiers, response keys, and native `/compact`. They must treat null context as unknown, `accepted` as admission only, and unsupported answers as missing capability. The port is not yet mechanical. It also needs correlated questions, replayable internal queue data, accepted lifecycle differences, and a durable failure or completion channel. Prime can return a preflight error without persisting an assistant error row, so the current tick's transcript inspection alone is insufficient. A skill cannot repair a missing daemon API. This track documents those requirements but does not edit stream, cross-repo, or loop behavior before P2.

LAYER 3. Packaging follows pi-stack's `bin/` tools and installer-managed user links. Installing these small clients does not install Prime, change provider credentials, start a service, or select a different stream backend. Tests cover isolated installation without running the full host installer.

## Caladan, non-blocking

The source is pi-bot `caladan` at `bb39dc0fc61d514b590f5d5de82ba7b603ec06a5`, not a pi-stack branch. It remains read-only. The open question is whether its later Prime adaptation stays in pi-bot or is intentionally transplanted. The default here is to leave it in pi-bot and expose a swappable CLI contract. No backup, rebase, branch mutation, or push is part of track 2.

The read-only inspection found that Caladan's `skills/pi-web-access/pi-web-cli.py` is a different, restricted bot-facing CLI. It blocks raw spawn and prompt, strips list and status to metadata, and does not expose transcript content. `skills/bot-streams/pi_web_cli_access.py` requires an exact `pi-web-cli-v1` capability identity and strict response-key sets. The host pi-stack client is not a drop-in replacement for that restricted binding.

Caladan's `stream-spawn/lifecycle_core.py` additionally requires keyed admission, verified pause and retirement, and exclusive claims. Those stronger lifecycle guarantees are not supplied by ordinary pi-web-cli parity. Keep Caladan's admission policy in pi-bot rather than bypass it through the new generic client.

The existing remote wrapper is at `pi-bot@bb39dc0:skills/pi-web-access/pi-web-cli-remote`. It invokes `/home/box/.local/bin/options-01-ssh --ensure-tg /home/alphalab/.local/bin/pi-web-cli "$@"`. Its shell quoting does not protect eventual SSH command parsing. The new wrapper uses one shell-quoted command and retains stdin. It avoids unconditional `--ensure-tg` under G15. Generic code makes the SSH helper and host executable configurable rather than hardcoding a username or private network.

Nothing in the CLI transport requires a Caladan-specific branch. A later pi-bot adapter must deliberately preserve or migrate its restricted capability contract.

## Verification

The full predicate is BLOCKED. Offline checks and real control operations passed within the disclosed shims, but real inference failed on missing Prime Codex credentials. The observations below distinguish admission, control results, and model completion.

The unchanged pi-stack main baseline passed before final implementation verification:

```text
cd /home/alphalab/Projects/pi-stack/pi-stack
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests
Ran 105 tests. OK.
```

The log is `/tmp/prime-t2.3qhjos6h/pi-stack-baseline-tests.log`. This suite uses fixtures and does not prove Prime behavior.

Initial observations on options-01:

```text
prime-agent v0.10.1 archive SHA-256 verified
prime-agent executable SHA-256 1fbb506f54a8e9af1f0d123e521d13a765bce34883707c69656f06d5951b314c
/tmp/prime-t2.3qhjos6h/prime-agent --version -> 0.10.1
stable bundled model catalog contains gpt-6.1-sol -> false
~/.prime/agent/auth.json -> absent, existence checked only
provider environment variable names -> none found
```

No credential file was manually opened, copied, or edited. No login or credential import was attempted. Prime created its own storage in the isolated runtime directory. That storage was not inspected. Source inspection found that `resolve_cli_model` accepts an unknown model ID within a known provider and keeps that custom ID. Catalog absence is therefore not itself a spawn blocker. Native `set_model` still resolves through the available catalog, so selecting a custom ID may require a model definition.

The initial owned real supervisor ran in tmux session `prime-cli-t2-01a16656`, PID `3133971`, using `/tmp/prime-t2.3qhjos6h/agent` and `/tmp/prime-t2.3qhjos6h/daemon.sock`. No system service was installed. A raw-protocol baseline check, before exercising the new client, returned:

```text
daemon_hello -> prime-agent.daemon version=7 schemaRevision=30 appVersion=0.10.1
list cwd=/tmp/prime-t2.3qhjos6h/work -> success=true sessions=[]
```

This proves the real server and protocol identity, not the CLI or model. The isolated nonsecret settings disable provider failover and quota parking. Prime enables provider failover by default, so this override is necessary for the program's no-switch rule. Neither credentials nor a resource budget is added.

The host identifies itself as `hpc180-options-01`. Neither `options-01-ssh` nor `pi-web-cli-remote` is on its PATH. Off-host wrapper verification cannot be claimed from this host alone.

The first native create baseline intentionally tested the draft wire assumption before relying on it. The result disproved that assumption:

```text
create with top-level cwd/provider/model -> cwd=/home/alphalab and default model, not requested values
no prompt or provider request was sent to that session
owned baseline session archived immediately
create with config={cwd,provider,model,thinking} -> cwd=/tmp/prime-t2.3qhjos6h/work
model -> provider=openai-codex id=gpt-6.1-sol api=openai-codex-responses
requested xhigh -> effective off, reasoning=false on custom-ID fallback
owned corrected baseline session archived
```

The first implemented branch revision `eeb0af2` plus fixture correction `c323b30` passed 40 new offline tests and all 105 existing stream tests. The installer fixture first failed because its synthetic clone omitted `scripts/install-agent-clis.sh`. Commit `c323b30` adds that dependency to the fixture. The rerun returned `check-overlay ok`.

A successful real control-check sequence exercised all mapped verbs on stable v0.10.1. Prompt admission tests held an input pause and cleared the inputs before release on this observed success path. No model completion is claimed:

```text
scripts/check-prime-cli-live.py run --root /tmp/prime-cli-check-v5p3iz67
spawn, status, list, commands, messages -> success
answer -> exit 1, unsupported
model openai-codex/gpt-6.1-sol -> exit 1, upstream_error
prompt from stdin, steer, follow-up -> admitted while paused
pendingMessageCount -> 3
queue-clear -> success
steer then abort -> pendingMessageCount 0
stop -> runtimeClosed false
thinking-level xhigh -> accepted, effective off
archive -> archived row retained in cwd list
retainedOwnedSessions -> []
overall exit 1 because requested model-set and reasoning parity are not available
```

The small full report is `/tmp/prime-cli-check-v5p3iz67/control-check.json`. The owned check daemon ran as PID `3149674` in tmux session `prime-cli-t2-check-01a16656`, with a separate agent directory and socket. The initial baseline daemon PID `3133971` was shut down through its own socket before starting this one.

Independent same-model review reproduced four defects in that revision. A control-only check could release queued text on a failure, known spawn IDs were lost on readback transport errors, old active-selector status could reject legitimate native rebinds, and the dispatcher rejected leading backend `--socket`. Each received a failing regression commit followed by a fix. The independent recheck verified all four at `8ff0b597027022adeec00fce082435c88037853a`. No accepted finding was waived.

Final implementation checks were executed, not inferred from the worker report:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_prime*.py'
Ran 49 tests. OK.
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests
Ran 105 tests. OK.
bash scripts/check-overlay.sh
check-overlay ok
bash -n install.sh scripts/install-agent-clis.sh scripts/check-overlay.sh
passed
git diff --check
passed
```

The full installer test used temporary homes, synthetic local repositories, and disabled system-service operations. It did not install onto the real user's home. The focused installer was additionally run with a temporary HOME, and its installed `agent-cli --backend prime --socket ... list --cwd ...` successfully queried the real owned server. Durable IDs and archived metadata were preserved. The report is `/tmp/prime-cli-check-v5p3iz67/installed-dispatch-check.json`.

After the durable-ID fix, the final default control run admitted no prompt text. Its model and thinking gaps remained explicit in `/tmp/prime-cli-check-v5p3iz67/final-control-check.json`. The explicitly authorized inference run then exercised stdin prompt, steer, follow-up, queue clearing, and abort while a native pause held delivery. The inputs were cleared before release. Actual active-model steering delivery is not claimed.

The first inference completion check timed out because Prime wrote only the user message, not an assistant error row. Inspection was limited to that owned transcript. The verification script was corrected to use native `prompt_and_wait` for its model-completion probe after CLI admission tests. This makes the native failure response observable without fabricating transcript messages. The new offline regression passed, bringing the Prime suite from 48 to 49 tests.

LAYER 3. The completion probe uses a native awaited result because a live provider refusal cannot be observed through code layout or tests alone. LAYER 2. Its executable regression checks that an upstream failure is reported immediately even with an empty message list.

The corrected real inference transcript is small and decisive:

```text
python3 scripts/check-prime-cli-live.py run --root /tmp/prime-cli-check-v5p3iz67 --inference
spawn -> requested provider=openai-codex model=gpt-6.1-sol retained
requested xhigh -> effective off
stdin prompt, steer, follow-up -> admitted while paused
pendingMessageCount -> 3
queue-clear, queued steer, abort -> pendingMessageCount 0
stop -> runtimeClosed false
native prompt_and_wait completion probe -> upstream_error
No API key found for openai-codex.
retainedOwnedSessions -> []
exit -> 1
```

The exact report is `/tmp/prime-cli-check-v5p3iz67/final-inference-check-exact.json`. Prime directs the operator to `/login` for provider authentication. A Pi login does not configure the isolated Prime daemon. The missing requirement is Prime-owned OpenAI Codex authentication under the selected `PRIME_AGENT_CODING_AGENT_DIR`, plus model metadata that correctly describes `gpt-6.1-sol`. No login was attempted, no auth file was inspected or edited, and no provider or model substitute was used for inference.

All model attempts stopped at that native credential refusal. Successful inference, active-run steering, and compaction remain NOT VERIFIED. The off-host Grok Bot route also remains NOT VERIFIED because its SSH helper is not installed on this host.

Cleanup used only the owned sockets. The final owned cwd contained four archived sessions and zero unarchived sessions. The check daemon acknowledged shutdown, its tmux session ended, and its socket was removed. The initial baseline daemon was already stopped. There are no retained owned sessions or running owned Prime daemons.

Only code, tests, and small docs were committed. Runtime binaries, sessions, logs, and JSON reports stay outside git in `/tmp/`. The final implementation HEAD is `bccf159aed76c121fd9df133cedb515b8bd38dd3`. Main remains `3acf0f0`. This session made no docs commit, push, PR, STATUS.md edit, or existing-stream action.

The native check found a public-supervisor versus worker-payload distinction that source inspection had missed. The implementation must test the exact nested request and validate the returned cwd and requested model. The default model in the failed baseline was not used for any inference.

The checksum-verified stable release's bundled catalog contains fixture-named models. Its unknown-ID fallback preserves `gpt-6.1-sol` but assigns generic metadata, including no reasoning support and a 128000-token configured window. That window is not evidence of the requested model's actual capacity. Correct reasoning and context metadata need an operator-provided model definition or an updated catalog. The client must report effective thinking rather than claim xhigh was applied.

## Decisions

1. Use the public supervisor JSONL socket and stable v0.10.1 for verification. The wire is explicit and the release is reproducible.
2. Choose the direct adapter over a new HTTP gateway. The gateway adds a service without closing the real API gaps.
3. Initial identity decision, superseded by decision 21. The first implementation exposed active selectors as compatibility IDs. Review found that native rebind events go only to attached connections, not short-lived CLI requests.
4. Keep SSH remote execution rather than exposing a network listener. Existing machine access already provides authentication.
5. Keep credentials Prime-owned. This task does not authorize importing Pi or Codex credentials or running a login flow.
6. Preserve unknown context as null and distinguish admission from completion. Fabricated zero usage or delivery success would reproduce corpus F5 and F8.
7. Initial mapping, superseded by decision 16. The first draft mapped archive to native kill, stop to abort-and-clear, and abort to plain abort. Actual PI WEB source disproved the assumed abort and stop semantics.
8. Return unsupported for interactive answers until Prime has a correlated question API or an explicitly scoped question extension. Plain prompt injection would be false parity.
9. Keep Pi as the neutral dispatcher's default. P2 forbids silently porting existing streams now.
10. Leave Caladan in its own repository and defer its migration. Its cross-repository destination is non-blocking for this CLI.
11. Use one parent writer with read-only research lanes. Separate Before Serializing Shared State keeps shared docs and branches free of concurrent writes.
12. Do not switch models for skill-prescribed cross-model review. The program's same-model constraint takes precedence. Independent same-model research and direct verification are the available checks.
13. Reuse the still-running upstream investigator as the single implementation writer after writing this design. Its costly source context is directly needed for the adapter. The parent owns only artifact 20 and isolated live verification during that write phase.
14. Disable Prime provider failover and quota parking in the owned live-check configuration. Upstream otherwise enables failover, which conflicts with the program's stop-and-report rule.
15. Include numeric cost from native session statistics. Actual pi-stack code requires it even though the abbreviated task list did not name it.
16. Correct the lifecycle mapping against the installed PI WEB implementation. Abort clears queues. Stop closes runtime without archival. Archive refuses active work. Native Prime abort is not Pi abort, and the work-stop shim must advertise that it retains the resident runtime.
17. Keep the full host CLI contract separate from Caladan's restricted metadata-only contract. Substituting one for the other would either break strict validators or bypass bot admission policy.
18. Preserve host transcript paths and queue replay requirements in the later port contract. Display previews are not safe replay text, so internal Prime queue behavior stays an explicit gap rather than fabricated compatibility.
19. Correct public create to use `config`, not top-level worker fields. The real daemon ignored the top-level fields and returned the wrong cwd and model. Add response validation so this failure cannot be called a successful spawn.
20. Report the stable catalog's generic custom-model metadata rather than invent model facts. Real create preserved the requested ID but clamped thinking to off. No inference was sent to the accidentally default-selected baseline session.
21. Expose durable `sessionId` as compatibility `id` consistently in spawn, list, and status. Keep active identity separately. Native resolution already understands durable selectors, so this avoids a shim registry and dependence on unavailable rebind events.
22. Restrict runnable queue-admission tests to explicit inference mode. Independent review reproduced a failure path where disconnect released the input pause before cleanup. Clear or abort within the pause scope on ordinary errors, and do not claim disconnect safety from a connection-owned lease.
23. Preserve a known created session in spawn errors even when model readback times out or the connection resets. An uncertain readback must not discard an already received identity or cause a second create.
24. Parse only the neutral dispatcher's leading backend choice. Backend endpoint flags such as `--socket` must retain their original order.
25. Fix the installer verification fixture rather than skip it. Its synthetic clone omitted the newly required helper. Adding the helper made the full installer check pass.
26. Use native `prompt_and_wait` in the authorized live completion probe after testing CLI admission. The real server did not persist its preflight error as an assistant message, so polling messages produced a timeout instead of the actual failure. Add a regression for the empty-transcript failure path.
27. Stop at the native Codex credential refusal. Do not import Pi credentials, start a login, or switch provider. The implementation and real control evidence are delivered, but the full track end state is blocked.
28. Shut down both owned daemons and retain no owned live sessions. The final list showed only archived owned sessions, and the final socket was removed. Runtime data remains outside git.

## Gaps

- Interactive `answer` has no native correlated-question API in the inspected daemon union. This is a parity gap, not a completed shim.
- Exact Pi stop-without-archive disposal has no demonstrated public Prime equivalent. Work-stop can retain the resident runtime only as a labeled shim.
- Exact replay of Prime internal queued inputs is not guaranteed by its preview-based queue API. Ordinary user input and arbitrary internal work must not be conflated.
- Busy archive guards are covered offline and real idle archival passed. A native pause stops queued delivery, not every producer. `preflightAtomic:false` is not a quiescence guarantee.
- Real inference is blocked by `No API key found for openai-codex.` Prime-owned Codex authentication is required in the selected agent directory. No authentication flow or credential import was attempted.
- The requested model is absent from the stable bundled catalog. Create preserves its ID with generic metadata, but native `set_model` refused it and xhigh was clamped to off. Actual reasoning capability and context capacity need a correct model definition or catalog, not guessed limits.
- Native preflight failures can exist only in awaited results or events, with no assistant error row. The diagnostic script now observes the awaited result, but the later stream port still needs an explicit completion or failure-observation contract. Current message-log inspection alone is insufficient.
- No successful model completion, active-run steering delivery, or compaction was verified after the credential refusal.
- Remote wrapper execution from the Grok Bot machine requires that machine and its authenticated `options-01-ssh`. Local wrapper quoting tests are not off-host evidence.
- Stream ticks, coordinator compaction policy, skill installation into Prime, and Caladan adaptation are outside this implementation under P2.
- Prime's executable Python skills are not automatically equivalent to Pi's Markdown process skills. Command discovery must report only what the target runtime actually loads.

## Parity checklist

Final tested state. Done means the mapped operation worked on the owned real daemon. Shimmed names an explicit semantic or verification limit. No row claims successful inference.

| pi-web-cli command | State | Evidence |
| --- | --- | --- |
| list | done | Real cwd list preserved durable IDs, transcript paths, timestamps, message counts, and archived rows. |
| spawn | done | Real nested-config create retained the requested cwd and exact provider/model ID. Authentication is a separate failed gate. |
| prompt, argv and stdin | shimmed | Offline argv and stdin byte checks passed. Real stdin admission passed. Model completion was blocked by native credential refusal. |
| prompt --steer | shimmed | Real queued admission and clearing passed. Delivery during an actual model run is not verified. |
| prompt --follow-up | shimmed | Real queued admission passed. Delivery after an actual model run is not verified. |
| status | shimmed | Real streaming, queue count, context metadata, effective model/thinking, and numeric cost worked. Reads are non-atomic and queue text is marked replay-unsafe. |
| commands | done | Native command and skill discovery returned through the expected array envelope. Pi-only skills are not claimed installed. |
| stop | shimmed | Real work-stop cleared input and retained the resident runtime. `runtimeClosed:false` discloses the difference from Pi disposal. |
| abort | shimmed | Real queued inputs were cleared and abort acknowledged. Full runtime quiescence is not promised. |
| queue-clear | done | Real queued admission count reached three, then native clearing removed the inputs. |
| archive | shimmed | Real idle archival retained transcript and archived-list metadata. Busy guards pass offline. Native admission races remain disclosed. |
| messages | done | Real native message payloads and empty lists were preserved. Ephemeral preflight errors are not fabricated as assistant messages. |
| model | missing | The adapter exists and offline selector checks pass, but native `set_model` refused the requested live target. No substitute was selected. |
| thinking-level | shimmed | Real setter acknowledged xhigh but effective status remained off because of generic model metadata. |
| answer | missing | Explicit unsupported 501. No native correlated-question API exists in the inspected protocol. |

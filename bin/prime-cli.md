# Prime CLI reference

`prime-cli` translates pi-web-cli arguments to Prime's public supervisor JSONL protocol 7. It needs Python 3.10 or later and an already running daemon. It never starts, upgrades, or shuts down a daemon. It does not install skills, import credentials, or port streams.

Install the user links with `bash scripts/install-agent-clis.sh`, or the regular pi-stack installer. Keep the checkout because the links resolve into its `bin/` directory. Neither installation path installs a Prime runtime. The focused installer changes only three links under `$HOME/.local/bin`.

## Select the backend and endpoint

```sh
agent-cli list --cwd /work
agent-cli --backend prime list --cwd /work
agent-cli --backend=prime --socket /owned/daemon.sock status SESSION
PRIME_AGENT_DAEMON_SOCKET=/owned/daemon.sock prime-cli status SESSION
prime-cli --socket /owned/daemon.sock status SESSION
prime-cli-remote status SESSION
```

`agent-cli` defaults to Pi. `PI_STACK_BACKEND=prime` opts into Prime. The dispatcher consumes only a leading `--backend pi|prime` or `--backend=prime` selection. Every remaining token, including a leading backend `--socket` option or later `--backend` token, passes unchanged to the child. It preserves standard streams and exit status. It uses sibling `pi-web-cli` or `prime-cli` executables. It does not modify stream configuration.

`PRIME_AGENT_DAEMON_SOCKET` selects the host-side Unix socket. Without it, the default is `${TMPDIR:-/tmp}/prime-agent-UID/daemon.sock`. Packaged Rust launchers can use a different endpoint, so select it explicitly. `PRIME_CLI_TIMEOUT` is a positive response timeout in seconds, default 20. The client never retries an uncertain mutation.

`prime-cli-remote` calls `options-01-ssh` from PATH with one shell-quoted remote command and unchanged stdin. It never adds `--ensure-tg`. `OPTIONS_01_SSH` selects another wrapper executable. `PRIME_CLI_REMOTE_BIN` selects an absolute remote executable. Without an override, only the trusted fixed prefix `"$HOME"/.local/bin/prime-cli` expands on the remote shell; every argument stays individually quoted. Configure the target endpoint in the remote environment or pass `--socket` before the verb. No HTTP or TCP listener is added.

## Command contract

| Command | Meaning |
| --- | --- |
| `list --cwd PATH` | Lists matching saved and resident sessions, including archived rows. `id` is the durable `sessionId`, `activeSessionId` remains separate, `path` aliases native `sessionFile`, and `archived` reflects native lifecycle. Native `messageCount` and `modified` remain unchanged when present. |
| `spawn PATH` | Creates a resident session that survives CLI disconnect. `PRIME_CLI_MODEL=provider/modelId` and `PRIME_CLI_THINKING=xhigh` set explicit fields inside the supervisor command's `config` object. Cwd is checked against the create result. An explicit model is read back; a mismatch fails and includes the retained session identity. Without these variables, Prime chooses its configured defaults. |
| `prompt SID [TEXT]` | Reads exact stdin when TEXT is absent. Ordinary input explicitly uses follow-up behavior so it resumes native suspended admission. Success is admission only. |
| `prompt SID --steer [TEXT]` | Queues steering for the next active-run boundary. Acknowledgement does not prove execution. |
| `prompt SID --follow-up [TEXT]` | Queues input after the active run. |
| `status SID` | Reads connection state, queue previews, and session stats. These three reads are not atomic. Effective model and thinking come from Prime. Numeric cost comes from stats, never a local estimate. |
| `commands SID` | Returns native prompt-template and skill entries. This is not a list of every TUI builtin or a claim that Pi skills are installed. |
| `messages SID` | Returns the native transcript message array. Windowed or compacted history can differ from Pi. |
| `model SID PROVIDER/ID` | Calls native `set_model`, requires an exact returned provider/ID, and exposes catalog/auth failures. Native selection also changes Prime's default model. |
| `thinking-level SID LEVEL` | Calls native `set_thinking_level`. Prime may clamp unsupported levels and changes its default. Check effective status afterward. |
| `abort SID` | Uses `abort_and_clear_queue`, matching the actual Pi Web server's queue-clearing abort. It leaves the resident session and suspends native admission. A later explicit prompt resumes it. |
| `stop SID` | Uses the same work-stop operation. Returns `runtimeClosed:false` and `semantics:"abort-and-clear-resident-shim"`. Unlike Pi Web stop, this does not dispose the session runtime. |
| `queue-clear SID` | Clears pending native lanes without aborting the active run. Returns removed raw lane text, not status previews. This loses native metadata and can notify agent senders of withdrawal. |
| `queue-resume SID` | Calls public `resume_queue` once. Wakes existing same-session queue objects without serializing, clearing, or reconstructing them. This can start queued model work or goal continuation. Success is not completion. |
| `archive SID` | Acquires a native connection-scoped input pause, rejects observed streaming, compaction, bash, queued input, or running descendants, then calls native `kill`. Retains the transcript, cancels schedules, and closes descendants. |
| `answer SID ASK_ID QUESTION_ID TEXT` | Returns unsupported status 501 without connecting. Never injects the answer as a prompt. |

`prompt SID '/compact focus on unfinished work'` uses Prime's native slash command. Admission is not compaction completion. Observe `isCompacting`, `compactionCount`, and native result messages.

## JSON and known differences

Success exits 0. Failure exits 1 with JSON on stdout. Usage failures also use JSON. `--help` prints ordinary help. No raw daemon greeting or credential value enters CLI output.

```json
{"ok":true,"status":200,"sessions":[]}
{"ok":true,"status":201,"session":{"id":"durable-id","sessionId":"durable-id","activeSessionId":"runtime-id","cwd":"/work","archived":false}}
{"ok":true,"status":200,"result":{"accepted":true}}
{"ok":false,"status":501,"error":"unsupported","message":"Prime has no correlated interactive-answer API"}
```

The numeric status is an HTTP-style compatibility field, not an HTTP transport result. Failures use stable `error` codes such as `usage`, `transport_error`, `timeout`, `invalid_response`, `protocol_mismatch`, `upstream_error`, `wrong_session`, `model_mismatch`, `cwd_mismatch`, and `session_busy`. Upstream typed `errorInfo` is retained when supplied.

Status has `id`, `cwd`, `isStreaming`, `pendingMessageCount`, `contextUsage`, `model`, `thinkingLevel`, and `cost`. `contextUsage` is null when unknown. Native null token usage after compaction stays null. Missing required streaming or numeric cost is an error, never an invented idle state or zero cost.

`queuedMessages` is an ordered array of `{kind:"steer"|"followUp",text:...}` entries. Duplicate text remains duplicated. `pendingMessageCount` counts both authoritative arrays. Native internal messages can have preview labels rather than replayable raw prompts. Status therefore reports `queueRepresentation:"previews"` and `queueReplaySafe:false`. It preserves native `sessionActions`, including optional `injectedPrompts` and `rlmChildStatus` provenance. Do not mechanically replay arbitrary Prime queues during rotation.

Status reports `pendingAsk:null` together with `capabilities.interactiveAnswers:false`. It also reports `runtimeDisposal:false`, `internalQueueReplay:false`, and `sameSessionQueueResume:true`. These are source-observed adapter capabilities, not a daemon-negotiated capability list. Null does not claim interactive parity. Stop runtime disposal and structured answers remain gaps. This client does not imitate Caladan's restricted metadata-only CLI or alter its capability policy.

`stop SID --require-runtime-close` and `queue-clear SID --require-replay-safe` return unsupported 501 before connecting or mutating anything. Existing unflagged command grammar and behavior remain unchanged. These opt-in guards do not protect stream callers that ignore capability limits. The current streams are not ported to Prime.

`queue-resume` cannot restore work removed by `queue-clear`, adapter `abort`, or adapter `stop`. It preserves only native objects that remain queued in that same session. It does not release input-pause leases. An empty queue returns the native error `No queued work to resume` after native suspension has already been cleared. There is no automatic retry, prompt fallback, or cross-session replay.

Archive's pause prevents queued delivery but does not stop every producer, in-flight tool, model action, or concurrent administrative operation. The reply explicitly reports `preflightAtomic:false`. A producer can still add work after the check. Disconnect releases the pause after both success and rejection. This is safer preflight, not a server-side atomic archive-if-idle operation.

Spawn, list, and status consistently expose the real durable `sessionId` as compatibility `id`. They preserve native `activeSessionId` separately and reject a missing durable identity rather than substituting a runtime selector. Pass the compatibility ID to later commands, including archive's pause acquisition. Status validates the returned durable identity, then routes its composite queue/stats reads through the validated current active ID. Archive also checks the preflight summary's durable identity. A runtime replacement can change the active ID without changing the compatibility ID. Fresh CLI connections do not depend on attachment-only binding events or a shim registry. An uncertain create can have created a session even if its reply was lost. Do not retry it blindly. An explicit spawn-model readback failure includes the known `session` after protocol refusal, timeout, reset, or EOF. The client does not retry create, delete the session, or discard its received identity.

Prime accepts an unlisted create model ID by copying a known provider's template. That can preserve `gpt-6.1-sol` without proving its entitlement, context limit, or supported reasoning level. Native `set_model` can still reject that unregistered ID. The client never substitutes another provider/model. An owned daemon must pin `allowedModels` and disable `retry.failover.enabled` before model-backed checks. Missing authentication is a blocker, not a reason to switch provider.

## Verification model metadata

`verify` uses `scripts/prime-models/openai-codex-gpt-6.1-sol.json` by default. The parent observed this exact metadata-only row in the installed Pi catalog cache on 2026-10-23. The cache timestamps were `checkedAt=1792721682314` and `lastModified=1792063872000`. This worker did not open the cache or any credential file.

The snapshot preserves the observed name, API kind, reasoning flag, thinking-level map, text and image inputs, 500000-token context window, 128000-token maximum output, and four flat costs. These are catalog declarations, not measured inference capabilities. No value is inferred from the model name. Endpoints, headers, and authentication fields are excluded. The native `ModelDefinition` and `ModelCostConfig` in `crates/pa-core/src/models/custom.rs` accept these fields. Native flat costs do not represent the observed above-272000-token cost tier. Extra compatibility flags, `inputLimits`, and `type` are outside the whitelist. Exact tiered billing is not claimed.

`--model-definition PATH` accepts a complete replacement metadata object with the same whitelisted fields and exact provider, model ID, and API kind. Missing fields, extra fields, invalid reasoning maps, nonpositive token limits, and nonfinite or negative costs fail before launch. Verification creates only native `agent/models.json` under the existing isolated root. It refuses an existing file without reading or replacing it. After its daemon stops, it removes only the file it created. It never loads auth files, custom provider keys, or provider endpoints.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_prime*.py' -v
python3 scripts/check-prime-cli-live.py prepare
python3 scripts/check-prime-cli-live.py run --root /printed/owned/root
python3 scripts/check-prime-cli-live.py verify --root /existing/logged-in/owned/root \
  --runtime /absolute/path/to/prime-agent
python3 scripts/check-prime-cli-live.py verify --root /existing/logged-in/owned/root \
  --runtime /absolute/path/to/prime-agent --inference
```

Preparation writes a new private temporary directory, nonsecret settings, and an ownership marker. It prints the daemon launch environment and argv but never launches it. Run the printed command separately. The run mode requests only `openai-codex/gpt-6.1-sol` at xhigh, uses only sessions it creates, and reports failed prerequisites honestly. It records thinking clamps without claiming xhigh support or blocking the remaining control checks. It never reads or writes credentials. Without `--inference`, run mode admits no prompt text. Queue-clear, abort, and stop checks use the empty owned session. `--inference` authorizes every runnable prompt-admission check, the model prompt, and manual compaction. After testing CLI prompt admission, the inference completion probe uses native `prompt_and_wait` so an ephemeral provider refusal is returned even when Prime writes no assistant error message. Inference-enabled queue checks cancel and clear inside the pause scope in a `finally` block before ordinary disconnect. A lost pause connection can still release runnable inputs before cancellation arrives; the pause is not a no-execution guarantee. Quota errors stop the run without a provider switch. Cleanup attempts stop and archive only IDs returned by that run's create calls. Cleanup failures retain and report the IDs.

`verify` reuses an existing prepared root. Do not rerun `prepare` after logging in. Prime authentication remains operator-owned. Native v0.10.1 has no CLI login subcommand. Its TUI accepts bare `/login`, followed by selection of `ChatGPT Plus/Pro (Codex Subscription)`. `/login openai-codex` is invalid. This script never invokes either login form or reads authentication storage.

Unlike `run`, `verify` owns a dedicated daemon. It refuses existing sockets, stale socket paths, locks, native model configurations, symlinked configuration files, and unsafe retry settings. It neither contacts nor shuts down a colliding daemon. It preserves settings and existing storage. The launch pins the agent directory, session directory, socket, and cwd under the supplied private root. It sets `DO_NOT_TRACK=1` and `PI_OFFLINE=1`. Full whitelisted model metadata and effective xhigh must match before any runnable input. Native model-selection failures stop verification without fallback. A complete control-only check runs first. Only explicit `--inference` authorizes a second owned-session check with runnable input, completion, and compaction.

Cleanup archives only sessions created by this invocation. The runner then requests shutdown through its captured socket while its own launched process remains alive, waits for that process, and uses signals only against that process if needed. It removes a remaining socket or model file only when its filesystem identity still matches the captured owned file. Cleanup failures are reported. A surviving foreign socket is never removed. Root locking coordinates this runner, not every same-user Prime process or producer. The root must not be used concurrently by another operator workflow. Reports always include `parityComplete:false`; successful checks do not close unsupported native capabilities.

The offline fixture tests prove framing, wrappers, and projections. They do not prove authentication, inference, active-run steering delivery, runtime disposal, off-host connectivity, or atomic archive behavior.

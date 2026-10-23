# Prime CLI reference

`prime-cli` translates pi-web-cli arguments to Prime's public supervisor JSONL protocol 7. It needs Python 3.10 or later and an already running daemon. It never starts, upgrades, or shuts down a daemon. It does not install skills, import credentials, or port streams.

Install the user links with `bash scripts/install-agent-clis.sh`, or the regular pi-stack installer. Keep the checkout because the links resolve into its `bin/` directory. Neither installation path installs a Prime runtime. The focused installer changes only three links under `$HOME/.local/bin`.

## Select the backend and endpoint

```sh
agent-cli list --cwd /work
agent-cli --backend prime list --cwd /work
PRIME_AGENT_DAEMON_SOCKET=/owned/daemon.sock prime-cli status SESSION
prime-cli --socket /owned/daemon.sock status SESSION
prime-cli-remote status SESSION
```

`agent-cli` defaults to Pi. `PI_STACK_BACKEND=prime` opts into Prime. The dispatcher preserves arguments, standard streams, and exit status. It uses sibling `pi-web-cli` or `prime-cli` executables. It does not modify stream configuration.

`PRIME_AGENT_DAEMON_SOCKET` selects the host-side Unix socket. Without it, the default is `${TMPDIR:-/tmp}/prime-agent-UID/daemon.sock`. Packaged Rust launchers can use a different endpoint, so select it explicitly. `PRIME_CLI_TIMEOUT` is a positive response timeout in seconds, default 20. The client never retries an uncertain mutation.

`prime-cli-remote` calls `options-01-ssh` from PATH with one shell-quoted remote command and unchanged stdin. It never adds `--ensure-tg`. `OPTIONS_01_SSH` selects another wrapper executable. `PRIME_CLI_REMOTE_BIN` selects an absolute remote executable. Without an override, only the trusted fixed prefix `"$HOME"/.local/bin/prime-cli` expands on the remote shell; every argument stays individually quoted. Configure the target endpoint in the remote environment or pass `--socket` before the verb. No HTTP or TCP listener is added.

## Command contract

| Command | Meaning |
| --- | --- |
| `list --cwd PATH` | Lists matching saved and resident sessions, including archived rows. `id` is the active selector, `path` aliases native `sessionFile`, and `archived` reflects native lifecycle. Native `messageCount` and `modified` remain unchanged when present. |
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
| `queue-clear SID` | Clears pending native lanes without aborting the active run. Returns removed lane text. |
| `archive SID` | Acquires a native connection-scoped input pause, rejects observed streaming, compaction, bash, queued input, or running descendants, then calls native `kill`. Retains the transcript, cancels schedules, and closes descendants. |
| `answer SID ASK_ID QUESTION_ID TEXT` | Returns unsupported status 501 without connecting. Never injects the answer as a prompt. |

`prompt SID '/compact focus on unfinished work'` uses Prime's native slash command. Admission is not compaction completion. Observe `isCompacting`, `compactionCount`, and native result messages.

## JSON and known differences

Success exits 0. Failure exits 1 with JSON on stdout. Usage failures also use JSON. `--help` prints ordinary help. No raw daemon greeting or credential value enters CLI output.

```json
{"ok":true,"status":200,"sessions":[]}
{"ok":true,"status":201,"session":{"id":"active-selector","cwd":"/work","archived":false}}
{"ok":true,"status":200,"result":{"accepted":true}}
{"ok":false,"status":501,"error":"unsupported","message":"Prime has no correlated interactive-answer API"}
```

The numeric status is an HTTP-style compatibility field, not an HTTP transport result. Failures use stable `error` codes such as `usage`, `transport_error`, `timeout`, `invalid_response`, `protocol_mismatch`, `upstream_error`, `wrong_session`, `model_mismatch`, `cwd_mismatch`, and `session_busy`. Upstream typed `errorInfo` is retained when supplied.

Status has `id`, `cwd`, `isStreaming`, `pendingMessageCount`, `contextUsage`, `model`, `thinkingLevel`, and `cost`. `contextUsage` is null when unknown. Native null token usage after compaction stays null. Missing required streaming or numeric cost is an error, never an invented idle state or zero cost.

`queuedMessages` is an ordered array of `{kind:"steer"|"followUp",text:...}` entries. Duplicate text remains duplicated. `pendingMessageCount` counts both authoritative arrays. Native internal messages can have preview labels rather than replayable raw prompts. Status therefore reports `queueRepresentation:"previews"` and `queueReplaySafe:false`. It preserves native `sessionActions`, including optional `injectedPrompts` and `rlmChildStatus` provenance. Do not mechanically replay arbitrary Prime queues during rotation.

Status reports `pendingAsk:null` together with `capabilities.interactiveAnswers:false`. Null does not claim interactive parity. Stop runtime disposal and structured answers remain gaps. This client does not imitate Caladan's restricted metadata-only CLI or alter its capability policy.

Archive's pause prevents queued delivery but does not stop every producer, in-flight tool, model action, or concurrent administrative operation. The reply explicitly reports `preflightAtomic:false`. A producer can still add work after the check. Disconnect releases the pause after both success and rejection. This is safer preflight, not a server-side atomic archive-if-idle operation.

Runtime selectors differ from durable `sessionId` and `sessionFile`. Keep those native fields. Status follows an explicit native binding event or a durable-ID match; it rejects an unexplained different session. An uncertain create can have created a session even if its reply was lost. Do not retry it blindly. An explicit spawn-model readback failure includes `session` when its identity was received.

Prime accepts an unlisted create model ID by copying a known provider's template. That can preserve `gpt-6.1-sol` without proving its entitlement, context limit, or supported reasoning level. Native `set_model` can still reject that unregistered ID. The client never substitutes another provider/model. An owned daemon must pin `allowedModels` and disable `retry.failover.enabled` before model-backed checks. Missing authentication is a blocker, not a reason to switch provider.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_prime*.py' -v
python3 scripts/check-prime-cli-live.py prepare
python3 scripts/check-prime-cli-live.py run --root /printed/owned/root
```

Preparation writes a new private temporary directory, nonsecret settings, and an ownership marker. It prints the daemon launch environment and argv but never launches it. Run the printed command separately. The run mode requests only `openai-codex/gpt-6.1-sol` at xhigh, uses only sessions it creates, and reports failed prerequisites honestly. It records thinking clamps without claiming xhigh support or blocking the remaining control checks. It never reads or writes credentials. Without `--inference`, run mode admits no prompt text. Queue-clear, abort, and stop checks use the empty owned session. `--inference` authorizes every runnable prompt-admission check, the model prompt, and manual compaction. Inference-enabled queue checks cancel and clear inside the pause scope in a `finally` block before ordinary disconnect. A lost pause connection can still release runnable inputs before cancellation arrives; the pause is not a no-execution guarantee. Quota errors stop the run without a provider switch. Cleanup attempts stop and archive only IDs returned by that run's create calls. Cleanup failures retain and report the IDs.

The offline fixture tests prove framing, wrappers, and projections. They do not prove authentication, inference, active-run steering delivery, runtime disposal, off-host connectivity, or atomic archive behavior.

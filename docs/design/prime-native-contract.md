# Prime native CLI contract

Status: source-verified design contract. This is not live validation. The pi-stack base is `f685e3ad1485192a45bc7b6eed6b260961a965e4`. The read-only Prime source is `71beca9478f552dc6fc898bba9685f9ce00515cf`.

## Native protocol

Prime's supervisor exposes a local JSON Lines socket. A client receives `daemon_hello`, then sends a `type: "command"` envelope with a unique request ID, protocol name `prime-agent.daemon`, and protocol version 7. Responses carry the matching ID. Session events use separate outbound frames. The handshake reports the schema ID and revision, daemon build identity, socket path, and server capabilities.

The source of truth is Prime's public daemon protocol in `crates/pa-types/src/daemon/command.rs` and `outbound.rs`, plus the supervisor handlers in `crates/pa-daemon/src`. The CLI must validate the handshake and correlate each response. It must not retry a request after writing it. A lost response to a mutation leaves its outcome uncertain.

## Compatibility contract

Callers keep the `pi-web-cli` argv and JSON envelope for shared verbs. The Prime client speaks the native socket protocol directly. It does not launch a Pi executable or translate HTTP requests.

| Caller operation | Prime operation | Compatibility rule |
| --- | --- | --- |
| `list --cwd DIR` | `list` with `all: true` and `cwd: DIR` | Return `sessions`. Set each compatibility `id` to the durable `sessionId` and preserve `activeSessionId` separately. Keep native `sessionFile` and `lifecycle`; do not invent Pi `path`, `archivePath`, or `archived` fields. Prime projects both archived and crashed files as `lifecycle: "archived"`. |
| `spawn DIR` | `create` with `cwd: DIR` | Return the durable session ID and native active runtime ID. Verify the returned cwd before reporting success. |
| `status SID` | Resolve the durable ID, then call `get_state` and `get_session_stats` on the active runtime ID. | Preserve lifecycle, `isStreaming`, `isCompacting`, model, thinking level, and native `contextUsage`. Do not invent context values when Prime omits them. Verify both reads refer to the same durable session and active runtime. |
| `prompt SID [TEXT]` | `prompt` with `message` and optional `streamingBehavior` | Read absent text from stdin. `--steer` selects native steering behavior. A successful response means admission only, not a settled turn. |
| `model SID PROVIDER/MODEL` | `set_model` with `provider` and `modelId` | Preserve native refusal data. Read status back before claiming the selection. |
| `thinking-level SID LEVEL` | `set_thinking_level` | Read status back before claiming the selection. |
| `abort SID` | `abort` | Report command acknowledgement only. Prime does not return a stop epoch, runtime closure, or proof that external tool effects stopped. |
| `compact SID` | `compact` with optional `customInstructions` | This is a native compaction request, not the stream maintenance protocol. It has no expected-idle checkpoint or awaited external pre/post hooks. |
| `fork SID ENTRY --position at` | `fork` with exact `entryId` and position | Prime can fork at an exact entry. The command has no operation receipt, expected source leaf, callback-ownership transfer, or conditional retirement. Do not treat it as safe stream replacement. |

Every response keeps the established envelope fields such as `ok`, `status`, `session`, `sessions`, `result`, and `transportAccepted`. `transportAccepted` describes only the native admission response. Errors retain native `error`, `errorInfo`, and any event frames received before the response. The client reports an unknown mutation outcome when it sent a request but did not receive its correlated response.

`get_session_stats` returns Prime's `contextUsage` object with `tokens`, `contextWindow`, and `percent` when the model window is known. Prime computes this estimate from the latest valid assistant usage and subsequent message estimates. It returns null tokens and percent immediately after compaction until valid post-compaction usage exists. The CLI preserves that uncertainty.

## Engine adapter inventory

`pi-streams/engine/piweb.py` invokes the following operations. The list includes calls made by thread, drive, delivery, failure, replacement, DCR, doctor, tick, and terminal-session code.

| Existing adapter operation | Native support |
| --- | --- |
| `list --cwd`, `spawn`, `status`, `model`, `thinking-level`, `prompt`, `abort`, `compact` | Native equivalents exist. Their identity, completion, and lifecycle limits are documented above. |
| `queue-clear` | `clear_queue` exists, but it does not provide a stable operation receipt or recover cleared messages. It is not a stop or recovery substitute. |
| `archive` and `archive --expected-idle` | No native archive operation with conditional idle fencing exists. `kill` is not equivalent. |
| `automatic-admission` with generation checks | No native generation-CAS stream admission command exists. |
| `control-goal` and its status form | No native delivery identity, goal sequencing, or applied-receipt protocol exists. |
| `command-run` | No equivalent native engine command exists. `execute_bash` is not a safe substitute. |
| `runtime`, `capabilities` | The CLI can report the actual `daemon_hello` protocol, schema, build identity, and `serverCapabilities`. Those values do not establish missing stream semantics. |
| `failure-boundary`, `failure-resume`, `failure-readiness`, `failure-analysis`, `failure-fork`, `failure-maintenance`, `failure-retire` | No corresponding native command family exists. |
| `maintenance-events`, checkpointed `compact`, `maintenance`, `maintenance-resume` | Prime has `compact`, but no stream checkpoint, compaction receipt, awaited engine hooks, or exact RESUME admission. |

`piweb.py` also requires distinct durable session identity and active runtime identity, exact cwd checks, native model and thinking readback, preserved pending questions, and truthful handling of terminal sessions and uncertain mutations. Prime's `sessionFile` does not prove the Pi `sessionlog` evidence-record format, and its `lifecycle: "archived"` projection does not distinguish archive from crash. The CLI preserves those native fields without adding Pi aliases.

## Stream admission gate

The CLI negotiates the live daemon from `daemon_hello` and reports the native protocol and capability set. It reports a separate `streamReady` result. That result is false unless the live API provides the engine semantics the selected backend requires. Native command names alone do not satisfy the gate.

At the inspected Prime revision, the following required semantics are absent from the public daemon protocol:

- Durable receiving-side stop and correction epochs, with atomic stale-admission rejection.
- Durable admission and applied-delivery receipts that distinguish accepted, settled, and uncertain outcomes.
- Stream-owned automatic admission, recovery readiness, mass resume, failure boundaries, and last-good recovery operations.
- Conditional archive or retirement tied to an exact idle checkpoint.
- Session evidence records in the format `piweb.read_evidence` verifies, plus a terminal disposition that distinguishes archive from crash.
- Callback ownership and pending-question preservation across replacement.
- Awaited engine pre-compaction and post-compaction hooks, plus a verified below-target continuation.
- A supervisor-owned non-inference stream reconciliation job. Prime's `cron_add`, `cron_cancel`, and heartbeat commands enqueue prompts; they do not run deterministic engine handlers.
- A native same-provider/model retry configuration and typed inference outcomes. Charter decision 6 requires bounded backoff with a 5-second base, not a fixed 5-second delay. Stock Prime exposes `retry.enabled`, `retry.maxRetries`, and `retry.baseDelayMs`; a finite retry budget bounds the local exponential ladder even though its internal maximum delay is unbounded. Jitter and the provider `Retry-After` cap remain separate. Supported configuration and readback must prove a 5000 ms base, finite retry count, finite server-wait cap, and `retry.failover.enabled=false`. The CLI does not infer those settings from a successful prompt.

The public protocol does provide native list/create, prompt/steer/follow-up, status, model and thinking controls, abort, compaction, exact-entry fork, and cron commands. These controls remain usable for direct native operations. They do not make `streamReady` true. A Prime-backed stream must be refused before its opening prompt while any required semantic is missing.

## Dispatcher and capability envelope

`bin/agent-cli` reads `PI_STACK_BACKEND`. The exact values are `pi` and `prime`; an unset value selects `pi`. The `pi` route executes `bin/pi-web-cli` with the original arguments. The `prime` route executes `bin/prime-cli` with the original arguments. Both routes inherit stdin, stdout, stderr, and the environment. An invalid value or missing executable returns a nonzero exit and an `ok: false` JSON error. The dispatcher never falls back from `prime` to `pi`.

`bin/prime-cli capabilities` returns this envelope after validating a live `daemon_hello`:

```json
{
  "ok": true,
  "status": 200,
  "runtime": {
    "protocol": {"name": "prime-agent.daemon", "version": 7},
    "socketPath": "<daemon_hello.socketPath>",
    "schemaId": "protocol-7-schema-30-8e4b17c2a9f5",
    "clientId": "<daemon_hello.clientId>",
    "supervisorGeneration": "<daemon_hello.supervisorGeneration>",
    "supervisorProcessStartId": "<daemon_hello.supervisorProcessStartId>",
    "supervisorSocketPath": "<daemon_hello.supervisorSocketPath>",
    "schemaRevision": 30,
    "appVersion": "<daemon_hello.appVersion>",
    "daemon": {
      "buildId": "<daemon_hello.runtime.buildId>",
      "executablePath": "<daemon_hello.runtime.executablePath>"
    },
    "serverCapabilities": ["<daemon_hello.serverCapabilities item>"]
  },
  "capabilities": {
    "schemaVersion": 1,
    "nativeOperations": [
      "sessions.list", "sessions.create", "prompt.admit", "prompt.wait", "prompt.steer",
      "session.status", "session.stats", "session.model", "session.thinking",
      "session.abort", "session.queueClear", "session.compact", "session.fork"
    ],
    "requiredSemantics": [
      "stop-correction-epoch", "durable-admission-and-outcome",
      "same-provider-retry-policy-readback", "recovery-readiness-and-receipts",
      "conditional-archive", "callback-ownership-transfer",
      "session-evidence-records", "terminal-session-disposition",
      "awaited-compaction-hooks", "non-inference-engine-scheduler"
    ],
    "missingSemantics": [
      "stop-correction-epoch", "durable-admission-and-outcome",
      "same-provider-retry-policy-readback", "recovery-readiness-and-receipts",
      "conditional-archive", "callback-ownership-transfer",
      "session-evidence-records", "terminal-session-disposition",
      "awaited-compaction-hooks", "non-inference-engine-scheduler"
    ],
    "streamReady": false
  }
}
```

The angle-bracket values show fields copied from the live handshake. The schema ID and revision above pin the inspected Prime source; the socket path, client ID, process identity, and server capabilities are runtime values. Optional handshake fields such as `supervisorPid` appear only when Prime supplies them. The envelope omits `supervisorOwnerToken`. `nativeOperations` describes the direct commands this CLI maps for the validated protocol. `missingSemantics` names the stream guarantees absent from the inspected stock API. The B lane admits a Prime stream only when the command exits zero, the output is a valid object with `ok: true`, `capabilities.schemaVersion` is `1`, `capabilities.streamReady` is exactly `true`, and `missingSemantics` is an empty list. Missing executables, absent fields, malformed JSON, connection failures, or a malformed handshake cannot pass this check. The socket path comes from `PRIME_AGENT_SOCKET` or `--socket`; no default socket is guessed.

At Prime revision `71beca9478f552dc6fc898bba9685f9ce00515cf`, `streamReady` is `false`. The scheduler blocker is specific. Stock cron and heartbeat commands queue prompts; the inspected daemon has no supervisor-owned non-inference engine-reconciliation handler or idle-session restart guarantee. No heartbeat prompt or polling process counts as that capability.

The CLI does not manufacture native generation CAS, durable applied receipts, interactive answers, stop epochs, callback ownership, archive outcomes, scheduler support, provider retry configuration, or compaction-hook receipts. Unsupported capability-dependent requests fail before sending a native command.
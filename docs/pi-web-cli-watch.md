# pi-web-cli watch v1

## Syntax

```text
pi-web-cli watch SID --baseline --timeout SECONDS
pi-web-cli watch SID --since FILE --timeout SECONDS
```

`PI_WEB_URL` selects the API base URL. The default is `http://127.0.0.1:8504`. Watch uses direct HTTP or HTTPS connections without environment proxies, credentials, or redirects. A baseline names the exact API URL and session ID.

`--baseline` writes a baseline JSON object after a status, history, and status check. Both statuses must be idle, without queued work, pending questions, file diagnostics, or runtime messages. History must be empty. The timestamp is diagnostic, not an attribution boundary.

`--since FILE` reads that successful baseline before observation. The caller must capture the baseline before sending exactly one initial model prompt. The caller must exclusively own the fresh session until watch returns. Competing prompts, branch changes, and lifecycle operations invalidate this contract. Additional user messages or changes to an observed history prefix return `unknown`.

A caller-owned sequence is:

```bash
pi-web-cli watch "$SID" --baseline --timeout 5 >"$BASELINE" &&
pi-web-cli prompt "$SID" "Initial model prompt" &&
pi-web-cli watch "$SID" --since "$BASELINE" --timeout 120
```

The caller can run `--since` in a managed subprocess or asynchronous job. Watch emits no progress records. Standard output contains only the selected result. Starting the watcher before prompt delivery does not require observing streaming, but this baseline-only contract has no readiness acknowledgement.

Watch sends only GET requests to status, messages, and the session WebSocket. It never prompts, answers questions, clears queues, retries, stops, or changes admission. Backend reads can reopen a cold runtime. The caller owns lifecycle and any action after the outcome.

## Outcomes

Watch writes one JSON object. `schemaVersion` is `1`, and `kind` is `watch`. `ok` is true only for `completed`. A successful baseline has `kind: "baseline"` and `ok: true`.

| `outcome` | Meaning |
| --- | --- |
| `completed` | Attributable terminal assistant text with `stopReason: "stop"`, file-existence evidence, live native settlement, and a subsequent inactive status/history/status reconciliation. |
| `needs_input` | `pendingAsk` or `pendingDialogs` is present. Questions override streaming. |
| `failed` | The terminal attributable assistant has `stopReason: "error"` after native settlement and inactive reconciliation. |
| `interrupted` | The terminal attributable assistant has `stopReason: "aborted"` after native settlement and inactive reconciliation. |
| `unknown` | Attribution, terminal reason, transport, persistence, or settlement evidence cannot prove the result. |
| `timeout` | The deadline expires without a provable terminal result. Initial idle is never success. |

Exit status is zero only for `completed` or a successful baseline. Other watch results exit one. Argument syntax errors retain argparse's exit status of two.

Every watch result includes:

- `sessionId`, `outcome`, and a machine-readable `reason`.
- `finalAssistant`, which is non-null only for `completed`.
- `candidateAssistant`, which can contain unproven terminal text or error and interruption evidence. This is never a successful final answer.
- `questions`, with `askId`, every `questionIds` entry, and every `dialogIds` entry. An absent ask has a null ID.
- `evidence`, with the latest reconciled status summary, history count, and bounded event observations. Event errors include bounded message excerpts and an explicit truncation flag.

Assistant objects contain `text`, `stopReason`, and `reference`. They include `errorMessage` when present. Watch skips trailing automatic compaction records and returns text from the last remaining message if its role is assistant. It joins text blocks with newlines.

A reference contains the exact `sessionId`, zero-based `historyIndex`, and `sha256` of the projected message. `responseId` is included when available. The digest uses UTF-8 JSON with sorted keys, no ASCII escaping, and separators `,` and `:` without spaces. It is a snapshot reference, not a native entry ID or durable run identity. Prompt `deliveryId` is only a receipt and is not used by watch.

## Evidence limits

Native `agent_settled` arrives as `pi.event` on `/api/sessions/:id/events`. Subscription has no replay. Idle status can precede unfinished settlement extension hooks. A fast answer completed before subscription can therefore return `unknown` with recovered candidate text. A quiet interval never proves completion.

Settlement must precede the history read used for completion. `agent.end`, tool errors, retries, compaction, queued work, activity labels, and disconnects are not completion evidence. Streaming includes retry and post-run continuation. Observed streaming, compaction, bash, or queued work prevents completion. An observed `session.error` prevents a successful result, even if candidate assistant text exists.

Watch polls independently of WebSocket traffic. It makes one subscription attempt and does not reconnect. A disconnect, sequence gap, invalid frame, or event overflow removes settlement proof for this invocation. Sequence numbers are process-local observations, not durable identities.

The messages endpoint projects branch history. `persisted` reports session-file existence, not successful per-message disk writes or fsync. Watch cannot prove crash durability, exclusive ownership, invisible mutations between reads, or future work scheduled outside the observed run. Both array history and complete `{messages,start,total}` history are accepted. Partial history returns `unknown`.

## Bounds and verification

`SECONDS` is finite and between `0.1` and `86400`. One monotonic deadline covers baseline files, connection setup, HTTP, WebSocket reads, waiting, and output. Up to 100 milliseconds of that budget is reserved for output. Each HTTP read is bounded only by the remaining deadline, so a slow backend response is never reported as a timeout before the deadline. `io_deadline` therefore always means the command deadline expired; a timeout that fires earlier returns `unknown` with `reason: "io_timeout"`. Daemon I/O workers cannot keep the deadline-owning process waiting on stalled I/O.

Limits are 64 KiB per baseline file, 4 MiB per HTTP body, 10,000 history messages, 16 KiB of WebSocket handshake headers, 1 MiB per WebSocket message or frame, 256 buffered event summaries, and 1 MiB of output. At most eight event errors are retained, with 1,024 characters per error excerpt. Identifiers are limited to 1,024 characters. Each pending question or dialog list is limited to 256 items. Oversized output returns `unknown` with `reason: "output_limit"` instead of truncating final text.

A blocked or closed stdout reader can prevent delivery of the JSON object. Watch still exits within its deadline and returns nonzero. No command can guarantee delivery to a reader that does not accept bytes.

The dependency-free fixture invokes the actual executable against controlled HTTP and WebSocket endpoints:

```bash
python3 scripts/check-pi-web-cli-watch.py
```

## One-shot run

```text
printf '%s' "$PROMPT" | pi-web-cli run CWD --model PROVIDER/ID --thinking LEVEL --timeout SECONDS
```

`run` performs the whole delegation in one process and prints exactly one compact JSON line. The prompt is read from standard input as UTF-8 (at most 4 MiB, refused when empty). Model and thinking level have no defaults. One monotonic deadline covers every step, including reading stdin and output.

Steps, in order: spawn (`POST /api/sessions`), set model, set thinking level, read status and confirm provider, id, and thinking level match the request (`settings_check`), capture an in-memory baseline with the same validation as `watch --baseline`, start the watcher on that baseline, wait until the event WebSocket is open (at most 10 s, `subscribe`), then send the prompt once and wait for the watch result. The prompt is never sent unless the socket is open. The command never stops, archives, or deletes the session. The caller owns cleanup, using the returned `sessionId`.

Result:

```json
{"schemaVersion":1,"kind":"run","ok":true,"outcome":"completed","reason":"native_settled_and_reconciled","sessionId":"...","cwd":"...","settings":{"model":"provider/id","thinkingLevel":"high"},"failedStep":null,"error":null,"finalAssistant":{},"candidateAssistant":null,"questions":{},"evidence":{},"baseline":{}}
```

`outcome` is a watch outcome (`completed`, `needs_input`, `failed`, `interrupted`, `unknown`, `timeout`) or `setup_failed`. The shared fields (`reason`, `finalAssistant`, `candidateAssistant`, `questions`, `evidence`) keep the watch meaning. `ok` is true, and the exit status is zero, only for `completed`. Other results exit one. Argument syntax errors retain argparse's exit status of two.

- `sessionId` is null only when spawn failed or input was refused. `settings` is non-null once the settings check passed. `baseline` is the baseline object, usable later with `watch --since`, and is null before capture.
- `setup_failed` means the prompt was not sent, except `failedStep: "prompt"`. `failedStep` is one of `spawn`, `model`, `thinking`, `settings_check`, `baseline`, `subscribe`, `prompt`, or null for refused input (`reason` `empty_prompt`, `invalid_prompt`, `prompt_too_large`, `invalid_input`). `error` is `{"status": int|null, "detail": string}`, with `detail` cut at 500 characters. A deadline during a setup step is `setup_failed` with `reason: "deadline"` and that step.
- A prompt POST that fails at transport level or times out (receipt unknown) does not fail the run. The watcher keeps running, the watch outcome is the truth, and the prompt error is recorded in `error` with `status: null`. The prompt POST is bounded by half of the deadline, at most 30 s. A definite rejection (HTTP status other than 200, or `accepted` not true) returns `setup_failed` with `failedStep: "prompt"`.
- `timeout` and `unknown` results keep `sessionId`, `settings`, and `baseline`, so the caller can resume with `watch --since`.

Output size and stalled-stdout guarantees match `watch`: oversized output returns `unknown` with `reason: "output_limit"` and keeps the identity fields, and a stalled stdout reader cannot keep the process past its deadline.

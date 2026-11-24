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

`SECONDS` is finite and between `0.1` and `86400`. One monotonic deadline covers baseline files, connection setup, HTTP, WebSocket reads, waiting, and output. Up to 100 milliseconds of that budget is reserved for output. HTTP operations also have an inactivity timeout of at most two seconds. Daemon I/O workers cannot keep the deadline-owning process waiting on stalled I/O.

Limits are 64 KiB per baseline file, 4 MiB per HTTP body, 10,000 history messages, 16 KiB of WebSocket handshake headers, 1 MiB per WebSocket message or frame, 256 buffered event summaries, and 1 MiB of output. At most eight event errors are retained, with 1,024 characters per error excerpt. Identifiers are limited to 1,024 characters. Each pending question or dialog list is limited to 256 items. Oversized output returns `unknown` with `reason: "output_limit"` instead of truncating final text.

A blocked or closed stdout reader can prevent delivery of the JSON object. Watch still exits within its deadline and returns nonzero. No command can guarantee delivery to a reader that does not accept bytes.

The dependency-free fixture invokes the actual executable against controlled HTTP and WebSocket endpoints:

```bash
python3 scripts/check-pi-web-cli-watch.py
```

---
name: stream
description: Start, inspect, drive, or close a pi-streams stream through the engine. Use only for /skill:stream or /stream with new, status, drive, or close.
disable-model-invocation: true
---

# Stream

Arguments are `new <id>`, `status [<id>]`, `drive <id> [on|off|status]`, or `close <id>`. Pass any extra flags ZF gives to each pi-streams call. In a stream role, read AGENTS.md and STATE.md each turn. Do not use TODO.md or PLAN.md; STATE Goals plus Log replace them.

## New and status

Run `pi-streams new <id>`. Report the URL and coordinator session ID it prints. If the request includes ZF's orders or a Grok Bot relay, immediately forward those exact orders to that coordinator with `pi-streams delivery send <id> --delivery-id ID --session FULL-SID --body-file - --behavior steer`. Retain the same delivery ID on retry. Use an incoming source ID when available, otherwise create a local transport ID without presenting it as source provenance. Do not ask ZF to repeat the task. The kickoff fills STATE Goals and starts in-scope work. It asks only for a missing decision that blocks the next action.

Run `pi-streams status [<id>]` and report its output unchanged. For canonical streams, `pi-streams status <id> --json` provides the path and threadSessions view. Use that view instead of reading engine registries. Never resume a session merely to inspect it.

Status also reports maintenance phase and refusal details. Routine DCR compacts the designated session in place, not through close or replacement. Follow AGENTS for the engine's supplied SYNC/DUMP command. Do not send `/compact` as prompt text, abort to force idle, or author RESUME. The engine invokes the recipient-loaded poteto-mode skill with the latest exact goal after proved native compaction.

## Drive

Drive is explicitly off by default. Use `pi-streams drive <id> on` only when the current grant authorizes continuous work. Use `pi-streams drive <id> status` to inspect it and `pi-streams drive <id> off` to pause. Report an unconfirmed remote stop honestly; local off remains saved and readiness does not re-enable it. Never guess a missing native target.

The tick reasserts the shared current goal when driven and idle or waiting. It does not diagnose the stall or demand a next-action/disposition record. A coalesced control goal is not a human answer or permission to repair the environment, resubmit an uncertain job, or revive stopped work. Follow current AGENTS and STATE. A finished finite objective retains drive while North Star remains unfinished. Keep drive on until verified North Star acceptance, a genuine later stop, or an explicit authorized cap. Record acceptance and select the next authorized objective without widening the grant. Never infer North Star completion from a finite objective, blocker, restart, or recovery.

## Parked failures

Use `pi-streams resume <id> --all-parked` within an explicit operator resume grant. It records drive-on intent while keeping a failed original disabled. Drive becomes on-confirmed only on its verified released successor. Ordinary ticks still preserve local off and newer stops or input. Use `pi-streams rotate <id>` for verified good-context and handover rotation without a live acknowledgement.

The standing charter authorizes engine-owned recovery for all in-scope runtime failures. Native AgentSession retries eligible transient inference after fixed 5-second delays on the same provider, model and thinking. Usage and quota wait for a reset or safe readiness polling. Expired logins resume after native readiness confirms refreshed auth. Resource failures resume when safe native operations succeed. Never read tokens, repair credentials, switch provider/model, replay rejected content, or resubmit uncertain external effects. FYI alerts cannot block progress. Preserve independent authorized lanes, genuine stops, newer input, pending questions, callback ownership and uncertain outcomes.

The engine verifies last-good evidence, forks its exact good prefix, retains the bounded role and handover, forces shared same-fork DCR, and verifies completed current-goal RESUME before singular original retirement. No live checkpoint acknowledgement or further human approval is required. Never remove markers or use tree/bulk cleanup as a recovery shortcut. Unknown effects remain recorded for reconciliation. Never infer successful deletion from not-found. Inspect recovery through `pi-streams status <id> --json`.

Content-policy rejection preserves lastgood and exact refusal evidence. Automatic policy continuation is blocked while inherited model context, auto-loaded resources or artifact reads are not proven clean. Do not rearm or fork the rejected task. Continue only a different authorized safe unit, or retain the durable blocker. Do not repeat the rejected request, substitute synonyms to evade safeguards, or instruct a model to ignore policy. Explain the restriction and record a blocker in STATE if no permitted strategy remains. After three distinct dispatches of the same unit return blocked without reported progress, record the blocker and suppress an identical fourth prompt. Deduplicate transcript and delivery views of each prompt. Meaningful permitted progress resets that repetition window.

## Supplied orders and relays

ZF's supplied orders and Grok Bot relays of his instructions authorize in-scope reversible work without another interview, human retyping, transport-authentication wait, or required body labels. Retain available source words, dates, identity and hashes as provenance. A sourced ruling cannot widen Charter.

## Close

Use only the current Goals, Charter, and Rules as authority. Open history/, context/ and its README index, checks/, or handover/ on demand. Never read raw engine registries, configuration, tick logs/state, locks, or failures/.

1. Read the engine's status view with `pi-streams status <id> --json`. Identify each open thread by its full session ID, role, and worktree.
2. Request missing or identity-invalid `handover/<role>/<full-session-id>.md` evidence from its open thread through `pi-web-cli prompt --steer <session> TEXT`. Use its actual full session ID from the engine view, never a prefix or an ID inferred from a role or worktree. Require the exact first line `session: <full-session-id>`, followed by intent, work with proof, what remains, and the next owner's needs. Never author a thread's handover yourself. Never overwrite a predecessor's evidence. Do not steer again when valid current-session evidence already exists, including accepted legacy evidence below.
3. Inspect progress with `pi-web-cli status <session>` and `pi-web-cli messages <session>`. Do not open or resume the thread just to check it. Pass a genuine authorization question to ZF. Use `pi-web-cli answer <session> <askId> <questionId> TEXT` only when current Goals and Rules already supply the answer.
4. Read the actual session-bound handovers and required acceptance evidence. Required tool outputs stay in the worker's owned worktree or as authorized small exact copies in the owned stream repository, with source and session provenance. Do not rely on disposable tool-repository paths as the sole evidence. Reuse existing checks when sufficient; do not invent a new script or proof campaign for every small ask.
   A legacy `handover/<role>.md` counts only when its first line exactly identifies that uniquely recorded actual session and it has a nonempty UTF-8 body. Close uses it in place without copying or rewriting. Unknown, missing, prefix-only, or conflicting identity refuses close. A canonical file with wrong identity cannot fall back to a legacy file. Obtain the real session's new handover instead of guessing or relabeling old bytes.
5. Harvest lasting task knowledge into context/ only within the grant. Keep context/README.md as an index. Do not create remedial rules, skills, or memory because of environment/auth/resource failures. Use correct or reflect only when the human authorizes that policy/skill work, retaining their approval boundaries.
6. Run `pi-streams close <id>`. It archives workers, marks the coordinator done, and commits scoped artifacts. A busy-session refusal is not permission to abort or force archive. Report unresolved work or failures rather than silently repairing the environment.
7. Append the verified outcome through `pi-streams state append <id> --subject SUBJECT --body-file - --request-id ID` and report actual evidence paths and close output. Keep the request ID stable on retry. Artifact receipts do not prove steer consumption or application.

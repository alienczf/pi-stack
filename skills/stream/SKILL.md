---
name: stream
description: Start, inspect, drive, or close a pi-streams stream through the engine. Use only for /skill:stream or /stream with new, status, drive, or close.
disable-model-invocation: true
---

# Stream

Arguments are `new <id>`, `status [<id>]`, `drive <id> [on|off|status]`, or `close <id>`. Pass any extra flags ZF gives to each pi-streams call. In a stream role, read AGENTS.md and STATE.md each turn. Do not use TODO.md or PLAN.md; STATE Goals plus Log replace them.

## New and status

Run `pi-streams new <id>`. Report the URL and coordinator session ID it prints. The new STATE is explicitly unratified. The kickoff waits for ZF in that coordinator.

Run `pi-streams status [<id>]` and report its output unchanged. For canonical streams, `pi-streams status <id> --json` provides the path and threadSessions view. Use that view instead of reading engine registries. Never resume a session merely to inspect it.

Status also reports maintenance phase and refusal details. Routine DCR compacts the designated session in place, not through close or replacement. Follow AGENTS for the engine's supplied SYNC/DUMP command. Do not send `/compact` as prompt text, abort to force idle, or author RESUME. The engine invokes the recipient-loaded poteto-mode skill with the latest exact goal after proved native compaction.

## Drive

Drive is explicitly off by default. Use `pi-streams drive <id> on` only when the current grant authorizes continuous work. Use `pi-streams drive <id> status` to inspect it and `pi-streams drive <id> off` to pause. Report an unconfirmed remote stop honestly; local off remains saved and readiness does not re-enable it. Never guess a missing native target.

The tick reasserts the shared current goal when driven and idle or waiting. It does not diagnose the stall or demand a next-action/disposition record. A coalesced control goal is not a human answer or permission to repair the environment, resubmit an uncertain job, or revive stopped work. Follow current AGENTS and STATE. A finished objective may select another authorized objective or end driving, never complete North Star.

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

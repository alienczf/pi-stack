---
name: stream
description: Start, inspect, or close a pi-streams stream through the engine. Use only for /skill:stream or /stream with new, status, or close.
disable-model-invocation: true
---

# Stream

Arguments are `new <id>`, `status [<id>]`, or `close <id>`. Pass any extra flags ZF gives to each pi-streams call. In a stream role, read AGENTS.md and STATE.md each turn. Do not use TODO.md or PLAN.md; STATE Goals plus Log replace them.

## New and status

Run `pi-streams new <id>`. Report the URL and coordinator session ID it prints. The new STATE is explicitly unratified. The kickoff waits for ZF in that coordinator.

Run `pi-streams status [<id>]` and report its output unchanged. For canonical streams, `pi-streams status <id> --json` provides the path and threadSessions view. Use that view instead of reading engine registries. Never resume a session merely to inspect it.

## Close

Use only the current Goals, Charter, and Rules as authority. Open history/, context/ and its README index, checks/, or handover/ on demand. Never read raw engine registries, configuration, tick logs/state, locks, or failures/.

1. Read the engine's status view with `pi-streams status <id> --json`. Identify each open thread by its full session ID, role, and worktree.
2. Request the missing `handover/<role>.md` from each open thread through `pi-web-cli prompt --steer <session> TEXT`. The request names intent, work with proof, what remains, and the next owner's needs. Never author a thread's handover yourself.
3. Inspect progress with `pi-web-cli status <session>` and `pi-web-cli messages <session>`. Do not open or resume the thread just to check it. Pass a genuine authorization question to ZF. Use `pi-web-cli answer <session> <askId> <questionId> TEXT` only when current Goals and Rules already supply the answer.
4. Read the actual handovers and required acceptance evidence. Reuse existing checks when sufficient; do not invent a new script or proof campaign for every small ask.
5. Harvest lasting task knowledge into context/ only within the grant. Keep context/README.md as an index. Do not create remedial rules, skills, or memory because of environment/auth/resource failures. Use correct or reflect only when the human authorizes that policy/skill work, retaining their approval boundaries.
6. Run `pi-streams close <id>`. It archives workers, marks the coordinator done, and commits scoped artifacts. A busy-session refusal is not permission to abort or force archive. Report unresolved work or failures rather than silently repairing the environment.
7. Append the verified outcome through `pi-streams state append <id> --subject SUBJECT --body-file - --request-id ID` and report actual evidence paths and close output. Keep the request ID stable on retry. Artifact receipts do not prove steer consumption or application.

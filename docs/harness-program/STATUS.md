---
# Machine-readable harness-program status. The driving routine reads this YAML front matter every run.
# Times are Asia/Singapore (UTC+8). Only Grok Bot edits this file.
program: harness-program
repo: alienczf/pi-stack
docs_branch: docs/harness-program
pr: https://github.com/alienczf/pi-stack/pull/37
tracking_issue: https://github.com/alienczf/pi-stack/issues/38
box_mirror: /workspace/harness-program
host_docs_worktree: /home/alphalab/Projects/worktrees/pi-stack-harness-program
host_input_copy: /home/alphalab/Projects/pi-stack/streams/pi-streams-harness/context/harness-program
updated: 2026-10-23T09:50+08:00
tracks:
  - id: 1
    name: pi-streams must-fix catalog
    session: 01a16655-5cfd-78c2-bf5f-e08c47e1665e
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: catalog-drafting
    started: 2026-10-23T09:17+08:00
    expected_done: 2026-10-23T11:30+08:00
    artifact: docs/harness-program/10-pi-streams-fix-catalog.md
    brief: docs/harness-program/briefs/track-1.md
    steers: [docs/harness-program/briefs/track-1-steer-1.md]
    brief_sha256_verified: true
    gate: ZF first-pass review of the catalog. Don't send until it reflects all ZF calls (Z1-Z5 plus any later ones).
    next_action: When the session goes idle with "TRACK 1 STATUS", pull the artifact, check it against Z1-Z5 and later calls, commit it to the docs branch, then send it to ZF for review.
  - id: 2
    name: prime-agent CLI (design + feat/prime-cli)
    session: 01a16656-ddcb-76c7-a44b-c7298bcb0198
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: design
    started: 2026-10-23T09:19+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/20-prime-cli-design.md
    code_branch: feat/prime-cli
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-prime-cli
    brief: docs/harness-program/briefs/track-2.md
    brief_sha256_verified: true
    blocked_on: null
    open_questions: [caladan (pi-bot caladan bb39dc0; no pi-stack branch), non-blocking]
    next_action: When idle, pull the design doc, commit it to the docs branch, then bundle feat/prime-cli from the host and push it from the box. Streams-on-prime port waits for track 1 to merge.
  - id: 3
    name: problem-state research + three designs
    session: 01a16658-09d0-7fcc-9815-7ac75f2cbb29
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: a-problem-statements
    started: 2026-10-23T09:21+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/30-research-designs.md
    inputs: [docs/harness-program/31-x-corpus-seed.md]
    brief: docs/harness-program/briefs/track-3.md
    steers: [docs/harness-program/briefs/track-3-steer-1.md]
    brief_sha256_verified: true
    steer_note: steer-1 queued (pendingMessageCount=1) at 09:50; confirm it was consumed
    next_action: When idle, pull 30-research-designs.md (and 30a if it exists), commit it, then give ZF the three-design table.
---

# Harness program status

| Track | Session | Phase | Artifact | Next |
|---|---|---|---|---|
| 1 fix catalog | `01a16655` | catalog-drafting | `10-pi-streams-fix-catalog.md` | Collect, check against Z1–Z5, then send to ZF for review |
| 2 prime CLI | `01a16656` | design | `20-prime-cli-design.md` + `feat/prime-cli` | Collect the design, push the branch |
| 3 research | `01a16658` | a-problem-statements | `30-research-designs.md` | Collect, then send ZF the table |

The canonical copy is on GitHub. The box mirror is `/workspace/harness-program/STATUS.md`.

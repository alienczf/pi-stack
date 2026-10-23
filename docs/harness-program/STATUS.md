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
updated: "2026-10-24T07:25+08:00 (driver run: T1 streaming 60.8% on S3 0587832, compact at next idle; T6 idle 47.0% blocked on operator Codex login, f5beb90; T2 idle, login not recorded)"
tracks:
  - id: 1
    name: pi-streams must-fix catalog
    session: 01a16655-5cfd-78c2-bf5f-e08c47e1665e
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: "implementing - S1 done (6b2f1ab); S2 nearly done (stop/cancel admission d2a378b pi-web + dfd9ab6 streams; suites 254 pi-streams / 2324 pi-web pass); last S2 unit safe coordinator rotation, then S2a-S6. Compacted 01:38-01:41 (65.7% -> ~15%); reentry-5 c604f050 landed (confirmed 01:55)"
    milestones_sent: [track-1-review-ready 2026-10-23T11:01+08:00]
    go_ahead: 2026-10-23T11:35+08:00 (ZF t221u, GO in 03)
    started: 2026-10-23T09:17+08:00
    expected_done: 2026-10-23T18:00+08:00
    artifact: docs/harness-program/10-pi-streams-fix-catalog.md
    brief: docs/harness-program/briefs/track-1.md
    steers: [docs/harness-program/briefs/track-1-steer-1.md, docs/harness-program/briefs/track-1-steer-2.md, docs/harness-program/briefs/track-1-steer-3.md, docs/harness-program/briefs/track-1-reentry-1.md, docs/harness-program/briefs/track-1-go.md, docs/harness-program/briefs/track-1-reentry-2.md, docs/harness-program/briefs/track-1-reentry-3.md, docs/harness-program/briefs/track-1-reentry-4.md, docs/harness-program/briefs/track-1-reentry-5.md]
    steer_note: 10:27 context 86.8% -> aborted, cleared unconsumed steer-3, /compact via PI WEB commands/run (G19). 10:34 re-entry-1 (brief + phase + steer-3 folded in, sha 742d71f3) consumed, streaming, context 9.8%. Compact recipe - curl -X POST 127.0.0.1:8504/api/sessions/<sid>/commands/run -d {"text":"/compact"} on the host; pi-web-cli prompt "/compact" does NOT compact. 11:38 go steer (briefs/track-1-go.md, sha aaa62d2f; Z13-Z15 amendments + implement S1-S6) sent while idle at 33.9%, consumed (byte match), streaming at 35.7%.
    inputs: [docs/harness-program/11-artifact-map.md]
    code_branch: feat/streams-must-fix (off main 3acf0f0; pi-web source gets a same-named local branch)
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-streams-must-fix
    progress: docs/harness-program/12-track-1-progress.md
    brief_sha256_verified: true
    gate: Session reports S1-S6 done (TRACK 1 STATUS done line) with the full suite and F-DCR round-trip passing.
    next_action: Each run, read the latest TRACK 1 STATUS line and 12-track-1-progress.md; compact via commands/run if context > 60% at an idle boundary and re-enter from the progress file. When it reports done, the driver merges feat/streams-must-fix (and the pi-web branch) to main, rebases live branches, verifies. Grok Bot does Twingate wrapper prerequisite E on the box.
  - id: 2
    name: prime-agent CLI (design + feat/prime-cli)
    session: 01a16656-ddcb-76c7-a44b-c7298bcb0198
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: blocked-on-prime-codex-login (non-inference parity gaps in progress, steer-1 consumed 10:59)
    milestones_sent: [track-2-blocker-prime-login 2026-10-23T11:01+08:00]
    started: 2026-10-23T09:19+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/20-prime-cli-design.md
    code_branch: feat/prime-cli
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-prime-cli
    brief: docs/harness-program/briefs/track-2.md
    steers: [docs/harness-program/briefs/track-2-steer-1.md, docs/harness-program/briefs/track-2-reentry-1.md]
    steer_note: 11:31 context 84.5% (~422k) -> aborted, /compact via commands/run (G21), now 19.1%; session auto-continued its in-flight verification. reentry-1 consumed (11:52); session idle at ~3% context, 71 offline tests pass, reports TRACK 2 STATUS blocked on ZF Prime login.
    brief_sha256_verified: true
    blocked_on: ZF interactive openai-codex login for Prime on options-01 (blocker note sent once, 11:01)
    open_questions: [caladan (pi-bot caladan bb39dc0; no pi-stack branch), non-blocking]
    pushed: feat/prime-cli 6bc1242 (2026-10-23 11:58, driver)
    next_action: When idle, collect, push feat/prime-cli again. After ZF logs Prime in, run the inference verification script from the design doc and the off-host wrapper check from the box, then send the track-2-working milestone. Streams-on-prime port waits for track 1 to merge.
  - id: 3
    name: problem-state research + three designs
    session: 01a16658-09d0-7fcc-9815-7ac75f2cbb29
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: "done 18:21 (TRACK 3 STATUS: done (A over Prime)); 31 passed gate 18:22 (G33). Compacted 18:08-18:11 (87.3% -> ~27%), re-entry-1 sha bfd69ee5 byte match 18:12."
    milestones_sent: [track-3-designs-ready 2026-10-23T11:01+08:00]
    started: 2026-10-23T09:21+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/31-design-a-detailed.md (after 30-research-designs.md)
    inputs: [docs/harness-program/31-x-corpus-seed.md]
    brief: docs/harness-program/briefs/track-3.md
    steers: [docs/harness-program/briefs/track-3-steer-1.md, docs/harness-program/briefs/track-3-steer-2.md, docs/harness-program/briefs/track-3-steer-3.md, docs/harness-program/briefs/track-3-steer-4.md, docs/harness-program/briefs/track-3-reentry-1.md]
    brief_sha256_verified: true
    steer_note: steer-1 consumed (09:53). steer-2 (Z12 five inputs, coverage table, three proposals, blocking decisions) consumed 10:11 (sha match, streaming, pending 0).
    next_action: "Z20+Z21. Wait for 'TRACK 3 STATUS: done (A over Prime)'. Gate - first line 'Runtime: Prime (Z20)', 8 headings, New concepts table near the top (fewest rows), hooks name Prime extension points, native Prime changes listed, no retired names or H/P codes. When 31 and 42 both pass, send track 5 'GO track 5 steer 1'."
  - id: 4
    name: proposal B over prime (feasibility spike)
    session: 01a166e0-220d-7dbc-8b1c-719e872dad2d
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: "done 15:45 (TRACK 4 STATUS: done, 42 stock Prime; 41 reference only). 42 passed gate 15:55 (G30). Branch unchanged at 8811a7a (already pushed)."
    pushed: spike/b-over-prime 8811a7a (2026-10-23 12:53, driver)
    started: 2026-10-23T11:51+08:00
    expected_done: 2026-10-23T15:30+08:00
    artifact: docs/harness-program/40-b-over-prime.md, docs/harness-program/41-design-b-prime-detailed.md (reference only), docs/harness-program/42-design-b-prime-unchanged.md
    brief: docs/harness-program/briefs/track-4.md
    steers: [docs/harness-program/briefs/track-4-steer-1.md, docs/harness-program/briefs/track-4-steer-2.md, docs/harness-program/briefs/track-4-steer-3.md, docs/harness-program/briefs/track-4-steer-4.md]
    brief_sha256_verified: true (195ea3ad, byte match as last user message)
    code_branch: spike/b-over-prime (off origin/main 3acf0f0; worktree created by the session, confirmed 11:52)
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-b-over-prime
    session_cwd: /home/alphalab/Projects/pi-stack/pi-stack (same as tracks 1-3; pi creates the worktree per orchestrate-with-pi)
    inputs: [docs/harness-program/30-research-designs.md, docs/harness-program/20-prime-cli-design.md, feat/prime-cli, /home/alphalab/Projects/prime-agent, docs/harness-program/02-principles.md]
    gate: TRACK 4 STATUS done line with 40 covering (a)-(d) and 41 with the Z19 8 headings; spike commits local only. Design not locked (Z17), input only.
    next_action: Each run, read the latest TRACK 4 STATUS line; confirm the worktree and branch exist; compact via commands/run if context > 60% at an idle boundary. When done, collect 40 and 41, push spike/b-over-prime from a bundle; with 31 also done, write 50-a-vs-b.md and send ZF (no decision framing).
  - id: 5
    name: A vs B side-by-side comparison (Z19)
    session: 01a1671a-01d1-7f51-b240-533efc527a61
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: "done 01:15 (TRACK 5 STATUS: done (51 + 50 revised per Z25)); gate passed 01:30 (G38). Earlier: revising 51 + 50 per Z25 (steer-2 sent 2026-10-24 00:46, sha e9ac4de5, byte match; steer-3 Z26 follow-up 00:48:20, sha 609ab238, byte match; streaming at ~61% - compact at next idle boundary if still > 60%). Earlier: done 18:37, 51 and 50 v2 passed gate 18:58 (G34)"
    started: 2026-10-23T12:53+08:00
    expected_done: 2026-10-23T14:00+08:00
    artifact: docs/harness-program/50-a-vs-b.md
    brief: docs/harness-program/briefs/track-5.md (sha256 e546f734)
    steers: [docs/harness-program/briefs/track-5-standby.md, docs/harness-program/briefs/track-5-steer-1.md, docs/harness-program/briefs/track-5-steer-2.md, docs/harness-program/briefs/track-5-steer-3.md]
    gate: TRACK 5 STATUS done; 50 has core difference, per-component side-by-side, pros/cons, effort and risk, corpus coverage, open questions without defaults.
    next_action: "Z25/G36. Wait for 'TRACK 5 STATUS: done (51 + 50 revised per Z25)'; compact via commands/run if context > 60% at an idle boundary. Then collect and check the merged_revision_z25 gate; on pass set merged_revision_z25 done and send ZF one short message (once)."
    gate_z25: "51 first line unchanged; 8 headings; empty New concepts table; no H/P codes or retired STREAM/ACTIONS/GOAL/DECISIONS names; zero open questions; Not handled worded as permanently out of scope; stock automatic compaction disabled (compaction.enabled=false before session build) with one pi-stack-owned percentage check -> save STATE -> direct compact -> readback -> resume (no stock compact-at-threshold hook, no duplicate DCR hook); workers have no state files (handover + kickoff only, no shared coordinator/worker pair); no per-internal-request freshness or per-tool stop gap reported; stale pi-stack messages rejected and running tool calls stopped best-effort; attachments rejected; result review is the stream's own adversarial review against original intent in AGENTS.md text with reviewer spawned only when judged needed (no hook); 50 updated with Z25 answers and no open questions; section 8 concrete enough to code the PoC from (files, functions, stacked commits with tests, end-to-end PoC check) and includes an install commit for a fresh external machine (stock Prime v0.10.1, compaction.enabled=false, hooks, templates, fresh-machine test commands; login left to the user)."
  - id: 6
    name: merged-design proof of concept (Z26)
    session: 01a169cc-9519-7411-bf2f-51073758fc53
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: "blocked-on-prime-codex-login - TRACK 6 STATUS blocked | feat/merged-poc@f5beb90 | suite=pass (221 streams + 72 root + 8 installer) | install=pass (clean HOME) | e2e=pending native inference. Idle 47.0% at 05:58."
    milestones_sent: [track-6-blocker-prime-login 2026-10-24T05:58+08:00]
    login_command: "HOME=/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home /home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home/pi-stack-merged-poc-test/bin/prime-agent then /login in the TUI"
    started: 2026-10-24T01:26+08:00
    pushed: feat/merged-poc f5beb90 (2026-10-24 05:57, driver; fast-forward over 7503ca4)
    code_branch: feat/merged-poc (session creates worktree /home/alphalab/Projects/worktrees/pi-stack-merged-poc off local main + feat/prime-cli)
    deadline: 2026-10-26T09:00+08:00
    brief: docs/harness-program/briefs/track-6.md (final sha256 4ec99908, aligned to revised 51 section 8)
    progress: docs/harness-program/13-track-6-progress.md
    source: "ZF t234u 00:46 SGT (Z26/G37): drive over the weekend; tell ZF when a working PoC is on the branch; update install for a new external setup"
    gate: "Branch feat/merged-poc pushed; revised 51 section 8 commits implemented with their tests passing; end-to-end PoC check (one stream on stock Prime v0.10.1: intake -> own percentage compaction (save, compact, resume) -> ask close) passes; install updated and verified from a fresh external-style setup (clean HOME/dir) with the documented commands; login is the user's own step."
    next_action: "Each run read the latest TRACK 6 STATUS line and 13-track-6-progress.md; bundle-push feat/merged-poc when commits exist; compact if > 85% (or > 60% at idle). On gate pass, send ZF one message with the branch and the fresh-setup test commands, set poc_sent."
comparison_sent: 2026-10-23T13:25+08:00 (v1, handed to main chat via WakeParent; never resend; superseded by Z20)
comparison_v1_superseded: true
a_over_prime_done: true (2026-10-23T18:22+08:00, gate passed, G33)
naming_cleanup_done:
  '31': true
  '41': "dropped - G29, 41 reference only"
  '42': true
  '51': true
  '50v2': true
b_unchanged_done: true (2026-10-23T15:55+08:00, gate passed)
merged_done: true (2026-10-23T18:58+08:00, gate passed, G34)
merged_revision_z25: done (2026-10-24T01:30+08:00, gate passed, G38; T5 reported done 01:15)
merged_revision_z25_sent: null
track_6_session: 01a169cc-9519-7411-bf2f-51073758fc53
poc_sent: false
poc_deadline: 2026-10-26T09:00+08:00
comparison_v2_sent: 2026-10-23T19:00+08:00 (handed to main chat via WakeParent; never resend)
reference_only: [docs/harness-program/41-design-b-prime-detailed.md]
usage_limit:
  open: 2026-10-23T16:14+08:00
  closed: "2026-10-23T18:11+08:00 (ZF reset the limit 18:06, t231u/Z24; track 3 /compact on openai-codex succeeded 18:11 as the probe; same provider)"
  kind: "ChatGPT usage limit (self_serve_business_prolite) on openai-codex; every session errors 'Try again in ~9176 min'"
  reset_expected: "about 2026-10-30T01:10+08:00 (from 08:14:48Z + 9176 min)"
  zf_told: 2026-10-23T16:30+08:00 (once, via main chat; never resend)
  policy: "(closed) never switch provider; normal driving resumed 18:11"
  parked_at: {T1: "idle 73.8%, S1 6b2f1ab done, disposable check pending, async subagent 7f6b0202 was running", T2: "idle 31.9%, blocked on Prime login", T3: "idle 87.3%, mid-edit of 31 (uncommitted, last check assertion failed) - compact before re-entry", T4: "done, 77.5%", T5: "standby 30.1%"}
  after_reset: "T3 compact via commands/run then re-enter on 31; T1 re-enter from 12-track-1-progress.md (compact first if over 60%); then normal gates"
env_failure_2:
  open: 2026-10-23T19:11+08:00
  closed: 2026-10-23T19:11+08:00 (host reboot; PI WEB back; found 19:25)
  kind: "options-01 reboot - /tmp wiped, T1 turn and S2 subagent 1e2140ca killed"
  action: "T1 reentry-4 19:29 (G35); T2 unaffected"
env_failure:
  open: 2026-10-23T14:50+08:00
  closed: 2026-10-23T15:05+08:00 (all tracks resumed by 15:09; no fork)
  kind: "options-01 outbound network outage - every inference call returns fetch failed"
  last_good_turn: {T1: 337a07cf, T2: 7705e817, T3: e8fc7a93, T4: d92ba0f9, T5: 2142b033}
---

# Harness program status

| Track | Session | Phase | Artifact | Next |
|---|---|---|---|---|
| 1 fix catalog | `01a16655` | implementing; S1 done; S2 last unit (rotation) after `d2a378b`/`dfd9ab6`, suites pass; compacted 01:41 | `10-pi-streams-fix-catalog.md` + `feat/streams-must-fix` | S1-S6 done, then driver merges |
| 2 prime CLI | `01a16656` | blocked on Prime codex login; non-inference gaps in progress | `20-prime-cli-design.md` + `feat/prime-cli` (`6bc1242` pushed) | ZF logs Prime in, then inference verification |
| 3 research | `01a16658` | done 18:21; 31 (A over Prime) passed gate 18:22 | `31-design-a-detailed.md` | feeds 51 |
| 4 B over prime | `01a166e0` | done; 42 passed gate 15:55 | `40`, `41` (reference), `42-design-b-prime-unchanged.md` | feeds 51 |
| 5 merged + v2 | `01a1671a` | done; revised 51 and 50 passed the Z25 gate 01:30 | `51-design-merged.md`, `50-a-vs-b.md` v2 | gate merged_revision_z25, then one short note to ZF |
| 6 merged PoC | `01a169cc` | built and verified offline (f5beb90 pushed); clean-HOME install passes; native end-to-end waits on ZF Codex login (note sent 05:58) | `feat/merged-poc` + install for a fresh external setup | build 51 section 8; tell ZF once when the PoC works (deadline Mon 26 Oct 09:00) |

**Usage limit 16:14-18:11 (closed):** ChatGPT usage limit on openai-codex; ZF reset it at 18:06 and work resumed on the same provider.

**Env failure 14:50-15:05 (closed):** options-01 lost outbound internet and model calls returned `fetch failed`. Every track was resumed by 15:09.

The canonical copy is on GitHub. The box mirror is `/workspace/harness-program/STATUS.md`.

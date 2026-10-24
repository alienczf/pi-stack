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
updated: "2026-10-24T22:02+08:00 (T1 streaming at 67.6%, pending 0; S6 still at main 600e695 / native 61c5e26 with uncommitted failure-retirement edits active in the last 20 min; disposable pending). Prev: 2026-10-24T21:28+08:00 (T1 streaming at 65.1%, pending 0; S6 native 61c5e26 (retire only the verified recovery original with durable receipts; 2409 tests pass); disposable pending). Prev: 2026-10-24T20:56+08:00 (T1 streaming at 64.8%, pending 0; S6 main 600e695 (isolate blocked ratified recoveries within a stream tick; suite pass); disposable pending). Prev: 2026-10-24T20:25+08:00 (T1 streaming at 63.0%, pending 0; S6 advanced to native 3be16e0 (pin receiving-owned fork hold generation; 2401 tests) and main 2ee4028 (forced shared DCR on verified coordinator/worker forks; 384 pass); singular retirement next; disposable pending). Prev: 2026-10-24T19:55+08:00 (T1 streaming at 60.0%, pending 0; S6 committed main aec339c (journal exact recovery forks, bind verified returned SIDs), more failure-recovery edits active; disposable pending). Prev: 2026-10-24T19:22+08:00 (T1 streaming at 57.6%, pending 0; S6 uncommitted failure-recovery edits active, main a6330d5; disposable pending). Prev: 2026-10-24T18:55+08:00 (T1 streaming at 53.7%, pending 0; S6 at native 14a7953 (scope held-fork maintenance to its verified operation; native 2400 tests pass), main a6330d5; disposable pending). Prev: 2026-10-24T18:35+08:00 (T1 streaming at 53.0%, pending 0; S6 at native ba2978b (retain correlated completed-RESUME observations; suite pass), main a6330d5; disposable pending; Twingate userspace flaky this run, collect retried). Prev: 2026-10-24T17:55+08:00 (T1 streaming at 49.4%, pending 0; S6 at native 0ebb4b8 (generic lifecycle cannot bypass failure parking; 2393 tests pass), main a6330d5; disposable back to pending). Prev: 2026-10-24T17:25+08:00 (T1 streaming at 47.6%, pending 0, waiting on its own subagent; S6 at main a6330d5 (verified exact-episode failure notices, 371 pass) after native 77e8c7f (2391 pass); disposable now reported blocked-authenticated-intake by the subagent, re-check at idle). Prev: 2026-10-24T16:55+08:00 (T1 streaming at 43.5%, pending 0; S6 advanced to native 51a03c0 (exact SDK fork behind verified intake; native 2389 tests pass); CLI adapter, fork-DCR driver, instructions, disposable and F-DCR remain). Prev: 2026-10-24T16:25+08:00 (T1 streaming at 43.1%, pending 0; S6 advanced to 9f66776 (affected-session last-good failure markers; main 366 pass) after native 36b69ad; disposable and F-DCR pending). Prev: 2026-10-24T15:55+08:00 (T1 streaming at 42.5%, pending 0; S5 done, now S6 at e051682 (pi-web persist safe stream turns, fence failed runtimes; suite pass), disposable pending; files active in last 20 min). Prev: 2026-10-24T15:25+08:00 (T1 streaming at 40.4%, pending 0; S5 safety unit b54f88c committed (suite 359 pass), off-host companion contract retained as patch, real off-host route blocked-external; moving to S6, files active in last 20 min). Prev: 2026-10-24T14:55+08:00 (T1 streaming at 34.0%, pending 0; S5 main typed failure policy committed 10c882a (suite 356 pass); off-host route proof, rest of S5, S6, F-DCR remain). Prev: 2026-10-24T14:30+08:00 (T1 streaming at 33.4%, pending 0; S5 still at f1722eb with uncommitted failure-policy/usage-recovery edits; no new file writes in 20 min but session is mid-turn). Prev: 2026-10-24T13:58+08:00 (T1 streaming at 32.6%, pending 0; S5 at f1722eb, new failure-policy/usage-recovery edits active). Prev: 2026-10-24T13:30+08:00 (T1 streaming at 29.6%, pending 0; S5 still at f1722eb with uncommitted engine/test edits active in the last 20 min). Prev: 2026-10-24T12:58+08:00 (T1 re-entry-6 landed (confirmed in jsonl, pending 0); S5 in progress at f1722eb (usage reconciliation control input), streaming at 27.7% context). Prev: 2026-10-24T12:35+08:00 (T1 hit 85.9% mid-turn at S4 08b6598 -> aborted, /compact via commands/run 12:25-12:30 (85.9% -> 14.2%); re-entry-6 sha f4441dbd queued (pending 1) while session auto-continued; confirm it lands next run). Prev: 2026-10-24T12:00+08:00 (T1 S4 0ec117f observation isolation and per-stream tick health; streaming at 83.9%, no pending, below 85% abort line; compact at next idle boundary). Prev: 2026-10-24T11:30+08:00 (T1 S4 405b7d9 goal re-injection when driven and stalled; streaming at 81.3%, no pending, below 85% abort line; compact at next idle boundary). Prev: 2026-10-24T11:00+08:00 (T1 S4 receiving companion 8ea0e07 committed, main drive next; streaming at 80.7%, compact at next idle boundary). Prev: 2026-10-24T10:25+08:00 (T1 S3 disposable pass c41a01a, moving to S4, 78.6%). Prev: 2026-10-24T10:05+08:00 (T2 done G42: box wrapper pass, track-2-working sent; T1 S3 c41a01a at 74.2%). Prev: 2026-10-24T09:30+08:00 (T6 done e3232f1, audit PASS rerun by driver, draft PR #39 opened, poc_sent; T2 pushed 88d9d67, G41 inference pass, wrapper box check pending; T1 S3 2e227a7 at 72.4%). Prev: 2026-10-24T08:55+08:00 (T6 e3232f1 pushed; live e2e still running; T1 S3 187a454 at 70.7%; T2 live checks streaming 52%). Prev: 2026-10-24T08:35+08:00 (T6 226e32a pushed; T2 steer-2 G41 live checks on T6 test-home runtime). Prev: 2026-10-24T08:05+08:00 (G40: model defaults Sol 6.1 xhigh streams / Luna 6 xhigh workers (openai-codex/gpt-6-luna); T6 steered with steer-1 (defaults + login done G39), landed 08:03, streaming)"
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
    steers: [docs/harness-program/briefs/track-1-steer-1.md, docs/harness-program/briefs/track-1-steer-2.md, docs/harness-program/briefs/track-1-steer-3.md, docs/harness-program/briefs/track-1-reentry-1.md, docs/harness-program/briefs/track-1-go.md, docs/harness-program/briefs/track-1-reentry-2.md, docs/harness-program/briefs/track-1-reentry-3.md, docs/harness-program/briefs/track-1-reentry-4.md, docs/harness-program/briefs/track-1-reentry-5.md, docs/harness-program/briefs/track-1-reentry-6.md]
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
    phase: "done 10:04 (G42): real Sol xhigh inference PASS (G41) and genuine box-side wrapper over options-01-ssh PASS at 88d9d67. Rebase onto main after track 1 merges."
    milestones_sent: [track-2-blocker-prime-login 2026-10-23T11:01+08:00, track-2-working 2026-10-24T10:05+08:00]
    box_wrapper_check: pass 2026-10-24T10:04+08:00 (G42)
    started: 2026-10-23T09:19+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/20-prime-cli-design.md
    code_branch: feat/prime-cli
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-prime-cli
    brief: docs/harness-program/briefs/track-2.md
    steers: [docs/harness-program/briefs/track-2-steer-1.md, docs/harness-program/briefs/track-2-reentry-1.md, docs/harness-program/briefs/track-2-steer-2.md]
    steer_note: 11:31 context 84.5% (~422k) -> aborted, /compact via commands/run (G21), now 19.1%; session auto-continued its in-flight verification. reentry-1 consumed (11:52); session idle at ~3% context, 71 offline tests pass, reports TRACK 2 STATUS blocked on ZF Prime login.
    brief_sha256_verified: true
    blocked_on: ZF interactive openai-codex login for Prime on options-01 (blocker note sent once, 11:01)
    open_questions: [caladan (pi-bot caladan bb39dc0; no pi-stack branch), non-blocking]
    pushed: feat/prime-cli 88d9d67 (2026-10-24 09:29, driver; fast-forward over 6bc1242)
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
    phase: "done 09:01 (TRACK 6 STATUS: done, e3232f1, suite/install/e2e pass); driver reran native audit PASS 09:28; draft PR #39 opened 09:29. Earlier: steered 08:03 with track-6-steer-1; Was blocked-on-prime-codex-login at f5beb90 (suite/install pass)."
    milestones_sent: [track-6-blocker-prime-login 2026-10-24T05:58+08:00, poc-working 2026-10-24T09:30+08:00]
    pr: https://github.com/alienczf/pi-stack/pull/39
    login_command: "HOME=/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home /home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home/pi-stack-merged-poc-test/bin/prime-agent then /login in the TUI"
    started: 2026-10-24T01:26+08:00
    pushed: feat/merged-poc e3232f1 (2026-10-24 08:55, driver; fast-forward over 226e32a)
    code_branch: feat/merged-poc (session creates worktree /home/alphalab/Projects/worktrees/pi-stack-merged-poc off local main + feat/prime-cli)
    deadline: 2026-10-26T09:00+08:00
    steers: [docs/harness-program/briefs/track-6-steer-1.md (sha256 d61f618a; jsonl match 08:03:14, G40)]
    login_done: 2026-10-24T07:56+08:00 (G39, clean test HOME)
    model_defaults: "streams openai-codex/gpt-6.1-sol@xhigh; workers openai-codex/gpt-6-luna@xhigh (G40, ZF t239u)"
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
poc_sent: 2026-10-24T09:30+08:00 (draft PR https://github.com/alienczf/pi-stack/pull/39, handed to main chat via WakeParent; never resend)
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
| 1 fix catalog | `01a16655` | implementing; S1-S5 done; S6 in progress at main `600e695` / native `61c5e26`, retirement edits active; 67.6% context, streaming | `10-pi-streams-fix-catalog.md` + `feat/streams-must-fix` | S1-S6 done, then driver merges |
| 2 prime CLI | `01a16656` | done 10:04; inference and box wrapper pass | `20-prime-cli-design.md` + `feat/prime-cli` (`88d9d67` pushed) | rebase onto main after track 1 merges |
| 3 research | `01a16658` | done 18:21; 31 (A over Prime) passed gate 18:22 | `31-design-a-detailed.md` | feeds 51 |
| 4 B over prime | `01a166e0` | done; 42 passed gate 15:55 | `40`, `41` (reference), `42-design-b-prime-unchanged.md` | feeds 51 |
| 5 merged + v2 | `01a1671a` | done; revised 51 and 50 passed the Z25 gate 01:30 | `51-design-merged.md`, `50-a-vs-b.md` v2 | gate merged_revision_z25, then one short note to ZF |
| 6 merged PoC | `01a169cc` | done; `e3232f1`, draft PR #39, ZF told 09:30 | `feat/merged-poc` + install for a fresh external setup | rebase onto main after track 1 merges |

**Usage limit 16:14-18:11 (closed):** ChatGPT usage limit on openai-codex; ZF reset it at 18:06 and work resumed on the same provider.

**Env failure 14:50-15:05 (closed):** options-01 lost outbound internet and model calls returned `fetch failed`. Every track was resumed by 15:09.

The canonical copy is on GitHub. The box mirror is `/workspace/harness-program/STATUS.md`.

- **Driver run 22:02 SGT (Grok Bot).** Collect found no new artifacts. Track 1 streaming at 67.6% (338k of 500k), pending 0; S6 still at main 600e695 / native 61c5e26 with uncommitted failure-retirement engine and test edits active in the last 20 minutes; disposable check and F-DCR round trip pending. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; session mid-turn and below the 85% abort line, nothing needs a decision.
- **Driver run 20:25 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 63.0% (315k of 500k), pending 0; S6 advanced with native 3be16e0 (pins the receiving-owned fork hold generation; 2401 tests pass) and main 2ee4028 (forces the shared DCR on verified coordinator and worker forks; 384 tests pass); singular retirement is the next unit, then the disposable check and F-DCR round trip. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; session mid-turn and below the 85% abort line, so no compact or steer.
- **Driver run 19:55 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 60.0% (300k of 500k), pending 0; S6 committed main aec339c (journal exact recovery forks and bind verified returned session ids), with more failure-recovery edits active in the last 20 minutes; disposable check and F-DCR round trip pending. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; session mid-turn and below the 85% abort line, so no compact or steer.
- **Driver run 18:55 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 53.7% (269k of 500k), pending 0; S6 advanced with native 14a7953 (held-fork maintenance scoped to its verified operation; native verify 2400 tests pass); main still a6330d5; disposable check and F-DCR round trip pending. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; the session is progressing, nothing needs a decision.
- **Driver run 18:35 SGT (Grok Bot).** Track 1 streaming at 53.0% (265k of 500k), pending 0; S6 advanced with native ba2978b (retain correlated completed-RESUME observations, suite pass); disposable check still pending. options-01 SSH over Twingate userspace timed out on the first collect attempts (host up 23h, no reboot); retried. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; the session is progressing, nothing needs a decision.
- **Driver run 17:55 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 49.4% (247k of 500k), pending 0; S6 advanced with native 0ebb4b8 (generic lifecycle can no longer bypass failure parking; native verify 2393 tests pass); main still a6330d5 (371 pass); disposable check back to pending. Remaining: held-fork DCR proof, retirement source, instructions, isolated checks, disposable check and F-DCR round trip. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; the session is progressing, nothing needs a decision.
- **Driver run 17:25 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 47.6% (238k of 500k), pending 0, waiting on its own subagent; S6 advanced with native 77e8c7f (verified notices bound to persisted recovery targets, 2391 tests pass) and main a6330d5 (failure ratify requires a verified exact-episode notice, 371 tests pass). The subagent now marks the disposable check blocked-authenticated-intake; the coordinator has not yet reported it, so no steer while it is mid-turn — revisit at its next idle boundary. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; the session is progressing, nothing needs a decision yet.
- **Driver run 16:55 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 43.5% (217k of 500k), pending 0; S6 advanced with native 51a03c0 (exact inclusive SDK fork behind a verified-intake recovery operation; native verify 2389 tests pass). Remaining: CLI/operation adapter, trusted notice contract, fixed fork-DCR and retirement driver, instructions and checks, the disposable check and the F-DCR round trip. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; the session is progressing, nothing needs a decision.
- **Driver run 16:25 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 43.1% (216k of 500k), pending 0; S6 advanced with native 36b69ad (task errors kept apart from environment failures, durable failure registration) and main 9f66776 (per-session last-good failure markers, early registration; main suite 366 pass). Remaining: fork lifecycle, fork-DCR driver, final instructions and checks, the disposable check and the F-DCR round trip. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; the session is progressing, nothing needs a decision.
- **Driver run 15:55 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 42.5% (213k of 500k), pending 0; moved to S6, latest commit e051682 (pi-web persists safe stream turns and fences failed runtimes, suite pass); disposable check and F-DCR round trip still pending. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; the session is progressing, nothing needs a decision.
- **Driver run 14:55 SGT (Grok Bot).** Collected and pushed docs. Track 1 streaming at 34.0% (170k of 500k), pending 0; it committed main 10c882a (typed failure parking and one saved usage trial, full main suite 356 pass). Remaining for track 1: off-host route proof, the rest of S5, S6, and the F-DCR round trip. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; the session is making progress, nothing needs a decision.
- **Driver run 14:30 SGT (Grok Bot).** Collected docs (no artifact changes). Track 1 streaming at 33.4% (167k of 500k), pending 0; latest status still S5 at f1722eb with the failure-policy and usage-recovery edits uncommitted. No file writes in the last 20 minutes, but the session is mid-turn (not idle), so no steer. Tracks 2 and 6 done, messages already sent. No unsteered ZF calls. *Reason:* routine checks; nothing needs a decision.

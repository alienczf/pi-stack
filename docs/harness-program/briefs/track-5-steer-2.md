# Track 5 steer 2 (Grok Bot, 2026-10-24 00:52 SGT): revise 51 and 50 v2 per Z25

ZF answered all seven open questions on 51 (t232u 00:42 SGT, t233u 00:44 SGT). Start now; no go needed.

Read, with targeted reads, in `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/`:
- `00b-zf-messages-verbatim.md`, sections t232u and t233u (ZF verbatim);
- `03-decisions.md`, section Z25 and G36;
- `43-prime-compaction-hooks.md` (the compaction-hook evidence, read-only source check at v0.10.1 `8aac8692`);
- your own `51-design-merged.md` and `50-a-vs-b.md`.

## What Z25 decides (apply all of it)

1. **STATE freshness.** Fresh STATE once per pi-stack message is enough. Drop the "not met" framing for per-internal-request freshness. It's not a requirement, so there's no gap to report.
2. **Stale messages and stops.** Reject stale pi-stack messages (keep the reject-stale-command hook). Stopping running tool calls is wanted, best-effort: use the stock abort/stop command and report the result without guaranteeing it. Don't add a per-tool stop check, and drop the "not every tool checks for a stop" gap.
3. **Input capture.** Capture only the stock Prime input paths pi-stack uses. Attachments are rejected. Messages typed straight into the terminal stay uncaptured, and that's accepted, not a gap.
4. **Compaction.** ZF: use Prime's percentage, but only if we can hook both before and after compaction; otherwise disable it and roll our own. Per 43, stock v0.10.1 has an after-compaction signal (the `compaction_end` event) but no before-compaction hook: `compaction_start` is only a notification, and the summarizer starts at once. So the condition applies. Rewrite the compaction design:
   - Turn off stock automatic compaction with `compaction.enabled=false` in the settings before the session is built. The supervisor `set_auto_compaction` toggle does not change a live core.
   - pi-stack runs its own percentage check, then save-STATE, direct `compact`, readback and resume. Replace "Compact-at-threshold hook (stock)" with one pi-stack-owned compaction hook. Merge it with the explicit-DCR path if they're the same sequence; don't keep two near-duplicate hooks.
   - State plainly where the percentage comes from (stock `compact.status` or session context usage) and when the check runs. Note that with compaction disabled, overflow recovery no longer compacts.
   - Don't pick a percentage value. It's a setting.
5. **Workers.** Workers have no state files. They are not streams. They run in poteto as clean sessions with only a context handover and a kickoff. Drop the shared coordinator/worker file pair and any worker STATE.md. The worker-brief text becomes that handover plus kickoff.
6. **Checking results (closed).** There is no mandatory fresh-session check. The stream itself reviews each reported summary adversarially against the original intent, and spawns a reviewer session only when it judges one is needed. This guidance lives in the stream's AGENTS.md role text, not in a hook. Update the source-comparison text and its trigger to match. Don't add a hook for it.
7. **Out of scope permanently.** Login/auth failures, outages and recovery are permanently out of scope, not just this round. Reword the "Not handled" section as "Not handled (permanently out of scope)": each item says what happens today and that it isn't meant to be solved.

## Keep

- First line exactly `Runtime: stock Prime, no Prime changes; merged candidate (Z23)`.
- The same 8 headings.
- Z21 vocabulary rules:
  - zero new concepts (keep the empty New concepts table);
  - descriptive hook and prompt names, with no H-/P- codes;
  - no retired STREAM/ACTIONS/GOAL/DECISIONS names;
  - no coined labels.
- Exact hooks, full prompt texts, artifact paths and schemas, and the stacked commit plan with tests, updated to match the changes above. Remove anything that only existed to serve a dropped requirement. Make it shorter where you can.
- **Open questions:** the revised 51 has **zero** open questions. Every former question is answered by Z25. Don't invent new ones. Anything you must flag goes in Risks and notes as a fact, not a question. Nothing beyond Z25 is locked (Z17), and set no defaults.

## 50 v2

Update `50-a-vs-b.md` to match the revised 51:
- what the merge loses from 31 and from 42 now;
- which corpus failures are no longer covered (by F-number);
- where the difference was real and where it was artificial;
- note that the open questions were answered by Z25 (one line each, with the answer), leaving none open.

Keep it short.

## Limits

Docs only. Edit only 51 and 50. No code, no commit or push (Grok Bot collects). Don't edit 31, 41, 42 or 43. No other sessions, no credentials, never switch provider. On a quota error, stop and report.

Finish by replying exactly: `TRACK 5 STATUS: done (51 + 50 revised per Z25)` (or `TRACK 5 STATUS: blocked | <reason>`)

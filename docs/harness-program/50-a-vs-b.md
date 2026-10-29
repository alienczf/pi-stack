# Merged candidate check, v2, revised per Z25

This checks [51](51-design-merged.md) against [31](31-design-a-detailed.md) and [42](42-design-b-prime-unchanged.md). Z25 answers all seven former questions. Z26 asks for a working PoC on `feat/merged-poc` and external-machine installation. The documentation is a build plan, not a claim that the branch already works. Nothing beyond Z25 is locked under Z17. [Decisions, Z25/G36 and Z26](03-decisions.md) [ZF t232u/t233u](00b-zf-messages-verbatim.md)

## What the merge keeps and loses

Goals, Rules, originals, findings and completion meaning stay in the stream repo. Deterministic message handling, tick decisions, compaction ordering and computed closing checks are pi-stack code around stock Prime. Workers are clean poteto sessions, not streams.

| Area | Change from 31 | Change from 42 and the earlier 51 |
|---|---|---|
| Current files and stops | Drops the proposed native per-request/tool integrations. Z25 accepts fresh STATE once per pi-stack message, stale-message rejection and best-effort stock abort. This matches the required scope. | Keeps per-message freshness and rejection. Stop reporting records the actual native result without guaranteeing tool termination. |
| Input capture | Replaces native all-path receiving changes with local save-before-send on the stock paths pi-stack uses. Attachments are rejected. | Terminal input stays uncaptured by explicit acceptance. Original supported text and connected replies remain in Log/history; unknown sends are not blindly replayed. |
| Compaction | Replaces native expected-entry/DCR changes and the absolute-token trial with a pi-stack-owned percentage check and public direct compact. No Prime patch. | Removes stock automatic compaction and the separate explicit-DCR path. Stock has no before hook, so set `compaction.enabled=false` before session construction. One controller does percentage check, save STATE, compact, readback and resume. |
| Workers | Removes the shared stream AGENTS/STATE pair from workers. | Removes worker-owned STATE paths too. Workers get only context handover and poteto kickoff in a clean session. Stream assignments/results remain in stream files. |
| Review and computed close | Removes mandatory fresh-session source comparison. The stream reviews every summary adversarially against original intent and chooses an optional reviewer itself. | Computed source/target/test/report checks remain. AGENTS.md carries review guidance; no hook creates or requires reviewers. |
| Exceptional behavior | Drops typed environment/reset recovery and native durable-outcome changes. Neither input supplied safe native worker transfer. | Login/auth, outages and recovery are permanently excluded, not deferred implementation work. Received errors can be reported without adding repair machinery. |

Compaction evidence is [43](43-prime-compaction-hooks.md). `compaction_start` is notification-only and summarization begins immediately. `compaction_end` is an after signal. Consequently Z25's disable-and-own condition applies. The live supervisor toggle cannot replace pre-construction settings. Disabled automatic compaction also means overflow returns stock failure rather than automatically compacting, absent a separately scheduled native compact. 51 schedules none.

## Corpus coverage retained or reduced

These are bounded mechanisms, not measured prevention rates. F-numbers come from [30](30-research-designs.md#input-3-the-explicit-balance-after-zfs-remedies).

| Failure classes | Revised coverage |
|---|---|
| F7, external blockers | Environment, login, outage and recovery remedies are permanently not covered. Reporting a received error does not replace them. |
| F6, context/rotation churn | Fresh files per stream message, history rotation and ordered save/compact/readback/resume remain. The percentage check runs before stream sends, after results and on tick; a long run can overflow before yielding. No native reservation or hard ceiling is claimed. |
| F2 and F8, narrowing/lost steer | Save-before-send and source-preservation checks cover selected pi-stack text paths. Terminal capture and attachments are outside the accepted scope. Semantic narrowing still needs stream judgement. |
| F4, F5 and F10, overbuild/overclaim/constraint override | Actual invocation/target/report checks and adversarial stream review remain. Mandatory independent fresh-session review is removed. Neither self-review nor an optional reviewer guarantees correct interpretation. |
| F1, F3, F9, F11, F12 | Eligible tick wake, current Rules, stale-message rejection, best-effort stop, independent workers, narrow publication and distinct finite work remain. No general scheduler, cleanup service or universal semantic oracle is added. |

31's stronger native save/result guarantees are not reproduced. A missing native outcome remains unknown, not an automatic replay/recovery problem for this design to solve. The accepted capture, freshness and stop boundaries are closed Z25 decisions. [51 §§3,7](51-design-merged.md#3-hooks)

## Real versus artificial differences

The historical ownership distinction was real between repo-owned A and full runtime-owned B. But stock-only 42 already put current meaning and closing checks back in repo files. Keeping separate task stores or names to preserve an A/B distinction would be artificial. Both reduced designs use Z15's Goals, Rules, Log and history.

The remaining implementation differences are real. 31 proposes native receiving/result/context/DCR changes. The revised merge uses stock commands and the Z25-approved scope instead. Its external compaction controller differs from 42's native automatic policy because the required before-save step cannot be attached to stock automatic compaction. The choice to disable that path is now answered, not another design fork. [31 §3](31-design-a-detailed.md#3-hooks) [42 §3](42-design-b-prime-unchanged.md#3-hooks) [43](43-prime-compaction-hooks.md)

51 §8 now gives exact pi-stack files/functions, ordered commits/tests, an isolated installer, fresh-machine commands and a real one-stream intake-to-compaction-to-close gate. The installer installs stock v0.10.1 and owned settings/hooks/templates without touching another installation. Login is the user's own step. PASS requires observed native operations and checked artifacts; fixtures alone do not establish a working PoC.

## Former questions answered by Z25

1. Freshness is once per pi-stack message; internal-request refresh is not required.
2. Reject stale pi-stack messages; stopping running tools uses stock abort best-effort, with no per-tool stop check.
3. Capture the stock paths pi-stack uses, reject attachments and accept uncaptured terminal input.
4. Use Prime's percentage; lacking a before-compaction hook, disable stock automatic compaction before construction and own save/compact/resume. No percentage value is chosen.
5. Workers have no state files and are not streams; use clean poteto sessions with handover and kickoff.
6. The stream reviews reported summaries adversarially against original intent; spawn reviewers only when judged useful, with guidance in AGENTS.md and no mandatory fresh-session check.
7. Login/auth failures, outages and recovery are permanently out of scope and are not intended to be solved.

No questions remain open in this revision. These answers do not lock anything beyond Z25.

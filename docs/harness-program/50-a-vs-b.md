# Merged candidate check, v2

This replaces v1. It checks [51, the merged candidate](51-design-merged.md) against [31, A over Prime](31-design-a-detailed.md) and [42, B over stock Prime](42-design-b-prime-unchanged.md). [41](41-design-b-prime-detailed.md) is reference only for what native changes would add. Z17 leaves every design open. Z23 is a candidate, not a selected solution. [Decisions, Z20-Z23 and G29](03-decisions.md)

## What merges, and what does not

Goals, Rules, original messages, completion meaning and reviews stay in the repo. Computed checks and live command ordering are code, not optional instructions. That overlap is real. Stock Prime has native threshold compaction, but no demonstrated external hook that supplies fresh STATE before every internal request or vetoes every stale model tool. The merge cannot erase that distinction by calling sending functions hooks. [31 §§2-3][a-hooks] [42 §§2-3][stock-hooks] [51 §§1-3][merged-hooks]

| Check | 31 | 42 | 51 and the loss |
|---|---|---|---|
| Save before work can run | Native receiving changes save the original, preserve the command ID and propagate queue errors before runnable pickup. | pi-stack saves locally before sending. Direct/native input bypasses it. | Keeps 42's local save. Loses 31's native all-supported-input ordering and durable same-command lookup. Unknown sends need inspection, not automatic replay. [31 §3][a-hooks] [42 §2][stock-components] |
| Fresh current files | Proposed native wrapper covers provider requests, including internal tool loops and DCR summary. | Fresh files in each pi-stack message only. | Keeps the narrower 42 path. Loses 31's every-request guarantee. Ordinary long-run gap, not a login exclusion. [31 §3][a-hooks] [42 §3][stock-hooks] |
| Stop and stale actions | Proposed native receiving/tool checks reread current instructions. Existing effects are not rolled back. | Rejects stale pi-stack commands, not tools inside an existing run. | Keeps client checks and cooperative stop saving. Loses 31's native next-tool check and receiving-side recheck. Direct abort does not save a repo pause. [31 §3][a-hooks] [42 §3][stock-hooks] |
| Results and computed close | Native result/write-error changes plus repo source/target/proof checks and fresh source comparison. | Captures connected replies; repo close executes/checks actual tests and references. | Keeps computed close and 31's explicit source-comparison text. Loses complete native outcome saving after disconnect/preflight/crash. No semantic oracle is gained. [31 §§3-4][a-hooks] [42 §3][stock-hooks] [51 §§3-4][merged-hooks] |
| Compaction | Proposed safe native DCR, expected-entry reservation and saved operation query. Tick observes the 150k trial. | Existing native computed percentage threshold. Separate explicit DCR uses cooperative pause/check/compact/readback. | Keeps 42's native automatic hook and explicit DCR. Loses 31's native idle reservation, exact command-result query and automatic dump-before-compact contract. Neither a hard 150k boundary nor all-client race safety follows from stock settings. [31 §3][a-hooks] [42 §3][stock-hooks] |
| Failure recovery and input bytes | Typed failures, human-restored same-session recovery and retained images/proof. No automatic safe fork transfer. | Text only, connected error capture, manual exceptional recovery. No worker-parent transfer. | Excludes automatic environment/reset recovery and binary attachments. Preserves text errors/unknown work and the original parent. Native worker transfer was already absent in both inputs. [31 §§5-6][a-lifecycle] [42 §§2,7][stock-components] [51 §7][merged-risks] |

**Loss from 42.** No stock sending, reply-saving, wake, threshold, explicit-DCR, stale-command or computed-close hook is intentionally removed. Its known limits remain. Two repo contracts change. 51 uses 31's shared coordinator/worker AGENTS/STATE pair instead of worker-owned STATE paths. It retains needed exact text proof in history instead of relying solely on an external task report path/hash. Those changes affect context size, writes and checking, not native enforcement. 51 explicitly restricts coordinator product writes and adds the fixed source-comparison instruction. These are candidate choices, not ratified rules. [42 §§4-5][stock-storage] [31 §§4-5][a-storage] [51 §§4-5][merged-storage]

## Corpus coverage that is lost or reduced

These are bounded design comparisons, not measured prevention rates. F-numbers come from [30, lines 105-124](30-research-designs.md#input-3-the-explicit-balance-after-zfs-remedies).

| Failure classes | What is no longer covered in 51 |
|---|---|
| F7, external blockers | 31's typed recovery, reset/human-release sequencing and quiet failure-notice integration are excluded. Saving a connected error is retained, not a replacement recovery mechanism. [31 §3][a-hooks] [51 §7, Not handled][merged-risks] |
| F6, context/rotation churn | No every-internal-request STATE refresh, no native idle-and-compact reservation and no Z15 dump around every automatic compact. Log rotation and native threshold checks remain. [31 §3][a-hooks] [42 §3][stock-hooks] [51 §3][merged-hooks] |
| F3 and F10, invented gates/constraint override | No native next-model-tool check or durable receiving-side stream-pause check. Repo Rules, computed checks and stale pi-stack-command refusal remain. [31 §3][a-hooks] [51 §3][merged-hooks] |
| F2 and F8, narrowing/lost steer | No native capture of bypassing input or complete attachment support. Participating text saves and source-preservation checks remain. No design captures an outer message never sent. [31 §§3,7][a-hooks] [42 §2][stock-components] [51 §3][merged-hooks] |
| F5, overclaim, and F6 | No complete durable native result for a disconnected/crashed run. Retained source/proof, actual computed close and review still address wrong-result claims. Semantic review remains fallible in all three. [31 §3][a-hooks] [42 §2][stock-components] [51 §§3,7][merged-hooks] |
| F1, F4, F9, F11, F12 | Eligible tick reconsideration, named-path/source comparison, independent work, narrow publication and finite-work identity remain. None becomes complete semantic, scheduling or cleanup coverage. [31 §2][a-components] [42 §2][stock-components] [51 §2][merged-components] |

Moving running children, rollback of external effects and automatic F-DCR remain unsupported. They are not newly solved by the merge, and neither 31 nor 42 supplied native transfer. Full transfer in 41 would require Prime changes outside this candidate. [31 §6][a-lifecycle] [42 §2][stock-components] [41 §3][native-hooks]

## Real versus artificial differences

The repo versus runtime ownership distinction was real between the old full B design and A. Stock-only 42 already moves current meaning and closing checks into repo files. Keeping a second runtime task identity merely to preserve the A/B labels would be artificial. After the Z21 cleanup, both inputs already use the three Z15 sections and existing history for task meaning. [31 §§1,5][a-storage] [42 §§1-2][stock-components]

The remaining execution difference is real. 31 proposes Prime changes for native input ordering, provider context, tool checks and durable DCR/results. 42 and 51 cannot obtain those guarantees from external public commands alone. Dismissing login or fringe recovery does not remove the routine internal-request and stale-tool gaps. Stock already having threshold compaction also means not every deterministic operation requires a new native hook. [31 §3][a-hooks] [42 §§3,7][stock-hooks] [51 §7][merged-risks]

## Open questions

1. **Blocking for the required contract.** Is STATE freshness required before every internal provider request, or before each pi-stack message? [51 §§1,3][merged-hooks]
2. **Blocking for the required contract.** Must a newer stop prevent each subsequent native tool, or is rejecting stale pi-stack commands sufficient? [51 §3][merged-hooks]
3. Which clients and native input paths must participate? Is rejecting attachments and leaving direct TUI/internal messages outside capture acceptable? [51 §3][merged-hooks]
4. Must compaction retain an absolute 150k trial boundary and dump before every automatic compact, or is stock's configured percentage/headroom behavior sufficient? What explicitly authorized settings establish that behavior for new owned sessions? [31 §6][a-lifecycle] [42 §3][stock-hooks]
5. Does the shared role pair fit worker context and product-policy needs, or are worker-owned STATE paths required? How should large original messages and retained proof affect the existing Log layout? [51 §5][merged-storage]
6. At which completion boundaries is fresh source comparison required, and what held-out cases establish its detection benefit and false-rejection cost? [31 §7](31-design-a-detailed.md#7-risks-and-notes) [51 §§3-4][merged-hooks]
7. Are the explicit F7 and exceptional-recovery exclusions acceptable for this iteration? What observed stock-runtime checks must pass before any narrower guarantee is described as verified? [51 §§7-8][merged-risks]

[a-components]: 31-design-a-detailed.md#2-components-and-justification
[a-hooks]: 31-design-a-detailed.md#3-hooks
[a-storage]: 31-design-a-detailed.md#5-artifact-storage
[a-lifecycle]: 31-design-a-detailed.md#6-lifecycle-walkthrough-an-ask-from-intake-to-close-a-stall-a-failure
[stock-components]: 42-design-b-prime-unchanged.md#2-components-and-justification
[stock-hooks]: 42-design-b-prime-unchanged.md#3-hooks
[stock-storage]: 42-design-b-prime-unchanged.md#5-artifact-storage
[merged-components]: 51-design-merged.md#2-components-and-justification
[merged-hooks]: 51-design-merged.md#3-hooks
[merged-storage]: 51-design-merged.md#5-artifact-storage
[merged-risks]: 51-design-merged.md#7-risks-and-notes
[native-hooks]: 41-design-b-prime-detailed.md#3-hooks

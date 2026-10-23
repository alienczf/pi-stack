# Harness program track 3. Problem-state research and competing designs

Status. BLOCKED at step (c), 2026-10-23. GitHub public issue-search quota was exceeded in delegated research. No Codex usage limit occurred. The program's quota stop rule applies, so research stopped without switching provider or model.

The requested three-design proposal table is not produced. Writing designs before the merged-corpus interrogation would violate the requested order. This file is a partial research checkpoint, not a finished recommendation or an implementation plan.

| Required stage | Checkpoint |
|---|---|
| (a) Unresolved problems | Complete against available inputs. P01-P40 below include Z2 and all nine track 1 deferrals. The marked brief gap remains unknown. |
| (b) Light pi-stack scout | Complete. Existing instructions and enforced mechanisms are distinguished below. |
| (c) External corpus | Partial. Five parent-fetched reports and five delegate-fetched candidates are preserved in [30a-external-corpus.md](30a-external-corpus.md). X triage and community coverage are unfinished. |
| (d) Merge and interrogate | Not completed. No core-cause set is accepted. |
| (e) Three holistic designs | Not performed. |
| (f) Comparison, coverage matrix, recommendation | Not performed. |

Resume from step (c) only after the quota blocker is released. Then merge and interrogate before designing.

## Work sequence

1. Route through the **how** skill. For motivation questions, also route through the **why** skill.
2. Throughput checkpoint stays one line: `throughput checkpoint: n/a, read-only investigation`.
3. Produce the `how`-shaped output (Overview / Key Concepts / How It Works / Where Things Live / Gotchas), or a recommendation with a tradeoffs table if the request is a decision between alternatives.
4. Apply the **unslop** skill to the reply.

throughput checkpoint: n/a, read-only investigation

- [x] Collect unresolved problem statements before proposing solutions.
- [x] Scout pi-stack's principles-to-playbooks structure.
- [ ] Gather and deduplicate practitioner failure reports, including the X seed.
- [ ] Interrogate the combined corpus and identify three to six causes.
- [ ] Compare three holistic designs with explicit layer placement.
- [ ] Check coverage, track 1 deferrals, source reachability, and decision compliance.

## Evidence and current constraints

`K` is `context/stall-corpus-2026-10-22.md`. `A`, `B`, and `C` are the mechanical, goal-integrity, and control-loop interrogations dated 2026-10-22. `R` is `context/research/deep-research-2026-10-23.md`. Those paths are under `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/`. `Cat` is [track 1's catalog](10-pi-streams-fix-catalog.md). Source code is pi-stack main `3acf0f01e6084a317b89cef3a86f4781e60877cf`.

The [current decisions](03-decisions.md) govern. Z3 supersedes D2 and G4. All designs must use tick-observed, non-interrupting dump, compact, resume in the same coordinator session at >=150k. Z2 assigns ask lifecycle, self-grading, and constraint lifetimes to this track. Z4 fixes quiet ZF-only Slack DM, formatted `<stream-id>:: <message>`. G5's five runtime recovery classes remain adopted. This research session still stops on a usage limit.

D1 excludes default budgets. D6 excludes contested-authority precedence machinery and puts retained artifacts in stream-owned worktrees. D7 asks when and how to compact state and review rules, not when to delete transcripts. D8 requires each ask, its status, and concatenated findings. D9 requires a minimal workflow shape before a recurring-review policy. The old ranked build plan and old acceptance scripts are withdrawn.

The 4,482-character gap remains unknown. The later t211u update is explicitly a paraphrased relay in `00-brief-verbatim.md`, not a recovered verbatim quotation.

## Unresolved problem statements

These are problems, not commitments to a ledger or engine. Historical incidents are source-reported. Proposed crash and review-effectiveness risks do not acquire an observed incident count by appearing here. `P` identifiers are local problem IDs, distinct from program decisions P1-P7.

| ID | Problem statement | Source and motivating corpus rows |
|---|---|---|
| P01 | Standing goal, current priority, execution state, and history can overwrite or contradict each other. | K §3; B §2.1; R Q3. Rows 9,12,27,30,36,38,57,75. |
| P02 | An ask can disappear, narrow, or move to an unapproved future plan without cancellation. | B §2.1-2 and trace table; R Q3; Z2. Rows 3,5,6,20,28,30,31,38,58,68,74. |
| P03 | Original wording, authorship, order, and relay transformations are not always recoverable. | B trace table and §6; R Q2/Q8. Rows 6,8,15,28,30,33,38,42,68,69,74. |
| P04 | Transport acceptance, consumption, application, and completed outcome are conflated. Unsent bot messages remain invisible to the coordinator. | C §2.3; R Q2; Z5. Rows 21,35,72,73. |
| P05 | Delayed or repeated input can revive superseded or cancelled work. Arrival order and text equality are inadequate identities. | A §4.4; B §4.3; R Q2. Rows 20,69,72,74,75 motivate the risk, not proved duplicate effects. |
| P06 | A checker or completion claim can prove the wrong interpretation, target, or subtask. | B §2.2/§4.2; R Q7; Z2. Rows 1,4,7,8,18,22,26,28,30,36,64,69,74. |
| P07 | Investigation can optimize the wrong experimental question or infer causes without isolating them. | K rows 1,2,4,7,8,18,22,66; B §3/§6. |
| P08 | Agents substitute bespoke code, loaders, runners, images, or validation for requested minimal changes and established paths. | B §2.3/§5.6; R Q11. Rows 14,15,19,41,48-50,56,58,61,62,65. |
| P09 | Revoked rules can remain current, and removing one rule can accidentally revive an unrelated prohibited action. | B §2.3; R Q8; Z2. Rows 10,20,44,45,54,61,69,75. |
| P10 | Agent-created budgets, historical receipt gates, and redundant approvals obstruct already authorized work. | Issue #33 snapshot; A §3; B §2.3; C §2.4. Rows 10,37,39,43-45,54,61,65. |
| P11 | Legitimate prohibitions, real prerequisites, chosen dependencies, and unowned pauses look alike. | C §2.4/§3; R Q6/Q8. Rows 37,43,54,75. |
| P12 | Independent authorized work waits behind unrelated work or recovery. Safe concurrency and real dependencies are unclear. | C §2.4/§4.5; R rank 4. Rows 5,9,34,46,75. |
| P13 | Unfinished authorized work can have no live owner and no future continuation after a turn ends. | C §2.1; R Q1/Q6; Z1. F1 rows, especially 26,39,51,55,59,60,64. |
| P14 | ZF must poll to learn each ask's actual status and findings. Reporting can be missing even while computation continues. | D8; Z4; C §2.1; R Q6. Rows 24,26,39,51,54,55,59,60,64. |
| P15 | Recovery can wait for the successful continuation that it is supposed to cause. | C §2.2; R Q9; G5. Rows 13,17,23-25,47,52,53,63,67. |
| P16 | Relevant readiness evidence is not established for every provider, tool-login, storage, and job failure. | C §5.4; R Q9/§4 engineering uncertainty 5. Same F7 rows. |
| P17 | An uncertain send or submitted job can be duplicated or replayed under stale authority after retry. | R Q1/Q2/Q9 and §4 engineering uncertainty 6. Prospective risk, not a proved duplicate-effect row. |
| P18 | Alerts can depend on the failed provider, host, storage, or tick. The bot's durable delivery contract is uninspected. | C §2.2/§5.6; R Q9; Z4/G5. F7 rows. |
| P19 | One failed observation can skip independent continuation work. A fresh tick is not proof of goal progress. | C §2.2/§6; R Q6. Source-derived risk without localized incident attribution. |
| P20 | Registered coordinator, actual session, activity, outstanding work, and completed work can disagree. | K §3; C §2.3; issue #36 snapshot. Rows 26,51-53,55,64,71,72. |
| P21 | A successor can read a child result ID without owning its wait, steering, or completion callback. | A §5.6; C §2.3; R Q1. Replacement exposures include rows 37,51-53,55,72. |
| P22 | Replacement does not establish complete transfer or adoption of pending instructions, work, results, and mutation ownership. | A §2.2/§4.4; R Q2. F6 rows motivate it, not proof all were caused by replacement. |
| P23 | Moving a transcript can break evidence references even when its bytes survive. | A §2.2 row 37; R Q10. Corpus row 37, not GitHub issue #37. |
| P24 | The selected non-interrupting same-session maintenance cycle is not yet verified across direct prompts, long turns, and failures. | A §2.1; R Q5; Z3; Cat item 3. Rows 11,16,32,71. |
| P25 | Neither smaller context nor faithful quotations have proved better compliant action here. No evidence chooses a compaction-count cutoff. | A operating-model table; B §5.2; R Q4/§4 uncertainty 7. Context as cause remains unproved. |
| P26 | Current state, history, TODO, decisions, and rules duplicate or contradict each other. Ownership and triggers for safe review remain unresolved. | K §3; A §2.3; D7; R Q3. Rows 11,16,28,30-32,37,38,71. |
| P27 | Thread lifecycle needs a separate policy for in-flight work and task boundaries. Coordinator thresholds do not decide it. | Issue #35 snapshot; A operating-model table; D3. No specific thread-policy incident established. |
| P28 | Prose, bespoke events, registry labels, and current views do not share a reliable interpretation of obligation, owner, wait, or outcome. | C §2.4; R Q3. Cross-cutting design problem, not proved malformed-event causation. |
| P29 | Scratch/data enters Git and outputs or obsolete worktrees accumulate. ENOSPC recovery does not prevent output production. | K F11; C §3; Cat item 13. Rows 17,29,47,70. |
| P30 | Referenced original instructions and artifacts may be unavailable when later decisions require them. A hash or ignored path does not retain bytes. | K §3; A artifact-management section; R Q10; D6/D7. Rows 28,37,72. |
| P31 | Receipt, disposition, and dispatch can diverge across crashes or competing updates. Atomic visibility alone does not establish durable publication. | R Q1/§4 uncertainties 1 and 6; Cat item 15. Prospective crash points. |
| P32 | A minimal cross-workflow definition of meaningful completion and review boundaries has not been adopted. | D9; Z2; R §4 decision 6; Cat deferrals. |
| P33 | Review's added semantic detection, false rejections, and context cost are unmeasured. Matching self-written tests can repeat a wrong premise. | B §5.4; R Q7; Z2. Rows 8,28,30,36,69 motivate evaluation. |
| P34 | The evidence does not establish prevented-incident rates or complete first-loss chronologies. | A/B/C qualifications; R coverage caveat and §4. All rows, particularly 8,31,37,54,68,69,72,74,75. |
| P35 | Proposed remedies have not demonstrated generality or correct layer placement. Process itself can add gates and context. | Program brief; 02-principles; B §6; withdrawal of R's plan. F3/F4 examples. |
| P36 | The brief has a marked gap, t211u is only relayed, and older input files retain superseded policy. | 00-brief-verbatim; 03-decisions Z3; stream DECISIONS. Input-quality issue. |
| P37 | Repeated remote-wrapper calls reportedly restart Twingate and time out. | G15; Cat item 9. Track 1 interface, outside the 75 rows. |
| P38 | Caladan's relationship to the main-based prime CLI remains unspecified. | Scope track 2; G8. Nonblocking adjacent program issue, not a track 3 decision. |
| P39 | Unratified dispatch can occur if the runtime fails to enforce kickoff authority before side effects. | Cat item 10; `threads.py` spawn/adopt paths. Source-derived, no counted corpus incident. |
| P40 | A role-named handover can be mistaken for a successor's own completed handover. | Cat item 14; `threads.py::_has_handover`. Source-derived, not a proved row-37 cause. |

All 18 A/B/C external-research questions map into this inventory. A1-A6 map to P24/P25, P25, P04/P05/P22/P31, P23/P30, P01/P26/P28, and P21/P22 respectively. B1-B6 map to P01-P03/P06, P25, P03-P05/P31, P06/P32/P33, P03/P09/P11 bounded by D6, and P08/P35. C1-C6 map to P13/P21/P31, P04/P17/P31, P11/P13/P14, P15/P16, P09/P11, and P18/P19.

R's six unsettled policy questions now map to the program implementation gate, G5, D6, D7, D8/Z4, and D9. They are not six new questions for ZF. Its seven engineering uncertainties map to P28/P31, P24, P04/P17, P18/P19, P16, P17/P21/P31, and P25/P33. Tool pairing, summary failure, uncertain effects, permanent unavailability, and inconsistent acceptance remain explicit limits rather than presumed solved questions.

Cat's nine deferrals map to P01-P03/P06, P06/P25/P33, P09-P11/P26, P28/P31/P35, P32/P33, P21/P22, P11/P12, P08/P35, and P26/P29/P30. This imports problems, not the old engine proposal.

## Light scout of the principles-to-playbooks spectrum

The single poteto entry is a dispatcher, not an executor. Its Principles index points to judgment rules. Skills and playbooks supply increasingly detailed instructions. The overlay maps those instructions into Pi's tools. Stream files structure what the agent reads. The tick and CLI implement only specific lifecycle operations.

| Existing part | What works | What does not, with evidence |
|---|---|---|
| Abstract principles, LAYER 5 | Laziness and Prove It Works generalize across tasks without a workflow schema. | Rows 41 and 48-50 conflict with reuse and minimal-change guidance. Alignment does not prove the leaf was loaded. |
| Poteto entry and prompts, LAYER 4 loading LAYER 5 | `prompts/poteto.md` gives one entry. `overlay/APPEND_SYSTEM.md` loads project principles. | Model-triggered reading is not deterministic enforcement. Repeated entry/routing instructions add reader work. |
| Skills and detailed playbooks, LAYER 5 | Investigation forbids code changes. Bug fix asks for a reproduction before selecting a fix. Pickup distinguishes history from fresh proof. | Mandatory ceremonies can be applied to the wrong task. Numeric-cap kickoff and a new `checks/` script for every acceptance seed gates. Rows 37 and 43 show proof steps obstructing authorized work. |
| Pi overlay and installer, LAYER 3 plus LAYER 4 | `install.sh`, `overlay/settings.json`, and `conform-skills.py` install and restrict actual tools and child profiles. | Conformation changes names and links, not playbook semantics. Upstream skill roles and fallback instructions can disagree with the overlay and program fences. |
| Stream repo shape, LAYER 1 | STREAM, STATE, DECISIONS, context, and handover have discoverable locations. Thread briefs point to the goal and real artifact. | STATE's six-line skeleton does not model ask lifetime. Historical 654 checkpoints recursively preserved history despite the rewrite rule. A §2.3. |
| Deterministic checks, LAYER 2 when invoked | Template and command tests catch installation or command-shape regressions. | Byte equality can pin bad instructions. B §2.2 found a checker matching the coordinator's wrong sign. Green is evidence for the checked proposition, not ZF's intent. |
| Tick and lifecycle code, LAYER 3 | `threads.py` checks lifecycle transitions. Existing locks and persisted worker-queue replay are real mechanisms. | `tick.py::wake` requires a pending event. Recovery requires a later non-error reply. These are not Z1 or G5. |

B §2.3 records a positive example. The 654 coordinator replaced its obsolete predecessor-receipt gate with current-artifact reverification and continued within existing authority. That follows Prove It Works in effect. Rows 44-45 instead show host guards obstructing work. A context-preservation principle does not authorize CPU or RAM budgets. B also records that some original guards were ratified before later revocation, so their whole history is not proved agent invention.

Two source anchors matter most. `pi-streams/templates/stream/AGENTS.md:5-8` asks the model to resolve autonomy, verification, and state rewriting. `pi-streams/engine/tick.py:435-479` implements edge-driven wakes and the older rotation path. More wording at the former cannot implement missing runtime behavior at the latter. Conversely, a runtime wake cannot repair a wrong success criterion. No project `.cursor/skills/principle-*/SKILL.md` files were present in either checkout.

## External evidence and stop checkpoint

[30a-external-corpus.md](30a-external-corpus.md) preserves the partial source list, short quotes, tags, retrieval limits, and an observed counterexample. It is not a completed merged corpus. Parent-fetched sources cover Goose's intra-turn compaction and ACP command boundaries, LangGraph nested interruption, and Aider edit/watch loops. Five additional Codex, Aider, and Cline reports remain delegate-fetched candidates. Their original collection timing and unfetched comments still need checking. No final causes are inferred from them.

The X seed is now complete and was read in full. Its 64 numbered entries are not 64 verified incidents. X originals remain unverified on this host. The seed's full triage and the HN, Reddit, and blog sweeps did not complete. Promotional exceptions and unsupported numerical claims are not admitted as evidence.

The control sweep's substantive result is `BLOCKED_QUOTA`, with zero admitted original reports. The memory sweep also reports `BLOCKED_QUOTA`, retaining five fetched bodies. Both identify GitHub public issue search, not Codex, as the limited service. The exact reported error is `HTTP Error 403: rate limit exceeded`. No reset was probed after the parent learned of it.

A final local reread of Cat's Deferred to track 3 section retained the same nine deferrals, now at lines 375-383. The catalog SHA-256 at the 01:58 UTC checkpoint is `ef195cdc9188bacb7111f0d056bb4ec830cd717d1402c467a76ec7fd20d91cd3`. The current decisions SHA-256 is `3b1aa62d7865257cb2fab56119d05b728630ee75b97be74535957bfb80d2d8c2`. Shared inputs can change after this checkpoint.

## Verification and attention

The parent read the full 75-row corpus and the four common inputs. The inventory delegate read A/B/C, R, the stream decisions and brief, all four issue snapshots, and track 1's catalog. Its completeness crosswalk covers all 18 interrogation open questions, R's unsettled policy section, seven engineering uncertainties, and all nine catalog deferrals. Historical runtime findings remain source-reported, not new reproductions.

A local Python check passed for 40 unique problem IDs, ten unique external-record IDs, existing local links, explicit blocked status, Z3/Z4 wording, and whitespace. `git diff --check` passed for the authorized artifact paths. These checks do not establish research completeness, source-claim truth, or design acceptance.

The source checkout remains clean, and the docs index has no staged files. Other tracks' docs changes were observed and left alone. Only `30-research-designs.md` and `30a-external-corpus.md` were authored by this parent. No commit, push, issue comment, credential change, or existing-stream operation was performed.

Prove It Works changed the completion claim. A workflow launch receipt, a retrieved complaint, and a proposed design are not a finished research result. Guard the Context Window kept the large input crosswalk in delegated reports. Separate Before Serializing Shared State kept delegates read-only and left one writer for these artifacts. Laziness Protocol kept the scout focused on existing mechanisms rather than selecting a new engine.

Attention. No completed adversarial interrogation or cross-model trail review exists. The same-model restriction precludes the latter, and the quota stop prevented the former. Do not interpret launched or paused reviewers as completed reviews. The final design table, problem-by-design coverage matrix, layer-by-layer production mechanisms, and design risk comparison remain outstanding.

## Decisions

- T3.1. Only the parent writes the two authorized artifact paths. Delegates return read-only reports. This avoids competing writes in the shared docs worktree.
- T3.2. Use the required openai-codex/gpt-6.1-sol model for every delegate. Independent same-model interrogation does not provide multi-model diversity.
- T3.3. Do not reconstruct the missing brief text. Treat the explicit program decisions as the available constraints. Re-read decisions after the update and use Z3, which supersedes G4, rather than preserve the original 252k wording.
- T3.4. Keep progress in this authorized artifact rather than create a separate repository planning file. The other tracks share the worktree.
- T3.5. Recheck the X seed and track 1 catalog before closing. Both are being written in parallel and were absent or incomplete at the initial read.
- T3.6. Reject workflow wrapper completion as evidence of child completion. The first workflow returned launch receipts and started dependent readers prematurely. I interrupted only my own dependent delegates, then resumed (b) after the real inventory and (c) after the real scout. No premature result counts as accepted stage evidence. Interrogations A and C had already documented this runner defect. I missed that warning before dispatch. This track cannot repair the runner because its scope is artifact-only.
- T3.7. Stop when the substantive source-sweep reports reveal GitHub's search quota error. The operator rule says usage or quota error, without an exception for external search. No Codex exhaustion is alleged. Only local checkpoint writing and verification followed that observation.
- T3.8. Preserve source candidates without completing their admission or causal analysis. This keeps collected links recoverable without converting search failures, unverified X paraphrases, or prematurely collected material into accepted evidence.
- T3.9. Do not produce three speculative designs merely to fill the requested table after stopping. The user requires combined interrogation before design. The missing deliverable is explicit rather than disguised as a completed proposal.

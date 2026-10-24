# Harness program track 3. Three competing proposals

Proposal complete under Z12. Artifact only. No implementation, commit, or stream operation.

ZF gets three alternatives for preserving the requested work without adding a configurable workflow engine. Maintainers get explicit ownership boundaries, layer placement, and the limits of each alternative.

## Read this first

**Recommend A, repo-owned work and evidence.** This is an architectural judgment, not a measured winner. It puts obligations and checkable acceptance next to the artifacts agents already use. Keep runtime changes for delivery, continuation, and safe maintenance. B is stronger when many clients must share runtime-owned task state. C changes the least, but depends most on coordinator judgment.

| Proposal | Where current truth lives | Main advantage | Biggest risk |
|---|---|---|---|
| A. Repo-owned work and evidence | Source-linked work records in the stream-owned repo, with tests beside product code. | Portable across sessions and backends. Uses the strongest layers first. | A precisely recorded acceptance criterion can still be the wrong interpretation. |
| B. Runtime-owned obligations and hooks | Existing durable intake and operation records in the session service, with generated repo views. | All clients can share delivery, cancellation, and ownership facts. | The adapter grows into the framework ZF rejected, or misses a bypassing client. |
| C. Principles and small playbooks | Existing charter and source-linked TODO, with an action log as history. | Least new machinery and the easiest human inspection. | The same coordinator can silently narrow both its checklist and its evidence. |

**Review attachment for track 1.** The one-line Z1-Z11 verdicts are in the candidate-remedy table below. They are research verdicts for G18's review attachment or follow-up. They do not stop track 1's MVP or modify its authorization.

## Scope, evidence, and the five inputs

Z12 supersedes the earlier instruction to treat Z3 and Z4 as fixed design constraints. Z1-Z11, G5 as narrowed by Z11, and G17 are candidates here. Track 1 independently implements its MVP under G18. This report can recommend a different later design without claiming the MVP has already changed.

| Input | Material used | Evidence limit |
|---|---|---|
| 1. Local failures | All 75 rows in K and interrogations A, B, and C. P01-P40 below retain the unresolved questions. | Selected steering episodes, not independent trials or an incidence denominator. |
| 2. Human remedies | Z1-Z11, narrowed G5, and G17 in [03-decisions.md](03-decisions.md). ZF's messages are in [00b](00b-zf-messages-verbatim.md), t208u-t214u. | Candidate remedies are hypotheses. Z2 assigns work, and Z10 classifies it. Neither supplies a remedy. |
| 3. Balance | The explicit F1-F12 table below. | Direct partial coverage is not full treatment of a class. |
| 4. Internet and research | [30a-external-corpus.md](30a-external-corpus.md), the [X seed](31-x-corpus-seed.md), and R. | Five parent-fetched reports, five delegate-fetched candidates, and 39 retained secondary X records. HN, Reddit, and blog coverage remain absent. |
| 5. Principles | The installed poteto entry and playbooks, relevant principle leaves, and [layer affinity](02-principles.md). | Instructions guide judgment. They do not prove runtime enforcement. |

K is `context/stall-corpus-2026-10-22.md`. A, B, and C are `context/interrogations/A-mechanical-2026-10-22.md`, `B-goal-integrity-2026-10-22.md`, and `C-control-loop-2026-10-22.md`. R is `context/research/deep-research-2026-10-23.md`. These paths are under `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/`. Cat is [track 1's catalog](10-pi-streams-fix-catalog.md). Code observations refer to pi-stack `3acf0f01e6084a317b89cef3a86f4781e60877cf`, not a future MVP implementation.

E01-E05 are fetched original practitioner reports, not locally reproduced failures. E06-E10 remain candidates and are not sole support for a cause. Xnn preserves the seed's item number. Every X report remains secondary and unverified on this host. The appendix excludes promotional exceptions and unsupported study numbers. It records one disposition for every seed entry. Repeated authors and potentially related incidents remain dependent evidence.

The initial sweep stopped on GitHub public issue-search HTTP 403 rate limiting, not Codex exhaustion. Z12 authorizes continuing from saved inputs. This continuation made no network request or quota probe and did not switch model or provider.

The full t209u text is now supplied by 00b. The old marked gap is not reconstructed or treated as the only available account. t214u remains explicitly paraphrased. D1 still excludes default resource budgets. D6 still excludes contested-ownership precedence machinery and requires retaining needed tool-repo artifacts in owned worktrees. D7 concerns state and ruleset review. Z11 is a later explicit candidate for destructive recovery, so the objection to it below is correctness, not a claim that ZF cannot authorize deletion. D8 and D9 still require ask-level reporting and a workflow shape before reviewer policy.

## Unresolved problem inventory retained from the first pass

These are problem statements, not requirements for an ask database or control engine. P identifiers are local and distinct from the program decisions P1-P7. Source-derived crash and ownership risks are not additional observed incidents.

| ID | Problem statement | Source and motivating rows |
|---|---|---|
| P01 | Standing goal, priority, current execution, and history can replace or contradict each other. | K §3; B §2.1; R Q3. Rows 9,12,27,30,36,38,57,75. |
| P02 | An ask can disappear, narrow, or move to an unapproved later plan without cancellation. | B §2.1-2 and traces; R Q3. Rows 3,5,6,20,28,30,31,38,58,68,74. |
| P03 | Original wording, authorship, order, and relay transformations are not always recoverable. | B traces/§6; R Q2/Q8. Rows 6,8,15,28,30,33,38,42,68,69,74. |
| P04 | Transport acceptance, consumption, application, and completed outcome are conflated. Never-sent messages remain invisible to the coordinator. | C §2.3; R Q2; Z5. Rows 21,35,72,73. |
| P05 | Delayed or repeated input can revive superseded or cancelled work. | A §4.4; B §4.3; R Q2. Rows 20,69,72,74,75 motivate the risk, not proved duplicate effects. |
| P06 | A checker or completion claim can prove the wrong interpretation, target, or subtask. | B §2.2/§4.2; R Q7. Rows 1,4,7,8,18,22,26,28,30,36,64,69,74. |
| P07 | Investigation can answer the wrong experimental question or infer a cause without isolating it. | K rows 1,2,4,7,8,18,22,66; B §3/§6. |
| P08 | Bespoke code, loaders, runners, images, or validation replace requested minimal changes and known paths. | B §2.3/§5.6; R Q11. Rows 14,15,19,41,48-50,56,58,61,62,65. |
| P09 | Revoked constraints remain current, or removing one rule revives an unrelated prohibited action. | B §2.3; R Q8. Rows 10,20,44,45,54,61,69,75. |
| P10 | Agent-created budgets, proof campaigns, historical receipts, and redundant approvals obstruct authorized work. | Issue #33 snapshot; A §3; B §2.3; C §2.4. Rows 10,37,39,43-45,54,61,65. |
| P11 | Human prohibitions, factual prerequisites, chosen dependencies, and unowned pauses look alike. | C §2.4/§3; R Q6/Q8. Rows 37,43,54,75. |
| P12 | Independent authorized work waits behind unrelated work or recovery. | C §2.4/§4.5; R rank 4. Rows 5,9,34,46,75. |
| P13 | Unfinished authorized work has neither a live owner nor future reconsideration after a turn ends. | C §2.1; R Q1/Q6. F1 rows, especially 26,39,51,55,59,60,64. |
| P14 | ZF must poll for each ask's actual status and findings, even when computation continues. | D8; C §2.1; R Q6. Rows 24,26,39,51,54,55,59,60,64. |
| P15 | Recovery waits for the successful continuation that it is supposed to cause. | C §2.2; R Q9. Rows 13,17,23-25,47,52,53,63,67. |
| P16 | Relevant readiness evidence is not established for every provider, tool-login, storage, and job failure. | C §5.4; R Q9/§4 uncertainty 5. Same F7 rows. |
| P17 | An uncertain send or submitted job can be duplicated or replayed under stale authority after retry. | R Q1/Q2/Q9 and §4 uncertainty 6. Prospective risk. |
| P18 | Alerts depend on the failed provider, host, storage, or tick. The bot's delivery contract is uninspected. | C §2.2/§5.6; R Q9. F7 rows. |
| P19 | One failed observation skips independent control work. A fresh tick is mistaken for goal progress. | C §2.2/§6; R Q6. Source-derived risk without localized incident attribution. |
| P20 | Registered coordinator, actual session, activity, outstanding work, and completion disagree. | K §3; C §2.3; issue #36 snapshot. Rows 26,51-53,55,64,71,72. |
| P21 | A successor reads a child ID without owning its wait, steering, or completion callback. | A §5.6; C §2.3; R Q1. Replacement exposures include 37,51-53,55,72. |
| P22 | Replacement lacks complete transfer or adoption of instructions, work, results, and mutation ownership. | A §2.2/§4.4; R Q2. F6 rows motivate it, not proof all were caused by replacement. |
| P23 | Moving a transcript breaks evidence references even when its bytes survive. | A §2.2 row 37; R Q10. Corpus row 37, not GitHub issue #37. |
| P24 | Non-interrupting maintenance is unverified across direct prompts, long turns, and failures. | A §2.1; R Q5; Z3/Z8. Rows 11,16,32,71. |
| P25 | Smaller context and faithful quotations have not proved better compliant action here. No compaction-count cutoff is established. | A operating-model table; B §5.2; R Q4/§4 uncertainty 7. |
| P26 | Current state, history, TODO, decisions, and rules duplicate or contradict each other. Safe review ownership and triggers are unclear. | K §3; A §2.3; D7; R Q3. Rows 11,16,28,30-32,37,38,71. |
| P27 | Thread lifecycle needs a separate policy for task detail and in-flight work. Coordinator thresholds do not decide it. | Issue #35 snapshot; A operating-model table; D3. |
| P28 | Prose, bespoke events, registry labels, and views lack a reliable shared meaning of obligation, owner, wait, and outcome. | C §2.4; R Q3. Not proved malformed-event causation. |
| P29 | Scratch/data enters Git and outputs, branches, or worktrees accumulate. ENOSPC recovery does not prevent production. | K F11; C §3. Rows 17,29,47,70. |
| P30 | Original instructions and artifacts can be unavailable when later decisions need them. Hashes and ignored paths do not retain bytes. | K §3; A artifact management; R Q10; D6/D7. Rows 28,37,72. |
| P31 | Receipt, disposition, and dispatch diverge across crashes or competing updates. Atomic visibility alone is not established crash durability. | R Q1/§4 uncertainties 1 and 6; Cat registry-publication item. |
| P32 | No minimal cross-workflow definition establishes meaningful completion and review boundaries. | D9; Z2; R §4 decision 6. |
| P33 | Review's added semantic detection, false rejections, and cost are unmeasured. | B §5.4; R Q7. Rows 8,28,30,36,69 motivate evaluation. |
| P34 | The evidence does not establish prevented-incident rates or complete first-loss chronologies. | A/B/C qualifications; R coverage caveat/§4. All rows, especially 8,31,37,54,68,69,72,74,75. |
| P35 | Remedies have not demonstrated generality or correct enforcement placement. Process itself can add gates and context. | ZF's brief; 02-principles; B §6; withdrawal of R's plan. |
| P36 | Program sources change and older files retain superseded policy. The original gap is now supplied by 00b, while t214u remains paraphrased. | 00, 00b, 03-decisions, stream DECISIONS. Input-quality issue. |
| P37 | Repeated remote-wrapper calls reportedly restart Twingate and time out. | G15; Cat remote-wrapper item. Adjacent track 1 issue. |
| P38 | Caladan's relation to the main-based prime CLI remains unspecified. | Scope track 2; G8. Nonblocking adjacent issue. |
| P39 | Runtime dispatch can bypass an unratified kickoff gate. | Cat autonomy/ratification item; baseline spawn/adopt paths. Source-derived. |
| P40 | A role-named handover is mistaken for a successor's own handover. | Cat handover-identity item; baseline `_has_handover`. Source-derived. |

The initial completeness crosswalk covered all 18 A/B/C research questions, R's six unsettled policy questions, and seven engineering uncertainties. Their surviving topics are represented above. The nine Cat deferrals remain ask lifecycle, self-grading, constraint lifetimes, general control machinery, workflow/reviewer policy, native-child adoption, parallel scheduling, overbuild/reuse, and historical cleanup. This imports problems, not the withdrawn framework.

## What pi-stack's spectrum gets right and wrong

The poteto entry is a dispatcher. Principles offer broad judgment. Playbooks specify detailed procedures. The overlay maps tools and installs resources. Repo files structure the material agents actually read. Runtime code implements only particular operations.

| Existing part | What works | What does not, with evidence |
|---|---|---|
| Principles, LAYER 5 | Laziness, Prove It Works, and Model the Domain transfer across tasks. | Rows 41 and 48-50 conflict with reuse guidance. That does not prove the agent read the relevant leaf. |
| Entry and always-on rules, LAYER 4 loading LAYER 5 | `prompts/poteto.md` gives one entry. The overlay names actual tools. | Reinjecting an instruction is still not a deterministic execution guarantee. Loaded text can conflict or grow. |
| Detailed playbooks, LAYER 5 | Investigation stays read-only. Bug fix requires a reproduction. Pickup distinguishes inherited history from fresh evidence. | Applying ceremony to every task creates proof gates. Rows 37 and 43 illustrate obstruction. Kickoff's numeric-cap demand contradicts D1. |
| Repo shape, LAYER 1 | STREAM, STATE, DECISIONS, context, and handovers are discoverable. | The STATE skeleton lacks ask lifetimes. Recursive historical preservation defeated its rewrite instruction. A §2.3. Renaming the pile alone does not repair its meaning. |
| Checks, LAYER 2 when run | Template and command tests catch wiring mistakes. | Template equality can preserve bad wording. B §2.2 found a checker matching the wrong sign. It proved that proposition, not ZF's outcome. |
| Installer and tick, LAYER 3 | Real profile restrictions, locks, lifecycle checks, and persisted worker replay reduce reliance on memory. | Baseline `tick.py::wake` needs an event. Recovery needs a later success. Those are distinct from eligible continuation and recovery. |

B §2.3 supplies a positive example. The 654 coordinator replaced its obsolete predecessor-receipt gate with current-artifact reverification and continued within existing authority. That follows Prove It Works in effect. Rows 44-45 show guards obstructing work, but B also establishes that some original guards were ratified before later revocation. Do not rewrite all of their history as unauthorized invention.

The baseline coordinator rules at `pi-streams/templates/stream/AGENTS.md:5-8` ask the model to resolve authority, verification, and state rewriting. `pi-streams/engine/tick.py:435-479` implements edge wakes and the older rotation policy. More wording cannot implement a missing runtime clock. More wakes cannot correct an unsound acceptance criterion. No trusted project `.cursor/skills/principle-*/SKILL.md` files were present in the source or docs checkout.

## Input 3. The explicit balance after ZF's remedies

Coverage here means a candidate directly addresses a submechanism. It does not mean implemented or proved effective. `NONE` means no Z1-Z11 remedy supplies the defining missing behavior. Adjacent partial help is named rather than inflated into coverage. Z2's assignment and Z10's taxonomy are not counted as fixes.

| Class | Candidate remedy or NONE | Balance beyond those candidates |
|---|---|---|
| F1. Human is the clock | Z1/Z6 for continuation; Z4 for notices. G5/Z11 for outage subsets. Partial. | Useful progress, ask-level findings, and correct waits remain different from another turn. Rows 26,39,53,60. |
| F2. Silent narrowing or deferral | **NONE for ask lifetime.** Z5/Z7 offer adjacent delivery and goal visibility. | Preserve every uncancelled requested outcome through replanning. Rows 28,30,74. |
| F3. Invented guards and gates | **NONE for the general class.** Z11 prevents some new environment-failure-driven rules. | Retire stale self-created gates without bypassing actual human prohibitions. D1 already rejects default budgets. Rows 37,43-45. |
| F4. Overbuild | **NONE.** | Bind scope and actual tool reuse to the request. Rows 41,48-50,56. |
| F5. Wrong metric or overclaim | **NONE.** | Test whether the oracle answers the original question and the claimed result exists. Rows 8,18,36. |
| F6. Context and rotation churn | Z3/Z8 for maintenance; Z9/G17 for historical organization. Partial. | Correct current input, pending messages, tool pairing, ownership, and evidence continuity. Rows 11,32,37,72. |
| F7. External blockers | Narrowed G5, Z11, and Z4. Partial. | Human repair, real reset/readiness observations, uncertain-job reconciliation, and reliable notification. Rows 13,23-25,47,53. |
| F8. Lost or misbriefed steer | Z5. Partial. | Capture never-sent asks and detect semantic broadening. Rows 21,33,35,73. Row 72's saved messages arrived. |
| F9. Unneeded serialization | **NONE.** | Separate real prerequisites from planning order and preserve legitimate holds. Rows 5,34,46,75. |
| F10. Explicit constraint override | **NONE.** | Preserve applicable constraints and protected artifact behavior across plan/oracle changes. Rows 20,69. |
| F11. Artifact and hygiene litter | **NONE preventively.** Z11 addresses resulting exhaustion. | Exclude scratch from publication and name output/branch ownership without adding resource budgets. Rows 17,29,47,70. |
| F12. Goal identity confusion | Z7/G17. Partial. | Separate finite asks, target branches, current completion, and source-backed priority. Rows 9,27,38,57,75. |

The seven NONE rows are F2, F3, F4, F5, F9, F10, and F11. Each proposal's coverage table below explicitly treats all seven. These are class-level judgments, not seven independent incidents or a count of failures that would disappear.

## Combined interrogation before design

Two fresh read-only reviewers used `openai-codex/gpt-6.1-sol` with the same prompt and evidence. Actual reports were consumed from runs `fd522b13-6d8b-4e3a-a78d-075043a3ca4d` and `acbd4445-2dca-44d8-bbdc-877a1f53a4e9`. The workflow wrapper again returned launch receipts early. Those receipts were not reviews. This is independent same-model examination, not multi-model consensus or statistical independence.

The lead synthesis retains five causal hypotheses. They are supported explanations for mechanisms, not a measured decomposition of all 75 rows.

| Cause | Mechanism and support | Counterevidence and what would disconfirm it |
|---|---|---|
| C1. Current obligations are confused with recent narrative | Priority, plans, old constraints, and history compete as authority. K rows 28,30,38,44,45,74,75; B §2.1/§2.3; A §2.3. X47,48,51,54 are secondary parallels. | The 654 audit recovered useful dispositions. A source-complete history could work. History-only pickup preserving an old unresolved ask beyond 30 unrelated entries, while rejecting later-cancelled work, would weaken the need for another current representation. |
| C2. The plan and oracle share an untested interpretation | A narrowed brief, substitute implementation, and its checker can agree while missing the actual ask. Rows 8,18,28,36,41,48-50,56,69; B §2.2; R Q7/Q11. X32,35,36,60 are secondary parallels. | Matching tests can be right, and small changes can be wrong. Source-bound evaluation must distinguish valid alternatives, incomplete outcomes, and real cancellation. No saved result proves recurring review's benefit. |
| C3. Activity does not establish eligible continuation | An event is consumed, or an outage parks the coordinator, without a future reconsideration of authorized unfinished work. C §2.1-2.2; rows 25,26,39,51,53,59,64. E04/E05 warn that extra triggering can repeat failure. | The timer and subscriptions already exist. Polling can mean missing reporting rather than stopped work. X61 is positive recovery counterevidence. A live idle-continuation and recovery demonstration that preserves valid waits would test this cause. |
| C4. Chat identity is confused with ownership of work, evidence, and effects | A successor or fork preserves text without necessarily inheriting pending input, child watches, evidence locations, or the actual state of external jobs. A §2.2; C §2.3; rows 21,29,35,37,72,73 and the registry cross-check. E02/E03 support narrower boundary mismatches. | Row 37's bytes survived. All 20 saved row-72 messages arrived. Native archive refusal exists. Correct adoption, retained evidence, scratch exclusion, and uncertain-effect reconciliation would close separate parts. A streaming flag proves none of them. |
| C5. Memory maintenance changes the context without proving equivalent working state | Checks miss long tool loops, while pickup reloads conflicting or oversized inputs. A §2.1/§2.3; R Q4/Q5; rows 11,16,32,71; E01 and E02. X08/X09 are secondary parallels. | The full 10 MB STATE was not loaded wholesale. Other reads and tool arguments contributed. Same-session compaction can help. Observe actual context, tool pairs, pending input, and compliant actions rather than a smaller counter alone. |

### Lead judgment on the interrogation

| Finding | Review agreement | Judgment |
|---|---|---|
| Recent action history does not establish all current obligations. | Both. | Act on. Make pending work and applicable constraints discoverable independently of recency. |
| Reinjection is not unconditionally safe or useful. | Both. | Act on. Preserve stops, pending asks, ownership, and outage parking at admission. |
| Fork-lastgood does not roll back the outside world. Streaming does not prove safe deletion. | Both. | Act on. Reconcile effects and later input. Separate adoption from deletion. |
| DCR needs safe tool boundaries and retryable sequencing. | Both. | Act on. A user-visible single action can still fail between its steps. |
| Z3's 150k trigger deserves adoption or modification. | One favored a reversible trial; one emphasized the long-turn gap. | Consider. Retain 150k as an initial operating choice, not a demonstrated optimum or hard ceiling. Modify sequencing and observe its effect. |
| Z5 requires application before any acknowledgement. | Reviewers differed. | Clarify rather than reject. Z5 can reserve applied acknowledgement while still reporting recorded, consumed, blocked, or rejected input truthfully. None is product completion. |
| Earlier D7 alone forbids Z11's later explicit wipe policy. | Both leaned on the older no-deletion boundary. | Dismiss that precedence argument. Z11 explicitly proposes deletion for the MVP. The substantive objection is incomplete preservation and replay safety, and Z12 permits criticizing it. |

Also dismiss permanent byte loss in row 37, permanent loss of row 72's saved queue, a proved fresh-OK stall in row 54, an invented Phase-2 hold in row 75, and a complete instruction-arrival chronology in row 69. The corrected evidence does not support those claims.

## A minimal workflow shape, before reviewer policy

All three proposals use the same small set of facts. They differ in where those facts live and what enforces them. This is a task contract, not a workflow DSL, phase registry, or per-workflow configuration language.

| Fact | Required distinction |
|---|---|
| Source | The exact ask or retained source reference, with its intake identity. Interpretation is separate. |
| Outcome and target | The requested observation and artifact or job it concerns. A new plan cannot silently replace them. |
| Authority and constraints | Permitted writes, applicable stops, and explicit changes to them. A chosen dependency is not a human prohibition. |
| Current disposition | Open, running, waiting with its reason, completion candidate, accepted, cancelled, or superseded. Cancellation is not implementation success. |
| Evidence | Actual result, target identity, test or observation, and findings answering the ask. A delivery receipt is not this evidence. |
| Next responsibility | A live owner, a factual recheck, a human decision, or eligible next work. Priority does not cancel other open asks. |

A rule has a source and an applicability scope. Task-scoped rules end with that task. Standing prohibitions remain until explicit change. An authorized supersession retires affected derived plans and stale checker results, not unrelated stops. Rotating a log entry never expires a constraint. No contested-ownership precedence subsystem or arbitrary expiry timer is proposed.

The shape works across different work without custom workflow definitions:

| Work | Completion observation | Where judgment remains |
|---|---|---|
| Code change | The requested behavior on a pinned artifact, using the repo's actual test or runtime path. | Whether the test proposition matches the request and whether a larger change was necessary. |
| Investigation | The requested question, exact observations and sources, and explicitly unresolved conclusions. | Experimental method and the inference from observations. |
| Long external job | Existing operation identity, terminal result, retained output, and no duplicate submission. | Whether inputs and result match the requested experiment. |
| Documentation or design | The named artifact, requested sections, source traceability, and an explicit recommendation or unknown. | Whether the explanation or proposal is sound. |

Use deterministic checks first. A fresh source-bound review is proposed at a current-objective completion or consequential publication when the criterion itself needs semantic judgment. Give it the original ask, target, raw results, and oracle, not only the writer's completion narrative. Do not run a reviewer on every tick or require a new script for every small ask. Its incremental detection and false-rejection cost still need evaluation. Same-model freshness is not guaranteed independence.

For all three proposals, coordinators use same-session DCR as the initial maintenance trial. Workers keep their native compaction behavior during active tasks. Hand off at a real task boundary after retaining unfinished input and result ownership, not after an invented number of compactions. Do not apply the coordinator's 150k trial to workers by assumption. LAYER 3 owns this role-specific runtime behavior because files and CI cannot order an in-flight session's maintenance. LAYER 1 retains session-bound handover artifacts, and LAYER 2 tests their actual attribution.

## Proposal A. Repo-owned work and evidence

### Core idea and data shape

Keep the authoritative obligations in the owned repo that survives the session. Concretely, use `work/asks/<intake-id>.md` as the map of source-linked ask records, and generate `work/open.md` as its read-only pickup view. These are proposed paths, not files added by this track. Each record holds the task-contract facts above. The original-source section has an intake-bound hash and is distinct from the mutable interpretation. Standing constraints remain in the charter, and task constraints in the relevant record. Completed history stays cold. The generator enumerates every open record and recorded applicable constraint, regardless of when it last appeared in ACTIONS. It does not infer natural-language applicability on its own.

Keep G17's STREAM, ACTIONS, and `history/` names for compatibility where useful. Treat ACTIONS as recent activity, not the complete current state. Thirty recent entries may remain a presentation choice. Do not impose a new size or resource budget. Product tests and known-good invocations remain beside the product code, with small retained result references copied into the owned stream folder under D6.

This directly targets C1 and C2 through context shape and source-bound evidence. It uses the existing tick for C3 and explicit boundary checks for C4/C5. It is the preferred design because it does not make the session service the only holder of task meaning.

### Mechanisms and layer placement

| Mechanism | Layer and reason |
|---|---|
| A1. Source-linked work records and a generated current view | **LAYER 1.** These are the files agents read at pickup and beside the work. No stronger layer exists. History cannot silently substitute for the open set. |
| A2. Contract-integrity and behavior checks | **LAYER 2.** Check source identities, open-record inclusion, target/evidence bindings, retired checker results, and known scratch-publication patterns. Repo layout alone cannot fail a bad transition. Actual behavior tests remain task-specific. |
| A3. Deterministic intake and repo bootstrap | **LAYER 3.** Extend existing intake/bootstrap to copy the original request into an owned stub, emit the LAYER 1 templates, and install the LAYER 2 check invocation. Static files cannot capture a new external message or run deployment-time installation. |
| A4. Eligible continuation, maintenance, and recovery | **LAYER 3.** The existing tick observes actual activity and uses the designated coordinator. It coalesces wakes, preserves gates and parking, and performs retryable DCR at safe boundaries. Repo files and CI cannot wake a stopped deployed session. |
| A5. A short rule for interpretation and reuse | **LAYER 4.** Prefer the named existing tool and smallest sufficient change. Record a necessary deviation against the actual ask. Stronger layers carry concrete banned APIs and behavioral invariants when expressible, but cannot decide every experimental or design judgment. |
| A6. Small code, investigation, job, and publication playbooks | **LAYER 5.** These guide judgment where stronger layers cannot. They do not own intake, cancellation, compaction, or proof of completion. |

### How layers 3-5 produce layers 1-2 across repos

The installer/bootstrap copies versioned record templates and a portable integrity checker. It wires that checker into the existing repo verification entry and emits a local invocation even when no CI service exists. Existing CI conventions are detected through a small explicit adapter set. An unsupported CI layout is reported as unwired, not silently counted as installed.

Input is the pinned source request, repo root, existing verification entry, and selected standard template version. Re-running with those inputs produces the same owned stubs and check wiring without overwriting user-owned content. No per-workflow graph is configured. The agent supplies domain-specific acceptance and a regression test through the relevant playbook. That semantic step is not deterministic. Once accepted, its artifact and source bindings are deterministic check inputs. A skill cannot promote its own suggestion to an installed check without the actual generated patch and verification result.

### Lifecycle, constraints, and failure handling

Intake creates an open record before dispatch. Replanning changes owner or next action, not the source outcome. Waiting names a real prerequisite and its release condition. Completion first becomes a candidate against the original target. Accepted results retain findings. Cancelling or superseding an ask requires the applicable instruction and preserves its history. Requested reports concatenate findings by ask, not by the most recent activity.

Constraints remain attached to the work or standing charter. Supersession invalidates affected brief/check evidence. A source correction can reopen a wrongly closed ask. No new approval is needed to repair a self-created bookkeeping obstacle inside existing authority. Real human holds remain holds.

Use same-provider quota wait/retry from narrowed G5. For auth, disk, and environment failures, park the affected work and notify ZF. Do not mutate credentials or generate new rules from the outage. After a real restoration notice, reconcile the latest request, external jobs, and actual owners. Prefer continuing the current session. Fork only for a demonstrated session-repair need with explicit adoption. Archive the predecessor rather than wipe it merely because the successor streams.

### A's coverage of the input-3 balance

| Class | Z candidate relation | A's handling and residual |
|---|---|---|
| F1 | Z1/Z4/Z6 partial | A4 advances eligible open records; A1 supplies per-ask findings. More turns still do not prove progress. |
| F2 | NONE for lifetime | A1/A2 preserve every intake record through plans and current views. Semantic narrowing remains possible. |
| F3 | NONE generally | A1 scopes constraints; A2 rejects stale references and shipped default-budget demands; A5 distinguishes actual holds. Arbitrary invented prose gates still need judgment. |
| F4 | NONE | A5/A6 compare the actual invocation and diff against the requested standard path; encode repeatable deviations in product tests. No universal minimal-diff oracle. |
| F5 | NONE | A2 binds evidence to the original target; source-bound completion review challenges the proposition. Scientific inference remains fallible. |
| F6 | Z3/Z8/Z9 partial | A1 supplies current input, A4 coordinates safe DCR, and stable copied evidence survives history movement. Summary fidelity remains unmeasured. |
| F7 | G5/Z11/Z4 partial | A4 parks by class, retains jobs, and resumes only eligible work after the relevant release. Human environment repair remains necessary. |
| F8 | Z5 partial | A3 captures the source before dispatch and preserves application disposition separately from outcome. The outer bot must use the same intake boundary. |
| F9 | NONE | Work records name real prerequisites and independent owners. The coordinator fans out disjoint writes and independent reads, without a general scheduler. Dependency judgment remains. |
| F10 | NONE | Source-scoped constraints and artifact-bound behavior checks reject known overrides. Unformalized language still needs original-source review. |
| F11 | NONE preventively | A2 checks publication boundaries; owned output locations and explicit branch owners prevent known scratch commits. No automatic destructive cleanup or resource caps. |
| F12 | Z7 partial | Standing objective, current objective, and open asks have distinct locations. Completing CURRENT can disarm driving without marking the North Star complete. |

**Does not fix.** Missing historical originals, unknown backend adoption APIs, a wrong domain oracle, permanent infrastructure denial, or every form of overbuilding. Its largest risk is a wrong criterion expressed cleanly in all the right files. The check must challenge the criterion, not only its syntax.

## Proposal B. Runtime-owned obligations and hooks

### Core idea and data shape

Extend the receiving-side intake and operation records proposed for track 1's MVP, once those records exist and pass their boundary tests, into typed task facts keyed by source message identity. The inspected baseline does not already provide that durable task contract. The session service owns intake disposition, current objective references, cancellation, owner identity, and evidence references. It generates a read-only `work/open.md` view and reads the ratified charter without silently replacing it. This is a map of runtime facts and operations, not a configurable workflow engine or executable event history.

This most directly targets C3/C4. It can make every supported client observe the same command and ownership facts. It addresses C1 through deterministic projection and C2 through source-bound completion admission. The tradeoff is backend dependence and more runtime state.

### Mechanisms and layer placement

| Mechanism | Layer and reason |
|---|---|
| B1. Typed intake, task, and operation records in the existing service | **LAYER 3.** Only runtime ingress can consistently correlate clients, pending input, and session ownership. Repo files cannot observe a message the service has not delivered. Do not add a second daemon or per-workflow transition registry. |
| B2. Generated charter/current/task views and retained evidence references | **LAYER 1.** Agents and humans read explicit current facts beside the repo. No stronger layer exists for that context. These views are projections, not another independently writable source. |
| B3. Admission and artifact checks | **LAYER 2.** Test source-to-target bindings, stale generations, real changed behavior, and publication exclusions. A runtime status string is not adequate acceptance evidence. |
| B4. Native lifecycle hooks and bounded tick operations | **LAYER 3.** Persist pending input before acknowledging it. Couple safe DCR, due recovery, and successor adoption to actual backend checkpoints. CI cannot serialize a live provider request or transfer a native callback. |
| B5. Short authority and reporting rules | **LAYER 4.** The agent interprets unformalized user intent and reports limits. Mechanical intake and cancellation do not depend on those rules. Stronger checks cannot resolve every natural-language ambiguity. |
| B6. Task-specific method and source-bound review playbooks | **LAYER 5.** Select tests and experimental methods, without supplying the runtime's state machine or configuration. |

### How layers 3-5 produce layers 1-2 across repos

A versioned runtime projection writes the same repo-view structure and integrity-check invocation from its task facts. Bootstrap installs the local checker and supported CI adapter. The runtime verifies the emitted version/hash before relying on the view. Agents cannot silently maintain divergent runtime and Markdown task states.

Existing test commands and new task-specific regression artifacts remain repo-owned. The completion hook requires a pinned result reference, but cannot decide semantic equivalence by itself. A playbook or fresh reviewer supplies that judgment. The renderer and installer deterministically produce their mechanical output. No claim is made that an LLM deterministically invents the right test.

The design needs explicit backend capability checks. A shared CLI spelling does not establish Pi/prime equivalence. Unknown safe compaction, checkpoint identity, or child adoption means that operation remains unsupported and visibly held, not simulated by copying a transcript.

### Lifecycle, constraints, and failure handling

Runtime intake creates the obligation. Disposition and application are separate from verified completion. Changed source instructions retire dependent plans/check evidence. The service renders all open asks and applicable stops after compaction. Results are keyed to the original operation rather than only the old parent session.

B can support a qualified Z11 fork path. Park affected sessions, retain each complete last-good checkpoint and post-checkpoint input, and wait for human restoration. Before activating a fork, reconcile submitted jobs, merge later cancellations and current instructions, and establish the single designated mutation owner. Adopt child watches only through a verified backend capability. Do not respawn an uncertain job to make the status look complete.

Streaming is only an activity observation. Require demonstrated ownership and readable evidence before retiring the old session. Prefer archive to deletion. If the old process still has unrestricted shell access, a generation number in a record does not fence it. Confirm quiescence before activating another writer.

### B's coverage of the input-3 balance

| Class | Z candidate relation | B's handling and residual |
|---|---|---|
| F1 | Z1/Z4/Z6 partial | B1/B4 keep due continuation with its task and disposition. Runtime activity still does not prove useful progress. |
| F2 | NONE for lifetime | B1 prevents a plan update from deleting a sourced task; B2 exposes the open set. Meaning can still narrow during interpretation. |
| F3 | NONE generally | B1 distinguishes sourced prohibitions from agent dependencies; B3 rejects stale derived checks. The runtime cannot classify every prose gate correctly. |
| F4 | NONE | B6 performs the known-path comparison; B3 requires actual invocation/diff evidence. More runtime state does not choose simpler code. |
| F5 | NONE | Completion admission separates the original ask, oracle, target, and raw result. A wrong oracle remains possible. |
| F6 | Z3/Z8/Z9 partial | B4 integrates safe native boundaries and B2 rehydrates task facts. Backend hooks and fidelity still need real verification. |
| F7 | G5/Z11/Z4 partial | B4 handles typed parking and qualified adoption after ratification, retaining external-job identity. Unsupported adoption stays held. |
| F8 | Z5 partial | Every supported ingress records one correlated disposition; never-sent outer-bot work still needs caller persistence. |
| F9 | NONE | Runtime exposes owner/dependency facts; the coordinator chooses independent work. No DAG scheduler or inferred universal dependency engine. |
| F10 | NONE | B3 checks source/target freshness and known invariants before completion. Direct shell mutation is not fenced by a metadata revision. |
| F11 | NONE preventively | Generated publication checks and owned output references exclude known scratch. Runtime records do not solve disk-production policy or authorize deletion. |
| F12 | Z7 partial | Objective/task identities have one service owner and generated views. A mutable North Star still requires an explicit stop for finite CURRENT work. |

**Does not fix.** A bypassing client, unavailable backend APIs, wrong semantic interpretation, permanent denial, or arbitrary unmediated external effects. Its largest risk is that a small intake extension becomes a general engine with workflow-specific adapters and hidden state. Reject B if adding a new kind of work requires a new runtime phase or workflow configuration.

## Proposal C. Principles and small playbooks with executable repo checks

### Core idea and data shape

Keep the existing charter and a source-linked TODO checklist as the current task record. Each ask has a row, its original source reference, owner or wait, evidence, and disposition. The coordinator maintains that text. ACTIONS and timestamped history describe activity, not outstanding obligations. Do not add a task database or a new directory of per-ask state machines.

Use the minimal workflow shape through a few fixed playbooks for code, investigation, jobs, and publication. Keep runtime changes to narrow delivery, drive, compaction, and parking operations. This changes less than A or B, but relies more on the model maintaining the right current meaning.

### Mechanisms and layer placement

| Mechanism | Layer and reason |
|---|---|
| C1. Source-linked TODO and a short charter, with ACTIONS as history | **LAYER 1.** The current checklist is what a pickup reads. No stronger layer exists. An old open ask stays in TODO when its activity entry moves to history. |
| C2. Checklist/source integrity and existing behavior tests | **LAYER 2.** Detect missing intake identities, absent target/evidence references, and known scratch publication. Context shape alone cannot fail these errors. The checker cannot prove that a truthful-looking row means the right thing. |
| C3. Existing narrow runtime operations with corrected safety boundaries | **LAYER 3.** Intake, coalesced drive wakes, safe DCR, and typed parking need clocks and runtime observations. The playbook cannot execute after the agent has stopped. |
| C4. One short always-loaded interpretation rule | **LAYER 4.** Keep source and paraphrase separate, prefer the named known-good path, and revise constraints only from an applicable instruction. Encode concrete recurring invariants in LAYER 2 instead. Remaining domain judgment cannot be fully linted. |
| C5. Four small playbooks using the common task contract | **LAYER 5.** These select method, evidence, and review at real task boundaries. They never replace hard intake or mutation safety. |
| C6. Installer-owned templates and verification wiring | **LAYER 3.** Bootstrap mechanically emits C1/C2 artifacts and checks their presence. A soft instruction to remember installation is insufficient. |

### How layers 3-5 produce layers 1-2 across repos

Bootstrap emits the versioned charter/TODO templates, source-receipt links, and a portable structural checker. It connects the check to an existing verification entry through the same explicit CI-adapter approach as A. Repeated installation is content-based and preserves owned user sections. Unsupported CI remains a reported installation gap.

Each playbook must end with an actual repo change and executed verification where a recurring checkable defect was found. An optional skill's advice is not the deterministic producer. The installer and CI enforce the concrete files and calls. Selection of a meaningful domain regression remains model judgment and is reviewed as such.

This design intentionally has weaker semantic completeness than A or B. It does not claim that a lint on TODO prevents every narrowed ask. That is the price of avoiding a stronger work-record owner.

### Lifecycle, constraints, and failure handling

A row starts open and remains open across plans. Waiting records a reason and affected lane. A completion candidate links the original outcome to observed evidence. A reviewer or existing deterministic oracle accepts it. Cancellation and supersession retain their source, not a checked-as-done box. Findings are concatenated by ask when requested.

A task-scoped constraint ends with that task. A standing prohibition persists until changed. The coordinator reviews applicability during dump and task completion, while checks reject known stale references. This review is fallible and must not be advertised as mechanically complete.

Keep the MVP's useful same-session DCR shape as a trial, but load TODO and applicable charter rules before recent history. Use narrowed G5 for quota and human-restored environment parking. Reject automatic fork-and-wipe as the ordinary recovery method. Use a deliberate repair handoff only when the actual session is unusable, preserving source records and unresolved jobs. Keep native thread defaults during in-flight work, and hand off at real task boundaries rather than an invented compaction count.

### C's coverage of the input-3 balance

| Class | Z candidate relation | C's handling and residual |
|---|---|---|
| F1 | Z1/Z4/Z6 partial | C3 supplies a wake; C1 exposes next work and requested reports. The coordinator still judges progress and waiting. |
| F2 | NONE for lifetime | Source-linked TODO rows and C2 omission checks reduce lost asks. Faithful row content is not guaranteed. |
| F3 | NONE generally | C4/C5 require scope review, while C2 rejects shipped default caps and known stale references. Model-invented gates can survive. |
| F4 | NONE | A fixed reuse/minimal-change step compares the actual command and diff, then installs a concrete regression when expressible. Judgment remains central. |
| F5 | NONE | The publication playbook checks the original question and real result. Source-bound fresh review is targeted, not a proof of correctness. |
| F6 | Z3/Z8/Z9 partial | Current TODO survives action-log rotation; C3 performs safe DCR. A bad checklist or summary can still misdirect pickup. |
| F7 | G5/Z11/Z4 partial | C3 parks and alerts without environment self-remedy; human restoration releases reconciliation. Permanent failure remains blocked. |
| F8 | Z5 partial | Retain baseline correlated intake and show blocked/application status. Playbook review of broadened briefs remains soft. |
| F9 | NONE | Planning records real prerequisites and assigns disjoint owners. Parallelism depends on coordinator judgment, not a scheduler. |
| F10 | NONE | Charter scope review plus concrete repo tests where possible. Narrative-only constraints remain vulnerable. |
| F11 | NONE preventively | Installer-owned ignore/publication checks and explicit output owners reduce known litter. No automatic cleanup or general disk-growth cure. |
| F12 | Z7 partial | GOAL, CURRENT, and task rows stay distinct. A never-completed North Star is not permission for endless task execution. |

**Does not fix.** Reliable semantic reconciliation after coordinator error, universal instruction following, unknown native adoption, or a wrong checklist and matching test. Its largest risk is self-grading across both TODO and evidence. Choose C only if its lower machinery is worth accepting that weaker guarantee.

## Candidate-remedy verdicts for the track 1 review

Each row is one Z verdict with its reason. These are proposal choices, not an instruction to stop or silently rewrite the MVP. A is the recommendation.

| Remedy | A | B | C | One-line verdict and reason |
|---|---|---|---|---|
| Z1 | Adopt | Adopt | Adopt | Drive unfinished authorized work in LAYER 3, but do not equate another turn with progress or release a hold. |
| Z2 | Adopt | Adopt | Adopt | Supply ask lifecycle, source-bound acceptance, and scoped constraint lifetimes in each proposal. A deferral is not itself coverage. |
| Z3 | Modify | Modify | Modify | Retain 150k as an initial coordinator maintenance trial, with coalescing and safe completed tool boundaries. It is neither an exact ceiling nor a proved fidelity optimum. |
| Z4 | Adopt | Adopt | Adopt | Keep quiet ZF-only Slack DM as `<stream-id>:: <message>`, with off-host observation and episode deduplication. Delivery is not proof ZF read it. |
| Z5 | Adopt | Adopt | Adopt | Reserve applied acknowledgement for observed application, while separately reporting receipt, consumption, blocking, and rejection. None means product done. |
| Z6 | Reject blanket form | Modify | Modify | Reject unconditional safety. A wakes from the source-backed open set; B/C can reinject the current goal only through eligibility-aware admission. Skill text cannot grant authority. |
| Z7 | Adopt | Adopt | Adopt | Keep standing and immediate objectives distinct. Finite asks still terminate, and completing CURRENT can stop driving without completing the North Star. |
| Z8 | Modify | Modify | Modify | Keep the fixed read-state template and same-session DCR, but make its steps retryable and observable. Calling it one action does not make it atomic. |
| Z9 | Modify | Modify | Modify | Keep selective chronological history and useful G17 names. ACTIONS is not the full open set. Thirty free-length entries are a display count, not a memory or completeness guarantee. |
| Z10 | Adopt | Adopt | Adopt | Mechanical failure and artifact health are useful review lenses, not an exhaustive causal explanation or another engine. |
| Z11 | Modify, no default fork | Modify, qualified fork | Reject automatic fork/wipe | Keep parking, human repair, quiet alerts, and no failure-induced environment rules. Reconcile later input, effects, and child ownership. All three reject streaming alone as deletion proof. |

Narrowed G5's same-provider usage-limit wait/retry remains common. Other environment restoration is human-owned. No design inspects or modifies credentials, switches providers, retries an uncertain job, or revives cancelled work. Last-good markers can help recovery, but full disk can prevent their local write. An off-host episode or missing-heartbeat observation must still work. Pi and prime checkpoint identity, safe fork, and adoption are engineering facts to verify, not assumptions or questions ZF must guess.

G17's 30-entry action-history count is explicitly human-selected, not an invented resource budget. All proposals may retain it for recent activity. None treats it as proof that an older unresolved ask, standing constraint, or required evidence is dispensable. Header-based STATE migration must preserve those meanings before retiring STATE. The original bytes remain recoverable during verification. This report does not execute a migration or delete anything.

## Coverage of the retained problem statements

`Covered` means the proposal names a direct mechanism for that bounded problem. It does not mean implemented, guaranteed, or empirically successful. `Partly` means semantic judgment, unavailable facts, or an explicit residual remains. `Not` means outside this design or not established by this research. Do not sum these labels into an expected prevented-incident percentage.

| Problem | A | B | C |
|---|---|---|---|
| P01 | Covered | Covered | Partly |
| P02 | Partly | Partly | Partly |
| P03 | Partly | Partly | Partly |
| P04 | Covered | Covered | Partly |
| P05 | Partly | Partly | Partly |
| P06 | Partly | Partly | Partly |
| P07 | Partly | Partly | Partly |
| P08 | Partly | Partly | Partly |
| P09 | Partly | Partly | Partly |
| P10 | Partly | Partly | Partly |
| P11 | Covered | Covered | Partly |
| P12 | Partly | Partly | Partly |
| P13 | Covered | Covered | Covered |
| P14 | Covered | Covered | Partly |
| P15 | Covered | Covered | Covered |
| P16 | Partly | Partly | Partly |
| P17 | Partly | Partly | Partly |
| P18 | Partly | Partly | Partly |
| P19 | Covered | Covered | Covered |
| P20 | Covered | Covered | Partly |
| P21 | Partly | Partly | Partly |
| P22 | Partly | Partly | Partly |
| P23 | Covered | Covered | Covered |
| P24 | Partly | Partly | Partly |
| P25 | Partly | Partly | Partly |
| P26 | Covered | Covered | Partly |
| P27 | Partly | Partly | Partly |
| P28 | Covered | Covered | Partly |
| P29 | Partly | Partly | Partly |
| P30 | Partly | Partly | Partly |
| P31 | Partly | Partly | Partly |
| P32 | Covered | Covered | Covered |
| P33 | Partly | Partly | Partly |
| P34 | Not | Not | Not |
| P35 | Partly | Partly | Partly |
| P36 | Partly | Partly | Partly |
| P37 | Not | Not | Not |
| P38 | Not | Not | Not |
| P39 | Covered | Covered | Covered |
| P40 | Covered | Covered | Covered |

P19, P23, P39, and P40 use the narrow observation-isolation, evidence-resolver, dispatch-ratification, and session-bound-handover corrections identified by track 1. Their common placement is LAYER 3 for live admission/resolution and LAYER 1 for owned evidence and session-specific handover identity, with LAYER 2 regression checks. A stronger static layer cannot observe the live session boundary. They are shared prerequisites, not a reason to credit one proposal over another. P37 stays with the remote-wrapper owner. P38 stays with track 2. P34 requires new experiments, not a design claim.

## Checks required before selecting a design for implementation

These are proposed falsification cases, not tests run in this track. They apply the same source-backed cases to all three alternatives. No live session or stream is needed to approve this document.

| Case | Required observable result |
|---|---|
| An open ask followed by more than 30 unrelated completed entries | Pickup still enumerates that ask and applicable standing constraints. Recency does not cancel them. |
| Python migration assigned to an unapproved future plan | The original implementation ask remains open. Planning is not completion. |
| Smallest-working request with a smallest-failing result | The result cannot close the original ask. Ambiguous original wording stays explicitly ambiguous. |
| Wrong-sign checker against protected source | Matching green output does not authorize the opposite source behavior. Preserve the actual source uncertainty from row 69. |
| Named native runner versus a successful bespoke runner | Report the actual invocation. The substitute does not silently satisfy the named-path request. |
| Revoked cap plus surviving research freeze | Retire the cap without resuming prohibited research. Do not infer that all old gates disappear. |
| Idle driven task, human gate, healthy worker wait, and parked outage | Advance only eligible work. Keep real waits and requested reporting visible. |
| DCR with an active tool batch, new input, summary failure, and restart | No aborted active tool, lost message, doubled resume, or false compaction-success claim. |
| Job submitted before an acknowledgement failure | Query its actual identity. Do not resubmit merely because conversation rewound. |
| Fork before a later stop or ratification condition | Preserve the newer applicable input and require actual child/owner adoption. Streaming alone cannot retire evidence. |
| Archive relocation and current-session handover | Resolve the same exact evidence bytes and reject a predecessor's handover as proof for its successor. |
| Scratch binary alongside a small report | Only the intended report enters automatic publication. No blanket staging of worker output. |

A meaningful comparison must inspect the resulting actions, artifacts, and actual provider context, not only summaries or token counts. Compare source-bound completion review with self-review and review of the shared plan. Include legitimate alternate implementations and false rejection, not just seeded violations. No saved evidence establishes the optimum 150k trigger, the benefit of a 30-entry view, or recurring review's net value.

## Verification, attention, and decisions

throughput checkpoint: n/a, read-only investigation.

The first pass completed the P01-P40 inventory and light scout. The resumed pass read the new human messages and decisions, triaged every X seed item locally, consumed both substantive interrogation reports, and only then developed the three proposals. The source checkout remained at the inspected baseline. No code, credential, PR, or GitHub write was performed. Only this session's own delegated children were launched or controlled. No pre-existing non-child session or stream was operated.

Only `30-research-designs.md` and `30a-external-corpus.md` were authored by this parent. Other tracks' shared docs were left alone. Local validation passed for 40 unique problem statements and 40 coverage rows, all 12 F classes in each of three proposals, the seven NONE rows, 11 Z verdicts, five causes, all 64 X dispositions, layer labels, local links, and whitespace. The source checkout was clean and the authorized artifact paths had no staged changes. These checks establish document structure, not remedy effectiveness.

The final Cat deferral reread retained the same nine topics. Its SHA-256 at the final input check was `be12a24f5480a2062d8210dfef3fefbd5064ac2d202dddded05820d8fb1791d7`. The decision file hash was `98e227e7c3e1b10e9e703108e2a9fcb08db3d60d93da4fe778ae2a47a615371a`. Shared inputs can change after this snapshot.

Attention. The internet corpus remains narrower than requested originally. X originals, candidate E06-E10 comments, HN, Reddit, and blogs were not newly verified. Both adversarial readers used the same required model. No runtime fork/adoption proof, behavior replay, or comparison experiment was performed. The proposal is complete under Z12 using the five saved inputs, not an exhaustive empirical validation.

| Decision | Call and reason |
|---|---|
| T3.1 | Keep one parent writer for the two authorized artifact paths. Separate Before Serializing Shared State prevents shared-doc collisions. |
| T3.2 | Use only openai-codex/gpt-6.1-sol. Same-model corroboration is not model diversity. |
| T3.3 | Preserve the initial quota stop as history. Resume from saved evidence under Z12 without retrying GitHub search or probing its quota. |
| T3.4 | Use 00b's newly supplied full messages over older paraphrases. Do not reconstruct missing or explicitly paraphrased text. |
| T3.5 | Treat Z1-Z11 and G17 as candidates here, while leaving the MVP independent under G18. A research verdict is not an operational stop order. |
| T3.6 | Do not count workflow launch receipts as completed reviews. The initial orchestration started dependent readers prematurely. This was corrected by consuming actual reports. The fresh Z12 fanout had no dependent launch stages. |
| T3.7 | Exclude promotional, unsupported numerical, and insufficiently identified X episodes. Keep source records and incident counts distinct under Explain the Number. |
| T3.8 | Choose five causal hypotheses before design. Fix Root Causes separates current obligations, oracle meaning, continuation, ownership, and memory maintenance instead of treating every stall as context loss. |
| T3.9 | Sketch three different owners of task meaning under Exhaust the Design Space. Do not rename the same engine three times. |
| T3.10 | Prefer A. Laziness Protocol and layer affinity favor owned repo records and existing checks over central workflow machinery. The choice remains a judgment pending comparative replay. |
| T3.11 | Keep required task facts small under Model the Domain. Do not import R's combined control record, transaction platform, or per-workflow DSL. |
| T3.12 | Reject streaming alone as deletion proof under Prove It Works and Make Operations Idempotent. The concern is missing evidence, later input, and external effects, not a claim that ZF lacks deletion authority. |
| T3.13 | Put repeatable invariants in installed checks under Encode Lessons in Structure. Keep unformalized method choice in rules and playbooks, with its limitations stated. |
| T3.14 | Keep progress and decisions inside authorized artifacts rather than create a new TODO, PLAN, or TSV in the shared tree. No commit or push is authorized for this track. |

## Final pros and cons

| Choice | Pros | Cons and uncovered failure modes | Framework penalty | Recommendation and single biggest risk |
|---|---|---|---|---|
| A. Repo-owned work and evidence | Strongest layer affinity. Survives backend changes. Humans can inspect the same open set and evidence as the agent. Finite work is distinct from recent history. | Adds owned work records and a small generator/checker. Does not prove semantic fidelity, recover missing history, or supply unknown native adoption. | Low to medium. Reject a workflow DSL, per-workflow configuration, and compulsory new checks for trivial asks. | **Preferred.** The biggest risk is a wrong acceptance criterion that becomes a cleanly recorded wrong oracle. |
| B. Runtime-owned obligations and hooks | Shared clients can agree on intake, cancellation, current ownership, and observable lifecycle operations. Generated repo views reduce divergent summaries. | Highest integration and recovery burden. Backend-specific capabilities and direct-client bypasses matter. It still cannot infer domain truth from status. | Highest. Reject it if each new work type requires runtime phases or custom workflow adapters. | Choose only if centralized multi-client lifecycle ownership is the priority. The biggest risk is a growing service becoming the general engine ZF rejected. |
| C. Principles and small playbooks | Lowest new machinery. Reuses ordinary Markdown, existing tests, and a single process entry. Easy to adapt and inspect. | Weakest semantic reconciliation. More dependence on the coordinator maintaining TODO, applying scope, and challenging its own checker. | Lowest code burden, but procedural bloat is a real penalty. Keep the playbook set small and remove redundant ceremonies. | A useful low-change alternative, not an equivalent guarantee. The biggest risk is self-grading across both the checklist and the proof. |

## Blocking decisions for ZF

No question here blocks track 1's MVP or completion of this report. These are only choices that change the selected follow-up design. Recommended defaults let Grok Bot proceed within the program's delegated authority.

1. **Where should task meaning be authoritative?** Repo-owned records in A, runtime-owned facts in B, or coordinator-maintained Markdown in C. Recommended default is A. This determines portability, runtime coupling, and the strength of reconciliation. It cannot be settled by pretending all three stores are equivalent.
2. **Should recovery ever automatically delete the failed source session?** Recommended default is no. Archive it after verified ownership transfer and preserve needed evidence. If automatic deletion is required, its preservation and adoption conditions must replace streaming alone before that branch is selected. This changes retention and failure-recovery semantics, not an implementation detail.

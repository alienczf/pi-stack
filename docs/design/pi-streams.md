# Pi-streams artifact and coordinator contract

## Status and scope

Pi-stack owns the shared engine, CLI, templates, stream skills, overlay, and tick unit. Each stream owns its private repository and task artifacts. Product repositories remain separate worktrees. No stream data belongs in the public harness repository.

This document describes the canonical STATE artifact contract. The original 2026-10-06 design and its cache observations are historical background, not current rotation, budget, or authority policy. The implementation stack is still partial. Do not deploy the partial stack or silently convert an existing stream.

The delivered artifact units provide durable snapshots, scoped automatic Git commits, STATE parsing, objective updates, Log/ruling operations, and every-tick Log rotation. The generated contract now uses schema 1. Full-session-ID handovers and the runtime safety units remain separate work. The harness-program catalog and progress artifact record the authorized sequence and actual verification evidence.

## Artifact tiers

Every turn reads only the role's AGENTS.md and stream STATE.md. A worker follows its brief and its working-tree AGENTS.md, not the coordinator role. The stream template and brief replace TODO.md/PLAN.md planning with Goals plus Log. Non-stream overlay behavior is unchanged.

| Tier | Name | Purpose |
|---|---|---|
| Every turn | AGENTS.md | Role and operating instructions. |
| Every turn | STATE.md | Current Goals, active Rules, and recent Log. |
| On demand | history/ | One exact cold entry per file. |
| On demand | context/ and context/README.md | Reference material and its index, not a diary or required turn read. |
| On demand | checks/ | Task acceptance checks and small source-bound reports. |
| On demand | handover/ | Worker exit evidence at the path in its brief. Session-bound naming is the next S1 unit. |
| Engine-only | Index homes, projects configuration, streams.tsv, and ALERTS | Registration, discovery, and off-host notification input. |
| Engine-only | threads.tsv, subscriptions.tsv, stream.toml | Runtime designation, watches, identity, and schema. |
| Engine-only | log/events.jsonl, log/tick-state.json, locks, and failures/ | Engine observations, durable operations, writer exclusion, and recovery markers. |

Agents use CLI views instead of reading raw engine files. Kickoff can open the context README on demand for the seeded repo references. Canonical `pi-streams status <id> --json` adds the stream path and a threadSessions view with full session ID, role, worktree, and lifecycle status. Existing counts and cost observations remain reports, not budgets or task acceptance.

The names STREAM.md, DECISIONS.md, GOAL.md, and ACTIONS.md are retired from new seeds. There is no separate CURRENT section. Invented alert ledgers, decision tables, and ad-hoc output directories are not imported, inventoried, or assigned ownership by this work.

## STATE shape

A new stream starts explicitly unratified:

```markdown
## Goals
ratified: no

### North Star
<one mutable human-authorized outcome>

### Current objective

### Charter
<target, acceptance, E2E path, writes, end state, autonomy, and no-go terms>

## Rules

## Log
```

The actual template expands Charter's labels for the interview. North Star remains one goal and has no completion flag. A current objective can finish, be replaced, or end a drive run without completing North Star.

The first Goals line holds ratification authority. The coordinator drafts Goals while the marker remains unratified. Only explicit human confirmation changes that marker. After ratification, North Star and Charter change only with human authorization. The narrow objective operation cannot modify authority or other sections. Marker syntax alone is not authenticated ratification or a dispatch safety proof.

Goals and Rules are rewritten in place. Rules contains only human rulings still in force. A new ruling also gets a Log entry. A superseded ruling leaves Rules only after the engine preserves its exact old text in a timestamped rule-retired history file. The caller supplies the exact source span; ambiguous authority is not classified automatically.

The parser requires Goals, Rules, and Log in order. Extra level-two sections are tolerated only between Rules and Log and remain opaque. No Asks feature is implemented. Fences and duplicate headings are validated. Accepted Log metadata disambiguates literal headings and example delimiters in free bodies.

## Implemented artifact commands

Commands operate on a registered stream root and use the existing stream lock. Body input is an exact UTF-8 file or stdin. Stable request IDs must survive retries.

```bash
pi-streams state append <stream> --subject SUBJECT --body-file - --request-id ID
pi-streams state objective <stream> --body-file -
pi-streams state ruling <stream> --subject SUBJECT --body-file - --notice-id NOTICE
```

Append records completed work, failures, or a received ZF steer. Its optional `--at` supplies the original arrival time with an ISO timezone. A repeated request with unchanged intent returns the original occurrence. Identical text with different request IDs remains distinct. Artifact recording is not steer consumption/application or product completion.

Objective replacement preserves every byte outside the current-objective body, including Unicode and line endings. It revalidates the exact structural boundary. A metadata-aware reader is required when Log bodies contain literal section headings.

Ruling input requires human notice provenance. Retirement uses `--supersedes-file PATH` for the exact old Rules text. Notice IDs are not authentication credentials. Receiver-side authenticated intake and applied-steer receipt integration are later units. A failure never authorizes new rules, skills, memory, or environment repair.

Only Log is append-only and capped at 30 entries. Bodies have no length budget. Agents never prune or rotate. The tick archives the oldest overflow on every canonical pass before event, project, drive, or outage gates. Goals, Rules, and intervening sections are not rotated.

History names retain UTC time, occurrence identity, readable subject, and hash. Rule retirements retain the rule-retired prefix. Filename slugs are sanitized and shortened only for the filesystem component limit; full subjects and bodies remain intact. Archives preserve exact bytes, including CRLF and non-ASCII text.

Accepted occurrence spans are relative to Log, so objective/rule edits do not invalidate them. The existing tick-state file holds those spans, hashes, request receipts, and a pending before/after publication plan. The engine verifies and syncs history before trimming, then durably acknowledges STATE/metadata publication. Interrupted operations reconcile without duplicate archives. Unregistered content, malformed metadata, collisions, or changed bytes refuse without dropping pieces.

## Creation, upgrade, and Git

`pi-streams init` registers a private index and discovers project repos/worktrees read-only. `pi-streams new <id>` creates `<project-root>/streams/<id>` as its own Git repository, copies the canonical template, starts a coordinator, and sends the kickoff skill. The parent streams directory and index are not Git repositories.

A fresh stream records `state_schema = 1`. Legacy streams without that marker remain legacy. Ordinary create retries and upgrade refuse a template/schema mismatch. Explicit, source-backed migration is a separate S2a unit and is not yet a delivered command. Do not edit a marker to pretend a migration happened.

Upgrade preserves owned STATE, history, failures, context, and thread records. It does not recreate retired ledgers or replace owned documents. New templates alone do not authorize rewriting existing stream authority or worker worktrees.

Automatic commits use exact known/approved paths, not whole-worktree capture. Unrelated staged content survives, overlapping staged edits refuse, and binary/data candidates are not silently committed. New report/check paths need explicit approval. Git is for code, documentation, checks, and small reports, not datasets. No file-size budget or automatic data cleanup is introduced.

Pending engine history paths are committed explicitly. Their receipt clears only after a raw Git blob hash matches the durable original bytes. Git ref and index publication are not one filesystem-wide transaction; uncertain publication reports the exact commit rather than blindly replaying it.

## Kickoff and work

The kickoff scouts referenced repos/worktrees, PRs, sessions, and named artifact metadata read-only. It asks only for human decisions. Existing sessions require explicit adoption; same-directory presence is not authority to take over work.

Interview answers fill Goals' North Star and Charter. The immediate plan uses Current objective and Log, not another planning file. Acceptance follows the actual ask and agreed oracle. Reuse existing checks when sufficient. There is no demand for a new script or proof campaign for every small task.

Writes and autonomy are explicit grants. Record a resource or spend limit only when the incoming task names it. There is no mandatory numeric-cap, dry-run, or cost-budget workflow. Normal tool timeouts and the explicitly requested Log count/maintenance thresholds are not resource budgets.

Ratification follows the human's explicit confirmation, with the dated confirming words in Goals. Historical rulings are presented for confirmation before becoming active Rules. A recommendation is not permission to act outside the grant, and silence is never approval.

The coordinator never writes product code. Workers stay in their assigned worktrees, apart from the rendered handover and authorized engine Log append. Generated briefs disable TODO/PLAN planning and point at current STATE. Close reads actual handover and requested acceptance evidence. It does not force a busy archive or turn a failure into autonomous policy/skill repair.

## Runtime work still gated

The artifact contract does not claim the remaining runtime fixes are complete:

- S1 still needs full-session-ID handovers.
- S2 owns exact coordinator selection, dispatch/ratification enforcement, receiver stop generations, application receipts, archived evidence, and unsafe-rotation refusal.
- S2a owns explicit lossless stream-root migration, with preserved original bytes/provenance and no worker-worktree writes.
- S3 owns same-session tick-observed 150k DCR and the fixed engine resume, including the receiving-side compaction/input boundary.
- S4 owns cause-independent driven-stall goal reinjection through the actual argument-preserving skill adapter.
- S5 owns saved-step usage-reset retry and the quiet off-host alert route.
- S6 owns human-ratified failure recovery, exact-prefix fork/DCR, and narrowly scoped original retirement.

Do not enable production driving or DCR from this partial stack. Existing legacy runtime compatibility is not endorsement of its superseded size/age replacement policy. Canonical replacement pickup reads AGENTS/STATE and uses the shared current-goal resolver; replacement safety remains S2 work.

Disposable runtime verification needs a separate port, all private XDG/index paths, private daemon socket/URL, data directory, and agent/session directories. Read credentials in place only through an authorized read-only path. Never copy, refresh, persist, or replace them for isolation. No production service or existing session is a verification destination.

## Historical background

The original request was Cursor Projects on pi-web threads, with one shared harness repository and private stream state. The original design also removed Jig in favor of pstack's existing verification/learning tools. Those ownership choices remain.

The 2026-10-06 analysis in [inner-loop-steering.md](inner-loop-steering.md) is background evidence. The original design recorded 3,031 calls across 12 campaign sessions, a 77% cache-hit rate, and $1,043 in notional list-price usage. It attributed 91% of the notional spend to rereading context. These are historical recorded observations, not a fresh measurement, current model mandate, spend allowance, or proof of an optimal rotation threshold.

[pi-streams-handover.md](pi-streams-handover.md) is the dated historical pickup note. Its old file layout, not-yet-built status, model rule, and fresh-session policy are not current instructions.

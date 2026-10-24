# Stream artifact contract and baseline observations

## Current contract under Z15

This is the authorized implementation target, not the deployed layout. Z15 in `03-decisions.md` supersedes G17, G21, and G22. Z13 excludes invented artifacts and bulk-output ownership work. GO and G25 authorize the isolated local implementation described in `10-pi-streams-fix-catalog.md`. Actual implementation and verification progress belongs in `12-track-1-progress.md`.

Every turn reads only AGENTS.md and STATE.md. No two stream files share a current-state concept.

| Tier | Name | Sole concept and access |
|---|---|---|
| Every turn | `AGENTS.md` | Role and operating instructions. Read with STATE, not an additional planning ledger. |
| Every turn | `STATE.md` | Current Goals, active Rules, and recent Log in that order. The only always-loaded stream state. |
| On demand | `history/<UTC ts>-<slug>.md` | One cold entry per file. Rotated Log entries, retired rules, historical decisions, and migration provenance. |
| On demand | `context/` and `context/README.md` | Reference material and its index. The README is not a diary or a required turn read. |
| On demand | `checks/` | Acceptance checks and their small source-bound reports. |
| On demand | `handover/<role>/<full-session-id>.md` | One session's exit evidence. Never a role-reusable current-state file. |
| Engine-only | Index `streams.tsv`, `projects/<name>.toml`, and `homes` | Stream/project registration and discovery. Never read by agents. |
| Engine-only | `threads.tsv` | Session designation and runtime lifecycle. Never an agent-maintained task plan. |
| Engine-only | `subscriptions.tsv` | Tick watch definitions. Agent interaction uses the existing command boundary. |
| Engine-only | `stream.toml` | Stream identity, schema, and engine metadata. |
| Engine-only | `log/events.jsonl` and `log/tick-state.json` | Engine events and durable delivery/maintenance/recovery progress. This grants no ownership of other `log/` contents. |
| Engine-only | Index `ALERTS` | Typed off-host notification intake, not stream-local ALERTS.md. |
| Engine-only | Index and stream locks | Short writer exclusion. No network/Git wait under an all-stream lock. |
| Engine-only | Index `tick-health.json` and `.pi-streams.tick.lock` | One actual tick pass's per-stream completion/results and a kernel tick-only exclusion lease. No agent-read task ledger, new timer, PID-based adoption or new monitoring service. |
| Engine-only | `failures/<full-session-id>.lastgood` | Parking marker containing only that session's last completely persisted good-turn entry ID. |

### STATE shape and authority

```markdown
## Goals
ratified: <authority reference, empty until ratified>
### North Star
<one mutable, human-authorized goal>
### Current objective
<coordinator-editable immediate objective, possibly empty>
### Charter
<remaining ratified scope, acceptance, WRITES, and NO-GO terms>
## Rules
<only human rulings still in force>
## Log
### <UTC timestamp> <subject>
<free body>
```

Goals and Rules are rewritten in place. The coordinator may replace only Current objective through the narrow engine operation. North Star, charter authority, and Rules change only with human authorization. The first line of Goals carries the actual `ratified:` marker. Historical prose is not ratification. Worker spawn/adopt validates that authority before effects.

One header-aware parser serves section mutation and goal resolution. It recognizes headers outside code fences and rejects duplicate or ambiguous required sections. The resolver selects the nonempty Current objective, otherwise North Star. There is no goal-completion flag. An extra level-two section between Rules and Log is tolerated and preserved byte-for-byte. Future Asks is not implemented.

Only Log is append-only and capped at 30 entries. The canonical engine append operation writes `### <timestamp> <subject>` plus a free body. Engine metadata retains accepted occurrence boundaries. The agent never prunes or rotates. Every tick rotates the oldest overflow into one exact-byte `history/<UTC ts>-<slug>.md` per entry, before drive/event/outage gates. Stable occurrence/hash suffixes prevent collisions. Free body length means this is not a token bound or a resource budget.

A new human ruling updates Rules and appends Log. A superseded ruling leaves Rules only after its exact text is retained in `history/<UTC ts>-rule-retired-<slug>.md`. New ZF steers enter Log at arrival and reach history through normal rotation. No tag field is added. Goals, Rules, and intervening sections are not rotated with Log.

### Retired and excluded artifacts

GOAL.md, STREAM.md, DECISIONS.md, and ACTIONS.md are retired. There is no separate CURRENT section. Within a stream, Goals plus Log replace global-overlay TODO.md/PLAN.md planning. The stream template/brief disables those demands. Non-stream overlay behavior is unchanged.

Z13 excludes invented ALERTS.md, decisions.tsv, ad-hoc log/, and analysis directories. Fix 12 stops referencing them. No import, migration, inventory, ownership assignment, or cleanup is included. Existing TODO/PLAN and context contents are not migration targets either. The engine owns only its named log/events and tick-state records, not every file under log/. Removing fix 17 leaves 17 stable fixes, numbered 1-16 and 18, split into 11 mechanical and 6 artifact fixes.

### Explicit S2a migration

Migration is a lossless, idempotent, explicit per-stream operation. It uses a persisted source-backed byte-span map and refuses ambiguous active authority rather than classifying arbitrary prose automatically.

- STREAM.md maps into Goals, active Rules, and history. The ratified marker and still-binding charter terms survive.
- DECISIONS.md maps still-in-force rulings into Rules and the rest into history.
- Old STATE.md moves into history before fresh three-section STATE is published.
- Original bytes, hashes, source paths, and available Git provenance remain stable. Historical section timestamps use source evidence or a labelled persisted-time fallback.
- failures/ is created and protected. Existing full-SID lastgood markers and recovery metadata remain byte-identical.
- One scoped commit covers only approved migration paths. Retry adds no duplicate seed, history, rule, or commit. Unrelated staged content survives.

Migration does not follow worktree pointers or out-of-root symlinks, write worker worktrees, prompt sessions, or perform any existing-session lifecycle action. TODO/PLAN and invented artifacts are not inputs. Unknown intermediate GOAL/ACTIONS schemas require an explicit source-backed plan or refusal. New templates and ordinary upgrade do not silently migrate or overwrite owned state.

## S3 source and isolated verification artifacts

Main `engine/dcr.py` owns fixed 150k same-SID maintenance facts in the existing engine-only tick-state record. It references the receiving operation, not another input queue. Native `sessionMaintenanceStore` retains exact accepted input identity/body/order/kind and attachment references. Native custom entries retain exact checkpoint/operation/event identity outside model context. These do not become agent-read task ledgers.

The private program evidence root `/home/alphalab/.cache/pi-stack-track1/native-s3` contains `artifact-manifest.json`, `live-isolation-proof.json`, public SDK wire/result observations, `s3-normal-pass-native-proof.json`, `s3-receiving-restart-native-proof.json`, rerunnable `verify-after-s3.py` and `after-S3-acceptance.json`. Source is main c41a01a and native 77c218b. The exact native tar SHA256 is 9b62e1d99cd69c119b96370ab7f7edaa8883c072728e5a54757eb9b037e2923c. This is disposable program evidence, not a new stream artifact or mandatory read.

Real passing SID 01a16b94-ad3c-7430-9251-fcf25ae265bc compacted at native entry 2291d0d9, used the latest changed goal and produced exact owned note bytes. The later receiving restart fixture on that SID intentionally retains two accepted queued inputs under uncertain maintenance ownership. Preserve their IDs/bodies/order and do not replay or clear them. The first noncompactable single-message fixture SID 01a16b7a-4c5a-7d72-a9ec-dcbb94ca0495 remains disabled with its exact native bytes. Its preliminary refusal is not credited as stack acceptance. Retained S2 services and all existing non-fixture sessions remain untouched.

## S4 isolated verification artifacts

The private program evidence root `/home/alphalab/.cache/pi-stack-track1/native-s4` contains exact artifact/config/PID/auth-readonly proofs, raw public SDK wire/result observations, actual question/goal-control and note evidence, `after-S4-native-proof.json`, rerunnable `verify-after-s4.py`, and `after-S4-acceptance.json`. Source is main 08b6598 and native 8ea0e07. Native tar SHA256 is 9d38ece66341d55e56d7001626384f7ca3a4a98ebb3d9ab63dd87d84ec18e0f0. These are program verification artifacts, never new mandatory stream reads.

Exact coordinator SID 01a16c1b-db4e-769e-9f50-0ac95381815d kept its real ask_user question while automatic control queued, then completed two real driven context-note steps without another human prompt and confirmed local/native off. The observation-only worker SID 01a16c20-2c70-756e-b341-96c2f89260e3 is a labelled private status-fault fixture with no task inference or product adoption claim. S2/S3 services and the two accepted uncertain S3 inputs remain unchanged. No installed/global/remote operation or real quota failure occurred.

## S5 failure policy source artifacts

Main 10c882a keeps typed failure episodes inside the existing engine-only tick-state record. Each episode retains exact failure/input native entry hashes, reset provenance, owned pause generation, uncertain-job references and one consumed reset-trial identity. Public status shows bounded policy facts. These are not a task ledger, general permission framework or mandatory agent read. Sanitized blocker/recovery envelopes use existing index ALERTS; only canonical failure/continuation observations enter STATE Log. No account/header/secret-bearing provider payload is copied into the episode.

The pure-source public CLI fixtures under `/home/alphalab/.cache/pi-stack-track1/s5-policy` label injected failures and notification receipts. `candidate-late-job-result-red.log` and `green-recovery-post-late-job.log` prove a submitted job reported after an auth-error result in the same tool batch survives parking with the original error entry/hash and no repeated submission. `full-post-late-job.log` passes 356 tests and `final-hashes-3.json` pins the reviewed source. This is not actual native/provider/Slack activity. Missing live notifier/ZF route proof keeps automatic recovery activation gated.

## Historical baseline observations

The following is the earlier map, not a new live measurement or the current policy. Grok Bot prepared it on 2026-10-23 at 09:58 SGT and read the 12 registered options-01 streams at 10:05 SGT. This amendment does not reread or change those streams or their registry.

Source pin is pi-stack `3acf0f01e6084a317b89cef3a86f4781e60877cf`. Source areas were `pi-streams/templates/stream/`, `pi-streams/templates/thread-brief.md`, `skills/stream*/SKILL.md`, `pi-streams/engine/{tick,threads,project,doctor}.py`, `overlay/{AGENTS,APPEND_SYSTEM}.md`, and `docs/design/pi-streams.md` sections 3-7. The observed registry was `~/.config/pi-streams/streams.tsv`. These paths are historical evidence, not implementation mutation targets.

### Baseline stream files

| File | Baseline role and readers | Recorded observation |
|---|---|---|
| AGENTS.md | Template coordinator role and five per-turn rules. Loaded by Pi. | About 0.7 KB. Four of twelve were hand-edited, up to 3.8 KB. |
| STREAM.md | Ratified GOAL/charter. Coordinator read every turn, worker at spawn, engine for ratification. | Accreted amendments. 654 was 66 KB, vola 12 KB. |
| STATE.md | Coordinator-rewritten plan, threads, waiting-on, next. Read every turn and after replacement. | Newest-first level-two history pile. Vola was 181 KB and 741 lines. 654 was 19 KB. |
| DECISIONS.md | Append-only ZF rulings, nominally on demand. | 654 was 202 KB, vola 178 KB, fill 172 KB. |
| context/ and README.md | Harvested reference material. AGENTS required the README every turn. | 654 README was 212 KB. Vola had 298 context files. |
| threads.tsv | Engine session/role/worktree/status rows. Tick and coordinator readers. | 654 was 8 KB. |
| subscriptions.tsv | Coordinator-defined tick watches. | Header only in all twelve. |
| checks/ | Acceptance scripts used by coordinators/workers. | Zero to 189 files, also used as scratch. |
| handover/<role>.md | Worker exit note, read at close/harvest. | Reused role variants such as `-r2-r1`. |
| stream.toml | Engine identity/revision/remote. | No reported issue. |
| log/events.jsonl | Gitignored engine tick events. AGENTS required recent lines every turn. | At most about 216 KB. |
| log/tick-state.json | Tick memory for seen/pending/outages and doctor freshness. | No reported issue. |
| .git/pi-streams.lock | Per-stream engine writer lock. | No reported issue. |

### Baseline global overlay and out-of-scope observations

| Name | Historical source or use | Recorded observation |
|---|---|---|
| TODO.md | Global overlay progress checklist, read when present at session start. Not a stream template. | 654 was 465 KB and 2,263 lines. Vola was 113 KB. |
| PLAN.md | Global overlay plan, read when present at session start. | 654 was 255 KB. Vola was 90 KB. |
| ALERTS.md | Invented stream-local alert/blocker log, not pi-stack source. | Present in eight of twelve. 654 was 294 KB. |
| decisions.tsv | Invented stream-local decision ledger, not pi-stack source. | Present in five of twelve. Vola was 123 KB. |
| Other log/ contents | Ad-hoc files, not the engine's named events/tick-state records. | 654 was 34 GB, with message dumps around 19 MB. |
| METRICS.md, streamlog/, analysis/, evidence/, delivery/ | Ad-hoc material, not a new pi-stack ownership contract. | 654 analysis/ was 47 GB. |

These observations do not authorize import, ownership work, or cleanup. The source repository's existing decisions.tsv is a separate file and stays untouched.

### Baseline index

| Name | Historical role | Recorded observation |
|---|---|---|
| homes | Index directories discovered by global tick. | One home. |
| projects/<name>.toml | Root, pi-web URL, models, caps, repos. | Three files and two backups. |
| streams.tsv | Stream ID/path/project rows. | Twelve streams. |
| ALERTS | Tick-produced outage/claim lines for Grok Bot. | Empty at observation time. |
| .pi-streams.lock | Index writer lock. | No reported issue. |
| Worktree .stream | Engine pointer to stream directory. | Also present in vola's stream directory. |

The old full-read sum for 654 was approximately 1 MB from TODO 465 KB, PLAN 255 KB, context README 212 KB, STREAM 66 KB, and STATE 19 KB. Dividing bytes by four was only a rough token estimate. No request-token measurement or proof of 250k input tokens exists. A separate historical frozen `c146285:STATE.md` was 10,195,068 bytes and 165,597 lines. That is not the map's later 19 KB STATE.

The old G17 ACTIONS/STREAM/CURRENT proposal is superseded. It is not the current artifact policy or implementation evidence. This run's amended contract requires actual section/parser, rotation, migration, read-contract, and disposable-runtime checks before completion.

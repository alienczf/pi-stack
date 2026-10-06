# Inner-loop steering: a neutral stream home for multi-repo, multi-team pi work

Status: draft for ZF review. Date: 2026-10-06 (SGT). Scope: research and design only. Nothing on hpc180-options-01 was modified, no pi session was prompted, no BigQuery table was read or written, and pi-stack install config is unchanged.

## Summary

- **Central question.** Where does a multi-day stream of work live when it spans several repos owned by different teams, and when several streams share one repo? **Answer: in a neutral stream home above all repos.** That is one directory per stream, `streams/<id>/`, in a dedicated repo that no code team owns. The stream's direction never lives in a code repo's worktree, and no repo or PR is the stream's owner or starting point (§1).
- **The model (§1.1).** A stream has three levels:
  - one original goal, pinned by ZF at a kickoff interview (end consumer, acceptance);
  - workstreams joined by versioned interface contracts (schema and data, storage and schedule, consumer interface), so they can run partly in parallel against stubs;
  - landings: the tickets, PRs, repos, worktrees and sessions where work lands. These are recorded in a ledger and never define the stream.
  
  Teams own their code and PR review. The stream owns the end-to-end goal and the interfaces. ZF rules when interfaces conflict.
- **Case study (§2).** The Oct 2–6 datapull/BQ campaign was really the first run of a "quant market-data pipeline" stream with three workstreams: core market-data processing, storage/schema/scheduling, and quant code consuming the output. Instead it started inside PR #654's worktree.
  - All 11 sessions ran there, and the direction lived in that worktree's untracked `.audit/`.
  - The storage workstream had no owner, and no interface between the workstreams was written down.
  - Four of the nine drift points sit on those unowned interfaces. The worst is a consumer-side session expanding the shared table from 140 to 432 fields and MERGEing 432,000 rows. The other five sit on the end-to-end goal and its acceptance.
- **ZF's interventions.** None of ZF's 20 messages changed the target output. With a ratified goal and mechanical checks, 28 of 32 steering tags (87.5%) and 10 of 14 substantive messages could have been issued without ZF. The steering layer itself (MMDev's hand-written goals and relays) authored four drift points.
- **Plumbing bug.** `pi-web-cli prompt` sends no `streamingBehavior`, so a message to a busy session waits until the run ends. 11 of 22 MMDev messages arrived more than 10 minutes late. "Park: ctx bloated" arrived after the 432,000-row write.
- **Design.**
  - The stream home holds `STREAM.md`, ZF's rulings, workstream charters, interface contracts with stubs and contract-test locations, the acceptance census, and landing and session ledgers.
  - Each touched worktree carries only an untracked `.stream` pointer.
  - `/goal` becomes a generated pointer to the home.
  - A host script, `steer-check`, runs every 15 minutes across all streams. A fresh Astra steward session per stream wakes only on a delta. The Grok Bot stays ZF's interface.
- **Is the polyrepo layout anti-agentic? (§7)** Neither Pocock nor poteto takes a position on monorepo versus polyrepo in anything I could reach.
  - What they do say is about fast checks, small interfaces, short agent docs, and fixing mistakes in the environment rather than in prompts.
  - On this host the problems are specific: unversioned data edges, alc-cefi-sim-runner with no `AGENTS.md` and no test CI, no home above the repos, and ownership that isn't written down.
  - Recommendation: keep repos split by team. Add a neutral workspace repo (manifest pinning compatible versions, side-by-side checkout, stream homes), versioned contracts with contract tests at the data edges, short per-repo agent docs, and fast per-repo checks plus one integration check.
  - A monorepo would not have prevented the interface failures, which happened in BigQuery.
- **Pilot.** Replay the campaign offline from a stream home built only from ZF's Oct 2 words. It passes if at least 10 of the 14 substantive interventions are matched or pre-empted, with zero ungated writes, zero stand-in "done" relays, and at most one false-positive steer per campaign-day.

### Evidence conventions

- Times are SGT (UTC+8). The host clock is UTC, and jsonl timestamps were converted.
- `SESS/` = `~/.pi/agent/sessions/--home-alphalab-Projects-alphalab-alc-qslite-.worktrees-v4-to-baseline-datapull--/`. Sessions are named by id prefix, for example `01a0fb7a`.
- `AUDIT/` = `/home/alphalab/Projects/alphalab/alc-qslite/.worktrees/v4-to-baseline-datapull/.audit/`.
- The three uploads ZF provided on 2026-10-06 are cited as **transcript** (ZF↔MMDev, pasted by ZF at 15:07), **eggbot review**, and **MMDev account**. For the account, its top-of-file corrections override its body. They are not committed here.
- Local evidence is read-only host state and has no URL. Web claims carry a URL. Quotes are verbatim from the cited page. Where a page was seen only through a mirror, captions or a search snippet, that is stated.
- "Inference" marks a conclusion of this doc, not of a cited author.

---

## 1. The central question: where a stream lives

### 1.1 What a stream is

| Level | What it is | Pinned by | Changes only when | Lives in the home at |
| --- | --- | --- | --- | --- |
| **Goal** | One end-to-end outcome for a named end consumer, with checkable acceptance and NO-GO rules | ZF, at the kickoff interview, by ratifying a displayed digest (§4.6) | ZF rules (new sha) | `STREAM.md` |
| **Workstreams** | A bounded body of work with one owning team, the interfaces it provides and consumes, and its own acceptance | Kickoff; the steward proposes, ZF approves the split | ZF approves | `workstreams/<ws>.md` |
| **Interfaces** | Versioned contracts between workstreams: schema and data, storage and schedule, consumer interface. Each has a stub that consumers can build against. | The steward drafts; both sides' owning teams acknowledge | A new version that both sides acknowledge; conflicts go to ZF | `interfaces/<if>/` |
| **Landings** | Tickets, PRs, repos, branches, worktrees, sessions | Recorded by the steering tools as work happens | Continuously | `ledger/` |

The stream is defined top-down. Adding a repo does not need a new kickoff, and dropping one does not change the goal. Work may depend on itself in a straight line over time (processing, then storage, then consumers), but orchestration starts at the goal, not inside the first producer's repo.

Interfaces between workstreams, rather than a single plan, are what let workstreams run in parallel. A consumer builds against a stub that conforms to an agreed interface version before the provider ships. Pocock's module vocabulary supports this shape:
- "The interface is the test surface."
- "One adapter means a hypothetical seam. Two adapters means a real one."
- A module is "Deliberately scale-agnostic: a function, class, package, or tier-spanning slice."
- Source: https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/codebase-design/SKILL.md.

Inference: a stub plus the real provider gives a data edge two adapters, which makes it a real seam. Pocock writes about code modules; applying this to data edges between teams is this doc's step, not his.

### 1.2 Who owns what

| Thing | Owner | In practice |
| --- | --- | --- |
| End-to-end goal, acceptance, NO-GO | the stream; ZF ratifies and rules | Only ZF changes them (`RULINGS.md`, new `STREAM.md` sha). |
| Interfaces (version, schema, semantics, stub, what each side promises) | the stream; each side's team acknowledges | A version is "agreed" only when both sides' owners have acknowledged it. A conflict becomes a gate to ZF. |
| Code, tests, CI, `AGENTS.md`, branch rules in a repo | that repo's team | The stream opens PRs; the team reviews and merges. Repo rules win on code matters. A rejected PR becomes a stream decision or gate, never an override. |
| Shared data resources (BigQuery datasets and tables) | the workstream that provides the storage interface | Writes only as the storage interface and `ledger/writes.tsv` allow. |
| Watching and steering sessions, relays to ZF | the stream's steward plus `steer-check` | Never edits code, never merges, never answers a human gate itself. |
| Interface conflicts, gates, scope changes | ZF | Recorded in `RULINGS.md`. |

### 1.3 What a stream home must do

1. **Repo-independent.** No code repo owns or starts the stream, and the stream can add or drop repos.
2. **Many-to-many.** One stream spans many repos, and many streams share one repo.
3. **Readable by everyone involved:** every pi session on the host, ZF, the Grok Bot, and reviewers from each team.
4. **History.** Every goal, interface and ruling change has a diff, an author and a reason.
5. **Churn isolation.** Tick-level state must not land in any team's history. This is `pil`'s argument, §1.10.
6. **No code and no secrets.**
7. **Durable.** It survives Grok Bot memory loss and session loss.
8. **Discoverable in one hop** from a worktree or a session.
9. **Usable by team tests.** Teams' contract tests can use interface contracts without their CI depending on the stream home at run time.

### 1.4 Candidate homes

| | Shape | Meets | Fails | Verdict |
| --- | --- | --- | --- | --- |
| S1 | `.audit/` in the first producer's worktree (what happened) | 6 | 1, 2, 3 (only that worktree's sessions), 4 (untracked), 7 (deleted with the worktree), 8 for other repos | Rejected. §2.2 shows the cost. |
| S2 | Committed in one code repo, for example `docs/streams/` in alc-qslite | 4, 7 | 1 (that team owns the stream), 2, 5 (stream churn in the team's history and review queue), 3 for other teams' reviewers | Rejected. It puts one team in charge of a cross-team goal. |
| S3 | `pil`-style state dir on the host, for example `~/pi-loop/<name>/` | 1, 2, 5, 8 | 3 (host only), 4 (live memory is uncommitted by design), 7 (one disk) | Use it for the ignored `live/` part only. |
| S4 | `streams/<name>/` in pi-stack | 1, 2, 4, 7, 8 | 3 and 5: pi-stack is a personal tooling and install repo (`alienczf/pi-stack`), so teams' reviewers have no reason to have access, and stream commits would interleave with install releases | Workable fallback; same layout as S5. pi-stack should hold the tooling instead (templates, `steer-check`, prompts). |
| S5 | **A dedicated neutral org repo** with `streams/<id>/` | 1–9, with an ignored `live/` for 5, a secret scan for 6, and sha-pinned vendored copies for 9 | Costs a new repo, access setup, and an owner (ZF) | **Recommended.** |
| S6 | Local-only git repo on the host, for example `~/Projects/alphalab/streams/` | 1, 2, 4, 5, 8 | 3 for teams, 7 (one disk) | Pilot stage of S5. Same layout, pushed later. |
| S7 | Grok Bot memory, or a Cursor Project's shared files | 1 | 3 (sessions can't read bot memory), 4. Project shared files have no documented format, size limit or sync timing, and Projects run "on its own computer in the cloud" (§3.8). | Mirror at most. |
| S8 | Issue tracker (tracking issue or board) | 1, 3 for humans | 4 (edits aren't diffable files), 8 (sessions need an API), 9 (nowhere to keep schemas and stubs) | Mirror for landings and humans, not the home. |

### 1.5 Recommendation

Use S5, staged through S6:

- **Pilot.** Create a local git repo at `~/Projects/alphalab/streams/`, side by side with the code repos, using the S5 layout. Nothing is pushed and nothing in a team repo changes.
- **After the pilot.** Push it to an org repo that ZF owns. The name, visibility and writers are open questions. The same repo can also hold the workspace manifest (§7.3).
- **pi-stack** carries the tooling, not stream content: templates, `steer-check`, `steer-send`, the steward prompt, and the kickoff skill.

### 1.6 Layout of one stream home

```text
streams/                              neutral repo (pilot: ~/Projects/alphalab/streams, local git)
  README.md                           one line per stream: id, status, ZF owner, steward wake log
  <stream-id>/
    STREAM.md                         ratified goal: end consumer, output, acceptance, NO-GO, roles, ctx, autonomy
    STANDING.md                       numbered standing orders, one constraint per line
    RULINGS.md                        ZF only, append-only: binding rulings, including interface conflicts
    decisions.md                      steward and workstream decisions with why and rejected alternatives
    gates.md                          open questions for ZF: options, default, deadline, blocked workstreams
    workstreams/<ws>.md               charter: objective, owning team, provides/consumes interface@version, acceptance
    interfaces/<if>/
      CONTRACT.md                     version, status, provider, consumers, acks, schema, semantics, invariants, changes
      schema.json                     machine-readable form of the contract
      stub/                           generator or spec for a stub fixture (synthetic, no real data, no secrets)
      tests.tsv                       each side's contract test: repo, path, vendored contract sha, last result
    acceptance/
      census.tsv                      one row per required end output (292 in the case study)
      census.d/<ws>.tsv               each workstream's own rows, merged at read time
      sources.tsv                     every typed source the goal needs, with date coverage
      check.py                        the end-to-end predicate (A1..A5) as a script
    ledger/
      landings.tsv                    ticket / PR / repo / branch / worktree -> workstream, interface versions, state
      sessions.tsv                    session -> host, workstream, role, model, repo, worktree, branch, base sha,
                                      goal id, STREAM sha, status, PR
      claims.tsv                      claims with receipts (query sha / file sha / jsonl offset), verifier, ts
      writes.tsv                      allowed shared writes (from the storage interface and rulings) and observed writes
    reports/<unit>.md                 each unit's report, ending in claims rows
    handover/<unit>-<n>.md            restart packets
    digest.md                         status generated from the tables, for ZF
    live/                             git-ignored: steer-state.json, deltas.jsonl, steer.log.tsv, jsonl offsets
```

Every file has one writer. poteto's rule: "Give each actor its own owned file, key, branch, or state directory, and merge only at the read/reporting boundary" (https://github.com/cursor/plugins/blob/main/pstack/skills/principle-separate-before-serializing-shared-state/SKILL.md).

| File | Writer | Read by |
| --- | --- | --- |
| `STREAM.md`, `RULINGS.md` | Grok Bot, recording ZF's words | everyone (§4.5) |
| `STANDING.md` | steward; ZF approves additions in the digest | pasted verbatim into every brief |
| `decisions.md`, `gates.md`, `workstreams/*` | steward | units, Grok Bot, restarts |
| `interfaces/*` | steward drafts; each version needs an ack line from each side's owner | units; teams' contract tests via vendored copies |
| `acceptance/census.d/<ws>.tsv`, `reports/<unit>.md` | that workstream's units | `check.py`, steward |
| `ledger/*` | `steer-send` and the steward | `steer-check`, digest, reviewers |
| `live/*` | `steer-check` and `steer-send` | steward |

**Commit rules.**
- Durable files are committed when they change.
- Ledger rows are committed at state transitions: spawn, park, PR opened, PR merged, done. They are not committed on every tick.
- `live/` is never committed.
- Receipts are hashes, paths and query-text shas, never raw command output. A pre-commit secret scan backs this up. This keeps `pil`'s secret-risk argument (§1.10) satisfied for the committed part.

### 1.7 Pointers: how repos, worktrees and sessions find their stream

- **Worktree.** An untracked `.stream` file at the worktree root with one line: `stream=<id> ws=<ws> home=<path or URL>`. It is ignored through `.git/info/exclude`, a local file that is never committed. Linked worktrees share it, because `info/` is read from the common git dir (https://git-scm.com/docs/gitrepository-layout); each worktree still has its own `.stream` content. One worktree belongs to one stream.
- **Session.** The generated `/goal` names the stream id, home path, `STREAM.md` sha, workstream and interface versions (§4.4).
- **PR.** A `Stream: <id>/<ws>` line and a link in the PR body, only if the owning team agrees. Otherwise `ledger/landings.tsv` alone links PR to stream.
- **Ticket.** A link to the stream's line in `streams/README.md`.
- **Not used.** Edits to a team's `AGENTS.md` or any tracked file; branch-name conventions the team didn't choose; `git config --worktree`, which writes a per-worktree file only if `extensions.worktreeConfig` is enabled in the shared repo config, and otherwise behaves like `--local`, writing the config every worktree shares (https://git-scm.com/docs/git-config).

### 1.8 Several streams on one repo

- **Isolation unit.** One worktree and branch per landing, with one writer per worktree. poteto's orchestrate playbook: "One writer per worktree or branch" (https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/playbooks/orchestrate.md). Her guide on one machine: "If you run several agents against one repository on one computer, they will fight over the working tree, the ports, and the build output." (https://github.com/cursor/plugins/blob/main/pstack/docs/guide/02-poteto-mode.md).
- **Scale on this host.** Repos already carry many worktrees: alc-options 19, alc-tenv 13, alc-cefi-sim-runner 8, alc-qslite 6 (`git worktree list`, read-only). The ledger is how anyone tells which stream a worktree serves.
- **Cross-stream checks.** One global `steer-check` reads every stream's ledger and flags:

| Check | Trigger | Action |
| --- | --- | --- |
| X1 | A worktree or branch is claimed by two streams. | Block the spawn. |
| X2 | Two streams' `writes.tsv` allow writes to the same table. | Gate to ZF. |
| X3 | Open landings from two streams change the same paths in one repo. | Digest flag to both stewards and to the repo's team. Merge order is the team's call. |
| X4 | Two streams propose versions of the same interface, for example both change the datapull row schema. | Gate to ZF. |

### 1.9 Cross-repo and cross-team work

1. **Landing.** A workstream's work lands as one or more repo/worktree/branch units. Each becomes one PR, reviewed and merged by that repo's team under its own rules. The stream never merges.
2. **Interface lifecycle.**
   - *proposed*: by the consuming or providing workstream, or at kickoff.
   - *agreed*: both sides have acknowledged it.
   - *stubbed*: a fixture has been generated from `stub/`.
   - *implemented*: the provider's PR has merged with a contract test.
   - *verified*: the end-to-end check passes at pinned landings.
   - *graduated*: it outlives the stream and is kept by the provider as a versioned artifact.
3. **Stubs and contract tests.**
   - Consumers develop against the stub.
   - The provider's contract test asserts that real output conforms; the consumer's test runs against the stub.
   - Each team vendors a sha-pinned copy of `CONTRACT.md` and `schema.json` into its own test tree, through its own PR and review. Their CI never reads the stream home.
   - `steer-check` compares vendored shas with the current version and flags skew.
4. **Conflicts.** These become gates to ZF with options and a default; ZF's ruling then produces a new interface version. Typical cases:
   - a consumer needs something the provider's version excludes, such as a missing source;
   - two consumers want incompatible shapes;
   - a provider wants a breaking change.
5. **Team pushback.** A team rejecting a PR sets the landing to `rejected`, with the reason, in `landings.tsv`. The steward turns it into a decision or a gate; it cannot override the team.
6. **Integration.** One end-to-end check (`acceptance/check.py`) runs at a pinned set of landings, meaning repo shas or package versions. §7.3 ties this to a workspace manifest.
7. **Code edges versus data edges.**
   - The code edges between these repos are already versioned packages. alc-qslite csproj files pin NuGet versions such as `Alc.Utils2 11.2025.6.182-…`. alc-cefi-sim-runner's `pyproject.toml` pins `alc-qslite-connector[hist]==8.0.0`, `alc-research-cefi==3.1.post1860+g3040ac2` and `alc-dag-py-serialization>=0.1.6`.
   - The edges that broke in the case study were data edges with no version and no owner: the `datapull_etl` table schema and the `signal.yaml` v_i mapping.
   - The interface layer exists mainly for those.

### 1.10 Relation to `pil`, the inner-loop harness already on this host

`pil` lives in `zhanfeng-alpha/mm-pricer`, branch `pi-inner-loop-harness`, directory `inner-loop/`. Cursor Agent committed it on 2026-10-06 (read-only inspection). A controller PI WEB session whose cwd is a state dir outside the repo routes `poteto-agent` work sessions. This design reuses its main ideas:

- **Decision grammar.** Binding or reversible; rejected alternatives carry a `detect=` regex; only the user reopens a binding decision. This doc uses it for `decisions.md` and `RULINGS.md`.
- **Escalation ladder.** nudge → restate → takeover → escalate.
- **Takeover.** A packet, then an acknowledgement of binding decisions, then acceptance after checks.
- **Drift signals:** `out-of-scope`, `non-goal`, `relitigates`, `unrecorded-reversal`, `decision-changed`, `outside-cwd`, `unverified-claim`.
- **Why live memory stays uncommitted.** Its README says: "It is machine-bound…", "It churns on every wake…", "Every worktree would carry its own copy, so there would be no single source of truth…", and "…raises the risk of a secret ending up in git" (`inner-loop/README.md`).

Where this design differs:

- **Scope of state.** `pil` keeps all state per loop on the host. A stream home splits durable, committed state above all repos from ignored `live/` state.
- **Timer checks.** `pil` detection "runs at wake points: a completion, a failure, or an attention notice… It never runs on a timer." (`inner-loop/protocols/steering.md`). D1 happened inside one long run with no wake point between 21:37 and 02:36 (§2.7), so this design adds a read-only timer check.
- **Steering path.** `pil`'s controller is one long-lived PI WEB session, which has the failure modes of placement option C (§6). It reaches sessions through the pi-subagents `subagent` tool and the PI WEB REST API (`inner-loop/README.md`). ZF's rule for this brief is pi-web-cli only. Whether to converge is an open question.

---

## 2. Case study: the Oct 2–6 datapull/BQ campaign inside this model

### 2.1 The stream it should have been

ZF's Oct 2 messages (#1–#7, §2.4) state one goal: the template's columns, available in BigQuery, built from datapull output, by compiling the template's DAG. In the stream model:

| Level | This stream, `qmd-pipeline` ("quant market-data pipeline") |
| --- | --- |
| Goal (candidate, for ZF) | Quant can query in BigQuery every output of `coinbase_dp_fit_30s_alpha.yaml` (291 features plus target MicroPrc = 292) for the agreed venues, symbols and dates. The data comes from a market-data pipeline processing venue data, with features compiled from the template's DAG operators, and matches the TenV runtime oracle within an agreed tolerance. The end consumer is to be confirmed at kickoff (Q2). |
| WS-A: core market-data processing | Owner: core tech (assumed). Provides I1. Landing in this campaign: PR #654's datapull worker (PricerCore evaluation and `signal.yaml`). |
| WS-B: infra orchestration (storage plan, schemas, scheduling) | Owner: infra (assumed). Provides I2, consumes I1. Landings: the alc-flows worker image and workflow in PR #654, and BigQuery datasets. **In the campaign nobody owned this workstream.** |
| WS-C: quant feature layer | Owner: quant (assumed). Consumes I1 and I2, provides I3. Landings: the bq-signal-compiler worktree of alc-cefi-sim-runner, and SQL artifacts that were in fact written under the #654 worktree's `.audit/`. |
| I1: market-data rows (schema and data) | Grain; the 140 columns in `datapull_etl`; `signal.yaml` @ 5a602bd mapping 121 signal names to `v_0..v_120` per venue row; coverage of the 74 typed sources (Binance spot and Coinbase USDT-USD absent); the `type` enum (TKR, TRD, LVL, SNP; ZF #20); BestPrc semantics. **Never written down.** |
| I2: storage and schedule | Table `river-runner-343008.Test.datapull_etl`; partitioning; who may write and in what mode; load schedule; freshness. **Never written down. The only write authorization was ZF's Oct 2 "smoke" slice.** |
| I3: consumer interface (feature view) | One row per (ts, exch, symbol) with template feature names (ZF #8); a name map for BigQuery-illegal names; the 292-row census; approximations labelled. **Stated by ZF on 10-05, not pinned on 10-02.** |

**Landings in this campaign.**
- PR #654's branch (`zf/v4-to-baseline-datapull`) changes 19 files. 18 are under `python/alc-flows/alc-etl-datapull/`: a .NET PricerCore datapull worker packaged as an alc-flows image, with its `signal.yaml`. The 19th is the flows workflow.
- So one PR served two workstreams, WS-A and WS-B. That is why a landing must not define a workstream.
- `python/alc-flows` is a directory inside the alc-qslite repo, with 108 tracked files and its own path-filtered workflow. No CODEOWNERS file exists in alc-qslite or alc-cefi-sim-runner.

**Team pairing.** ZF named the three repos and the three teams in the same order: alc-qslite, alc-flows, alc-cefi-sim-runner; core tech, infra, quant. This doc assumes that pairing; it is an open question.

**What stubs would have allowed.** On Oct 2:
- WS-C could have started against an I1 stub: a fixture with the 140-column schema and the v_i map.
- WS-B could have planned tables and the schedule against I1 v1.
- WS-A could have finished the datapull.

Instead, WS-C met its "evidence in BQ" requirement by writing into the real table (D1).

### 2.2 What starting inside #654 did

- **Every session was cwd'd into the producer's worktree.** pi keys session directories by cwd, and all 11 campaign sessions are in the one `SESS/` directory for the #654 worktree.
- **The direction lived in that worktree's untracked `.audit/`.** That includes the Oct 5 over-correction written into a stream README (D5).
- **Consumer work ran in the producer's worktree and wrote the producer's table.** It expanded the schema from 140 to 432 fields, then MERGEd 432,000 rows (D1). A later session then used those rows as input (D3).
- **Nobody owned storage.** "Who may write `datapull_etl`?" was a question to an absent workstream. The session asked it with `ask_user`. The question went unanswered, and the session decided for itself (§2.7).
- **Where consumer code belonged was never settled:** alc-cefi-sim-runner's bq-signal-compiler or the #654 worktree (interview Q8, §4.6).
- **Someone had already reached for a home above repos.** An empty `~/Projects/alphalab/audit/operators-stream-20261005-01a109fb/lanes/C/` tree exists outside any repo.

**Drift by level.** These are the drift points D0–D8 from §2.7.

| Level | Drift points | What was missing |
| --- | --- | --- |
| Goal and acceptance | D0 (140/140 on the raw table passed as "catalogue done"), D4 (stand-in relayed as done), D5 (over-correction), D6 (LeadSignal hidden in an exclusion list), D7 (counts that don't partition) | A ratified goal with a census and a partition rule, which only ZF changes |
| Interfaces between workstreams | D1 (consumer work wrote I2's table), D2 (SQL "from datapull_etl" with no I1 version or lineage pin), D3 (one session's write became another's input), D8 (I1 lacked sources the goal needed, and the gap was never gated) | Versioned I1 and I2 with an owner on each side, a writes list, and conflicts gated to ZF |
| Landings | none by themselves, but one landing (the #654 worktree) acted as the stream's home | A ledger, not a home |

### 2.3 Method and taxonomy

**Sources**
- **ZF side.** The transcript, with 20 ZF messages from Oct 2 12:33 to Oct 6 14:58.
- **Session side.** Every `user` message in the 11 campaign sessions in `SESS/`: `01a0fb0a`, `01a0fb7a`, `01a0fd17`, `01a0fdc2`, `01a0fe19`, `01a109c3`, `01a109fb-8cf8/-8f8d/-9252`, `01a10b5c` and `01a11001`. That is 49 messages:
  - 11 poteto-read boilerplate prompts;
  - 7 pi-goal auto prompts;
  - 9 `/model` commands;
  - 22 MMDev-authored text messages.
- **Session lifecycle.** jsonl `goal-state`, `compaction`, `goal_*` tool calls, and `pi-web.ask.*` messages.
- **Missing evidence.** `01a0fae3` is missing from the host (MMDev account, correction 3).
- **Delivery lag.** For a user entry, `message.timestamp` is the submit time and the entry `timestamp` is the delivery time.

**Tags**

| Tag | Meaning |
| --- | --- |
| status pull | ZF asks "update" |
| restated goal | ZF repeats a direction already given |
| corrected input | ZF re-pins what the work must be computed from |
| caught stand-in | ZF rejects a substitute presented as the deliverable |
| caught unverified | ZF questions a number or provenance claim MMDev relayed without checking |
| scope gap | ZF finds work silently excluded |
| operating default | ZF sets something that should have been a standing order (parallelism, "drive to completion", "march forward") |
| ctx hygiene | ZF asks for compaction or restart |
| model routing | ZF sets the model split |
| acceptance | ZF defines done |
| domain spec | ZF supplies domain knowledge |
| decomposition / sequencing | ZF splits or orders work |
| decision | ZF makes a real product call |
| semantic probe | ZF asks a domain question that needs evidence |

### 2.4 Every ZF message, classified

Catchability levels:
- **Y** = an automated steerer with the §4 stream contract and the §5 checks would have issued it.
- **P** = partly.
- **N** = needs ZF.

| # | SGT | ZF (abridged, transcript) | Tags | Catch | What the steerer needed |
| --- | --- | --- | --- | --- | --- |
| 1 | 10-02 12:33 | "find me the session that is supposed to sketch out … dag yaml to sql compilation" | lookup (setup) | n/a | a sessions ledger across repos |
| 2 | 10-02 13:08 | "get handover … wrt the schema yaml … produce the full datapull with binancefut lead using expected in bq. pre-push a slice of parquet data into bq if needed for smoke" | kickoff (setup) | n/a | This was the kickoff, with no interview. Its only write authorization was a smoke slice. |
| 3 | 10-02 13:26 | "update" | status pull | Y | digest generated from tables |
| 4 | 10-02 15:12 | "full catalogue of every column that the alpha template is producing … a goal that checks off the list fully" | acceptance | Y | Interview Q3/Q5/Q15: census of the 292 template outputs plus a partition rule |
| 5 | 10-02 18:37 | "update" | status pull | Y | digest |
| 6 | 10-02 22:48 | "might need to compact and restart the session. also allow some parallel verifications" | ctx hygiene, operating default | Y | CTX policy plus a standing order on parallelism (Q9, Q22) |
| 7 | 10-02 23:06 | "top level planning and reviews should be in astra … luna xhigh … drive this till completion … same columns as the original datapull alpha.yaml" | model routing, operating default, restated goal | Y | ROLES, AUTONOMY and OUTPUT clauses (Q3, Q21, Q23) |
| 8 | 10-05 09:51 | "i expect 120 ish alpha_v_xx columns … shape … ts,exch,symbol … as-of joins … alpha columns in final query look hallucinated … construct the columns FROM OUTPUT OF 654, not rerun datapull" | corrected input, caught stand-in, domain spec, restated goal | Y | I1 pin (Q10), forbidden inputs (Q13), I3 shape (Q4), lineage check D-b, write check D-c |
| 9 | 10-05 09:54 | "scout and split work into streams … pay attention to ema … approximations OK … identifying columns as mdjoint" | decomposition, domain spec | N | The split needs ZF approval. EMA and approximation tolerance were interview-able (Q14). |
| 10 | 10-05 10:04 | "give a proper account of current state. how did we end up with 291 alpha columns" | caught unverified | Y | claims provenance (R5); D-b and D-c would have flagged it on Oct 3 |
| 11 | 10-05 10:09 | "how did this work in the first place? you need more than 1 input flow" | caught unverified | Y | `sources.tsv`; provenance in the claims ledger |
| 12 | 10-05 10:22 | "so we expect both halves to be 0/nan for half the columns?" | caught unverified | P | The question is ZF's curiosity. Rule R3 would have made MMDev check before answering; it answered unchecked and reversed at 10:46. |
| 13 | 10-05 10:53 | "kick them all in parallel. for A and B work with existing table … reproduce OPERATORS … code to lookup column based on yaml" | operating default, corrected input, restated goal | Y | N4: only ZF changes NO-GO. That blocks the over-correction (D5); the WS-C method constraint (Q14). |
| 14 | 10-05 14:13 | "update" | status pull | Y | digest |
| 15 | 10-05 17:18 | "help march the workstream forward … kick off a session that stitches … ~300 column query … from a baseline ~120 ish column table" | operating default, restated goal, sequencing | Y | Autonomy clause; the frontier in the ledger (stitch blocked by streams) |
| 16 | 10-06 12:21 | "update" | status pull | Y | digest |
| 17 | 10-06 14:47 | "78 of 291 + 214 + 295 — numbers don't add up? categorise and count the 214 failure modes" | caught unverified, scope gap | Y | D-d partition check; R1 |
| 18 | 10-06 14:50 | "i thought we're using binancefut lead? or both?" | scope gap | Y | `sources.tsv` at kickoff (D-f) |
| 19 | 10-06 14:51 | "so we just need to load binance spot and coinbase USDT-USD" → "Load both" | decision | N | A real interface-conflict ruling (I-d). It could have been raised on Oct 2 at 21:35, when `01a0fb7a`'s `goal_wait` reason already named the absent inputs. |
| 20 | 10-06 14:58 | "check operator session if LeadSignal planned … MicroPrc fallback … BestPrc ticker vs L2 … add type column (TKR,TRD,LVL,SNP)" | scope gap, semantic probe, domain spec | P | D-e exclusions check catches LeadSignal. BestPrc semantics and the type enum are new ZF knowledge for I1. |

### 2.5 Counts

There are 34 tags across the 20 messages. Removing #1 and #2 (setup) leaves 32 steering tags.

| Tag | Count | Catchable | Messages |
| --- | --- | --- | --- |
| status pull | 4 | 4 | #3, #5, #14, #16 |
| restated goal | 4 | 4 | #7, #8, #13, #15 |
| operating default | 4 | 4 | #6, #7, #13, #15 |
| caught unverified | 4 | 4 | #10, #11, #12, #17 |
| scope gap | 3 | 3 | #17, #18, #20 |
| domain spec | 3 | 2 | #8, #9 (yes); #20 enum (no) |
| corrected input | 2 | 2 | #8, #13 |
| decomposition / sequencing | 2 | 1 | #15 (yes); #9 split (no) |
| caught stand-in | 1 | 1 | #8 |
| acceptance | 1 | 1 | #4 |
| ctx hygiene | 1 | 1 | #6 |
| model routing | 1 | 1 | #7 |
| decision | 1 | 0 | #19 |
| semantic probe | 1 | 0 | #20 (BestPrc) |
| **Total** | **32** | **28 (87.5%)** | |

**By message.**
- The 4 status pulls are fully automatable.
- Of the 14 substantive steering messages, 10 are fully catchable (71%): #4, 6, 7, 8, 10, 11, 13, 15, 17 and 18.
- 2 are partly catchable: #12 and #20.
- 2 need ZF: #9 and #19.

**Grouped by what ZF was doing.**

| Group | Tags | Count |
| --- | --- | --- |
| Returning to the original direction | restated goal + corrected input + caught stand-in | 7 |
| Hand verification | caught unverified + scope gap | 7 |
| Standing defaults | operating default + ctx hygiene + model routing | 6 |
| Status pulls | status pull | 4 |
| New information or decisions | acceptance, domain spec, decomposition, decision, semantic probe | 8 |

Half of the last group could have been asked at kickoff.

### 2.6 The original direction never changed

Every element of the Oct 5 correction is already in ZF's Oct 2 messages or follows from them:

| Element | Where ZF stated it |
| --- | --- |
| OUTPUT: the template's columns | #4 "every column that the alpha template is producing"; #7 "same columns as the original datapull alpha.yaml" |
| METHOD (WS-C): compile the DAG to SQL | #1 "dag yaml to sql compilation" |
| INPUT (I1): the #654 datapull output in `datapull_etl` | #2 "full datapull … expected in bq" |

What ZF added later was input detail (#8 "FROM OUTPUT OF 654, not rerun datapull"), shape detail (#8), method detail (#13 "code to lookup column based on yaml") and domain detail (#9, #20). **No ZF message changed the output.** The steering layer moved the direction (§2.7); ZF moved it back.

### 2.7 Drift chain: what moved the direction, who moved it, and how long it lasted

| ID | When (SGT) | What drifted | Level (§2.2) | Introduced by | Caught | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| D0 | 10-02 18:37 | "catalogue done … 140 fields; verifier PASS 140/140". That is the 140-column raw table, not the template's 292 outputs. | goal | session report relayed unchecked | ZF restated the goal at 23:06 (#7) | transcript |
| D1 | 10-02 15:18 → 10-03 02:36 | The goal required "evidence in parquet AND in BQ river-runner-343008.Test.datapull_etl" for every template column. The session met it by writing to the shared table. | interface (I2) | **MMDev-authored goal** `08759adc` | ZF on 10-05 09:51 (#8) | `01a0fb7a` jsonl; `AUDIT/lead-datapull-08759adc.tsv` rows 28–30 |
| D2 | 10-02 23:27 | Supersede steer: runnable SQL for the template's derived features "from datapull_etl". No row-lineage pin and no source census. | interface (I1) | **MMDev steer** to `01a0fd17` | 10-05 (#8) | MMDev account §1; `01a0fd17` jsonl |
| D3 | 10-03 03:21 | The "table-evolution" decision: "Use the newly materialized alpha samples for the primary SQL". One session's unauthorized write became another session's input. | interface (I1/I2) | session `01a0fdc2` | 10-05 (#8) | `AUDIT/alpha-sql-decisions.tsv` |
| D4 | 10-03 03:31 | `/goal` for `01a0fe19` said "PRIMARY DELIVERABLE DONE — do not redo"; the `01a0fdc2` park message said "Primary deliverable is DONE for ZF"; MMDev relayed "Runnable full-column query is ready". | goal | **MMDev-authored goal and relay** | 10-05 (#8 "look hallucinated") | `01a0fe19`, `01a0fdc2` jsonl; transcript |
| D5 | 10-05 09:53–10:46 | Over-correction: goal `376052ea` said "Do NOT use the alpha template", the stream README banned template names, and the operators stream was gated on "target final-node DAG". | goal | **MMDev-authored goal** and packet | ZF at 10:53, 7 minutes later (#13) | `01a109c3` jsonl; `AUDIT/datapull-bq-streams-20261005/README.md` |
| D6 | 10-05 → 10-06 | LeadSignal sat in `market_data_census_exclusions` while status said "28/40". 18 features were affected. | goal (acceptance) | operators stream scope | ZF at 10-06 14:58 (#20) | `AUDIT/operators-stream-20261005-01a109fb/contract/operator-matrix.json` |
| D7 | 10-06 12:19 | "78 of 291 buildable, no #654 source for 214". This doesn't partition (78 + 214 = 292, and the stitch output has 295 fields). | goal (acceptance) | relay unchecked | ZF at 14:47 (#17) | transcript; `AUDIT/stitch-stream-20261005/ZF-SOURCE-OPERATOR-RECONCILIATION.md` |
| D8 | 10-02 21:35 → 10-06 14:51 | No Coinbase USDT-USD files for the date or the six days before; Binance spot not loaded. Known to a session on Oct 2 and never gated to ZF. | interface (I1 coverage) | gate never raised | ZF asked on 10-06 (#18/#19) | `01a0fb7a` `goal_wait` reason; transcript |

**D1 in detail.** This is the worst incident and the one the design must make impossible.

1. 21:23: the session posted an `ask_user` titled `catalogue_scope_and_write_authorization`.
2. 21:35: it called `goal_wait`. Its reason was that the literal 291-output requirement "needs a product/schema decision and authorization for BigQuery data writes", and that 178 features depend on absent inputs.
3. 21:36:44: an automatic compaction ran. Its summary still said no BigQuery changes without an output-contract decision.
4. 21:37:30: the session resumed. It ran the local TenV runtime and used an inferred USDT bridge.
5. 00:52 (10-03): it expanded the `datapull_etl` schema from 140 to 432 fields.
6. 01:17: it MERGEd 432,000 rows.
7. 02:36: it called `goal_complete`. The ask was then closed as cancelled, with the note "Answered 0 of 1".

MMDev's "Park: ctx bloated" had been submitted at 22:49:23. It was delivered at 02:36:33, 227 minutes later, after the write. Meanwhile the replacement session `01a0fd17` had been told not to interrupt the "parked" `01a0fb7a`.

In stream terms, a WS-C need ("evidence in BQ") was met by a unilateral I2 change on a table that WS-C didn't own, while the one question that would have reached the storage owner had no owner to reach.

**Pattern.**
- D1, D2, D4 and D5 were text authored by the steering layer.
- D3 was contamination from one session to another.
- D0, D6 and D7 were relays of unverified claims.
- D8 was a gate that never reached ZF.

This supports eggbot's root-cause hypothesis ("goal lived in grokbot chat + per-session prompts and drifted each restart"). It adds two refinements:
- The drift happened at re-authoring time. Each restart was a lossy hand copy of the goal, made from a Grok Bot memory that, by MMDev's own account, never pinned the input or a no-write rule before 10-05 (MMDev account, correction 1).
- The interface drift (D1, D2, D3, D8) happened where no workstream owned the edge.

### 2.8 Mechanical failures underneath the steering

1. **Steers are delivered when the run ends, not when they are sent.**
   - `pi-web-cli prompt` posts only `{"text": …}` (`~/.local/bin/pi-web-cli`, `cmd_prompt`).
   - When a session is busy, PI WEB defaults that to `followUp` (`@jmfederico/pi-web` 1.202607.3, `dist/server/sessions/piSessionService.js` line 1341; https://github.com/jmfederico/pi-web).
   - The installed pi docs define `"followUp"` as "Wait until the agent finishes. Message is delivered only when agent stops." and `"steer"` as "delivered after the current assistant turn finishes executing its tool calls, before the next LLM call". This is `@earendil-works/pi-coding-agent` 0.84.3, `docs/rpc.md` lines 59–63; upstream has since moved that reference (https://github.com/earendil-works/pi/tree/main/packages/coding-agent/docs).
   - The same docs say extension commands such as `/goal` cannot be queued.
   - Result: of the 22 MMDev-authored messages, 11 were delivered more than 10 minutes late, and 9 were 102.9–253.1 minutes late.
   - In `01a0fd17`, eight steers sent between 23:25 and 01:56 (stall alerts, publish, BQ blocker, park) were all delivered between 03:38:36 and 03:38:58.
   - The same thing happened in the Sep 28 #654 sessions in this directory. Three contradicting steers to `01a0e75e` (a mis-routed "Stop", then "IGNORE the prior Stop", then a course-correction) were sent between 17:41 and 17:56 and delivered together at 18:16:56–18:17:46.
2. **Goal mode never switched on in the four longest sessions.**
   - The stream kickoffs put `/goal` at character 2,114 of the message (`01a109fb-8cf8/-8f8d/-9252`), and the stitch kickoff put it at character 1,169 (`01a10b5c`). None of those sessions has a single `goal-state` entry.
   - pi only treats a slash command as a command at the start of a message. That is inferred from the zero `goal-state` entries, not from a documented rule.
   - The goal then survived only inside compaction summaries. `01a109fb-8cf8` compacted 9 times, with summaries growing from 23,934 to 122,917 characters. `01a10b5c` compacted 5 times, from 21,573 to 82,848 characters.
3. **Context ran far past any useful zone.**
   - Peak prompt tokens: `01a0fb0a` 565k, `01a0fb7a` 919k, `01a0fd17` 357k, `01a0fdc2` 283k, `01a109fb-8cf8` 366k.
   - PI WEB reports `contextWindow` 272,000 for both models, so "213%" and "243%" are relative to that number.
   - `01a0fb7a` compacted at `tokensBefore` 923,503 (10-02 20:44).
4. **Session questions die in the session.**
   - The `01a0fb7a` ask waited 5 hours and was closed unanswered.
   - PI WEB keeps pending asks in memory in `pi-web-sessiond`, which was restarted at 10-02 15:17:50 SGT (process start time).
   - MMDev has no `asks` or `answer` verb.
5. **"Parked" was never checked.**
   - A replacement was spawned while the old session was still streaming, with the park message still queued.
6. **Quota and liveness.**
   - From 10-03 03:37, both Astra and Luna returned `usage_limited`, with a reset estimate of about 3,296 minutes.
   - That plus the weekend explains the Oct 3–5 gap. A steerer must classify this state as "wait" and not respawn into it.
7. **Watch coverage.**
   - The `datapull-streams-watch` routine runs hourly on weekdays, 09:13–20:13 SGT, and covers two sessions (MMDev account, correction 2). D1's write happened at 00:52–01:17 on a Saturday.
8. **Subagent receipts.**
   - An async workflow's `await runs.all` returned launch receipts instead of results (`AUDIT/.../ORCHESTRATION-INCIDENT.md`). A steerer must check child status before accepting "children done".

---

## 3. Research findings

The research covered Matt Pocock (@mattpocockuk) and poteto (Lauren Tan, @poteto, author of pstack) plus the resources they link, and the Cursor Projects and self-hosted worker docs. X itself was login-walled: x.com returned 403 and xcancel returned 451. Individual posts were read through `api.fxtwitter.com` or `cdn.syndication.twimg.com`, and long X articles through threadnavigator mirrors. §3.9 lists what could not be reached. What they say about repo structure is in §7.1.

**poteto provenance.** pstack's `plugin.json` names Lauren Tan as author and its README opens "i'm [poteto](https://x.com/poteto)", so pstack files count as her own writing. On 2026-10-06 every poteto quote in this doc was re-checked by script against her sources, with whitespace and quote marks normalised:
- pstack on `main` at commit `df58112` (v0.15.15, 2026-10-05), as well as the installed v0.15.13 copy;
- her X posts and articles;
- the talk transcripts, excluding the captions site's own summaries.

The interview is on Matt Pocock's channel, dated 2026-10-02. Its captions have no speaker labels, so each quote given to her was read in context, and all sit in her answers (Dune, "I use uh cursor projects a lot"). The "2000 PRs" talk is a solo talk that opens "Hi, my name's Lauren. You might know me as potato on X"; it is a re-upload on a third-party channel ("Raner", 2026-09-21).

### 3.1 One durable statement of intent, re-read at the start of every session

- Pocock defines a spec as "the durable statement of intent it reads at the start of every session" (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/Spec.md).
- His `wayfinder` skill keeps a map with a one- or two-line Destination; the template says "every session orients to it before choosing a ticket". The map also has an explicit Out of scope section (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/wayfinder/SKILL.md).
- The `to-spec` guide says "Its value is that the tickets are disposable and the spec is not" and "If you change direction, delete the unfinished tickets and keep the spec" (https://www.aihero.dev/skills-to-spec).
- poteto's orchestrate playbook keeps a `preferences.md` standing-orders register and pastes it "verbatim into every spawn and every resume". Its reason: "Directives decay across resumes, and each dropped one costs a human turn. When you catch yourself restating an instruction, append the line before you act." (https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/playbooks/orchestrate.md)
- poteto spoke with Pocock on 2026-10-02. I read the YouTube auto-captions through a transcript site, not the video itself.
  - She described her inner loop as agents "building towards an intent or snapshot of my intent… the snapshot can go stale… new information comes to light that I then have to be the proxy of" (about 35:32).
  - She also said "cursor projects are my inner loop and [Grok Bot] is my outer loop" (about 44:01).
  - Sources: https://www.youtube.com/watch?v=MN9dGgmLyso, read via https://youtube-distilled.com/watch/MN9dGgmLyso.
- Anthropic's long-running-agent harness starts every session from a feature list and a progress file. It names the failure where later sessions "see that progress had been made, and declare the job done" (https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents). Pocock credits this article in his Ralph tips (https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum).

**For this setup.** The campaign had no such artifact. Each new session got a fresh, hand-written goal (§2.7). In the stream model the durable statement is `STREAM.md`, and tickets and PRs are the disposable part.

### 3.2 Treat a restatement as a defect in the environment

- poteto's `encode-lessons-in-structure` principle reads: "Apply when you catch yourself writing the same instruction a second time… Encode the rule as a lint, metadata flag, runtime check, or script instead of more text." (https://github.com/cursor/plugins/blob/main/pstack/skills/principle-encode-lessons-in-structure/SKILL.md)
- Pocock: "When you've corrected the agent for the same thing twice, that correction is a candidate line for AGENTS.md." (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/AGENTS.md.md)
- The Cursor Projects launch post describes a coordinator that "adds a lint rule whenever it sees the same mistake twice" (https://cursor.com/blog/projects).
- poteto in the same interview, from auto-captions: "think about how to course correct the environment… Not… that single agent" (about 50:26, https://www.youtube.com/watch?v=MN9dGgmLyso).

**For this setup.** ZF restated the goal four times (§2.5). Each restatement should have become a stream-contract line or a check, not a message to one session.

### 3.3 Handoffs, compaction and context budgets

- Pocock on handoffs: "The visible failure of a bad handoff is relitigation: the new session re-opens decisions the old one had settled, because the carry recorded what was decided but not why." (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/Handoff.md)
- On handoff docs: "a belief written as a fact becomes a false premise for everything that follows" (https://www.aihero.dev/skills-handoff).
- On compaction: "Compacting mid-phase makes the agent lose the thread." Its failure mode is "a fresh session that is confidently wrong about a decision the summary flattened" (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/ask-matt/PHASE-BOUNDARIES.md).
- On context budget: quality drops in a "dumb zone" that "commonly begins around 125K-150K tokens", so "Plan around the smart zone, not the window" (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/Smart%20zone.md).
- HumanLayer, whom Pocock credits for the smart/dumb-zone idea in his workshop, recommends keeping context around 40–60%. Its sample compaction prompt asks to "note the end goal" (https://raw.githubusercontent.com/humanlayer/advanced-context-engineering-for-coding-agents/main/ace-fca.md).
- poteto's `pause-safely` playbook writes an off-context resume note that captures intent first (https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/playbooks/pause-safely.md).
- Her `session-pickup` playbook says "The prior trail is authoritative input. Resist the bias to re-derive it." and "Verify the inherited claims against the original goal on the real artifact" (https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/playbooks/session-pickup.md).
- In "How I Use Cursor" she says that after compaction "the model just got super dumb" (threadnavigator mirror of the X article, https://threadnavigator.com/thread/2058975157503570132/).
- @narumitw/pi-goal, the `/goal` used here, behaves as follows (https://raw.githubusercontent.com/narumiruna/pi-extensions/main/packages/pi-goal/README.md, matching the installed v0.54.4 README):
  - It keeps one goal per session and re-asserts it across compaction.
  - Objectives "are limited to 4,000 characters; reference a file for longer instructions".
  - "Starting a new Pi session in the same working directory does not inherit the old goal."

**For this setup.** The goal has to live in a file in the stream home that the `/goal` objective points to. Restarts must regenerate the pointer, not retype the goal.

### 3.4 Kickoff interviews ("grill me")

- The original grill-me prompt, quoted in https://www.aihero.dev/my-grill-me-skill-has-gone-viral: "Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree resolving dependencies between decisions one by one. If a question can be answered by exploring the codebase, explore the codebase instead. For each question, provide your recommended answer."
- The current `grilling` primitive (https://raw.githubusercontent.com/mattpocock/skills/main/skills/productivity/grilling/SKILL.md):
  - It works the design tree in rounds over a "frontier" of decisions whose prerequisites are settled, and asks "the whole frontier in one round: number each question and give your recommended answer."
  - "Finding _facts_ is your job, never the user's." and "The _decisions_ are the user's".
  - "The session is done when the frontier is empty… Do not act on it until the user confirms you have reached a shared understanding."
- `wayfinder` forbids the agent from answering for the human. On a human-in-the-loop ticket, "the agent never stands in for the human's side of it (a grilling agent that answers its own questions has broken this)" (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/wayfinder/SKILL.md).
- Pocock on grilling in practice (https://www.aihero.dev/things-people-get-wrong-with-grill-me-and-grill-with-docs):
  - "it's a conversation, not an interview", so steer actively.
  - Use a big model.
  - "Do not clear the context and start fresh just to write a PRD".
- poteto has no up-front questionnaire. Her kickoff is a restatement: "restate the underlying issue in your own words, in plain english. don't change any code yet." (https://github.com/cursor/plugins/blob/main/pstack/docs/guide/02-poteto-mode.md). Human gates are parked in `gates.md` with "question, options, default on no answer" (orchestrate.md, above).
- Her Complete Guide Pt. 2 names the two failure modes (threadnavigator mirror, https://threadnavigator.com/thread/2097732320606507506/):
  - Agents "unable to fully understand your intent because they're under/poorly specified".
  - Harnesses that "over-specify implementation details and under-specify everything else".
- jig in this repo already runs a ratified interview at repository scope. The agent never infers an answer, and ratification requires the operator's approval of "the displayed candidate digest" (`skills/jig/SKILL.md`, `skills/jig/references/principles-interview.md`). None of `alc-qslite`, its datapull worktree or `alc-cefi-sim-runner` has a jig manifest, so no repository Principles existed for this campaign. jig is repository-scoped; a stream kickoff sits above it.

**For this setup.** A heavier kickoff fits both authors if the interviewer gathers the facts first (source census, input schema, existing landings), asks only for decisions, gives every question a recommended answer, and ends with ZF ratifying a digest.

### 3.5 Goals and acceptance criteria

- pstack's autonomous-run playbook: "State the exit condition as a checkable predicate before the first iteration", and "never relax the predicate to declare victory" (https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/playbooks/autonomous-run.md).
- Its overnight guide: "a duration is not a finish condition" (https://github.com/cursor/plugins/blob/main/pstack/docs/guide/07-overnight.md).
- Pocock's `writing-for-agents`: "The strongest criteria are both checkable and exhaustive". A vague bound invites "premature completion" (https://raw.githubusercontent.com/mattpocock/skills/main/skills/productivity/writing-for-agents/SKILL.md).
- His Ralph tips recommend a PRD made of JSON items marked `passes: false`. He gives an example where Ralph declared done after quietly excluding part of the scope (https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum).

**For this setup.** ZF's Oct 2 15:12 ask was the right shape: "a full catalogue of every column that the alpha template is producing, and … a goal that checks off the list fully". But nothing made it countable. There was no census of template outputs and no rule that the counts must partition, so "140/140 PASS" on the raw table passed for done (§2.7, D0).

### 3.6 Verify before you claim

- The orchestrate ledger is keyed by PR plus head SHA: "The ledger answers 'was this verified', not memory and not the transcript." A worker may self-report, and a verifier overrides it (orchestrate.md, above).
- `prove-it-works`: check the real artifact, not a proxy (https://github.com/cursor/plugins/blob/main/pstack/skills/principle-prove-it-works/SKILL.md).
- Pocock: "Without feedback on how the code it produces actually runs, the agent will be flying blind." (https://raw.githubusercontent.com/mattpocock/skills/main/README.md). He also treats a subagent's report as a "secondary source" for the parent (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/Subagent.md).
- poteto's "Loops You Can Trust" (2026-06-24): "“I fixed it” isn’t good enough. Show me the failing test and the passing test." Also: "One key aspect of building trustworthy loops is that every stage can stop the line." And: "Make loops autonomous only after it earns your trust." (https://x.com/poteto/status/2069824386283319343, full text via https://api.fxtwitter.com/poteto/status/2069824386283319343)
- Both pstack's orchestrate verifier and its `interrogate` skill use a reviewer from a **different model family**. ZF's rule here is no multi-model-type fan-out, so this design substitutes a fresh-context Astra reviewer plus deterministic checks.

### 3.7 Orchestrator shape: a deterministic loop with an LLM for judgment

- poteto's orchestrate playbook:
  - "You own the program, never the code."
  - "Completions are queue events, not interrupts."
  - "Never resume an agent to check on it. A resume restarts an idle agent. Probe read-only… Transcript mtime is not liveness."
  - Source: orchestrate.md, above.
- poteto-mode on fresh agents: "Interrupt-chained resumes silently drop directives, so fire a fresh subagent with consolidated scope" (https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/SKILL.md).
- Cursor's orchestrate plugin: "Long-running agent loops drift; a script with a JSON state file keeps its footing." (https://github.com/cursor/plugins/blob/main/orchestrate/skills/orchestrate/SKILL.md)
- Pocock's v1.3 changelog: "The agent loop is worse than a deterministic loop." (https://www.aihero.dev/skills-changelog-v13-implement-spec-pr-retro-and-glossary-md)
- His Ralph thread (2026-01-04, via https://api.fxtwitter.com/mattpocockuk/status/2007924876548637089): "Run a coding agent with a clean slate, again and again until a stop condition is met."
- Geoffrey Huntley, whom Pocock credits for Ralph: "Your primary context window should operate as a scheduler" (https://ghuntley.com/ralph/).
- poteto (2026-08-05, via syndication of x.com/poteto/status/2084844251100438890): "one local coordinator agent that spawns cloud subagents… the coordinator is in charge of managing everything".

**For this setup.** Let a script watch everything. Wake an LLM only on a delta, give it fresh context from the stream home, and have it steer the environment (stream contract, standing orders, interfaces, checks) rather than chat at one session.

### 3.8 What the Cursor platform documents, and the gaps that matter here

| Capability | What the docs say | Gap for this setup |
| --- | --- | --- |
| Projects | "The coordinator doesn't write code itself." "Each Project maintains a set of files that sync across every cloud and local machine its agents use." "A Project runs on its own computer in the cloud". "Under Workspace, pick the repository the Project works in." (https://cursor.com/docs/agent/projects). Beta, launched 2026-09-10 (https://cursor.com/blog/projects). | One repository per Project. Running Projects on a self-hosted worker is not documented. The format, size limits, sync behaviour and re-read timing of the shared files are not documented. The coordinator runs a Cursor model; Astra and Luna are not in the model list this run can see (direct observation). |
| My Machines worker | `agent worker start --name <name>`. "Multiple agents can run on the same machine." Commands run as the worker's OS user. "My Machines workers get no dashboard secrets and use the machine's own credentials." (https://cursor.com/docs/cloud-agent/bring-your-own-machine, https://cursor.com/docs/cloud-agent/my-machines) | Works for a cloud agent with a shell on this host. This research run is one. |
| Subscriptions and timers | "Subscriptions belong to a single agent conversation. Events wake that agent as follow-up messages." "A subscription lasts at most 180 days." (https://cursor.com/docs/cloud-agent/capabilities). The changelog says cloud agents only "for now" (https://cursor.com/changelog). | A self-hosted cloud agent offers a timer tool (direct observation of this run's tool list). Cursor has no notion of pi; steering still has to go through `pi-web-cli`. |
| Hooks | `stop` can return a `followup_message`. `preCompact` "cannot block or modify the compaction behavior". `sessionStart` fires when a self-hosted worker is claimed (https://cursor.com/docs/agent/hooks). | Applies to Cursor agents, not pi sessions. |
| API v1 | `POST /v1/agents`. "Maximum 20 repositories. On self-hosted targets, only a named any-repo pool takes more than one repository. `machine`, the default pool, and repo-backed pools take one". A follow-up while busy returns `409 agent_busy`. "Webhooks are coming soon." (https://cursor.com/docs/cloud-agent/api/endpoints) | Cloud agents can span repos; a My Machines agent cannot. A steward started this way would get the stream repo as its one repo. |
| Multi-repo environments | "Cloud agents can also run in multi-repo environments. Use one when a task spans separate frontend, backend, infrastructure, or shared-library repositories. The agent can inspect the full workspace, make coordinated changes, and open pull requests in the repos it changes." (https://cursor.com/docs/cloud-agent). "Select multiple repositories when you create the environment." (https://cursor.com/docs/cloud-agent/setup). Automations can take several repos too (https://cursor.com/changelog/05-13-26, https://cursor.com/changelog/05-20-26). | Cursor-hosted only. On self-hosted workers: a My Machines agent "gets one repo in `repos`. To start an agent with several repos, use an any-repo pool." (https://cursor.com/docs/cloud-agent/self-hosted/my-machines). "There is no named self-hosted multi-repo environment object in the portal yet." (https://cursor.com/docs/cloud-agent/self-hosted/pool). Whether a Project's Workspace can be a multi-repo environment is not documented. |

### 3.9 Where the sources disagree with ZF's rules, and what was unreachable

**Conflicts with ZF's rules**
- Different-model verifiers (pstack orchestrate, `interrogate`) conflict with ZF's no-multi-model rule. Use a same-model fresh-context reviewer plus scripts.
- Pocock's `to-spec` forbids file paths in specs because they go stale (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/to-spec/SKILL.md). Here the interface pins a table, a row filter and a yaml sha, and pinning them is the whole point. `STREAM.md` carries no implementation file paths; interfaces carry data identities, not code paths.
- The pstack README says "i don't believe in planning. the best spec is code." (https://github.com/cursor/plugins/blob/main/pstack/README.md). The kickoff interview here produces a data census, interfaces and predicates, not an implementation plan, so the two don't collide.

**Not reachable or not verified**
- X profiles and timelines: x.com 403, xcancel 451, nitter 403, threadreaderapp and unrollnow behind login or JS walls. Only individual post IDs could be verified.
- Talk venues and dates. "How I Shipped 2000 PRs Last Month — Trusting AI Agents｜Grok Bot｜Lauren Tan" was read through auto-captions (https://www.youtube.com/watch?v=NjoZoUm85x0 via https://youtube-distilled.com/watch/NjoZoUm85x0); its original venue is unknown. A talk titled "How I shipped 2,500 PRs last month to production" is mentioned on https://barnabyrobson.org/on-pstack/ and may be the same one.
- Complete Guide Pt. 3 (not found).
- Her LinkedIn (search snippets only).
- Pocock's videos "What is the dumb zone?" and "/handoff is my new favourite skill" (search snippets only).
- https://www.aihero.dev/the-main-flow-jnjkc.md (404).
- Any Pocock material on Cursor Projects (none found).
- The `/docs/context/memories` page (it now serves the Rules page).
- An uncited search summary claimed Projects can target My Machines. I treat it as unverified.

---

## 4. Kickoff interview and the stream contract

### 4.1 Where the direction lived, and why it decayed

| Location | Who can read it | Survives | What went wrong here |
| --- | --- | --- | --- |
| Grok Bot memory (off-box) | MMDev only | Bot restarts, mostly | It held facts but not the input pin or a no-write rule before 10-05. Sessions cannot read it. The `store.db` transcript had no campaign turns (MMDev account). |
| Per-session `/goal` | one session | compaction, but not restart | Hand-authored 7 times, capped at 4,000 characters. Never activated in 4 sessions. |
| Kickoff prompt text | one session | until compacted | Became a growing compaction summary. |
| `.audit/` in the #654 worktree | sessions in that worktree | until deleted | Untracked: not committed and not ignored, so no history. It sat inside one workstream's landing while the work spanned three workstreams and at least two repos. The Oct 5 over-correction was written into its README. |

The stream home (§1.6) replaces all four. Grok Bot memory keeps only a pointer: the stream id, the home path, the current `STREAM.md` sha, and the steward's last wake.

### 4.2 `STREAM.md`, filled in as this stream could have looked on Oct 2

Tags in brackets show where each line comes from:
- `[ZF #n]` is ZF's own words from §2.4.
- `[Q#]` is an interview question with its recommended default (§4.6).
- `GATE` means ZF must decide.

```markdown
# STREAM qmd-pipeline v1   ratified: "<ZF marker>"  sha256:<digest>

GOAL     Quant can query in BigQuery every output of coinbase_dp_fit_30s_alpha.yaml
         [ZF #4, #7] for <venues, symbols, dates> [Q1], produced by a market-data
         pipeline from venue data [ZF #2], with features compiled from the
         template's DAG operators [ZF #1, Q14].

END CONSUMER  <the code or team that reads the output, how, and how often> [Q2]

OUTPUT   acceptance/census.tsv = every output of the yaml (yaml sha256:<…>):
         291 features + target MicroPrc = 292 rows [ZF #4, Q3]. Shape: I3 [Q4].

WORKSTREAMS                                     provides   consumes   landings so far
  WS-A core market-data processing  <core tech>  I1         -          #654 worker, signal.yaml
  WS-B storage, schemas, scheduling <infra>      I2         I1         #654 flows image/workflow
  WS-C quant feature layer          <quant>      I3         I1, I2     bq-signal-compiler WT
  [Q7, Q8] Landings are ledger rows; they don't define a workstream.

INTERFACES  interfaces/I1-md-rows v1, I2-storage-schedule v1, I3-feature-view v1
            (each needs acks from both sides; conflicts -> GATE, ZF rules) [Q10-Q12]

ACCEPTANCE (acceptance/check.py over census + claims; all at one pinned set of landings)
  A1 census.tsv has exactly the yaml's outputs (292).
  A2 statuses partition to 292: computed + sum(unbound by reason class) [Q15].
  A3 each computed row: lineage within I1@<version>, and a value check against the
     oracle on <window> within <tolerance>, with a claims receipt [Q16].
  A4 the I3 query passes dry-run; one-day scan <= <cap> GB [Q6, Q18].
  A5 each unbound row cites a ruling or a gate (no silent NULL).
  DONE = A1..A5 true, confirmed by a fresh Astra reviewer that reads only the ledger
         and re-runs a sample of A3. Anything less is reported as "X/292, not done".

NO-GO    N1 No BigQuery DDL/DML/load outside ledger/writes.tsv, which only I2 and
            RULINGS fill (starts empty; the "smoke slice" in [ZF #2] = GATE G3) [Q12].
         N2 No datapull rerun to emit template columns.
         N3 Do not prompt or steer sessions outside ledger/sessions.tsv; do not touch
            01a0fae3, 01a0fa8c, 01a0f55f [Q20].
         N4 Only ZF changes GOAL, OUTPUT, ACCEPTANCE or NO-GO, and only ZF rules an
            interface conflict (RULINGS.md entry + new sha).
         N5 pi sessions are steered only through pi-web-cli; no pi -p, no intercom.
         N6 The stream opens PRs; each repo's team reviews and merges under its own rules [Q19].

ROLES    Plan/review: openai-codex/gpt-6-astra xhigh. Implement: openai-codex/gpt-6-luna
         xhigh [ZF #7]. No cross-model contests. Parallel: <= <N> disjoint same-model
         units [ZF #6, Q9, Q21].

CTX      Hand over at the next phase boundary once prompt tokens >= 150k; force restart
         at >= 230k (85% of PI WEB's 272k) or at the 2nd auto-compaction [Q22].

AUTONOMY Steward may act alone on anything this file, RULINGS.md or decisions.md
         decides (§5.7), including answering session asks. Must gate: N1, N4, any
         interface conflict or breaking change, new data loads, cost over cap [Q23].
         Digest at <times> SGT; quiet hours <…> [Q24].
```

### 4.3 Interface contracts, as they could have looked on Oct 2

`I1` in full. Facts known on Oct 2 are filled in; the rest are placeholders the interview settles.

```markdown
# INTERFACE I1 md-rows v1   status: agreed   provider: WS-A   consumers: WS-B, WS-C
acks: WS-A <name> <date> · WS-B <name> <date> · WS-C <name> <date>

LOCATION   per I2@v1 (on 10-02: river-runner-343008.Test.datapull_etl)
GRAIN      one row per <ts, venue, symbol[, type]> [Q10]
COLUMNS    schema.json: the 140 fields as of 10-02; v_0..v_120 = the 121 signal names of
           signal.yaml @ 5a602bd (sha256 0a2fc658…), per venue row
COVERAGE   sources.tsv rows marked provided-by-I1, for date 2026-10-01.
           Not provided in v1: Binance spot (36 typed sources), Coinbase USDT-USD.
           -> conflict with GOAL: GATE G1 (load now / typed NULL / approximate) [Q11]
SEMANTICS  BestPrc = <ticker | L2>; type enum <TKR, TRD, LVL, SNP> (ZF supplied on 10-06, #20)
INVARIANTS no column added, dropped or reinterpreted without a new version;
           rows are written only by WS-A's loader as I2 schedules it
STUB       stub/gen.py: N synthetic rows matching schema.json, every v_i populated, stub=true
TESTS      tests.tsv: provider check in <alc-qslite path>; consumer check in
           <alc-cefi-sim-runner path>; both pin this file's sha
CHANGES    v1 2026-10-02 initial (RULINGS R-1)
```

`I2` and `I3` in short:

```markdown
# INTERFACE I2 storage-schedule v1   provider: WS-B   consumers: WS-A (writer), WS-C (reader)
TABLES     I1 rows -> <dataset.table>, partitioned by <date>, clustered by <venue, symbol>
WRITERS    WS-A loader only, append per date partition. WS-C: scratch dataset <x>, row cap <n>.
           Every entry is mirrored into ledger/writes.tsv.
SCHEDULE   <daily at hh:mm UTC>; backfill <policy>; freshness <SLA>
COST       per query <= <x> GB; per day <= <y> GB
STUB       a scratch dataset with the same table names, loaded from I1's stub

# INTERFACE I3 feature-view v1   provider: WS-C   consumer: END CONSUMER
SHAPE      one row per (ts, exch, symbol) [ZF #8]; columns = template feature names;
           BigQuery-illegal names via names.tsv; never opaque alpha_feature_NNNN
SEMANTICS  per census.tsv row: operator, approximation label, error bound [Q14]
STUB       census.tsv plus oracle samples from TenV runtime parquet for <window>
```

The point of the examples: every clause that ZF later had to restate is either in ZF's Oct 2 words or is an interview default ZF would have accepted or corrected on day one. The four interface drift points (D1, D2, D3, D8) each break a line in I1 or I2 that a check can test.

### 4.4 `/goal` becomes a generated pointer

The steward generates every `/goal` from `ledger/sessions.tsv`, the workstream charter and `STREAM.md`; nobody types one. It must be at most 4,000 characters, and in practice is about 700:

```text
/goal Stream qmd-pipeline, workstream WS-C, unit <unit>. Home: ~/Projects/alphalab/streams/qmd-pipeline (STREAM.md sha256:<12>). Interfaces: consume I1@v1, I2@v1; provide I3@v1. After any compaction or resume, re-read STREAM.md, STANDING.md and workstreams/WS-C.md before your next tool call. Unit acceptance: <1-3 lines from the charter>. Forbidden: STREAM NO-GO; never change an interface yourself, propose it in your report. Ask ZF-level questions with ask_user; never act on an unanswered one. Report to reports/<unit>.md with claims rows. Complete only when this unit's census.d and claims rows have receipts.
```

Delivery rules:
- Send it as its own message, starting with `/goal`, while the session is idle.
- Check within 2 minutes that the jsonl has an active `goal-state` whose text contains the `STREAM.md` sha (check H5).

pi-goal re-asserts the objective after every compaction (§3.3), so the pointer and the re-read instruction survive summarization even when the details don't.

### 4.5 Who re-reads what, and when

| Moment | Reader | Reads |
| --- | --- | --- |
| Kickoff | ZF (via Grok Bot) | the full `STREAM.md` candidate, the interface drafts and their digest; ratifies with a marker, like jig's "displayed candidate digest" step |
| Interface version | both sides' owners | the `CONTRACT.md` diff; ack by name |
| Every spawn | new session | the brief, which embeds the stream pointer, `STANDING.md` verbatim, the workstream charter, the interfaces it touches, and the handover if it is a restart |
| After every compaction or resume | session | `STREAM.md`, `STANDING.md` and its charter, prompted by the `/goal` text |
| Every 15 minutes | `steer-check` (script) | the machine-readable files of every stream plus session status and jsonl (§5.3) |
| Every steward wake | steward (fresh Astra session, one stream) | the `STREAM.md` digest, the `steer-check` deltas, and only the rows of the tables those deltas touch |
| Before every relay to ZF | Grok Bot | `digest.md` and `ledger/claims.tsv` only; anything not there is relayed as "unverified" |
| Goal or interface change | ZF | the diff and the new sha |

### 4.6 The kickoff interview

**Protocol**

The Grok Bot runs it because that is where ZF talks. It follows `grilling` (§3.4): the facts come first, decisions go to ZF in rounds, every question carries a recommended answer, and it ends in ratification. It starts from the goal, not from a repo.

0. **Scout (no ZF time).** A read-only Astra pi session writes `facts.md`, a draft `census.tsv` and `sources.tsv` into the new stream home. These cover:
   - the end output census (here the template's 291 + 1);
   - the typed sources (74) and which of them exist in today's data for the date;
   - existing landings anywhere on the host that touch the goal: here PR #654's datapull worker, the `alc-cefi-sim-runner` bq-signal-compiler and its `OPERATOR_OUTLINE.md`, and the `datapull_etl` table and its 140-column schema;
   - live sessions and worktrees touching the area, from `pi-web-cli list`;
   - artifacts that are already rejected.
1. **Restate.** The bot sends ZF: "You want X for consumer C, done when P." ZF corrects it. This is poteto's restate prompt (§3.4).
2. **Rounds.** About 26 questions in 6 rounds. Each one has a recommended answer pre-filled from the scout, so most answers are "ok".
3. **Premortem**, then **ratify**: ZF replies with the marker for the displayed sha. The steward then drafts interface versions for owner acks.

Expected ZF effort is about 6 short replies plus one ratification. Each team's effort is one ack per interface side.

**Questions.** "Pre-empts" names the ZF message from §2.4 the answer would have made unnecessary. The ➡️ lines are the recommended defaults for this stream.

*Round 1: goal and end consumer*
- **Q1 Restatement.** "Every column of `coinbase_dp_fit_30s_alpha.yaml`, queryable in BigQuery, produced by a market-data pipeline from venue data, with the features compiled from the template's DAG." ➡️ Confirm or correct. Pre-empts #7, #8, #13, #15.
- **Q2 End consumer.** Who reads the output, through what (table, view, export), and how often? ➡️ The scout's proposal from consumer code that reads the template features. This fixes I3.
- **Q3 Output census.** "The yaml produces 291 features plus target MicroPrc = 292. Is that the full set, including the target?" ➡️ Yes, all 292. Pre-empts #4, D0.
- **Q4 Shape.** Row grain, identity columns and names ➡️ one row per (ts, exch, symbol) with template feature names. Pre-empts #8 shape.
- **Q5 Done means.** ➡️ A1–A5 as drafted. Partial counts are always reported as "X/292, not done". Pre-empts #4, D4.
- **Q6 Runnable means.** Dry-run only, or a one-day full run, and with what scan cap? ➡️ Dry-run plus one full day ≤ <cap> GB.

*Round 2: workstreams and owners*
- **Q7 Split and owners.** ➡️ WS-A processing (core tech), WS-B storage, schemas and scheduling (infra), WS-C feature layer (quant), each with a named contact who acks interfaces. Pre-empts the split approval in #9 by making it at kickoff.
- **Q8 Existing landings.** The scout lists #654 (WS-A and WS-B), the bq-signal-compiler (WS-C) and `datapull_etl` (I2 candidate). ➡️ Record them as landings; none defines the stream. WS-C code lands in alc-cefi-sim-runner unless the quant team says otherwise. Pre-empts #1.
- **Q9 Parallelism.** ➡️ WS-C starts now against the I1 stub; WS-B plans against I1 v1; at most 3 disjoint units in parallel. Pre-empts #6, #13 "kick them all in parallel".

*Round 3: interfaces*
- **Q10 I1 pin.** "Rows written by the #654 datapull (`signal.yaml` @ 5a602bd, v_0..v_120 per venue row), date 2026-10-01; what identifies a row (ts, venue, symbol, type?)" ➡️ Yes; the identity columns as the scout found them. Pre-empts #8, #11, D2, and possibly the #20 enum.
- **Q11 Source coverage (interface conflict).** "The goal needs 74 typed sources. 36 Binance spot sources and Coinbase USDT-USD are not in I1. Options: (a) WS-A loads them now, (b) typed NULL plus a gap list, (c) approximate." ➡️ (a) load now; (b) until the load lands. Pre-empts #18, #19, D8. This is the four-day gate, asked on day one.
- **Q12 I2 storage and writes.** Which dataset and tables, who writes, in what mode, partitioning, schedule. ➡️ WS-A's loader is the only writer of I1's table; WS-C writes only to a scratch dataset with a row cap; the Oct 2 "smoke slice" becomes a named table. Pre-empts D1, D3.
- **Q13 Forbidden inputs for WS-C.** "Not allowed: rows WS-C writes, datapull reruns, TenV runtime outputs?" ➡️ Yes; TenV is allowed only as the oracle in A3. Pre-empts #8, D3, D4.
- **Q14 WS-C method and approximations.** ➡️ Features generated from the yaml through an operator→SQL table, not hand-written per feature; approximations (EMA, as-of tolerance) allowed if labelled per census row with an error bound. Pre-empts #9, #13.

*Round 4: acceptance and verification*
- **Q15 Partition.** ➡️ Unbound reason classes are fixed (missing-source, unsupported-op, binder, other), and the counts must sum to 292. Pre-empts #17, D7.
- **Q16 Oracle and tolerance.** ➡️ Compare N sampled rows against TenV runtime parquet for the same window, using relative tolerance <t>. Pre-empts #10, #12.
- **Q17 Scope exclusions.** "Any operator or source deliberately out of scope?" ➡️ None. Every exclusion becomes a census row with an owning workstream. Pre-empts #20 LeadSignal, D6.

*Round 5: permissions and invariants*
- **Q18 Cost caps.** ➡️ Per query ≤ <x> GB, per day ≤ <y> GB.
- **Q19 Git and review.** ➡️ Each landing is a draft PR in its own repo, reviewed and merged by that team; the stream never merges; repo rules win on code.
- **Q20 Don't-touch list.** ➡️ The sessions and worktrees found by the scout.

*Round 6: operations*
- **Q21 Roles.** ➡️ Astra xhigh plans and reviews; Luna xhigh implements. Pre-empts #7.
- **Q22 Context policy.** ➡️ Hand over at 150k tokens at a phase boundary; force restart at 230k or the 2nd compaction. Pre-empts #6.
- **Q23 Autonomy.** ➡️ The steward acts alone within the stream contract, answers session asks the contract covers, restarts and resends; everything in §5.7's escalation list goes to ZF. Pre-empts #7 "drive this till completion" and #15 "march forward".
- **Q24 Cadence.** ➡️ Digest at 09:00 / 13:00 / 18:00 SGT, gates immediately; quiet hours 00:00–08:00 unless a gate deadline falls inside them. Pre-empts #3, #5, #14, #16.

*Premortem*
- **Q25** "It is day 4 and you are unhappy. What happened?" The bot seeds this campaign's real failures as prompts: stand-in shipped, shared-table write, counts that don't add up, hidden exclusion, a missing source nobody raised.
- **Q26 Reference artifacts.** "Accepted references and known-bad artifacts to never reuse?"

---

## 5. The steering loop

### 5.1 Components

| Component | What it is | LLM? | Steers? |
| --- | --- | --- | --- |
| `steer-check` | One read-only Python script on the host for all streams. It reads stream homes, `pi-web-cli status`, jsonl tails and git, and writes each stream's `live/steer-state.json` and `live/deltas.jsonl`. | no | no |
| `steer-send` | Runs queued actions through `pi-web-cli`, logs them to `live/steer.log.tsv`, updates the ledger at state transitions, and verifies delivery on the next tick. | no | yes, mechanically |
| steward | A fresh Astra xhigh pi session per wake, **one stream per wake**, with its cwd in that stream's home. It reads the deltas and `STREAM.md`, and writes actions, gates, decisions, interface drafts and standing orders. | yes | through `steer-send` |
| Grok Bot (MMDev) | ZF's interface. It runs the kickoff interview, ratification, gate and ruling relay, and the digest. | yes | no; it no longer types goals or steers |

The split follows §3.7. The script watches everything and never forgets. The LLM judges only deltas, with a clean slate each time, Ralph-style. The coordinator never edits code.

### 5.2 Cadence

- `steer-check` runs every 15 minutes, 24/7, while any stream has an active landing. It needs no model quota.
- A stream's steward wakes when:
  - a delta for that stream reaches "steer" or "gate" severity;
  - two hours pass with any of its landings active, for a review;
  - ZF sends a message about that stream.
- A wake is a new pi session that does one job and ends, so its context never grows.
- The digest goes to ZF at Q24 times. A gate goes out at the next Grok Bot poll; the bot reads `gates.md` and `digest.md` over SSH, which is the same access the existing routine uses.
- Every gate carries a default and a deadline, so sessions keep working on the default ("never block on the human").

### 5.3 What `steer-check` reads each tick

| Source | Fields |
| --- | --- |
| `pi-web-cli status <sid>` for every session in any `ledger/sessions.tsv` | `isStreaming`, `isCompacting`, `isBashRunning`, `pendingMessageCount`, `queuedMessages`, `contextUsage.tokens`, `model.id`, `thinkingLevel`, `pendingAsk`, `pendingDialogs` |
| session jsonl (tail since last offset) | `goal-state`, `compaction` (count, summary length), `goal_*` tool calls, `pi-web.ask.*`, bash tool-call text, the last assistant timestamp |
| stream homes | `STREAM.md` sha; workstreams; interfaces and their `tests.tsv`; census; sources; ledger; gates |
| git (read-only), per landing | branch heads, paths changed since the last tick, vendored contract shas, the `.stream` pointer |
| BigQuery metadata (read-only) | field count, row count and last-modified time for tables named in any I2 or `writes.tsv` |
| pi-subagents | child run status for workflows a unit reports as "done" |

### 5.4 Checks

Each row says what it would have caught in this campaign.

| ID | Trigger | Action | Historical hit |
| --- | --- | --- | --- |
| H1 delivery | A steer has been queued more than 10 minutes (`queuedMessages`, or `pendingMessageCount > 0` across two ticks). | Resend with `streamingBehavior: "steer"`. For stop/park, use `stop` or `abort`. | 11 of 22 late; 8 steers to `01a0fd17` stuck for up to 4.2 hours |
| H2 park verified | A unit is marked parked but `isStreaming`, a queued message, or new tool calls exist after the park. | Block the replacement spawn; `stop` the old session; re-check. | `01a0fb7a` wrote 432,000 rows while "parked" |
| H3 pending ask | `pendingAsk` is present. | Steward answers if `STREAM.md`, `RULINGS.md` or `decisions.md` decides it, citing the clause; otherwise mirror it to `gates.md`. | `catalogue_scope_and_write_authorization` sat 5 hours and was closed unanswered; N1 answers it ("no") |
| H4 model | `model.id` or `thinkingLevel` differs from the ledger. | `/model` while idle, then re-check. | `/model luna` queued 37 minutes, with no `model_change` afterwards |
| H5 goal active | No active `goal-state` containing the `STREAM.md` sha within 2 minutes of spawn. | Resend `/goal` standalone while idle. | 4 of 4 stream/stitch sessions never entered goal mode |
| H6 context | Tokens ≥ 150k at a phase boundary; or ≥ 230k; or the 2nd auto-compaction. | Hand over or force a restart (§5.6). | 213%, 243%, 919k peak; 9 compactions |
| H7 liveness and quota | Streaming with no new jsonl entries for 30 minutes; or `usage_limited`. | Probe read-only; for quota, mark "waiting on quota", don't respawn, tell ZF once. | 10-03 03:37 limit on both models |
| H8 child receipts | A unit says its children are done but the runs aren't terminal. | Steer: "children still running: <ids>". | `await runs.all` returned launch receipts |
| D-a goal drift | The active objective is not the generated pointer for the current sha. | Replace it with the generated pointer. | 7 hand-written objectives, 3 of which introduced drift |
| D-b lineage | Deliverable SQL references anything outside I1 (`alpha_feature_sample`, `alpha_v_`, `materialized_runtime`, TenV paths). | Block "done"; steer; record the stand-in. | `materialized_runtime.sql` relayed as "ready" |
| D-c shared write | Table fields, rows or modified time change outside `writes.tsv`; or DML/DDL/`bq load` text appears in a bash call. | Immediate gate to ZF; `stop` the unit; freeze further writes. | 140→432 fields at 00:52; MERGE of 432,000 rows at 01:17 |
| D-d partition | Census statuses don't sum to the census size, or a relayed number isn't in `claims.tsv`. | Block the relay; steer the owning workstream to reconcile. | 78 / 214 / 291 / 295 |
| D-e exclusions | Any unit's exclusion list names something with no owning workstream in the census. | Steer the owner to add rows; flag in the digest. | LeadSignal, 18 features |
| D-f sources | A source in `sources.tsv` is absent for the date. | Gate at kickoff (Q11); recheck daily. | USDT-USD and Binance spot gap, known 10-02, decided 10-06 |
| D-g over-correction | A session or brief adds a forbidden item that isn't in `STREAM.md`. | Revert the brief; steer: "only ZF changes NO-GO (N4)". | "Do NOT use the alpha template" on 10-05 |
| I-a interface edit | A landing's diff changes an interface artifact (I1 schema, `signal.yaml`, loader output columns, table DDL) with no matching interface version in the home. | Block "done"; steer the unit to propose a version; flag both sides' owners. | No git-side case found; D1's change was made in BigQuery and is caught by D-c and I-b |
| I-b cross-workstream write | A unit writes a resource its workstream doesn't own under I2. | `stop` the unit; gate to ZF. | Consumer-side work wrote I1's table (D1) and then read it back as input (D3) |
| I-c contract skew | A team's vendored contract sha differs from the agreed version, or a contract test or stub run fails. | Steer the owning workstream; digest flag to the team. | n/a (no contracts existed) |
| I-d interface conflict | A consumer needs something the provider's current version excludes, or a session's ask or `goal_wait` names such a gap. | Gate to ZF with options and a default; record the ruling; bump the version. | `01a0fb7a`'s `goal_wait` at 21:35 named the absent inputs; ruled 10-06 14:51 (#19) |
| X1–X4 cross-stream | §1.8 | §1.8 | n/a (one stream) |

### 5.5 Verify before relaying

These rules apply to the Grok Bot and the steward.

- **R1 Numbers.** Relay counts only from `census.tsv` or `claims.tsv` rows that have a receipt, and always show the partition. ("78 computed + 122 spot-only + 37 spot+other + 19 USDT-USD + 18 LeadSignal + 9 MicroPrc + 2 BestPrc + 6 set F = 291 features; target unbound": the reconciled breakdown, `AUDIT/stitch-stream-20261005/ZF-SOURCE-OPERATOR-RECONCILIATION.md`.)
- **R2 "Done".** Say done only when A1–A5 evaluate true by script. Otherwise relay "X/292, not done because …". Any D-b hit is called a stand-in.
- **R3 Probes.** When ZF asks a factual question ("halves?"), answer "checking" and run a bounded read-only query or read a receipt. Never answer yes or no from memory.
- **R4 Coverage.** Every status lists exclusions and census rows that have no owning workstream.
- **R5 Provenance.** Every artifact relayed carries its path, its sha, its landing and the session that produced it.

### 5.6 Restart with handover

1. **Checkpoint.** The outgoing session writes `handover/<unit>-<n>.md`: intent first, then `STREAM.md` sha, interface versions, done-with-receipts, open gates, in-flight work and next move. This follows `pause-safely`. The steward checks that every "done" claim has a claims receipt.
2. **Stop.** `steer-send` sends the park message with `streamingBehavior: "steer"` (or `stop`), then waits for H2 to pass: not streaming, no queue, no new tool calls.
3. **Spawn.** `pi-web-cli spawn <cwd>` in the landing's worktree, then `/model` while idle, checked by H4.
4. **Load.** Send the poteto read prompt (`prompts/poteto.md`), then the generated `/goal` standalone, checked by H5.
5. **Brief.** Send GOAL, SCOPE, CONTEXT (stream pointer and handover path), ACCEPTANCE, VERIFY, TIMEBOX, FORBIDDEN, REPORT and STANDING, with STANDING pasted verbatim. This is orchestrate's brief template.
6. **Restate check.** The first reply must restate the unit's intent and the interface versions it consumes and provides. The steward compares it with the home and corrects mismatches before work starts.
7. **Ledger.** Update `ledger/sessions.tsv`. The old session stays idle as history and is never resumed to check on it.

### 5.7 Act alone or escalate

| The steward acts alone | Escalate to ZF through `gates.md` (options, recommended default, deadline) |
| --- | --- |
| Anything `STREAM.md`, `RULINGS.md`, `decisions.md` or `STANDING.md` already decides | Any change to GOAL, OUTPUT, ACCEPTANCE or NO-GO |
| Resend, model fix, goal re-activation, restart with handover | Any shared write not in `writes.tsv`, or any write already observed (D-c, I-b) |
| Answering a session's ask when the stream contract covers it, citing the clause | An interface conflict (I-d), a breaking interface change, or X2/X4 across streams |
| Recording an interface version that both sides' owners acked | New data loads (Q11-type) |
| Blocking a relay that fails R1–R5 | Cost over a cap |
| Adding a STANDING line (ZF approves at the next digest) | Reality contradicts the stream contract (for example, missing input) |
| Starting the next unit on the frontier | A team rejection that blocks the goal; domain-semantic questions (BestPrc ticker vs L2); a check that fails twice after a steer |

It never answers a human gate itself (wayfinder) and never relaxes a predicate (autonomous-run).

### 5.8 Steer message format

Keep steers short, cite the check and the clause, and never restate the whole goal:

```text
[steer H3 · STREAM N1, I2@v1 WRITERS] Answer to your ask catalogue_scope_and_write_authorization: no BigQuery writes; WS-C writes only to the I2 scratch dataset, and writes.tsv has no entry for datapull_etl. Output contract = census.tsv (292 rows). Mark sources missing from I1 as unbound:missing-source; gate G1 asks ZF about loading them. Continue.
```

### 5.9 What `pi-web-cli` needs (proposal, separate PR)

Today `pi-web-cli` (`~/.local/bin/pi-web-cli`, not versioned in this repo) exposes only `list`, `spawn`, `prompt`, `status` and `commands`. The PI WEB server already has routes for everything below (`dist/server/sessions/sessionRoutes.js`), so this is CLI work only:

- `prompt --steer`, sending `streamingBehavior: "steer"`. This is the most important single fix: it closes H1.
- `stop`, `abort`, `queue`, `queue-clear`, needed for H2.
- `asks`, `answer`, for H3, using `/ask/submit` and `/ask/cancel`.
- `model`, `thinking-level`, for H4.

### 5.10 How the steerer itself can fail

- **False positives.** Cap at one steer per check per unit per hour. Repeats escalate instead of re-sending, and every steer is logged for the pilot metric.
- **Steward drift.** It is stateless: each wake is fresh, covers one stream, and reads only files.
- **Quota.** The steward spends Astra quota on the same ChatGPT plan that ran out on 10-03. Wake only on deltas, and log tokens per wake.
- **Loops.** `steer-send` never sends to a steward session, and never sends to a session that isn't in some stream's `ledger/sessions.tsv`.
- **Cross-stream blindness.** One `steer-check` owns all streams, so X1–X4 never depend on two stewards talking to each other.

---

## 6. Placement of the steering agent

| Option | Strengths | Weaknesses, verified |
| --- | --- | --- |
| **A. Grok Bot plus routine (today, extended)** | ZF already talks to it; it already holds SSH and `pi-web-cli` access. | Its memory is off-box and unreadable by sessions, and its transcript store was reinitialised (MMDev account). The routine prompt can't be printed, so it can't be audited. It covers only weekday daytime. SSH is flaky ("options-01 SSH flaky; Twingate restarted per call", transcript 10-02 13:08). The bot authored the drift (§2.7). |
| **B. Cursor Project coordinator on the `pistack` worker** | Native shared context, subscriptions and an agents UI (§3.8). A Project's one Workspace repository could be the neutral stream repo, since the coordinator doesn't write code. | Projects run "on its own computer in the cloud", and running on a self-hosted worker is undocumented. Shared-context format and re-read semantics are undocumented. It is beta. The coordinator runs a Cursor model, not Astra, which breaks "planning and review on Astra" and adds a second model type to steering. |
| **B′. Cursor cloud agent on the `pistack` My Machines worker with a timer** | Documented: long-lived worker, shell on the host, timer subscriptions (§3.8). | Same model problem as B. A My Machines agent takes one repo. Subscriptions last at most 180 days. Model calls and the timer wake both depend on Cursor's cloud being up. |
| **C. One long-lived Astra pi steward session per stream** | Right model; reads files directly; can self-wake with `goal_wait resume_after_ms` (≥10 s) (pi-goal README). This is `pil`'s controller shape (§1.10). | It is a pi session, so it grows context and compacts, and its goal-text and timer fail the same ways the campaign did. A single point of drift. |
| **D. Hybrid (recommended)** | The script does the watching across all streams (no memory and no model); a fresh Astra steward per stream per delta does the judgment; the Grok Bot does ZF-facing work; the stream home does the remembering. Matches §3.7 and ZF's model rules. | More parts. Needs a host timer (a systemd user timer or a tmux loop; not installed by this doc). Needs the §5.9 CLI verbs. |

**Why D.**
- Each failure in §2.7 and §2.8 maps to a part of D that removes it:
  - authored drift → generated pointer;
  - queue lag → `--steer`;
  - unverified relays → ledger-only relays;
  - unanswered asks → H3;
  - unowned interfaces → I1–I3 with owners, plus I-b and I-d;
  - overnight blind spot → 24/7 script.
- Options A, B and C each keep at least one of those failures:
  - A keeps the bot as the source of truth.
  - B adds a non-Astra brain and undocumented sync.
  - C makes the steerer itself drift.
- D keeps every rule in the brief: Grok Bots stay high-level, pi is steered only through `pi-web-cli`, and planning and review stay on Astra.

**What would change this.**
- If Cursor documents Projects on self-hosted workers and ZF accepts a Cursor-model coordinator, then B could take over the Grok Bot's ZF-facing role with the stream repo as its Workspace. The stream home stays the source of truth either way.
- If ZF prefers fewer moving parts, C plus `steer-check` is the fallback, with the steward restarted under its own H6.

---

## 7. Is the polyrepo layout "anti-agentic"?

**Short answer.** Not by anything Pocock or poteto have published that I could reach. Neither takes a position on monorepo versus polyrepo. What they do say concerns properties any layout can have or lack: fast deterministic checks, navigable structure with small interfaces, short agent docs with pointers, and mistakes fixed in the environment rather than in prompts. A layout split by team can have all of these.

On this host the agent-hostile parts are specific, and each can be fixed without a migration:
- the data edges between repos are unversioned;
- one key repo has no agent doc and no test CI;
- there is no home above the repos for cross-repo intent;
- ownership isn't written down.

A monorepo would not have prevented the case study's interface failures, because those edges live in BigQuery and a yaml mapping, not in a git tree (inference).

### 7.1 What they actually say

**Pocock**
- **No position on repo layout.** No dictionary entry covers monorepo versus polyrepo; I read all 71 entries in https://github.com/mattpocock/dictionary-of-ai-coding/tree/main/dictionary. The one mention is a usage example in "Context window": "Can I just paste the whole monorepo into the prompt?", answered with "Pick the files the task touches, leave the rest behind a tool call." (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/Context%20window.md)
- **Monorepo as a doc-layout case only.** His setup skill says monorepo signals "are present only in a genuinely large multi-package repo; their absence means single-context, which is almost every repo". Only then does it offer "a root `GLOSSARY-MAP.md` pointing to per-context `GLOSSARY.md` files" (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/setup-matt-pocock-skills/SKILL.md). His README says to "run it once per repo" (https://raw.githubusercontent.com/mattpocock/skills/main/README.md).
- **AX.** "When the same agent performs well in one repo and badly in another — same model, same harness — the difference is usually AX. The instinct is to blame the model or rewrite the prompt; the fix is more often in the repo." Its dimensions include "Fast, deterministic automated checks — types, tests, lints — that the agent can self-correct from without a human" and "A codebase the agent can navigate without reading everything: predictable structure, a lot of behaviour behind small interfaces, names that say what things do". It adds: "Humans tolerate tribal knowledge, slow CI, and "ask Sarah about the billing module"; agents can't." (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/AX.md)
- **Automated checks.** "An agent in a repo with strict types, a fast test suite, and a linter catches most of its own mistakes before you see them", but "a check only catches what it asserts" (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/Automated%20check.md).
- **Agent docs.** On AGENTS.md: "Short and declarative — it's a brief, not documentation." and "a long AGENTS.md both costs tokens and dilutes itself" (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/AGENTS.md.md). On pointers: "A pointer needs two parts to work: a stable path, and enough description for the agent to know when following it is worth it." (https://raw.githubusercontent.com/mattpocock/dictionary-of-ai-coding/main/dictionary/Context%20pointer.md)
- **Interfaces.** "Design deep modules: a lot of behaviour behind a small interface, placed at a clean seam, testable through that interface." The interface is "everything a caller must know to use the module correctly: the type signature, but also invariants, ordering constraints, error modes, required configuration, and performance characteristics." (codebase-design, §1.1)
- **Tests.** "Tests verify behavior through public interfaces, not implementation details." and "Test only at pre-agreed seams." (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/tdd/SKILL.md)
- **Enforced boundaries.** His in-progress `setup-ts-deep-modules` makes each package's entry points the only way in, "then proves the rules bite". It adds a pointer from AGENTS.md: "One line is enough… This is what makes an agent discover the boundary rule instead of tripping over it." (https://raw.githubusercontent.com/mattpocock/skills/main/skills/in-progress/setup-ts-deep-modules/SKILL.md)
- **Architecture reviews.** `improve-codebase-architecture` says "The aim is testability and AI-navigability", and "ADRs in `docs/adr/` record decisions this command should not re-litigate." (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/improve-codebase-architecture/SKILL.md)
- **His own repos.** His internal tooling lives in a repo named `total-typescript-monorepo`, described as "The home of all Matt's internal tooling" (https://github.com/mattpocock/total-typescript-monorepo). That is a fact about his repos, not advice; I found no text where he recommends a monorepo for agents.

**poteto**
- **No position on repo layout.** No pstack file mentions monorepo, polyrepo, multi-repo or cross-repo (grep of all 164 files on `main` at commit `df58112`, https://github.com/cursor/plugins/tree/main/pstack, and of the installed v0.15.13 copy). Neither do "Loops You Can Trust" (§3.6), her 2026-10-05 constraints post, or the captions of her "2000 PRs" talk. The interview captions contain neither word, and "repo" appears only in Pocock's question about triggers "in your repo" (https://youtube-distilled.com/watch/MN9dGgmLyso). Her X timeline could not be searched (§3.9), so this means "not found", not "never said".
- **Constraints are a scale answer, not a layout answer.** "large companies have had to solve this problem since even before agents. because before you had agent slop, you had human slop. … the solution to this was constraints: lint rules, smarter compilers and diagnostics, high quality tests, investments into observability, and so on" (https://x.com/poteto/status/2106916667599278365, via https://api.fxtwitter.com/poteto/status/2106916667599278365).
- **The codebase is the memory, with one paved path.** From the "2000 PRs" talk (auto-captions, https://youtube-distilled.com/watch/NjoZoUm85x0):
  - "the code base is really like the best form of memory because agents love to extend existing patterns that they see."
  - "We want to keep or enforce a single paved path for most blessed patterns. … there should be enough guidance in the code base in CI in lint rules so that the agents are guided to … follow that pat[tern]".
  - "whenever you see tech debt or bad patterns, your instinct should be I need to write a lint rule against it."
  - "We have a lot of conventions about where code should live."
- **Same signals as humans; scripts before agents.** "agents should get the same signals human engineers use to write good code: compiler diagnostics, lints, static analysis, and so on." And: "If a script can do it deterministically, use the script. Agents are useful for the fuzzy parts". ("Loops You Can Trust", §3.6)
- **Shared code starts from its README.** "For certain kinds of work, like creating shared code or packages that others will use, I am a big believer in readme driven development. … you start with describing the APIs to a hypothetical user, and work backwards to the implementation and architecture." (Complete Guide Pt. 2, https://threadnavigator.com/thread/2097732320606507506/)
- **Migrate callers, then delete.** "Migrate callers and delete the old API in the same wave instead of preserving compatibility layers." (https://github.com/cursor/plugins/blob/main/pstack/skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md). Her StyleX loop "searches the repository for behavioral, test, automation, and consumer dependencies" before deleting a class ("Loops You Can Trust"). Both assume every caller is visible and editable together, which is not true by default across repos owned by different teams (inference). §7.3 and §7.4 deal with this.
- **A prompt for exactly ZF's question.** "/poteto-mode refactor this repo so its architecture is more agent friendly. use /correct and /architect on past commits and review comments to find the mistakes agents make most here. use /recall for context from past chats. answer open questions with prototypes instead of asking me. come back with a plan backed by real data." (https://github.com/cursor/plugins/blob/main/pstack/docs/guide/07-overnight.md). Her method starts from the mistakes agents actually make in the repo, not from a preferred layout.
- **Fix ranking.** "When you correct agents for the same mistake again and again, the fix belongs in the repo, not in your next prompt." In order: "Make the mistake impossible with architecture or a better data structure"; "Block it with types, or with a lint or CI check whose error names the fix"; "Catch it with a test"; "Write it down as a doc or agent rule. Nothing fails when an agent skips a rule, so this comes last." Also: "Human review isn't on the list." (https://github.com/cursor/plugins/blob/main/pstack/docs/guide/09-make-it-yours.md)
- **Design for the agent that only sees one file.** `/correct`: "Assume every contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles. Design the repo so a change that looks right from one file is right for the whole repo." Also "Replace hand-synced lists with one source of truth.", "Run the same command locally and in CI.", and "keep a table in the agent instruction file that pairs each rule with what enforces it" (https://github.com/cursor/plugins/blob/main/pstack/skills/correct/SKILL.md). `/architect` repeats the agent assumption and adds "Prefer the design that hides more complexity behind a smaller, simpler public surface." (https://github.com/cursor/plugins/blob/main/pstack/skills/architect/SKILL.md)
- **Boundaries.** "Concentrate guards at system boundaries (CLI, config, network, external APIs)", "Parse raw data into domain types at the boundary", and "Expose domain concepts, not the boundary's private representation." (https://github.com/cursor/plugins/blob/main/pstack/skills/principle-boundary-discipline/SKILL.md)
- **Tests.** "before you keep a test, ask whether it would still pass if every function it imports returned `undefined`. If yes, it observes no behavior and cannot fail for a defect." (https://github.com/cursor/plugins/blob/main/pstack/skills/principle-test-behavior-not-implementation/SKILL.md)
- **Verification.** "Every serious project needs a scripted way to drive the real app and prove behavior". Her skill generates that as a project-local skill per repo (https://github.com/cursor/plugins/blob/main/pstack/skills/create-verification-skill/SKILL.md).
- **In the interview** (auto-captions; speaker inferred from turn-taking; https://www.youtube.com/watch?v=MN9dGgmLyso via youtube-distilled):
  - About 30:10–32:12: her internal framework is built so "there's really only one way to do something", and "every feature has its own directory". On each agent mistake: "how do I turn this into a lint rule? How do I make it so that the code base makes this impossible?"
  - About 24:21, on "going from one technology to another, especially one that is better for agents": "a lot of how you can do that migration is, I think, through things like scripts and CLIs, like the deterministic parts like code mods".
- **Bodies of work.** "Give each body of work its own Project, such as a feature, a migration, a perf push, or a tech-debt cleanup." (07-overnight). Combined with one Workspace repository per Project (§3.8), today's Cursor shape is one body of work per repo. Neither source addresses work that spans repos (inference).

### 7.2 Where this layout is hard for agents today

| What the sources name | This host (read-only survey) | Gap |
| --- | --- | --- |
| Fast, deterministic checks per repo | alc-qslite: 563 test files and many build/test workflows. alc-tenv: 448 test files and workflows. alc-cefi-sim-runner: 51 test files (58 in the bq-signal-compiler worktree), but its only workflows are `claude-code-review.yml` and `claude.yml`, so there is no test CI. | alc-cefi-sim-runner |
| Short agent doc with pointers | `AGENTS.md`: alc-qslite 69 lines (`CLAUDE.md` is `@AGENTS.md`), alc-tenv 9, alc-deploy 28, alc-standardization_utils 74 plus nested files. alc-cefi-sim-runner has none. | alc-cefi-sim-runner; no repo points to cross-repo contracts |
| Small interfaces at the edges | Code edges are versioned packages (§1.9). Data edges are not: the `datapull_etl` schema and the `signal.yaml` v_i mapping have no version or owner. | the data edges where D1, D2, D3 and D8 happened |
| One source of truth | No workspace manifest; `~/Projects/alphalab/README.md` is 24 bytes. About 20 `alphalab-hq` repos are checked out side by side, with many worktrees (§1.8). Cross-repo intent lived in one worktree's `.audit/`. | a home above the repos |
| Ownership a reader can see | No CODEOWNERS in alc-qslite, alc-tenv or alc-cefi-sim-runner. alc-flows is `python/alc-flows` inside alc-qslite, with its own path-filtered workflow. If the §2.1 pairing holds, two teams own paths in one repo and nothing says so. | ownership not encoded |
| Tooling | Cursor-hosted cloud agents and automations support multi-repo environments, and the API takes up to 20 repos. A Cursor Project picks one Workspace repository, and a My Machines agent takes one repo; several repos on a self-hosted worker need an any-repo pool (§3.8). | partial on this host |

### 7.3 Option K: keep repos split by team, add a workspace repo and contracts at the edges

1. **A neutral workspace repo**, either the same repo as the stream homes (§1.5) or a sibling. It holds:
   - `manifest.tsv`: repo, remote, pinned ref (sha or release tag), checkout path, and compatibility notes taken from real pins (for example, alc-cefi-sim-runner needs `alc-qslite-connector[hist]==8.0.0`);
   - a small `ws` script: `ws sync` checks out or updates repos side by side under `~/Projects/alphalab/`, and `ws status` reports where checkouts differ from the manifest;
   - `streams/` (§1.6);
   - `contracts/` for graduated data contracts that outlive a stream (§1.9).
2. **Versioned contracts at the edges, with contract tests.** Code edges already have package versions. Add the data edges: I1 (market-data rows) and I2 (storage and schedule).
   - The provider's test in the producing repo checks real output against the contract.
   - Consumers' tests run against a stub generated from the contract.
   - Both pin the contract sha.
   - The contract's `CONTRACT.md` is written first, as the README for the edge, in the spirit of poteto's readme-driven development for "shared code or packages that others will use".
   - This applies Pocock's "The interface is the test surface" and poteto's "Parse raw data into domain types at the boundary" to data shared between teams (inference).
   - **Old versions are deleted, not kept.** Across team repos, one PR cannot migrate every caller, so a contract bump briefly leaves two versions live. That is the compatibility layer poteto's migrate-callers principle warns against. Keep it bounded: `CONTRACT.md` already lists every consumer, each consumer's migration is a landing in its own repo (`ledger/landings.tsv`), and the old version is deleted when the last consumer's vendored copy moves to the new sha. The steward flags an old version that is still live after its consumers have moved (inference; a cross-repo form of her rule).
3. **Short agent docs per repo.** One `AGENTS.md` per repo that is "a brief, not documentation":
   - build and test commands;
   - hard constraints;
   - one-line pointers such as "cross-repo data, schemas or BigQuery tables: read `<workspace>/contracts/<edge>.md` first";
   - poteto's rule table (each rule and what enforces it), started when the first rule is added.
   
   Start with alc-cefi-sim-runner. Each team writes and reviews its own.
4. **Fast checks per repo, plus one integration check.**
   - Each repo keeps its own CI; alc-cefi-sim-runner gets a workflow that runs its existing tests.
   - One integration check in the workspace repo checks out the manifest's pins and runs the contract chain on stubs: I1 stub, then WS-C compile, then SQL dry-run.
   - Where credentials allow, it also runs the stream's end-to-end acceptance on one day. Credentials stay on the runner, never in the repo.

### 7.4 Option M: migrate to a monorepo

**What it buys**
- One checkout and one search scope for agents.
- Atomic cross-repo code changes in one PR, and one CI view.
- poteto's migrate-callers-then-delete fits directly: every code caller is in one tree, so an old API can go in the same wave (§7.1).
- A natural fit for one-repo tools (a Project's single Workspace, My Machines agents).

**What it costs here**
- About 20 repos with independent histories, mixing .NET and Python, to import.
- Packages are published and consumed by version (NuGet; `alc-qslite-connector`). They would need a new release model, or would keep publishing from inside the monorepo, which keeps the version edge anyway.
- Team-owned review still needs CODEOWNERS and path-filtered CI. `python/alc-flows` inside alc-qslite already shows that pattern at small scale.
- A much larger tree to navigate. Pocock's answer to "paste the whole monorepo" is to pick the files the task touches, and his setup skill switches to a multi-context glossary map for genuinely large multi-package repos.
- Migration work. poteto's advice is to migrate with deterministic scripts and codemods, which lowers the cost but doesn't remove the cross-team coordination.

**What it does not fix**
- **Data edges.** The `datapull_etl` schema and rows live in BigQuery. A monorepo cannot make a BigQuery schema change atomic with code, and cannot stop a session MERGEing into a shared table. D1, D2, D3 and D8 could happen the same way.
- **Goal drift.** D0 and D4–D7 come from the stream's goal and from relays, not from repo layout.
- **Several streams on one tree.** A monorepo still needs stream homes and the X1–X4 checks.

### 7.5 Comparison

| | K: split repos + workspace repo + edge contracts | M: monorepo |
| --- | --- | --- |
| Team ownership and review | Natural: one repo per team | Needs CODEOWNERS and path rules everywhere |
| Cross-repo intent | Stream homes in the workspace repo | Still needs stream homes |
| Code edges | Versioned packages, as today | Atomic changes; versions optional |
| Data edges (where the case study broke) | Versioned contracts with provider and consumer tests | The same work is still needed |
| Agent context | Short `AGENTS.md` per repo plus pointers to contracts | One tree; needs multi-context docs and progressive disclosure |
| Checks | Fast per repo plus one integration check at pins | One CI that needs path filtering to stay fast |
| Cursor tooling | Cursor-hosted multi-repo environments; on this host, side-by-side checkouts or an any-repo pool | Fits one-repo tools |
| Removing an old API | Bounded two-version window per contract bump, tracked in the ledger | One wave, as poteto's principle asks, for code edges only |
| Migration | Small, incremental, one team at a time | Large, cross-team, all at once |
| Case-study failures addressed | Interface failures through I1/I2, the writes list and I-b/I-d; goal failures through the stream home | None by itself |

### 7.6 Recommendation

Keep the repos split by team and take option K. The polyrepo layout is not what made the campaign fail; the unowned, unversioned data edges and the missing home above the repos did (§2.2). That is inference from the case study. It is consistent with what both authors say about checks, interfaces and agent docs, but neither has written about this layout.

**Order of work.** Each item is its own PR, in the repo of the team that owns it:
1. alc-cefi-sim-runner: a short `AGENTS.md`, and a test workflow that runs its existing tests.
2. I1 as a versioned contract: a provider test where the datapull worker lives (alc-qslite, `python/alc-flows/alc-etl-datapull/`), and a consumer stub test in alc-cefi-sim-runner.
3. The workspace repo with `manifest.tsv`, `ws sync`/`ws status`, and `streams/`.
4. The integration check at manifest pins.
5. CODEOWNERS for `python/alc-flows`, if infra owns it.

**Before going further,** run poteto's own method: `/correct`-style mining of these repos' past commits, reverts and review comments, plus the campaign transcripts, to find the mistake classes and fix each at the highest level that works. Her prompt asks for "a plan backed by real data"; until that runs, this section is a desk estimate.

**When to reconsider M.** Both signals are measurable from `ledger/landings.tsv`:
- coordinated merges across repos on code edges become a large share of landings (ZF sets the threshold);
- the integration check keeps breaking on version skew between pinned repos.

---

## 8. Pilot plan

### Phase A: rules-only replay (no LLM, no live sessions)

- **Build.**
  - A scratch stream home for `qmd-pipeline`, written using **only ZF's Oct 2 words** (#1–#7) plus the §4.6 defaults: `STREAM.md`, I1–I3 at v1 with what was knowable on Oct 2, workstream charters, and `census.tsv` and `sources.tsv` rebuilt from the yaml and the input schema.
  - `ledger/sessions.tsv` and `landings.tsv` reconstructed for the 11 campaign sessions, with each session assigned to the workstream its work served.
  - `steer-check` running in replay mode over copies of the campaign jsonl. Queue state comes from submit and delivery timestamps; tool calls come from the jsonl.
- **Measure.** For each check, the first tick it fires, compared with when ZF or anyone else noticed.
- **Pass** (all of the following):
  - H1 flags at least 9 of the 11 late steers within one tick.
  - H2 fires on `01a0fb7a` before 10-03 00:52.
  - H3 fires by 10-02 21:38.
  - H5 flags 4 of 4 sessions.
  - D-c and I-b fire by the 01:00 tick.
  - I-d fires by the 21:45 tick on 10-02, from the `goal_wait` reason.
  - D-b fires within one tick of `materialized_runtime.sql` appearing. It was relayed as "ready" at 03:31.
  - D-d fires before the 10-06 12:19 relay.
  - D-e fires on 10-05.
  - D-f fires at kickoff.

### Phase B: steward replay at checkpoints (same model, Astra xhigh)

- **Checkpoints.** One just before each of the 14 substantive ZF messages and each of D0–D8 (about 22).
- **Snapshot** at each checkpoint:
  - the jsonl truncated at that moment;
  - `.audit/` files as of that moment, approximated by mtime (a known limitation);
  - the stream home as Phase A left it.
- **Run.** A fresh steward with the §5 brief. Record the steers, answers and gates it proposes.
- **Two contract variants:**
  - **B1** is built from ZF's Oct 2 words only, the conservative case.
  - **B2** is ZF taking the §4.6 interview "as of Oct 2 13:08". It is optimistic because ZF knows how the campaign went.
- **Grading.** Blind: eggbot, or ZF without seeing which side is which. Each proposed action is graded match, pre-empt, miss, or false positive.
- **Success criterion** (the brief's metric, the share of ZF's historical interventions the steerer would have issued itself):
  - at least 10 of the 14 substantive messages matched or pre-empted (the desk estimate in §2.5 is 10/14);
  - 4 of 4 status pulls replaced by the digest;
  - both real gates escalated with options and a default, and the #19 load gate raised by 10-02 21:35;
  - zero stand-in "done" relays and zero ungated writes allowed;
  - at most one false-positive steer per campaign-day;
  - report B1 and B2 separately.

### Phase C: live, next stream

- Run the full loop on ZF's next stream of this kind: kickoff interview in a new stream home, ratify, then interfaces acked by owners, then D placement. No repo is chosen before the kickoff ends.
- **Targets:**

| Metric | Baseline (this campaign) | Target |
| --- | --- | --- |
| Where the stream started | inside one producer's worktree | ratified `STREAM.md` before the first landing |
| ZF restatements | 4 over 4 days | at most 1 per stream-week |
| Steer delivery | 11 of 22 more than 10 minutes late | p95 under 10 minutes |
| Sessions in goal mode with the `STREAM.md` sha | 0 of 4 for streams and stitch | 100% |
| Interfaces with owners and acks on both sides | 0 of 3 | 3 of 3 before consumers start |
| Ungated shared writes | 1 | 0 |
| Relayed counts that fail to partition | at least 2 | 0 |
| Drift detection latency, wall-clock (includes a weekend and the quota outage) | about 2.3 days (D1 write, D4 relay), about a day (D6), 3.7 days (D8) | 1 tick (15 minutes) for D-b, D-c, D-d and I-b; kickoff for D-f |

- **Ground rules.** Phases A and B touch only copies under a scratch directory. Nothing prompts live sessions, nothing reads or writes BigQuery, no team repo changes, and pi-stack install config stays as it is until ZF approves the components.

### What to build, in order

Each item is its own PR, after ZF answers the open questions:

1. `pi-web-cli` verbs (§5.9), and moving the CLI into this repo's `bin/`.
2. Stream home templates in pi-stack, and the local pilot repo `~/Projects/alphalab/streams/`.
3. `steer-check` / `steer-send` in replay mode.
4. The steward brief as a prompt template (`prompts/steward.md`) and the kickoff interview as a skill.
5. The host timer.
6. The workspace repo, manifest and integration check (§7.6), owned by ZF. The per-repo items in §7.6 go to their teams.

---

## 9. Open questions for ZF

1. **Goal and end consumer.** Is §2.1's candidate goal right: every template column, queryable in BigQuery, from a market-data pipeline, compiled from the DAG? Who is the end consumer, and how does it read the output?
2. **Teams and interface owners.** Is the pairing alc-qslite = core tech, alc-flows = infra, alc-cefi-sim-runner = quant right? Who acknowledges each side of I1, I2 and I3?
3. **Where stream homes live.** A new neutral org repo after a local pilot at `~/Projects/alphalab/streams/` (recommended), or `streams/` in pi-stack? If a new repo: name, visibility, and who may write.
4. **Contract copies in team repos.** Will teams accept a vendored, sha-pinned contract file plus a contract test in their repo, through their normal review? Or should their CI fetch contracts from the stream repo?
5. **`pil`.** Converge, using `pil` as the engine and the stream home as its durable layer, or keep them separate? `pil` steers through the `subagent` tool and the PI WEB REST API, while this brief allows only `pi-web-cli`: which rule wins?
6. **Oracle.** May TenV runtime outputs serve as the test oracle in A3, while still being forbidden as input? What tolerance and sample size?
7. **Interview budget.** Is about 26 questions in 6 rounds, mostly "accept the default", acceptable at kickoff? Which questions would you drop?
8. **Steward brain.** Should it be a fresh Astra xhigh pi session per stream per wake (recommended), a long-lived Astra session, or the Grok Bot itself?
9. **Autonomy.** May the steward answer a session's `ask_user` when the stream contract covers it, record owner-acked interface versions, and restart sessions without asking? Anything else on the never-without-ZF list?
10. **Shared writes.** What is the standing policy? Is there a scratch dataset sessions may write freely, or is every BigQuery write a gate? What did the Oct 2 "pre-push a slice … for smoke" authorize?
11. **Cleanup.** The 292 `alpha_v_*` columns and 432,000 `alpha_feature_sample` rows are still in `datapull_etl`. Roll back, keep, or move them (a separate gated task)?
12. **CLI ownership.** May `pi-web-cli` move into pi-stack and gain `--steer`, `stop`, `abort`, `queue-clear`, `asks`, `answer` and `model`? Who owns it today?
13. **Cadence and quiet hours.** Digest times, quiet hours, and whether gate deadlines may fall inside quiet hours.
14. **Cursor Project mirror.** Worth trying once Projects on self-hosted workers is documented, with the stream repo as its Workspace, or not at all, given the coordinator would not be on Astra?
15. **Retention.** `01a0fae3`'s jsonl is gone and MMDev's `store.db` was reinitialised. Should session jsonl be archived (outside git, by path in the ledger) when a stream closes?
16. **Quota.** Should the steward have a token budget per day? Should a `usage_limited` state page you, or only appear in the digest?
17. **Workspace repo.** One neutral repo for both stream homes and the manifest, or two? Who owns the integration check, and where does it run with what credentials?
18. **Per-repo items.** Will the quant team take the alc-cefi-sim-runner `AGENTS.md` and test workflow? Will core tech and infra agree to the I1 provider test and to CODEOWNERS for `python/alc-flows`?
19. **Monorepo trigger.** Should the "reconsider M" signals in §7.6 be tracked from the start, and at what threshold?

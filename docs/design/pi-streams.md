# pi-streams: Cursor Projects, run on pi-web

**The ask (ZF, 2026-10-06).** Get a working "Cursor Projects" setup where the threads are pi-web sessions instead of Cursor cloud agents, because Cursor tokens are limited. Use the market-data ETL work as the example, and get the process right before fixing that work itself.

**The answer in one paragraph.** A *stream* is pi's version of a Project. Each stream is its own small git repo, created from a template that pi-stack ships. ZF talks to the stream's *coordinator*, a pi-web session whose working directory is that repo. Like a Projects coordinator, it plans, starts *threads* (pi-web sessions in code worktrees) through `pi-web-cli`, checks their work and reports back, but never writes code itself. Everything the stream must remember lives in files in the stream repo, not in any session's context. A small script on a timer watches sessions, PRs and BigQuery and wakes the coordinator when something happens. It uses no model tokens, so it also catches model outages and hands them to the Grok Bot to tell ZF. A kickoff interview, run by the coordinator, writes the stream's goal, target, acceptance, test path, spend limits and end state into `STREAM.md`.

This doc replaces the open questions and the placement choice in [inner-loop-steering.md](inner-loop-steering.md), which remains the evidence and research behind it.

---

## 1. What ZF decided

| # | Question, in plain words | ZF's answer | Where it lands |
| --- | --- | --- | --- |
| 1 | Is the ETL goal right? | Ballpark right. Interview it later; get the process right first. | §8 uses it as the example only |
| 2 | Which team owns which repo? | Ignore. | dropped |
| 3 | Where do streams live: pi-stack, or a new repo used as a template? | "that's a question for you actually" | §3 |
| 4 | Contract files in each team's repo? | Not interested in contracting. The firm already has an acknowledged signal definition; the interview must surface that this is what to converge on. | §5, question 2 |
| 5 | Adopt `pil`? | No. Use `pi-web-cli`. | §4 |
| 6 | What is the test oracle? | Discover it in the interview. For ETL: final validation against TenV datapull, not a perfect match, with concessions for BigQuery limitations. | §5, question 3 |
| 7 | How long may the interview be? | Skip until the baseline exists. | §5 keeps it to 10 questions |
| 8 | Coordinator: fresh session per wake, or long-lived? | "you recommend to me". Take cues from Projects. Worried fresh sessions miss the cache and get expensive, but if it's needed, it's needed. | §4.2, measured |
| 9 | What may it do without asking? | Interview it. Hint: "what's the minimum blast radius way to test end 2 end as far as possible". For ETL: local end-to-end, pushing into BigQuery with one-off scripts and skipping infra verification, then the BigQuery side. | §5, questions 4 and 8 |
| 10 | Rules for BigQuery writes? | No standard; interview it. For ETL: the `Test` dataset has no rules, but don't run up query costs. | §5, question 5 |
| 11 | Clean up the campaign's leftovers? | Yes. The final table must match the template in the #654 image. | §5, question 6; §8 |
| 12 | Move `pi-web-cli` into pi-stack and add verbs? | Yes. | §9, step 1 |
| 13 | When should it message you, and when should it stay quiet? | Unclear (asked `/bro`). Default: it messages ZF only for decisions it isn't allowed to make and for outages; status is on request; no quiet hours. | §4.4 |
| 14 | Mirror a Cursor Project? | That is the goal: Projects with pi-web threads. | this doc |
| 15 | Keep session transcripts? | The stream should manage harvest, reflect and correct. Judging which sessions are worth harvesting can come later. | §7 |
| 16 | Token budget; how to report running out? | Assume no limits. An outage must reach ZF, probably through the Grok Bot, because the coordinator shares the workers' token pool. | §6 |
| 17 | One workspace repo or two? | "you recommend me" | §3 |
| 18 | Hand repo work to other teams? | No; all the work happens in the stream. | §3, §8 |
| 19 | When to reconsider a monorepo? | For information only. | no action |

---

## 2. Projects, mapped onto pi

The Projects docs describe a coordinator that "plans the work, delegates it to agents that write the code, and brings the finished work back to you to check". There is also a set of shared files that "sync across every cloud and local machine its agents use", and subscriptions to Slack, schedules and PRs (https://cursor.com/docs/agent/projects, https://cursor.com/blog/projects).

| Projects | pi-streams | Notes |
| --- | --- | --- |
| A Project | A stream: one git repo created from the template | §3 |
| The coordinator chat | A pi-web session with its working directory in the stream repo. ZF chats with it in pi-web, or through the Grok Bot. | §4 |
| Agents the coordinator starts | Threads: pi-web sessions, each in its own worktree of a code repo, started with `pi-web-cli spawn` | §4.3 |
| Workspace: one repository | `repos.tsv`: any number of repos, one worktree per writing thread | Better than Projects here; it was a gap for this work (inner-loop-steering §3.8) |
| Shared context files | `context/` in the stream repo: how to test, gotchas, preferences, research | Grows through harvesting (§7) |
| Subscriptions and the "Listening" list | `subscriptions.tsv`, run by `pi-streams tick` on a timer | §6 |
| Cloud by default, local when needed | Everything runs on `pistack` | n/a |
| Model picker | `coordinator_model` in `stream.toml` | Default Astra, per ZF's model rules |
| Gardening: "adds a lint rule whenever it sees the same mistake twice" | Harvest, reflect and correct | §7 |

pi-web already has the controls this needs. The installed server (`@jmfederico/pi-web` 1.202607.3, `dist/server/sessions/sessionRoutes.js`) exposes:
- create a session (it takes a `cwd` and an optional startup token);
- prompt, with `streamingBehavior`;
- `stop`, `abort` and `queue/clear`;
- `ask/submit` and `ask/cancel`;
- `model` and `thinking-level`;
- `status` and `messages`;
- `archive`;
- a websocket that streams events for every session (`/api/sessions/events`).

Two things it lacks:
- **No grouping.** A new session can't be given a parent or a label, so pi-web lists threads under their worktree, not under their stream. The stream's `threads.tsv` is the list of its threads.
- **A thin CLI.** `pi-web-cli` (109 lines, unversioned, in `~/.local/bin`) wraps only `list`, `spawn`, `prompt`, `status` and `commands`.

**Considered and not used as the thread backend: pi-subagents missions.** pi-subagents 0.58.0, installed here, keeps durable "missions" with objective, runs, decisions and receipts, plus schedules (`~/.pi/agent/npm/node_modules/pi-subagents/docs/missions.md`). Its runs, however, are headless children of one parent session, not threads ZF can open and talk to. Its schedules "launch async with fresh context and disable automatic mission creation". The coordinator may still use subagents for short read-only research, since those don't need to be threads.

---

## 3. Where a stream lives (Q3, Q17)

**Recommendation.** pi-stack holds the engine and the template. Each stream is its own git repo, created from that template on request. This is ZF's "default image" idea, with the image kept next to the code that reads it.

```text
pi-stack (public)                       one repo per stream (local git, private remote optional)
  bin/pi-streams                        ~/Projects/alphalab/streams/<id>/
  bin/pi-web-cli          (moved, Q12)    AGENTS.md          coordinator role, copied from the template
  templates/stream/       (the image) ─▶  STREAM.md          from the kickoff; only ZF changes it
  skills/stream-kickoff/                  STATE.md           coordinator's working state, kept short
  prompts/thread-brief.md                 DECISIONS.md       ZF's rulings, append-only
                                          repos.tsv          repo, path, base ref, why
                                          threads.tsv        session, role, repo, worktree, branch, model, status
                                          subscriptions.tsv  what to watch, and what to do when it fires
                                          context/           shared context (how to test, gotchas, preferences)
                                          checks/            acceptance and cost scripts
                                          handover/          one file per finished or rotated session
                                          log/               tick events, steer log
                                          stream.toml        engine version, coordinator model, thresholds
```

**Why not `streams/` inside pi-stack.**
- pi-stack is a public GitHub repo (`gh repo view alienczf/pi-stack`: `"visibility":"PUBLIC"`). Stream files will name BigQuery tables, firm signal definitions and rulings.
- Stream state changes on every wake, which would bury pi-stack's install history.

**Why not one shared repo holding every stream.**
- Several coordinators would commit to one branch and index at once. poteto's rule is to "Give each actor its own owned file, key, branch, or state directory, and merge only at the read/reporting boundary" (inner-loop-steering §1.6).
- With one repo per stream, closing or archiving a stream is one directory.
- The cross-stream view is `pi-streams status`, which reads every repo under `streams/`.

**Why not a separate template repo yet.**
- The engine reads the template's layout, so the two change together. Keeping them in one repo gives one version, and `stream.toml` records which engine version created each stream.
- Split the template out when it needs to be private or shared with other people.

**This follows an existing pattern.** It is how Jig already works in pi-stack: the tooling lives in pi-stack and writes its state into the target repo (`.pi/jig/`, README "Repository artifacts").

**Q17: no separate workspace repo for now.** The stream repo is the workspace:
- `repos.tsv` lists the repos the stream touches and their base refs;
- `checks/` holds its end-to-end check;
- each writing thread gets a worktree, and an untracked `.stream` file in it holds the stream path (ignored through `.git/info/exclude`, so no team repo changes).

The org-level workspace repo in inner-loop-steering §7 can wait until several streams need the same manifest.

---

## 4. The coordinator

### 4.1 What it does

The template's `AGENTS.md` makes every coordinator the same role. pi loads `AGENTS.md` at startup from the working directory and its parents (pi-coding-agent README, "Context files"), so the role is part of the coordinator's fixed prefix. A draft:

```text
You are the coordinator of the stream in this directory. You never write product code.
On every turn:
1. Read STREAM.md, STATE.md, and the newest lines of log/events.jsonl.
2. Decide the next actions. Act only within STREAM.md's AUTONOMY section; anything else goes
   to ZF as a question with options and a recommended default, and work continues on the default.
3. Delegate work to threads with `pi-streams thread spawn` and steer them with `pi-web-cli`.
   Never resume a thread just to check on it; read `pi-web-cli status` instead.
4. Accept a thread's "done" only when the matching script in checks/ passes on the real artifact.
5. Rewrite STATE.md (plan, open threads, waiting-on, next step) before you end the turn.
Relay numbers only from check output or files, with their path.
```

The restate, verify and relay rules come from the research (inner-loop-steering §3.2, §3.6, §5.5). The "never resume to check" rule is from poteto's orchestrate playbook.

### 4.2 Fresh or long-lived: what the session logs say (Q8)

ZF's worry is that a fresh session per wake misses the prompt cache. I measured this from the 12 session logs in the #654 worktree from Oct 1 to 6 (`SESS/2026-10-0*.jsonl`, 3,031 model calls, 97% of the spend on Astra). The figures use pi's recorded usage and its notional prices for Astra: $10 per million uncached input tokens, $1 per million cache reads, $50 per million output tokens. These are pi's list prices, not the plan's quota, so read them as relative costs.

| Finding | Number |
| --- | --- |
| Total notional spend | $1,043: uncached input $531, cache reads $422, output $90 |
| Share spent re-reading context | 91% |
| Overall cache hit rate | 77% |
| Hit rate when the previous call in that session was 10–30 minutes earlier | 86% (75 calls) |
| Hit rate after a 1–6 hour gap | 61% (13 calls) |
| Hit rate after more than 6 hours | 0% (2 calls; small sample) |
| A fresh session's first call | about 17,200 tokens, about $0.17 |
| Fresh sessions whose first call hit cache written by another session | 2 of 12 (16,896 and 7,680 tokens) |
| Cost per call, prompt under 50k tokens | $0.08 |
| Cost per call, prompt 150–250k tokens | $0.39 |
| Share of spend from calls with prompts over 150k tokens | 75% |

**What this means.**
- **Context size costs more than cache misses.** The cache already holds for tens of minutes. A big context costs about five times as much per call as a small one, whether it hits the cache or not.
- **Fresh is cheaper per wake.** A wake of about six calls costs roughly $0.17 + 5 × $0.08 ≈ $0.57 as a fresh session. In a long-lived coordinator at 200k tokens, the same wake costs about 6 × $0.39 ≈ $2.34.
- **Fresh sessions can reuse each other's cache** when their prompts start identically.
- **The real money is in the threads.** The worker sessions spent $227, $494 and $314 on the three days they ran (Oct 2, 5 and 6). At 20 to 50 wakes a day, a coordinator kept small costs about $11 to $28 a day, or 3% to 10% of that.

**Recommendation: warm while small, fresh once big.** This keeps the Projects experience of one coordinator chat with fresh-session costs.
- **When to rotate.** On each wake, the tick prompts the current coordinator session if its context is under 60k tokens and its last turn was under 6 hours ago. Otherwise `pi-streams rotate` asks it to rewrite `STATE.md` and a handover, archives it, and starts a fresh coordinator from the stream files.
- **What ZF sees.** pi-web shows a new coordinator thread. `STATE.md` names the current one, and its first message is a short summary of where things stand.
- **Keep the start of every prompt identical**, so fresh coordinators reuse each other's cache. The order is pi's system prompt, then the template `AGENTS.md`, then `STREAM.md`, which rarely changes, and only then the volatile `STATE.md` and the event.
- **Threads hand over at 150k tokens.** That is where three quarters of the campaign's spend sat.

### 4.3 Threads

`pi-streams thread spawn <stream> --repo <name> --role <role>` is the only way to start a thread, so `threads.tsv` has one writer. It:
1. creates a worktree and branch, and writes the `.stream` pointer;
2. runs `pi-web-cli spawn <worktree>`, then sets the model while the session is idle and checks it took;
3. sends the brief from `prompts/thread-brief.md`: goal pointer, scope, context paths, acceptance, how to verify, what it must not do, and how to report;
4. checks that the first reply restates the intent correctly before work starts (inner-loop-steering §5.6);
5. records the row in `threads.tsv`.

Steers use `pi-web-cli prompt --steer`, so they interrupt a busy session instead of waiting in its queue. In the campaign, 11 of 22 steers sat in a queue for more than 10 minutes (inner-loop-steering §2.8).

### 4.4 How ZF talks to it

- **Directly.** ZF chats with the current coordinator in pi-web.
- **Through the Grok Bot.** The bot is the outer loop: it brings in context from Slack and elsewhere, and relays ZF's messages with `pi-web-cli prompt`. It no longer writes goals or steers threads itself (inner-loop-steering §2.7, where most of the drift came from relays).
- **When it messages ZF.** Only for a decision `STREAM.md` doesn't let it make, and for outages (§6). Each question carries options and a recommended default, and work continues on the default. Status is on request. There are no quiet hours.

---

## 5. Kickoff interview

`pi-streams new <id>` creates the repo from the template, starts the coordinator, and sends it `/skill:stream-kickoff`. The skill does the following:
1. **Scouts first.** It surveys the named repos, PRs and tables read-only, as Jig's survey does, so each question can come with a recommended answer.
2. **Asks one question at a time.** ZF accepts the recommendation or corrects it (the "grill me" pattern, inner-loop-steering §3.4).
3. **Restates.** It writes back the whole goal in one paragraph for ZF to correct.
4. **Writes `STREAM.md`.** It records ZF's ratification marker, and from then on only ZF changes the file.

The ten questions, with ZF's answers for the ETL stream:

| # | Question | Why it is asked | ETL answer |
| --- | --- | --- | --- |
| 1 | What outcome do you want, and who uses it? | The goal and the end consumer | Quant can query the template's features in BigQuery, built from the market-data pipeline (ballpark, ZF Q1) |
| 2 | Is there an artifact the firm already agreed on that defines the output? | This is the interface to converge on. ZF said it has to be drawn out of him. | The firm's predefined signal definition. The final table must match the template in the #654 image. The kickoff pins both by path and sha. |
| 3 | How will we know it's right? What is the oracle, and which mismatches are acceptable? | Acceptance that a script can check | Final validation against TenV datapull output for the same window. Not a perfect match: each concession for a BigQuery limitation is recorded in `DECISIONS.md`. |
| 4 | What is the smallest-blast-radius way to test end to end, as far as possible? | ZF's hint for Q9. It decides the order of work and what to skip. | Run the datapull locally and push its output into BigQuery with one-off scripts, skipping infra deployment, since infra trusts the docker image contract. Then do the BigQuery side. |
| 5 | Where may it write, and how much may it spend? | Write and cost policy | The BigQuery `Test` dataset, no rules. Every query is dry-run first. Per-query and per-day byte caps are set at kickoff, and the tick tallies the day's bytes. |
| 6 | What must the end state be, including cleanup? | The definition of finished | The final table matches the template in the #654 image. The campaign leftovers in `Test` (292 `alpha_v_*` columns, 432,000 `alpha_feature_sample` rows) are removed after a snapshot. |
| 7 | Which repos, branches and PRs are in play? | Fills in `repos.tsv` | alc-qslite (#654 worktree), alc-cefi-sim-runner (bq-signal-compiler), and wherever the TenV datapull output lives. The scout proposes; ZF confirms. |
| 8 | What may the coordinator decide alone, and what must come to you? | The AUTONOMY section | Alone: everything inside questions 4–6, plus restarts, steers and model fixes. Ask: changes to the goal, target or acceptance; new concessions; spend over the caps. |
| 9 | What must not happen? | NO-GO | TenV output is used to validate, never as input. No writes outside `Test`. Nothing changes the signal definition. |
| 10 | Here is the goal restated in one paragraph. Is it right? | Catches misreadings before any work starts | ZF corrects, then ratifies |

This is 10 questions instead of the 26 in inner-loop-steering §4.6. ZF deferred the length question (Q7), and the campaign-specific questions are now answered by questions 2 to 6.

---

## 6. The tick: subscriptions without a model

`pi-streams tick` runs every 5 minutes from a systemd user timer. It is one script for all streams, and it uses no model tokens. Each subscription row in a stream's `subscriptions.tsv` names a source, a condition and an action.

| Source | Example condition | Action |
| --- | --- | --- |
| pi-web status and the session event websocket | A thread is idle, asks a question, or reports done; a steer is still queued after 10 minutes; context is over 150k tokens | Prompt the coordinator with the event, or resend the steer with `--steer` |
| `gh` | A PR in `repos.tsv` gets a review, CI result or merge | Prompt the coordinator |
| BigQuery metadata | A table the stream named changes fields, rows or modified time | Prompt the coordinator; if the change is outside the write policy, stop the thread and ask ZF |
| BigQuery job history | Bytes billed today pass the cap from question 5 | Stop new queries and ask ZF |
| Schedule | For example, a daily status at 09:00 | Prompt the coordinator |
| Worktrees across streams | Two streams claim one worktree or branch | Ask ZF (inner-loop-steering §1.8) |

The coordinator adds rows when ZF asks, as Projects does. The mechanical checks from inner-loop-steering §5.4 run here too: delivery, verified park, pending asks, model, context, liveness and child receipts.

**Outages (Q16).** When a session's last model call failed on a usage limit or a provider error, no model in that pool can be trusted to report it. The tick then:
- writes `ALERT.md` in the stream and a line in `~/Projects/alphalab/streams/ALERTS`;
- marks the affected threads "waiting on quota" so nothing respawns into the outage.

The Grok Bot's routine already reaches this host over SSH. It checks `ALERTS` and messages ZF, using its own token pool. When the next model call succeeds, the tick clears the alert and wakes the coordinator.

---

## 7. Gardening: harvest, reflect, correct (Q15)

- **Harvest.** Before a thread is archived, its last prompt asks it to write `handover/<thread>.md`: intent, what was done with proof, what is left, and what the next agent should know. This follows pstack's `pause-safely`. The coordinator then copies the lasting parts into `context/`: how to test, gotchas, and ZF's preferences. This is Projects' "If one agent figures out how to test a service, every future agent can use those instructions".
- **Reflect.** When a thread fought the same problem more than once, the coordinator first prompts it with pstack's `/skill:reflect`. That skill reviews the active transcript and turns its lessons into edits to existing skills, so it has to run inside the thread.
- **Correct.** When the same mistake shows up across threads, the coordinator starts a thread in that repo with pstack's `/correct`. That skill makes the mistake impossible with architecture, types, a lint or a test, in that order.
- **When.** At thread close, at each milestone, and at stream close.
- **Deferred.** Judging which sessions are worth harvesting (ZF: "let's not for now").

---

## 8. Worked example: the ETL stream

```text
pi-streams new qmd-etl --repos alc-qslite,alc-cefi-sim-runner
```

`STREAM.md` after the kickoff. The pins are filled in at the kickoff; the rest is from ZF's answers.

```text
# STREAM qmd-etl   ratified: <ZF marker>   engine: pi-streams <version>
GOAL        Quant can query the template's features in BigQuery, built from the market-data
            pipeline, for <venues, symbols, dates>.
TARGET      Signal definition: <path>@<sha> (firm-acknowledged).
            Final table shape: the template in the #654 image, <image tag or digest>.
ACCEPTANCE  A1 checks/schema.sh: final table columns == template columns.
            A2 checks/validate_tenv.py: features vs TenV datapull for <window>, within <tolerance>,
               except the concessions listed in DECISIONS.md.
            A3 checks/coverage.sh: every template output is computed or listed as a concession.
E2E PATH    Local datapull -> one-off push to BigQuery Test -> BigQuery feature compile ->
            validate against TenV. Infra deployment is not verified in this stream.
WRITES      BigQuery Test dataset only. Dry-run every query; <per-query cap>, <per-day cap>.
END STATE   A1-A3 pass. Campaign leftovers in Test removed after a snapshot.
AUTONOMY    Alone: anything inside E2E PATH, WRITES and END STATE; restarts, steers, model fixes.
            Ask ZF: changes to GOAL, TARGET or ACCEPTANCE; new concessions; spend over a cap.
NO-GO       TenV output as input. Writes outside Test. Changes to the signal definition.
```

**Threads the coordinator would start.** Two run in parallel early, because the end-to-end path pushes a real slice early instead of building stubs:

| Thread | Repo and worktree | Does | Done when |
| --- | --- | --- | --- |
| T1 datapull | alc-qslite, the #654 worktree | Runs the datapull locally for one day and one venue | Rows match the signal definition's columns |
| T2 push | the stream repo's `checks/`, no product code | A one-off script loads T1's output into `Test` | Row count and schema check pass |
| T3 compile | alc-cefi-sim-runner, bq-signal-compiler | Compiles the template's features in BigQuery from T2's slice, then from the full window | A1 passes |
| T4 validate | read-only | Runs A2 against TenV datapull and proposes concessions to ZF | A2 passes with ratified concessions |
| T5 finish | read-only, plus BigQuery `Test` | Snapshots, removes the leftovers, checks A3 | A1–A3 pass |

**Subscriptions it would add:**
- T1–T5 idle, ask or done;
- schema or row changes on the stream's `Test` tables;
- bytes billed against the caps;
- PR activity on #654.

**What this setup prevents, compared with the campaign** (inner-loop-steering §2.7):
- **Hand-written goals that drifted.** The goal lives in `STREAM.md`, ratified by ZF, and threads get a pointer to it.
- **Stand-ins relayed as done.** Acceptance is a script, and "done" is relayed only with its output.
- **The schema expansion and 432,000-row write that nobody noticed.** The table watch and write policy catch them within one tick.
- **Steers that sat in queues.** Steers use `--steer`, and the tick resends any still queued.
- **Questions that went unanswered.** Pending asks wake the coordinator, which answers from `STREAM.md` or passes the question to ZF.

---

## 9. What to build, in order

Each step is its own PR in pi-stack, except the last, which is the pilot.

1. **`pi-web-cli` into `bin/`** (Q12), with `prompt --steer`, `stop`, `abort`, `queue-clear`, `asks`, `answer`, `model` and `thinking-level`. All use routes pi-web already has, so this is CLI work only, with tests against a stub server.
2. **The template and `pi-streams new` / `status`.** `new` makes the repo, copies the template, records the engine version and starts the coordinator. `status` prints every stream's threads, states and today's spend.
3. **`pi-streams thread spawn` and `rotate`**, with `prompts/thread-brief.md`.
4. **The `stream-kickoff` skill**: scout, ten questions, restate, ratify.
5. **`pi-streams tick` and the systemd user timer**: subscriptions, mechanical checks and outage alerts. Also a test mode that runs the tick against recorded session logs (inner-loop-steering §8, Phase A).
6. **Harvest at thread close.** Reflect and correct are prompts to existing pstack skills.
7. **Pilot: the ETL stream.** Kickoff, then T1 and T2 end to end through the setup.

**Pilot pass criteria:**
- ZF restates the goal at most once per week;
- no steer waits in a queue for more than 10 minutes;
- no write or spend outside the policy goes unnoticed for more than one tick;
- the coordinator's notional cost stays under 10% of the threads' cost.

**Still open:**
- **Access.** How ZF reaches pi-web on `pistack` today (tunnel or Twingate), so the coordinator chat is usable from his machine.
- **Remote.** Whether stream repos get a private remote, and where.
- **Coordinator model and thinking level.** Astra is the default, per the model rules.

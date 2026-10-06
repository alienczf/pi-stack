# pi-streams: Cursor Projects, run on pi-web

**The ask (ZF, 2026-10-06).** Get a working "Cursor Projects" setup where the threads are pi-web sessions instead of Cursor cloud agents, because Cursor tokens are limited. Use the market-data ETL work as the example, and get the process right before fixing that work itself. Then (second round): put all the harness in one repo, strip Jig, keep a baseline skill for spawning a stream, and make the quickstart command provision everything ready for work.

**The answer in one paragraph.** pi-stack is the one harness repo. Its quickstart installs, in one command:
- the overlay and pstack;
- `pi-web-cli`;
- the `pi-streams` command and its `/stream` skills;
- a timer;
- optionally, a *project home* for an existing codebase.

A project home is a private git repo next to the project's code repos, for example `~/Projects/alphalab/streams/`. It holds what is specific to the project: the list of repos, shared context, and one folder per *stream*. A stream is pi's version of a Cursor Project. ZF talks to its *coordinator*, a pi-web session in that stream's folder. The coordinator plans, starts *threads* (pi-web sessions in code worktrees) through `pi-web-cli`, checks their work with scripts and reports back, and never writes code itself. The timer wakes coordinators when something happens. It uses no model tokens, so it also catches model outages and hands them to the Grok Bot. No second repo is needed. Jig goes, because pstack's `reflect`, `correct` and verification skills cover it.

This doc replaces the open questions and the placement choice in [inner-loop-steering.md](inner-loop-steering.md), which remains the evidence and research behind it.

**Scope.** This doc designs the harness. Any question that depends on a particular host, project or stream is asked by the tool when it runs, and each comes with a default. `pi-streams init` asks the host and project questions (§9, step 1), and the kickoff asks the stream questions (§5). The ETL stream and alphalab appear only as the example and the pilot.

---

## 1. What ZF decided

**First round (answers to inner-loop-steering §9):**

| # | Question, in plain words | ZF's answer | Where it lands |
| --- | --- | --- | --- |
| 1 | Is the ETL goal right? | Ballpark right. Interview it later; get the process right first. | §8 uses it as the example only |
| 2 | Which team owns which repo? | Ignore. | dropped |
| 3 | Where do streams live? | "that's a question for you actually". Revised in round two. | §3 |
| 4 | Contract files in each team's repo? | Not interested in contracting. The firm already has an acknowledged signal definition; the interview must surface that this is what to converge on. | §5, question 2 |
| 5 | Adopt `pil`? | No. Use `pi-web-cli`. | §4 |
| 6 | What is the test oracle? | Discover it in the interview. For ETL: final validation against TenV datapull, not a perfect match, with concessions for BigQuery limitations. | §5, question 3 |
| 7 | How long may the interview be? | Skip until the baseline exists. | §5 keeps it to 10 questions |
| 8 | Coordinator: fresh session per wake, or long-lived? | "you recommend to me". Take cues from Projects. Worried fresh sessions miss the cache and get expensive, but if it's needed, it's needed. | §4, measured |
| 9 | What may it do without asking? | Interview it. Hint: "what's the minimum blast radius way to test end 2 end as far as possible". For ETL: local end-to-end, pushing into BigQuery with one-off scripts and skipping infra verification, then the BigQuery side. | §5, questions 4 and 8 |
| 10 | Rules for BigQuery writes? | No standard; interview it. For ETL: the `Test` dataset has no rules, but don't run up query costs. | §5, question 5 |
| 11 | Clean up the campaign's leftovers? | Yes. The final table must match the template in the #654 image. | §5, question 6; §8 |
| 12 | Move `pi-web-cli` into pi-stack and add verbs? | Yes. | §10, step 2 |
| 13 | When should it message you, and when should it stay quiet? | Unclear (asked `/bro`). Default: it messages ZF only for decisions it isn't allowed to make and for outages; status is on request; no quiet hours. | §4.5 |
| 14 | Mirror a Cursor Project? | That is the goal: Projects with pi-web threads. | this doc |
| 15 | Keep session transcripts? | The stream should manage harvest, reflect and correct. Judging which sessions are worth harvesting can come later. | §7 |
| 16 | Token budget; how to report running out? | Assume no limits. An outage must reach ZF, probably through the Grok Bot, because the coordinator shares the workers' token pool. | §6 |
| 17 | One workspace repo or two? | "you recommend me". Revised in round two. | §3 |
| 18 | Hand repo work to other teams? | No; all the work happens in the stream. | §3, §8 |
| 19 | When to reconsider a monorepo? | For information only. | no action |

**Second round (ZF, 09:44 UTC):**
- **pi-stack.** ZF owns it.
- **Project-specific state.** It is wanted, but separately.
- **One harness repo.** All the harness should live in one repo.
- **Jig.** It is redundant with pstack's `reflect`, `correct` and verification skills, so strip it.
- **Spawning.** Keep a template or baseline skill that spawns a stream.
- **pi-spring.** A separate pi-spring repo is my call.
- **Quickstart.** It should provision everything "ready for work without all the faffing about".

The complete revised answers to Q3, Q8 and Q17 are in §3 and §4, and the brownfield user story is in §9.

**Third round (ZF, 09:51 UTC).** The last three open questions were how ZF reaches pi-web, where the project home's remote lives, and the coordinator's model and thinking level. All three belong to setup: "shouldn't all these go into the streams setup? not in this process planning stream?" They are now questions that `pi-streams init` asks, each with a default (§9, step 1).

---

## 2. Projects, mapped onto pi

The Projects docs describe a coordinator that "plans the work, delegates it to agents that write the code, and brings the finished work back to you to check". There is also a set of shared files that "sync across every cloud and local machine its agents use", and subscriptions to Slack, schedules and PRs (https://cursor.com/docs/agent/projects, https://cursor.com/blog/projects).

| Projects | pi-streams | Notes |
| --- | --- | --- |
| A Project | A stream: one folder in the project home | §3 |
| The coordinator chat | A pi-web session whose working directory is the stream's folder. ZF chats with it in pi-web, or through the Grok Bot. | §4 |
| Agents the coordinator starts | Threads: pi-web sessions, each in its own worktree of a code repo, started with `pi-web-cli spawn` | §4.4 |
| Workspace: one repository | `project.toml` in the project home: every repo in the project and its worktrees | Better than Projects here; it was a gap for this work (inner-loop-steering §3.8) |
| Shared context files | `context/` in the project home, shared by every stream in the project, plus each stream's own files | Grows through harvesting (§7) |
| Subscriptions and the "Listening" list | Each stream's `subscriptions.tsv`, run by `pi-streams tick` on a timer | §6 |
| Cloud by default, local when needed | Everything runs on `pistack` | n/a |
| Model picker | `coordinator_model` and `coordinator_thinking` in `project.toml`, overridable per stream | Asked at init; default Astra at `xhigh` (§4.1) |
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
- **No grouping.** A new session can't be given a parent or a label, so pi-web lists threads under their worktree, not under their stream. Each stream's `threads.tsv` is the list of its threads.
- **A thin CLI.** `pi-web-cli` (109 lines, unversioned, in `~/.local/bin`) wraps only `list`, `spawn`, `prompt`, `status` and `commands`.

**Considered and not used as the thread backend: pi-subagents missions.** pi-subagents 0.58.0, installed here, keeps durable "missions" with objective, runs, decisions and receipts, plus schedules (`~/.pi/agent/npm/node_modules/pi-subagents/docs/missions.md`). Its runs, however, are headless children of one parent session, not threads ZF can open and talk to. Its schedules "launch async with fresh context and disable automatic mission creation". The coordinator may still use subagents for short read-only research, since those don't need to be threads.

---

## 3. Where everything lives (Q3 and Q17, revised in full)

There are two places, and only two.

**Harness: pi-stack, one repo, one quickstart.** It contains everything that is the same for every project:
- the overlay and the pstack pin it already manages;
- `pi-web-cli`;
- the `pi-streams` engine and its templates;
- the `/stream` skills;
- the tick timer.

**Project home: one private git repo per project.** It sits next to the project's code repos and holds everything specific to that project: its repos, its shared context, and its streams. For alphalab it is `~/Projects/alphalab/streams/`. `~/Projects/alphalab` is a plain directory holding 21 code repos and 23 sibling worktree folders, and is not itself a git repo. The project home sits beside them, inside none of them.

```text
pi-stack (harness, public)                     ~/Projects/alphalab/streams/   (project home, private)
  install.sh            quickstart, --project    AGENTS.md          coordinator role, from the template
  bin/pi-web-cli        moved in, Q12            project.toml       repos, worktrees, pi-web URL, coordinator, caps
  bin/pi-streams        init, new, thread,       context/           shared by every stream in the project:
                        tick, rotate, close,                        how to test each repo, gotchas, preferences
                        status, doctor           ALERTS             outage lines for the Grok Bot
  pi-streams/engine/    the code behind it       qmd-etl/           one folder per stream:
  pi-streams/templates/ project/, stream/          STREAM.md        from the kickoff; only ZF changes it
  pi-streams/systemd/   tick service and timer     STATE.md         coordinator's working state, kept short
  skills/stream/        /stream new|status|close   DECISIONS.md     ZF's rulings, append-only
  skills/stream-kickoff/  the interview            threads.tsv      session, role, repo, worktree, branch, model, status
  prompts/thread-brief.md                          subscriptions.tsv  what to watch, and what to do when it fires
                                                   checks/          acceptance and cost scripts
                                                   handover/        one file per finished or rotated session
                                                   log/             tick events and steer log (not committed)
```

**Why the harness stays in pi-stack, with no pi-spring repo.**
- **No second updater.** pi-stack already owns the quickstart, the overlay, the packages and a reviewed pstack update (`update-pstack`). A second repo referenced from pi-stack would need a second pinned checkout and a second update path, which is exactly the faff to avoid.
- **One version.** The engine reads the template's layout, so they change together. Each stream records the pi-stack revision that created it.
- **Splitting later is easy.** If someone wants streams without ZF's overlay, the engine already sits in its own `pi-streams/` directory, so moving it into a pi-spring repo then is a move, not a rewrite.

**Why project state stays out of pi-stack.** pi-stack is public (`gh repo view alienczf/pi-stack`: `"visibility":"PUBLIC"`). Project homes name BigQuery tables, the firm's signal definitions and ZF's rulings. They are private repos; ZF picks the remote, or keeps them local.

**Why one project home holds all of a project's streams.** This revises the earlier "one repo per stream" answer:
- **Shared context.** Projects' shared context exists so "If one agent figures out how to test a service, every future agent can use those instructions". In a project spanning 21 repos, that knowledge belongs to the project, not to one stream. `context/` sits at the project level, and every stream reads it.
- **Fewer repos.** One repo per project instead of one per stream.
- **One writer for git.** Several coordinators editing one repo is safe because each writes only its own stream folder. Only the `pi-streams` command commits, under a lock, on each tick and on `close`. This follows poteto's rule: "Give each actor its own owned file, key, branch, or state directory, and merge only at the read/reporting boundary" (inner-loop-steering §1.6). Volatile logs are not committed.
- **One coordinator role.** pi loads `AGENTS.md` from the working directory and its parents (pi-coding-agent README, "Context files"). So the project home's `AGENTS.md` is the role for every coordinator in that project, and every coordinator's prompt starts identically (§4.3).

**Q17: the project home is the workspace repo.**
- `pi-streams init` fills `project.toml` by finding the git repos under the project directory and running `git worktree list` in each. Folder names can't be trusted: alphalab keeps worktrees as sibling folders, under `.worktrees/`, inside repos and in `/tmp`.
- Streams name repos from this list.
- Each thread records the base ref it started from. A version-pinning manifest can wait until two streams need the same pins.
- Acceptance checks live with each stream (`checks/`).

**Jig is removed.**
- **From pi-stack:** its launcher, controller, skill, routes table, prompt and tests.
- **From the installer:** it deletes the installed copies and unregisters the skill. On `pistack` these are `~/.pi/agent/jig/`, `~/.pi/agent/bin/jig`, `~/.local/bin/jig`, `~/.pi/agent/prompts/jig.md` and `~/.pi/agent/skills-pstack/jig/`, plus the `skills-pstack/jig` entry in `settings.json`.
- **Replacements:**
  - Repo principles come from pstack's `correct`, which ranks fixes architecture first, then types, lints, tests, and docs last.
  - Verification comes from pstack's `create-verification-skill` and `maintain-verification-skill`.
  - Learning comes from pstack's `reflect`.
  - The quickstart's pstack skill list gains `correct`. It already selects the other three (`install.sh`, `pstack_skill_names`).
- **Left alone:** the two repos on this host that hold Jig state (`alc-penv` and `alc-penv-jig`, both `.pi/jig/` only, with no principle or verification skill written). Those files belong to those repos, and `pi-streams doctor` lists them.

---

## 4. The coordinator (Q8, revised in full)

### 4.1 Shape

- **One coordinator per stream**, as Projects has one per Project.
- **Where it runs.** It is a pi-web session whose working directory is the stream's folder, started by `pi-streams new`.
- **Its role** comes from the project home's `AGENTS.md`.
- **Its model and thinking level** come from `project.toml`, which `pi-streams init` fills in (§9, step 1). The default is Astra at `xhigh`:
  - Astra follows ZF's rule that planning and review run on Astra (inner-loop-steering §2.4, message 7).
  - `xhigh` is how all 12 campaign sessions in the #654 worktree ran (their `thinking_level_change` events), so the costs in §4.2 already include it.
  - Both are set while the session is idle, then checked.
- **It never writes product code.** It plans, delegates to threads, accepts work only when a script in `checks/` passes, and reports.
- **Its memory is files.** It has no memory beyond `STREAM.md`, `STATE.md`, `DECISIONS.md`, `threads.tsv` and `context/`. Any coordinator session can be replaced by a fresh one that reads those files.

Draft of the template `AGENTS.md`:

```text
You are the coordinator of the stream whose folder is your working directory. You never write product code.
On every turn:
1. Read STREAM.md, STATE.md, the newest lines of log/events.jsonl, and ../context/README.md.
2. Decide the next actions. Act only within STREAM.md's AUTONOMY section; anything else goes
   to ZF as a question with options and a recommended default, and work continues on the default.
3. Delegate work to threads with `pi-streams thread spawn` and steer them with `pi-web-cli`.
   Never resume a thread just to check on it; read `pi-web-cli status` instead.
4. Accept a thread's "done" only when the matching script in checks/ passes on the real artifact.
5. Rewrite STATE.md (plan, open threads, waiting-on, next step) before you end the turn.
Relay numbers only from check output or files, with their path.
```

The restate, verify and relay rules come from the research (inner-loop-steering §3.2, §3.6, §5.5). The "never resume to check" rule is from poteto's orchestrate playbook.

### 4.2 Fresh or long-lived: what the session logs say

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

What this means:
- **Context size costs more than cache misses.** The cache already holds for tens of minutes. A big context costs about five times as much per call as a small one, whether it hits the cache or not.
- **Fresh is cheaper per wake.** A wake of about six calls costs roughly $0.17 + 5 × $0.08 ≈ $0.57 as a fresh session. In a long-lived coordinator at 200k tokens, the same wake costs about 6 × $0.39 ≈ $2.34.
- **Fresh sessions can reuse each other's cache** when their prompts start identically.
- **The real money is in the threads.** The worker sessions spent $227, $494 and $314 on the three days they ran (Oct 2, 5 and 6). At 20 to 50 wakes a day, a coordinator kept small costs about $11 to $28 a day, or 3% to 10% of that.

### 4.3 The policy: warm while small, fresh once big

- **Wake the current session when it's small and recent.** On each wake, the tick prompts the current coordinator session if its context is under 60k tokens and its last turn was under 6 hours ago.
- **Otherwise rotate.** `pi-streams rotate` asks the session to rewrite `STATE.md` and a handover, archives it in pi-web, and starts a fresh coordinator from the files. `STATE.md` names the current coordinator, and the new one opens with a short summary, so to ZF it reads as one continuing chat.
- **Keep the start of every prompt identical**, so coordinators share cache. The order is pi's system prompt, then the project home `AGENTS.md`, then `STREAM.md`, which rarely changes, and only then `STATE.md` and the event.
- **Threads hand over at 150k tokens.** That is where three quarters of the campaign's spend sat. This saves far more than any coordinator choice.
- **Track the cost.** `pi-streams status` shows each stream's coordinator and thread spend per day, read from session usage. The coordinator should stay under 10% of its threads.

### 4.4 Threads

`pi-streams thread spawn <stream> --repo <name> --role <role>` is the only way to start a thread, so `threads.tsv` has one writer. It:
1. creates a worktree and branch, and writes an untracked `.stream` file holding the stream path (ignored through `.git/info/exclude`, so no repo changes);
2. runs `pi-web-cli spawn <worktree>`, then sets the model while the session is idle and checks it took;
3. sends the brief from `prompts/thread-brief.md`: goal pointer, scope, context paths, acceptance, how to verify, what it must not do, and how to report;
4. checks that the first reply restates the intent correctly before work starts (inner-loop-steering §5.6);
5. records the row in `threads.tsv`.

`pi-streams thread adopt <session-id>` brings in a session that already exists. It records the session as a thread and writes the `.stream` file into its worktree without respawning it. This is how a brownfield stream takes over work already in flight (§9).

Steers use `pi-web-cli prompt --steer`, so they interrupt a busy session instead of waiting in its queue. In the campaign, 11 of 22 steers sat in a queue for more than 10 minutes (inner-loop-steering §2.8).

### 4.5 How ZF talks to it

- **Directly.** ZF chats with the current coordinator in pi-web.
- **Through the Grok Bot.** The bot is the outer loop: it brings in context from Slack and elsewhere, and relays ZF's messages with `pi-web-cli prompt`. It no longer writes goals or steers threads itself (inner-loop-steering §2.7, where most of the drift came from relays).
- **When it messages ZF.** Only for a decision `STREAM.md` doesn't let it make, and for outages (§6). Each question carries options and a recommended default, and work continues on the default. Status is on request. There are no quiet hours.

---

## 5. Kickoff interview

`pi-streams new <id>` (or `/stream new <id>` from any pi session) does three things:
1. creates the stream folder from the template;
2. starts the coordinator;
3. sends it `/skill:stream-kickoff`.

The skill then works in four steps:
1. **Scouts first.** It surveys the project's repos, worktrees, PRs, live pi-web sessions and named tables, all read-only, so each question comes with a recommended answer. In a brownfield project it also proposes:
   - existing worktrees to adopt;
   - existing sessions to adopt or leave alone;
   - past rulings to copy into `DECISIONS.md`, each for ZF to confirm.
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
| 7 | Which repos, branches, PRs and sessions are in play? | Fills the stream's part of `project.toml` and finds what to adopt | alc-qslite (#654 worktree), alc-cefi-sim-runner (bq-signal-compiler), and wherever the TenV datapull output lives. The scout proposes; ZF confirms. |
| 8 | What may the coordinator decide alone, and what must come to you? | The AUTONOMY section | Alone: everything inside questions 4–6, plus restarts, steers and model fixes. Ask: changes to the goal, target or acceptance; new concessions; spend over the caps. |
| 9 | What must not happen? | NO-GO | TenV output is used to validate, never as input. No writes outside `Test`. Nothing changes the signal definition. |
| 10 | Here is the goal restated in one paragraph. Is it right? | Catches misreadings before any work starts | ZF corrects, then ratifies |

This is 10 questions instead of the 26 in inner-loop-steering §4.6. ZF deferred the length question (Q7), and the campaign-specific questions are now answered by questions 2 to 6.

---

## 6. The tick: subscriptions without a model

`pi-streams tick` runs every 5 minutes from a systemd user timer that the quickstart installs. The user manager on this host runs without a login (`loginctl`: `Linger=yes`), which is how pi-web's two services already run. It is one script for every registered project home, and it uses no model tokens. Each row in a stream's `subscriptions.tsv` names a source, a condition and an action.

| Source | Example condition | Action |
| --- | --- | --- |
| pi-web status and the session event websocket | A thread is idle, asks a question, or reports done; a steer is still queued after 10 minutes; context is over 150k tokens | Prompt the coordinator with the event, or resend the steer with `--steer` |
| `gh` | A PR in the stream's repos gets a review, CI result or merge | Prompt the coordinator |
| BigQuery metadata | A table the stream named changes fields, rows or modified time | Prompt the coordinator; if the change is outside the write policy, stop the thread and ask ZF |
| BigQuery job history | Bytes billed today pass the cap from question 5 | Stop new queries and ask ZF |
| Schedule | For example, a daily status at 09:00, or a daily `maintain-verification-skill` run | Prompt the coordinator |
| Worktrees across streams | Two streams claim one worktree or branch | Ask ZF (inner-loop-steering §1.8) |

The coordinator adds rows when ZF asks, as Projects does. The mechanical checks from inner-loop-steering §5.4 run here too: delivery, verified park, pending asks, model, context, liveness and child receipts. The tick also commits each project home's durable files (§3).

**Outages (Q16).** When a session's last model call failed on a usage limit or a provider error, no model in that pool can be trusted to report it. The tick then:
- writes a line to the project home's `ALERTS`;
- marks the affected threads "waiting on quota" so nothing respawns into the outage.

The Grok Bot's routine already reaches this host over SSH to run `pi-web-cli`. It reads `ALERTS` and messages ZF, using its own token pool. When the next model call succeeds, the tick clears the alert and wakes the coordinator.

---

## 7. Gardening: harvest, reflect, correct (Q15)

- **Harvest.** Before a thread is archived, its last prompt asks it to write `handover/<thread>.md`: intent, what was done with proof, what is left, and what the next agent should know. This follows pstack's `pause-safely`. The coordinator then copies the lasting parts into the project's `context/`: how to test, gotchas, and ZF's preferences. The next stream in the project starts with them. This is Projects' "If one agent figures out how to test a service, every future agent can use those instructions".
- **Reflect.** When a thread fought the same problem more than once, the coordinator first prompts it with pstack's `/skill:reflect`. That skill reviews the active transcript and turns its lessons into edits to existing skills, so it has to run inside the thread.
- **Correct.** When the same mistake shows up across threads, the coordinator starts a thread in that repo with pstack's `/correct`. That skill makes the mistake impossible with architecture, types, a lint or a test, in that order.
- **Verify.** When a thread needs to prove behaviour in a repo that has no verification skill, the coordinator starts a thread there with pstack's `/create-verification-skill`, and adds a daily `maintain-verification-skill` subscription. This is the job Jig used to start.
- **When.** At thread close, at each milestone, and at stream close.
- **Deferred.** Judging which sessions are worth harvesting (ZF: "let's not for now").

---

## 8. Worked example: the ETL stream

`STREAM.md` after the kickoff, at `~/Projects/alphalab/streams/qmd-etl/STREAM.md`. The pins are filled in at the kickoff; the rest is from ZF's answers.

```text
# STREAM qmd-etl   ratified: <ZF marker>   pi-stack: <revision>
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
| T1 datapull | alc-qslite, the #654 worktree (adopted) | Runs the datapull locally for one day and one venue | Rows match the signal definition's columns |
| T2 push | the stream's `checks/`, no product code | A one-off script loads T1's output into `Test` | Row count and schema check pass |
| T3 compile | alc-cefi-sim-runner, bq-signal-compiler (adopted) | Compiles the template's features in BigQuery from T2's slice, then from the full window | A1 passes |
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

## 9. User story: deploying into a brownfield project

*As ZF on `pistack`, with alphalab's repos, worktrees and sessions already in place, I want one command to make the host ready, and one more to start a stream on work that is already in flight. Nothing I have running should break.*

**What is already there.** This is the real state on 2026-10-06:
- pi with its own settings and seven packages;
- pi-web running as two systemd user services;
- an unversioned `~/.local/bin/pi-web-cli`, which the Grok Bot runs over SSH;
- 21 code repos and 23 worktree folders under `~/Projects/alphalab`;
- live sessions in the #654 worktree;
- Jig state in alc-penv.

**Step 1: one command.**

```bash
curl -fsSL https://raw.githubusercontent.com/alienczf/pi-stack/main/install.sh | bash -s -- -y --project ~/Projects/alphalab
```

The installer works through these in order. Each step checks before it changes anything, and a second run changes nothing.
1. **Overlay, pstack skills and packages,** as today. The skill list now includes `correct`. Unrelated settings and packages, `auth.json` and `sessions/` are untouched, as today.
2. **pi-web.** It finds pi-web running and leaves it alone. On a host without it, it installs pi-web the way pi-web's own help recommends (`npm install -g @jmfederico/pi-web --allow-scripts=node-pty`, then `pi-web install`).
3. **`pi-web-cli`.** It backs up the existing file and installs pi-stack's version. The old subcommands and their JSON output stay identical, so the Grok Bot's routine keeps working; the new verbs are additions.
4. **The `pi-streams` command,** the `/stream` and `stream-kickoff` skills, and the tick timer, enabled.
5. **Jig.** It removes Jig's installed copies, and reports that alc-penv and alc-penv-jig still hold `.pi/jig/`, which it leaves alone.
6. **The project home.** Because of `--project`, it runs `pi-streams init ~/Projects/alphalab`:
   - creates `~/Projects/alphalab/streams/` as a git repo, with the template `AGENTS.md`;
   - writes `project.toml` from the 21 repos and their `git worktree list`;
   - seeds `context/README.md` with one line per repo pointing to its `AGENTS.md` and test command, where they exist;
   - asks the setup questions below and writes the answers to `project.toml`;
   - registers the project home with the tick.

   It reads the code repos and never writes to them.

   The setup questions each show a default, and `-y` accepts all of them. ZF can change any answer later in `project.toml`.

   | Question | Default | Used for |
   | --- | --- | --- |
   | Which URL do you open pi-web at? | The address in `~/.config/pi-web/config.json`. On `pistack` that is `http://127.0.0.1:8504`, which another machine reaches only through a tunnel. | Links that `pi-streams new` prints and the Grok Bot relays |
   | Where should the project home's private remote live? | None; the project home stays a local git repo | The tick pushes after each commit when a remote is set |
   | Which model and thinking level should coordinators use? | Astra at `xhigh` (§4.1) | `coordinator_model` and `coordinator_thinking`; each stream can override them |

7. **`pi-streams doctor`.** It checks:
   - pi and pi-web health;
   - that `pi-web-cli` can list sessions;
   - that the timer is active;
   - that the project home is a clean git repo;
   - that `correct`, `reflect` and both verification skills are installed.

   It ends by printing the next command.

**Step 2: start the stream.** Run `pi-streams new qmd-etl --project ~/Projects/alphalab`, or type `/stream new qmd-etl` in any pi session, or ask the Grok Bot to start a stream. The command:
- creates `streams/qmd-etl/`;
- starts the coordinator on Astra;
- sends the kickoff;
- prints the coordinator's pi-web link.

**Step 3: kickoff, brownfield edition.** Before asking anything, the scout reports what is already in flight:
- the #654 worktree and branch, and the bq-signal-compiler worktree;
- the existing sessions in the #654 worktree, with their state;
- the campaign's `.audit/` notes and the rulings in them;
- the leftovers in `Test`.

It proposes to adopt both worktrees and to archive the idle sessions instead of resuming them. It also offers to copy six past rulings into `DECISIONS.md`, which ZF confirms one by one. Then come the ten questions (§5), the one-paragraph restatement, and ratification.

**Step 4: work.**
- The coordinator adopts T1's worktree and starts T1 and T2 in parallel (§8).
- ZF can open any thread in pi-web and talk to it directly.
- The tick wakes the coordinator on thread events, PR activity, table changes and spend. ZF hears from it only for decisions and outages.
- When T3 needs to prove behaviour in alc-cefi-sim-runner, which has no verification skill, the coordinator starts a thread there with `/create-verification-skill`. ZF reviews that PR like any other.

**Step 5: an outage at 03:37.**
- The tick sees usage-limit errors, marks the threads "waiting on quota" and writes `ALERTS`.
- The Grok Bot messages ZF.
- When calls succeed again, the tick wakes the coordinator, which picks up from `STATE.md`.

**Step 6: close.** After A1–A3 pass, `pi-streams close qmd-etl`:
- harvests the threads' handovers into the project's `context/`;
- archives the threads in pi-web;
- writes a final summary;
- commits.

The next alphalab stream starts knowing how to run the datapull, how to push to `Test` cheaply and how to validate against TenV.

**Upgrades.**
- Re-running the quickstart updates the harness without touching project homes.
- `update-pstack` still updates pstack on its own reviewed path.
- `pi-streams doctor` lists streams created by an older template; nothing migrates silently.

**What it never does in a brownfield project:**
- It writes nothing inside a code repo except untracked `.stream` files in worktrees it creates or adopts.
- It prompts no existing session unless that session is adopted into a stream.
- It never touches `auth.json`, session files or pi-web's config.

---

## 10. What to build, in order

Every step is a PR to pi-stack. The last one is the pilot.

1. **Strip Jig.** Remove its launcher, controller, skill, prompt, routes table and tests; the installer deletes installed copies and reports repo-side `.pi/jig/`. Add `correct` to the pstack skill list.
2. **`pi-web-cli` into `bin/`** (Q12). Keep today's subcommands and JSON output; add `prompt --steer`, `stop`, `abort`, `queue-clear`, `asks`, `answer`, `model` and `thinking-level`. All of these use routes pi-web already has. Test against a stub server; the installer backs up the old copy.
3. **The engine and templates:** `pi-streams init`, `new`, `status` and `doctor`, and the project and stream templates.
4. **Threads:** `thread spawn`, `thread adopt` and `rotate`, with `prompts/thread-brief.md`.
5. **Skills:** `/stream` (new, status, close) as a thin wrapper around the command, and `stream-kickoff`: scout, ten questions, restate, ratify.
6. **`pi-streams tick` and the systemd timer.** Subscriptions, mechanical checks, outage alerts and git commits. It gets a test mode that runs the tick against recorded session logs (inner-loop-steering §8, Phase A).
7. **Harvest and `close`.**
8. **Quickstart wiring:** `--project`, the setup questions with their defaults, pi-web detection, and `doctor` at the end.
9. **Pilot:** the ETL stream in `~/Projects/alphalab/streams/`.

**Pilot pass criteria:**
- the quickstart on this host completes with `doctor` green and the Grok Bot's `pi-web-cli` calls unchanged;
- ZF restates the goal at most once per week;
- no steer waits in a queue for more than 10 minutes;
- no write or spend outside the policy goes unnoticed for more than one tick;
- the coordinator's notional cost stays under 10% of the threads' cost.

**No design questions are open.** Questions about a particular host, project or stream are asked by `pi-streams init` (§9, step 1) or the kickoff (§5), each with a default.

# pi-streams: handover for a fresh session

Written 2026-10-06 at ZF's request, so this work can restart with fresh context. Treat this note and the two design docs as the authoritative trail, per pstack's session-pickup playbook: resume from here, and don't redo the research. Delete this file before PR #14 merges.

## Intent

ZF wants a working version of Cursor Projects whose threads are pi-web sessions instead of Cursor cloud agents, because his Cursor tokens are limited. The whole harness lives in pi-stack, and one quickstart command makes a host ready for work. The market-data ETL stream is the example and the first pilot, not the subject.

ZF's words, in order:
- "findout a working cursor project / 'pi-stream' setup using the etl workstream as an example usecase. don't get too distracted with this"
- "I'm more interesting in getting a 'working cursor projects' with pi-web as my 'threads' backend, instead of cursor cloud agents. I don't have enough tokens on cursor."
- "will be nice if we can push all these harnessing stuffs into a single repo. since jig is more or less made redudnant with pstacks reflect correct and validation skills we can strip that."
- "ultimately i want that quickstart command to provision all of these ready for work without all the faffing about"
- "shouldn't all these go into the streams setup? not in this process planning stream?"

## Where it stands

- **The design is done**, in [pi-streams.md](pi-streams.md), and has no open questions. Anything specific to a host, project or stream is asked by `pi-streams init` or the kickoff, each with a default.
- **The evidence** is in [inner-loop-steering.md](inner-loop-steering.md): the Oct 2–6 campaign analysis, the cited Pocock, poteto and Cursor sources, and the polyrepo answer. Where the two docs differ, pi-streams.md wins.
- **Nothing is built.** Nothing on `pistack` was changed, no live session was prompted, and no BigQuery table was read or written.
- **ZF has not yet said to start building.**

The decisions, in one line each (details in pi-streams.md):
- **Harness.** pi-stack, with no separate pi-spring repo (§3).
- **Project state.** One private project home per project, for example `~/Projects/alphalab/streams/`, with a folder per stream (§3).
- **Coordinator.** One per stream, kept warm while its context is small and started fresh once it is big (§4).
- **Wakeups.** A timer with no model calls; outages go to the Grok Bot (§6).
- **Jig.** Removed, and `correct` added to the pstack skills (§3).

## What was verified, and how

- **§4.2 cost and cache figures.** These come from the 12 session logs under `~/.pi/agent/sessions/--home-alphalab-Projects-alphalab-alc-qslite-.worktrees-v4-to-baseline-datapull--/2026-10-0*.jsonl`. For every assistant message I read `message.usage`: `input`, `cacheRead`, `output` and `cost`. The hit rate is `cacheRead / (input + cacheRead)`, bucketed by the gap since the previous assistant message in the same session. The script that did this was in `/tmp` and is not kept.
- **Thinking level.** Every one of those 12 sessions has one `thinking_level_change` event to `xhigh`: 9 on `gpt-6-astra` and 3 on `gpt-6-luna`.
- **pi-web.** The server is `@jmfederico/pi-web` 1.202607.3, and its routes are in `dist/server/sessions/sessionRoutes.js`. It binds `127.0.0.1:8504` (`~/.config/pi-web/config.json`, with an empty `allowedHosts`). It keeps "projects", which are registered directories (`~/.pi-web/projects.json`), and "workspaces" under them, which are worktrees.
- **Quotes.** Every Pocock and poteto quote was checked against its source; the provenance note is in inner-loop-steering §3. ZF is quoted verbatim.

## State

- **Repo and branch.** alienczf/pi-stack, which is public, on branch `cursor/inner-loop-steering-design-b18d`.
- **PR.** [PR #14](https://github.com/alienczf/pi-stack/pull/14), a draft against `main`.
- **Git identity.** Repo-local `Cursor Agent <cursoragent@cursor.com>`.
- **Working tree.** Clean after the commit that adds this file.
- **This session's transcript:** https://cursor.com/agents/bc-eac2fa79-bdd5-5248-8dc5-f9dc9e3bb18d. Read it only through a subagent; it is long.

## Next steps

Once ZF says to build, work through pi-streams §10 in order. Each step is its own PR to pi-stack, on its own branch off `main`. The build doesn't depend on #14 merging.

1. Strip Jig and add `correct`.
2. Move `pi-web-cli` into `bin/`, with the new verbs.
3. Add `pi-streams init`, `new`, `status` and `doctor`, plus the templates.
4. Add `thread spawn`, `thread adopt` and `rotate`.
5. Add the `/stream` and `stream-kickoff` skills.
6. Add the tick and its timer.
7. Add harvest and `close`.
8. Wire the quickstart.
9. Run the ETL pilot.

## Facts the build needs

- **Jig in the repo.**
  - Files: `bin/jig.sh`, `bin/jigctl.py`, `prompts/jig.md`, `scripts/check-jig.sh`, `scripts/jig_tests/`, `scripts/render-jig-routes.py`, `skills/jig/`.
  - Mentions elsewhere: `README.md` (28), `scripts/check-overlay.sh` (10), `overlay/AGENTS.md` (6), `decisions.tsv` (4).
  - Mentions in `install.sh`: lines 30, 37, 39, 255–364, 386 and 661–668.
- **Jig installed on `pistack`.** `~/.pi/agent/jig/`, `~/.pi/agent/bin/jig`, `~/.local/bin/jig`, `~/.pi/agent/prompts/jig.md` and `~/.pi/agent/skills-pstack/jig/`, plus the `skills-pstack/jig` entry in `~/.pi/agent/settings.json`.
- **Jig state in other repos.** `alc-penv` and `alc-penv-jig` hold `.pi/jig/`. Leave it alone; `doctor` only reports it.
- **The pstack skill list.** `install.sh` line 4 (`pstack_skill_names`) lacks `correct`.
- **`pi-web-cli`.** It is `~/.local/bin/pi-web-cli`: 109 lines of Python, `BASE = http://127.0.0.1:8504`, with the subcommands `list --cwd`, `spawn`, `prompt`, `status` and `commands`. `prompt` sends no `streamingBehavior`.
  - The Grok Bot runs it over SSH, so the new version must keep these subcommands and their JSON output byte-compatible.
- **Services.** pi-web runs as the systemd user services `pi-web.service` and `pi-web-sessiond.service`, with `Linger=yes`. The tick timer can run the same way.
- **Worktrees.** Find them with `git worktree list` in each repo. On this host they sit as sibling folders, under `.worktrees/`, inside repos, under `~/Projects/.worktrees` and in `/tmp`. `~/Projects/alphalab` itself is not a git repo.
- **Coordinators in pi-web's sidebar.** Registering the project home as a pi-web project is probably how coordinators get there. Check this in step 3; it isn't in the design yet.

## Rules that hold until ZF lifts them

- **Scope.** Design and build the harness. Don't bring ZF questions about a particular host, project or stream; they belong in `pi-streams init` or the kickoff, with a default.
- **Steering pi.** Only through `pi-web-cli`. Don't prompt live sessions.
- **BigQuery.** No reads and no writes.
- **The host.** Don't change the installed pi-stack config until ZF approves an install. Never write `auth.json`.
- **Models.** Plan and review on Astra, and never fan out across model types. The Grok Bot stays high-level.
- **Citations.** Cite a source for every view attributed to Pocock, poteto or Cursor, and quote ZF verbatim.
- **Language.** Use plain language. ZF answers with `/bro` when a question isn't plain.
- **Git.** No force-push and no amend.

## Handover prompt

Paste this into a fresh session on alienczf/pi-stack, then add the instruction for that session:

```text
You are picking up the pi-streams work for ZF in alienczf/pi-stack, branch
cursor/inner-loop-steering-design-b18d (draft PR #14). Follow pstack's session-pickup playbook:
the trail is authoritative, so don't redo the research.

Read, in order:
1. docs/design/pi-streams-handover.md: intent, state, verified facts, rules, next steps.
2. docs/design/pi-streams.md: the design to build. It has no open questions.
3. docs/design/inner-loop-steering.md: only the sections pi-streams.md cites.

The goal is Cursor Projects on pi-web threads, with the harness in pi-stack and one quickstart
that makes a host ready for work. The ETL stream is only the example and the pilot. Questions
about a particular host, project or stream go into `pi-streams init` or the kickoff with a
default; don't ask ZF them here. Keep to the rules in the handover.

ZF's instruction for this session:
```

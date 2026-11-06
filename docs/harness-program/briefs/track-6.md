# Track 6 brief (Grok Bot, 2026-10-24): build the merged design as a working proof of concept, with install for a new external machine

ZF (t234u, 2026-10-24 00:46 SGT, verbatim): "Going to leave you to drive and make this work over the weekend. Lmk when we have a working poc on branch. Update install so we can test the branch on a new external setup"

Grok Bot owns every decision. Make your own calls, log each in `13-track-6-progress.md` under "Decisions" with a one-line reason, and don't wait on ZF. Deadline: Mon 2026-10-26 09:00 SGT.

## Read first (targeted reads)

In `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/`:
- `51-design-merged.md` (revised per Z25): your spec. Section 8 "Implementation plan" is the commit plan. Build it as written; where it is silent, decide and log it.
- `43-prime-compaction-hooks.md`: stock Prime v0.10.1 has no before-compaction hook, so stock auto-compaction is disabled (`compaction.enabled=false` before the session is built) and pi-stack runs its own percentage check, save, `compact`, readback and resume.
- `00b-zf-messages-verbatim.md` (t232u, t233u, t234u), `03-decisions.md` (Z15, Z21, Z23, Z25, Z26), `02-principles.md` (layer affinity: codebase, then CI and deterministic checks, then hooks, then rules, then skills), `11-artifact-map.md`.
- `20-prime-cli-design.md` and branch `feat/prime-cli` (worktree `/home/alphalab/Projects/worktrees/pi-stack-prime-cli`, read-only for you): the Prime client to build on.

## Branch and worktree

- Create worktree `/home/alphalab/Projects/worktrees/pi-stack-merged-poc` on new branch `feat/merged-poc`, cut from local `main`, then bring in `feat/prime-cli` (merge or rebase; your call, log it). If track 1's `feat/streams-must-fix` lands on main while you work, Grok Bot rebases you; don't do it yourself.
- Stacked commits, each with its tests, each leaving the suite green. Commit locally only. Don't push (Grok Bot bundles and pushes).

## Hard design limits (Z21, Z23, Z25)

- Stock Prime v0.10.1 only. No change to Prime's source.
- Only what pi-stack defines. Don't touch coordinator-invented files.
- Workers have no state files. They are not streams. They run as poteto clean sessions with only a context handover and a kickoff.
- Result review is the stream's own adversarial review of each reported summary against the original intent, as guidance in the stream's AGENTS.md role text, not a hook. It spawns a reviewer session only when it judges one is needed.
- Fresh STATE once per pi-stack message. Reject stale pi-stack messages. Stopping running tool calls is best effort via the stock stop/abort. Capture only the stock Prime input paths pi-stack uses; reject attachments; terminal-typed messages stay uncaptured.
- Baseline vocabulary only (AGENTS.md, STATE.md Goals/Rules/Log, history/, stream, session, worker, tick, DCR, F-DCR, compaction, fork). Plain descriptive names, no H/P codes, no retired STREAM/ACTIONS/GOAL/DECISIONS names.
- Login, outages and recovery are permanently out of scope. Don't build handling for them.

## Install for a new external machine (one commit in the stack)

Update the install script and its README/install doc on this branch so a brand-new machine with no Caladan setup, no options-01 paths and no Alphalab credentials can:
1. install pi-stack from `feat/merged-poc` (fresh clone);
2. install, or point at, stock Prime v0.10.1;
3. log in with its own Codex account (the user's own step; document the command, never automate or copy credentials);
4. create a stream and run it.
Document the exact commands in order. Remove or guard every hard-coded Caladan, options-01, `/home/alphalab` or Alphalab-credential assumption on the install path.

## Verification (record evidence in `13-track-6-progress.md`)

1. The full test suite passes.
2. Fresh install in a clean environment on options-01, from the documented commands only: a new temp HOME under `~/.cache/pi-stack-track6/` (not /tmp, it does not survive reboots) and a fresh clone. Never touch the live `~/.pi-stack`, `~/.local/bin`, the live 8504 pi-web, the tick, or any existing stream or session. No copied credentials.
3. A disposable stream on that install runs end to end on real Prime inference through: at least one steer; one worker handover and kickoff; one compaction by our own percentage check with save and readback around it; one stale pi-stack message rejected; the stream's adversarial review of a worker summary against the original message.

Real inference in the clean HOME needs a Codex login there, which must be ZF's own and must not be copied. If everything else is built and checked and only that remains, stop and report `TRACK 6 STATUS: blocked | built and verified offline; waiting only on a Prime Codex login in <exact temp HOME> with <exact command>`. Grok Bot handles the ask.

## Limits

- Don't prompt, steer, stop or spawn any other existing session or stream. Your own subagents on the same model are fine; long runs go to background subagents.
- No push, PR, merge or GitHub comments. No credentials, never print tokens. Git holds code, docs and small reports, never data.
- On a usage limit or quota error, stop and report. Never switch provider or model.
- Edit only the new worktree and `docs/harness-program/13-track-6-progress.md` in the docs worktree.

## Progress and finish

Keep `13-track-6-progress.md` current: commits with SHAs, tests, evidence paths, decisions, what remains. Work through the whole stack without returning between commits. End your final reply with exactly one line:
`TRACK 6 STATUS: <done|blocked|partial> | branch=feat/merged-poc@<sha> | suite=<pass|fail> | install=<pass|pending> | e2e=<pass|pending> | next=<one line>`

## Alignment with revised 51 section 8 (Grok Bot, 2026-10-24 01:35 SGT)

The revised 51 passed its gate (G38). Section 8 is the build order: commits 1 to 8 as tabled (state writer, Prime transport, messages/wake/stop, clean poteto workers, own compaction, computed close, `install.sh --merged-poc`, `poc init/doctor/verify` with `scripts/check-merged-poc.py`). Follow its external-machine installer contract and fresh-machine commands exactly, with these calls already made:
- Clean-install test: use a prefix and HOME under `~/.cache/pi-stack-track6/<run-id>/`, cloned from the local `feat/merged-poc` worktree (the branch isn't on GitHub until Grok Bot pushes it); the documented commands must otherwise be the README's.
- For the options-01 test run use `POC_MODEL=openai-codex/gpt-6.1-sol`, `POC_THINKING=xhigh`, and pick `POC_PERCENT` yourself so the fixture really crosses it; log the value and why. These are test values, not installer defaults.
- `poc verify` must also cover the extra verification items above (one steer, one worker handover and kickoff, one stale pi-stack message rejected, the stream's own adversarial review of a worker summary), in addition to section 8's ordered compaction sequence.
- If `feat/prime-cli` and section 8's commit 2 disagree, section 8 wins; reuse the CLI code where it fits and log what you reused.

---
name: stream-kickoff
description: First-turn interview for a new pi-streams coordinator. Scouts the project read-only, asks ten questions one at a time with a recommended answer for each, restates the goal, and writes STREAM.md for ZF to ratify. Use only for /skill:stream-kickoff, which pi-streams new sends.
disable-model-invocation: true
---

# Stream kickoff

If STREAM.md's first line already holds a `ratified:` marker with ZF's words and a date, say so and stop. Find facts yourself. Ask ZF only for decisions, and never answer one for ZF. Start no thread and adopt no session until ZF ratifies STREAM.md.

## Scout

Survey these before the first question. This is read-only. Write nothing outside the stream folder and prompt no session.
- Each repo in `../project.toml` and its `git worktree list`.
- Open PRs in those repos with `gh pr list`, if `gh` works.
- The pi-web sessions in each worktree, from `pi-web-cli list --cwd <worktree>`.
- Any table or artifact ZF names at any point. Read its metadata only, and never run a query that bills bytes.

Report what you found in a short list. If work is already in flight, propose each of these on its own for ZF to confirm:
- A worktree and its session to adopt, as an exact `pi-streams thread adopt <stream> <session-id> --worktree PATH --role ROLE` command.
- A past ruling found in notes, to append to DECISIONS.md with its source.

## Interview

Ask one question at a time, with your recommended answer from the scout. ZF accepts or corrects it. The label in capitals names the STREAM.md section the answer fills. Keep each settled answer and confirmed adopt command in STATE.md as you go, and resume from there if STATE.md already holds some.

1. GOAL. What outcome do you want, and who uses it?
2. TARGET. Is there an artifact already agreed on that defines the output? Pin it by path and sha.
3. ACCEPTANCE. How will we know it's right? What is the oracle, and which mismatches are acceptable? Name a script in `checks/` for each check. Record each accepted mismatch in DECISIONS.md.
4. E2E PATH. What is the smallest-blast-radius way to test end to end, as far as possible?
5. WRITES. Where may it write, and how much may it spend? Get each cap as a number.
6. END STATE. What must the end state be, including cleanup?
7. Which repos, branches, PRs and sessions are in play? The answer goes into the plan, not STREAM.md.
8. AUTONOMY. What may the coordinator decide alone, and what must come to you?
9. NO-GO. What must not happen?
10. Restate the whole goal in one plain paragraph and ask ZF to correct it. Repeat until ZF confirms it.

## Ratify

Write the answers into STREAM.md's sections. Only after ZF confirms the restatement, set its first line to `ratified: <ZF's confirming words, verbatim> <UTC date>`, with the date from `date -u +%F`. From then on only ZF changes STREAM.md.

## Plan

Rewrite STATE.md with the first plan: each thread to start, with its repo, its role and the `checks/` script that must pass for it to be done. Add a row to `subscriptions.tsv` only when ZF asks for a watch. Then run the confirmed adopt commands and start the first threads with `pi-streams thread spawn`.

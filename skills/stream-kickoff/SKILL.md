---
name: stream-kickoff
description: First-turn interview for a pi-streams coordinator. Scouts read-only, asks for human decisions, and records the ratified charter in STATE Goals. Use only for /skill:stream-kickoff, which pi-streams new sends.
disable-model-invocation: true
---

# Stream kickoff

Read AGENTS.md and STATE.md. Goals' first line is `ratified: no` until ZF explicitly confirms the charter. If it already records ZF's dated confirmation, report that and stop the interview. Start no thread and adopt no session before ratification. Do not use TODO.md or PLAN.md; plan in Goals and record completed work in Log.

## Scout

Discover facts before asking for decisions. This phase is read-only and prompts no session.

- Open context/README.md on demand for its project repo index. Run `git worktree list` in the referenced repos.
- Inspect open PRs with `gh pr list` when available.
- List sessions in relevant worktrees with `pi-web-cli list --cwd <worktree>`.
- Inspect only the metadata of tables or artifacts ZF names. Do not run billed data queries without authorization.

Do not read raw engine registries or configuration. Use `pi-streams status <stream-id> --json` for the stream path and thread session view. If the index lacks a required reference, report the missing fact instead of guessing ownership.

Report sourced findings briefly. Propose any existing session adoption as an exact `pi-streams thread adopt <stream> <session-id> --worktree PATH --role ROLE` command for ZF to confirm. Present historical rulings for confirmation; do not automatically classify them as current authority.

## Interview

Ask one question at a time with a recommendation grounded in the scout. Never answer for ZF. Rewrite settled draft answers in Goals, preserving the three exact subsections `### North Star`, `### Current objective`, and `### Charter`. Keep the marker unratified. Resume from those draft answers rather than a second planning file.

1. North Star. What outcome is wanted, and who uses it?
2. Target. Which agreed artifact defines the output? Record its path and pin in Charter.
3. Acceptance. What oracle establishes success, and which mismatches are acceptable? Reuse existing checks. Create a script only when the task explicitly requires it or the agreed verification needs one.
4. E2E path. What authorized path verifies the real artifact with the smallest blast radius?
5. Writes. Which locations and effects are authorized? Do not invent resource caps, spend limits, or a mandatory budget interview. Record a limit only when the incoming task explicitly supplies it.
6. End state. What result is required? Which cleanup, if any, is explicitly authorized?
7. Existing work. Which repos, branches, PRs, and sessions are in play? Keep current references in the objective and sourced work entries in Log.
8. Autonomy. Which decisions are within the grant? Stop before actions outside it. A recommendation is not permission to continue without an answer.
9. No-go. What must not happen? Preserve every active prohibition.
10. Restate the outcome and Charter in one plain paragraph. Ask ZF to correct it until ZF confirms it.

## Ratify

Only after ZF's explicit confirmation, rewrite Goals in place and set its first line to `ratified: <UTC date> <ZF's confirming words, verbatim>`. Keep North Star, Current objective, and Charter distinct. Goals and Rules are current text, never an appended history pile.

Record each new human ruling through `pi-streams state ruling <stream> --subject SUBJECT --body-file - --notice-id NOTICE`. Rules contains only rulings still in force. The engine also appends Log. Retire a superseded ruling with its exact old source text; the engine preserves it in history before removal. Notice provenance is not an authentication receipt. Never create rules, skills, or memory to self-remedy a failure.

## Plan

Set the immediate authorized objective through `pi-streams state objective <stream> --body-file -`. The single resolver uses this objective, falling back to North Star. There is no North Star completion flag. Only if the confirmed grant authorizes continuous work, enable `pi-streams drive <stream> on`; otherwise leave it off. A verified finite objective may select the next authorized objective or use `pi-streams drive <stream> off`. No disposition record is required for the engine's current-goal re-injection, and injection is never permission to bypass a human question, stop, failure boundary or uncertain external job.

Append interview outcomes, work, failures, and ZF steers through `pi-streams state append <stream> --subject SUBJECT --body-file - --request-id ID`. Keep each request ID stable across retries. Only Log is capped at 30; the engine rotates overflow every tick. Never prune or rotate entries yourself. Open cold history only on demand. The same STATE remains authoritative through routine same-session DCR. Follow AGENTS for engine-requested SYNC/DUMP, then yield with the returned ready acknowledgement. The engine owns compaction and fixed current-goal RESUME; the agent never authors that prompt.

Run only confirmed adoption commands and start authorized threads with `pi-streams thread spawn`. A worker's acceptance follows the actual ask, not an automatic demand for a new check script. Do not edit engine-owned subscription files. If ZF requests a watch and no engine command supports it, report the missing capability. Do not start new task effects to repair environment/auth/resource failures. Log and report them for human repair.

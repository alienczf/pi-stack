# Track 4 steer 3 (Grok Bot, 2026-10-23 15:02 SGT): Z22 a B version with no Prime changes (in addition to steer 2)

This adds to steer 2; it doesn't replace it. Finish the Z21 cleanup of 41 (and 40 where cited), then do this. `03-decisions.md` now has Z22.

**Z22, ZF verbatim: "Yes let's do a no prime change version".**

Write `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/42-design-b-prime-unchanged.md`: design B on **stock Prime v0.10.1 only**.
- Not allowed: native Prime changes, a Prime fork, or a modified build.
- Allowed: only what pi-stack can add from outside Prime, meaning client-side code, its own files and checks, the tick, and Prime's existing commands and extension points.
- The first line must be exactly: `Runtime: stock Prime, no Prime changes (Z22)`
- Use the same 8 Z19 headings and the same Z21 vocabulary rules, including a New concepts table at the top (zero rows is best). Use the same plain names as your cleaned-up 41 so they line up.
- Hooks, prompts and storage must be exact:
  - hooks: trigger, layer, I/O, code location naming the stock Prime extension point or command, and failure behaviour;
  - prompts: full text;
  - storage: paths and schemas against Z15.
- Add a plain **gap table** covering each of the four gaps 41 needs Prime changes for:
  1. the message save that ignores write errors and returns no id;
  2. results that are not stored durably;
  3. no evidence check before an ask closes;
  4. no way to move child workers to a new parent.
- For each gap, say whether 42 **covers**, **works around**, or **leaves open** it, and what that costs: what can bypass it (which clients or paths), and which recovery stays manual.
- Keep the stacked commit plan with tests, and the risks. No defaults locked (Z17). Open questions stay questions.

**Limits:** same as steer 2. Docs only, no commit or push, don't touch 31 or 50, no credentials, never switch provider.

Finish by replying exactly: `TRACK 4 STATUS: done (naming cleanup + 42 stock Prime)` (or `TRACK 4 STATUS: blocked | <reason>`)

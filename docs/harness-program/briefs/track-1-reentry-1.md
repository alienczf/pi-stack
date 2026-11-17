Re-entry from Grok Bot, 2026-10-23 10:35 SGT. Your context passed 85%, so I aborted your turn mid-amendment and compacted the session. Nothing on disk was reverted.

Re-read, in this order, from the docs worktree `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/`:
1. `briefs/track-1.md` (your brief) and `02-principles.md` (layer affinity).
2. `00b-zf-messages-verbatim.md` and `03-decisions.md` (Z1–Z11, G17, G18).
3. `briefs/track-1-steer-2.md` (Z6–Z10, artifact health, `11-artifact-map.md`) and `briefs/track-1-steer-3.md` (Z11: park, per-session `failures/<session-id>.lastgood`, alert, ratify, F-DCR; G5 classes 2–5 move to the Z11 path).
4. `10-pi-streams-fix-catalog.md` as it is now.

Current phase: one amendment pass so the catalog reflects Z1–Z11. Your steer-2 edits were landing through the stacked plan (last edit touched Stack S1 at 10:25). Steer 3 had not been consumed yet; fold it into this same pass.

Do:
- Diff the catalog against every Z1–Z11 requirement and steer-2/steer-3 "what the catalog must say" list. Finish whatever is missing; don't rewrite what's already right.
- Z11 goes in class (a). Rewrite the G5 item so only usage limits stay wait-and-retry and classes 2–5 take the Z11 path. Add `failures/` to the migration item. Give each Z11 open item a chosen default (detection, fork support in pi-web-cli and prime, what "streaming" means for the fork, how the ratified notice reaches the tick). Make the stacked plan include the Z11 commits and an F-DCR round-trip check.
- Keep each fix's layer and blast radius in the review tables.
- Keep context lean: use targeted reads and `rg`, not whole-file dumps.

End with one line: `TRACK 1 STATUS: <complete|incomplete> — Z coverage <list>, open items <n with defaults>`.

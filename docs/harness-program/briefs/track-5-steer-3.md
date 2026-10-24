# Track 5 steer 3 (Grok Bot, 2026-10-24 00:50 SGT): follow-up to steer 2, Z26

This adds to steer 2. Keep working on it.

ZF (t234u, verbatim): "Going to leave you to drive and make this work over the weekend. Lmk when we have a working poc on branch. Update install so we can test the branch on a new external setup"

The revised 51's **8 Implementation plan** will be built directly as the proof of concept on branch `feat/merged-poc`, starting as soon as 51 passes the gate. So make section 8 concrete enough to code from without further design:
- exact files to add or change in pi-stack, function names, and the order of stacked commits, each with its tests;
- an end-to-end proof-of-concept check: one stream on stock Prime v0.10.1 going from intake through compaction (our own percentage check, then save, compact and resume) to an ask closing;
- **install changes for a new external machine**, as a commit in the plan. Cover:
  - what the installer sets up, including installing stock Prime v0.10.1, `compaction.enabled=false` in the owned session's settings, the pi-stack hooks, and the AGENTS.md/STATE.md templates;
  - what it must not touch;
  - the exact commands to test the branch on a fresh machine.
  The login itself stays the user's own step (permanently out of scope).

Everything else in steer 2 stands: zero open questions, docs only, edit only 51 and 50, and the same finish line: `TRACK 5 STATUS: done (51 + 50 revised per Z25)`

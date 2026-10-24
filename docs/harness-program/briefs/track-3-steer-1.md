Steer from Grok Bot, 2026-10-23 09:22 SGT. ZF has made his first-pass calls, recorded as Z1–Z5 in `docs/harness-program/03-decisions.md` (re-read it). Two of them affect you:

- **Z2:** per-ask lifecycle and ask ledgers, the coordinator grading its own homework (context decay, own-paraphrase oracles), and constraint lifetimes now belong to **track 3**, as the "lifecycle workflow design". Treat them as first-class problem statements in step (a), and make sure each of your three designs covers them in (e) and (f).
- **Z3/Z4 are now fixed constraints for your designs.** Z3: the tick runs "dump, compact, resume" on the same session at >= 150k, superseding the 252k target. Z4: alerts and waits go to ZF by Slack DM as `<stream-id>:: <message>`, as quiet as possible.

Continue from where you are; don't restart.

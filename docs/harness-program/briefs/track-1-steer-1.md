Steer from Grok Bot, 2026-10-23 09:22 SGT. These are ZF's first-pass calls on "what actually breaks". They are recorded as Z1–Z5 in `docs/harness-program/03-decisions.md`; re-read that file and `00-brief-verbatim.md` (section t211u). They are binding on the catalog, and where they differ from your brief, they win:

1. **Z1. Tick liveness is a track 1 fix.** When a stream is being driven, the tick aggressively pushes it forward: it turns unfinished work into the next action instead of only relaying changes. Quota and auth recovery is a separate catalog item, using the G5 five classes as adopted.
2. **Z2. Move these to "Deferred to track 3", not track 1:** per-ask lifecycle and ask ledgers, the coordinator grading its own homework (context decay, own-paraphrase oracles), and constraint lifetimes. Keep only a one-line problem statement for each.
3. **Z3. Context policy SUPERSEDES the 252k target (D2, G4).** It's one three-in-one, tick-driven action. On every tick where the coordinator is taking a turn and its context is >= 150k, don't kill or interrupt it. Instead:
   - (a) DUMP: the agent updates STATE.md, TODO and all relevant stream status and progress artifacts, and writes its own resume prompt for the same session after compaction.
   - (b) COMPACT the same session.
   - (c) RESUME it with that resume prompt.
   Prefer compacting early, because ZF watches token use from outside. Design the mechanism around existing tick and pi primitives, cover direct prompts, and drop the 252k-request-boundary/native-hook item unless it's still needed to make this work.
4. **Z4. Alerts and waits go to ZF as a Slack DM, in the format `<stream-id>:: <message>`, to him only (no BossOps).** Keep them as quiet as possible to avoid notification fatigue: one alert per blocker, plus one on recovery at most. Put the alert route at the right layer.
5. **Z5. Steer delivery ack stays track 1.** An ack counts only once the coordinator has actually consumed and applied the steer. "Accepted for transport" doesn't count.

More ZF calls may follow. Keep the review table easy to amend. Continue from where you are; don't restart.

Steer from Grok Bot, 2026-10-23 10:05 SGT. Addendum to steer 2: ZF's last candidate-fix call, t213u, is recorded as **Z11** in `docs/harness-program/03-decisions.md` (G5 is now marked NARROWED), and his words are in `00b-zf-messages-verbatim.md` section t213u. Both files are refreshed in the docs worktree; re-read them. ZF is done dictating candidate fixes, so after this the catalog goes to his first-pass review once it reflects Z1–Z11. Fold this into the same amendment pass; don't restart.

**Z11. Physical and environment failure modes** (SSO, auth or login, disk or resource exhaustion, outages). The human resolves these; agents don't.
1. On hitting one, record the last good turn id (the last unbroken turn before the failure) for the coordinator and every affected spawned worker, one file per session: `failures/<session-id>.lastgood` in the stream folder. File exists = parked on failure; content = last good turn id. Several can exist at once. Verify that pi exposes turn ids (session JSONL entry ids) and that prime does too.
2. Default: never touch the harness environment. No new rules, skills or memory are written in response to the failure (behavior drift). The only exception: the human's ratification message explicitly asks for it, and then that content goes into the continuation prompt.
3. Alert ZF in the Z4 format (`<stream-id>:: <message>`, Slack DM, quiet). ZF fixes it and sends a ratified notice.
4. On ratify, run **F-DCR**: fork the session at the last good turn id, run DCR (Z8) on the fork as if after a provider outage, and once the fork is confirmed streaming, delete the original session (its error-handling turns are noise; the fork keeps everything before the failure), then remove the lastgood file.

What the catalog must say:
- **Layer.** Tick/engine code for detect, record, fork, DCR and wipe. The re-injected stream prompt (the Z6/Z8 template) carries "don't self-remedy env failures; park and log". Templates/skills only for what code can't do.
- **Interaction with G5's five classes.** A usage limit stays wait-and-retry on the same provider. Classes 2–5 (Codex login, tool login, full disk, other model errors) now go to the Z11 park → alert → ratify → F-DCR path. Rewrite the G5 item to match.
- **Open items, each with a chosen default:** how a failure is detected (e.g. `stopReason=error` plus an error-text classifier and probe), fork support in pi-web-cli and in prime (route exists or must be added; fallback if not), what counts as "streaming" for the fork (e.g. `isStreaming` true, or `messageCount` grown past the resume prompt with a non-error assistant turn), and how ZF's ratified notice reaches the tick.
- Put Z11 in class (a), mechanical failures, and add the `failures/` dir to the migration item.

End with the same `TRACK 1 STATUS:` line.

# 01 — Program scope

This restates ZF's 2026-10-23 program brief (`00-brief-verbatim.md`) and the 09:12 SGT update. It replaces the deep-research build plan as the goal. ZF found that plan too frameworky and withdrew it at 09:09 SGT.

Canonical home: branch `docs/harness-program` on alienczf/pi-stack, folder `docs/harness-program/`, opened as a draft PR. It is mirrored to `/workspace/harness-program/` on the Grok Bot box, and the inputs are copied to the host at `~/Projects/pi-stack/streams/pi-streams-harness/context/harness-program/`. The pi-streams-harness stream is not trusted to hold the program, because it is itself the thing under repair.

## Track 1 — pi-streams must-fix catalog, then the fixes

- **What:** a catalog of every obvious or must-fix change to pi-streams itself. An item qualifies if it has a low blast radius, or if it must change no matter what. That includes the tick (continuation and liveness), the circular recovery, the coordinator compaction boundary imposed in the harness at 252k, removing the numeric-caps kickoff question (D1), the evidence-path archive bug (#37), STATE as a current view, steer delivery acknowledgement, and stale coordinator ids.
- **Artifact:** `docs/harness-program/10-pi-streams-fix-catalog.md`. It has one table that ZF can review in one sitting, with the fix, its layer, its blast radius and the default for any item that needs his call. It ends with a stacked, ready-to-implement plan of small commits.
- **Gate:** the catalog is the ONLY thing ZF reviews, as a first pass. After his go-ahead the fixes are implemented, merged to pi-stack main, and every open branch is rebased onto the new main.
- Frameworky or speculative items go to track 3.

## Track 2 — prime-agent CLI access (runs now, in parallel)

- **What:** agentic CLI and network access to PrimeIntellect prime-agent's long-running server. Grok Bot and the target box always sit on separate machines. The pi-web-cli command surface and the skills interface stay consistent, so the two cross-compatible with low changeover friction. No GUI.
- **Artifacts:** first the design, `docs/harness-program/20-prime-cli-design.md`. Then a WORKING implementation on branch `feat/prime-cli`, cut from current main, at parity with pi-web-cli for pi-stack's needs and verified against a real prime-agent server.
- **Dependency:** porting *streams* onto prime waits until the track 1 fixes land, so prime doesn't inherit broken streams. The CLI itself doesn't wait.
- **Open question for ZF, not blocking:** caladan. pi-stack has no caladan branch, and pi-bot has caladan at bb39dc0.
- **Coordinate, don't disturb:** the unratified prime-stack stream (coordinator `01a16177-96a3-7923-bfe9-55fbc3774482`).

## Track 3 — problem-state research and competing designs (runs now, in parallel)

- **What, in order:** (a) Collect the unresolved items as problem statements. (b) Do a light scout of pi-stack's own principles-to-playbooks spectrum around the single poteto-mode entry point. (c) Build an external corpus of real practitioner failure modes, seeded by Grok Bot's X pass in `31-x-corpus-seed.md`. (d) Merge and /interrogate the corpora down to a few core causes. (e) Write three competing holistic designs, each with its mechanisms assigned to layers per `02-principles.md`, penalising frameworky designs. (f) Build a pros/cons table plus coverage of the problem statements.
- **Artifact:** `docs/harness-program/30-research-designs.md`. Its end state is the three-design proposal table for ZF to read.

## Ordering and dependencies

```
t1 catalog ──(ZF first-pass go)──> t1 implement ──> merge to main ──> rebase all branches ──> streams-on-prime port
t2 design ──> t2 feat/prime-cli implement + verify ────────────────────────────────────────┘ (port also waits on t1)
t3 (a)→(b)→(c)→(d)→(e)→(f) ──> ZF reads table ──> chosen design feeds later work (not track 1)
```

- Tracks 1, 2 and 3 start together.
- Track 1 items deferred as frameworky become track 3 problem statements.
- `feat/prime-cli` rebases onto main after track 1 merges.

## Operating rules (all tracks)

- Reach options-01 only via `options-01-ssh` / `pi-web-cli-remote` over Twingate userspace. Never TUN, never raw scp.
- GitHub over HTTPS with the pi-bot credential helper on the Grok Bot box. Never print tokens.
- On a usage limit, stop and report. Never switch provider.
- Merge nothing without ZF's go-ahead. Git holds code, docs and small reports, never data.
- Status lives in `STATUS.md`, which is machine-readable and read by the driving routine every run.

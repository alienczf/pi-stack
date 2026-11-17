# Track 1 steer 9 (Grok Bot, 2026-10-28 23:40 SGT) - decision G49: align the stale model fixtures

Your last section ends "blocked on permission to align the contradictory fixture inputs". Grok Bot owns this decision under ZF's delegation and has decided it. Do not wait for an operator. Do not touch the native install, the live pi-web services, the live ~/.pi-stack, or any live stream or session in this steer.

Decision G49. The 16 remaining pi-streams failures on fa8566c are stale test fixtures, not product bugs: the track 1 fixtures return a fixed Astra status, while G40 (ZF's call) makes Sol 6.1 xhigh the stream default and Luna 6 xhigh the worker default. You may change those fixtures and their helpers so that the fake status reports the model the code actually requested (or so the fixture sets the G40 defaults explicitly). Keep every behavioral assertion, keep the production model-verification boundary strict (no accepting a mismatched model, no trusting setter acknowledgements in product code), and change no test outside the four affected families (coordinator identity, failure alignment, generated state, handover identity).

Also settle the socket-path finding at the lowest layer that fits: in the test environment setup the suites already use, make a too-long TMPDIR fail early with a clear message that names the AF_UNIX path limit, or document the short-TMPDIR requirement next to that setup. Pick the smaller change.

Next actions, in order, in private clones only (no push, no merge, no stash or reset in any live worktree):
1. Commit the fixture alignment (and the TMPDIR guard or note) as small commits on feat/merged-poc-rebased with a one-line reason each.
2. In the corrected private environment, rerun the full pi-streams suite, the full Prime suite and the PoC test file once on the new head.
3. Write a verified complete-history bundle of the new head and record its path and SHA256.
4. Record G49 and the evidence in 12-track-1-progress.md (and a short note in 13-track-6-progress.md), with the final head sha and suite counts.
5. End with exactly one line: `TRACK 1 STATUS: merged-poc-rebase <green|blocked> | head=<sha> | pi-streams=<n> pass | prime=<n> pass,<f> fail,<e> error | bundle=<path> <sha256>`.

Grok Bot then force-pushes feat/merged-poc with --force-with-lease from your bundle, runs the native install from outside the session, and sends part 2 (real-stream verification of the corpus symptoms). If a fix attempt fails twice or the evidence is ambiguous, stop and report the exact finding in the status line instead of looping.

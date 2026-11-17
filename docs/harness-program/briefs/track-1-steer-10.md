# Track 1 steer 10 (Grok Bot, 2026-10-29 00:35 SGT) - decision G50: verify the staged native tree, then start part 2 on what is already installed

Your G49 line is accepted. Grok Bot force-pushed feat/merged-poc to c913ff1 with --force-with-lease (draft PR #39 now shows the rebased branch). Grok Bot owns the next calls under ZF's delegation and has made them. Do not wait for an operator.

Decision G50. The native pi-web install is not applied yet, for two reasons. First, your handoff says 87 of 363 package-version records in the staged npm tree differ from the verified source lock and no full native suite has run on that tree; that gap gets closed with evidence before a live apply. Second, the host is not quiescent: other pi sessions (a qslite-654 stream coordinator and an alc-penv session) are mid-turn, and restarting pi-web-sessiond would cut their turns. Grok Bot applies install-native.sh from outside Pi only when the native suite on the staged tree is green and no other session is streaming.

Rules for this steer: private prefixes, clones and temp HOMEs only. Do not touch the live pi-web services, the live native package under ~/.local/share/pi-node, ~/.local/bin, or any session or stream other than a disposable one you create. No push, no merge, no stash or reset in any live worktree.

Next actions, in order:
1. Install the exact staged upgrade tarball (artifacts/upgrade/jmfederico-pi-web-1.202607.3.tgz, sha be4c5297...) with the same offline cache and npm flags install-native.sh uses, into a private prefix, so the dependency tree matches what a live apply would produce. Record the resolved dependency census and confirm it equals the staged one.
2. Run the full native pi-web suite against that private installed tree (source 61c5e26 tests resolving the staged dependencies), with the short TMPDIR from G48. If anything fails, run the same failing files on the rollback tree (base v1.202607.3, same cache) in the same environment: failures on both are pre-existing or environment and get documented; failures only on the upgrade tree get a root-cause finding (do not repair the live tree).
3. Part 2, first half. On a disposable stream created on the already-installed ~/.pi-stack (129415e), check which of the five corpus symptoms no longer reproduce using only what is already installed: a stream that stalls without ZF prompting, a lost ask, circular recovery, a coordinator that never compacts, and a bloated always-loaded state file. For each one, say whether its fix depends on the native pi-web build; mark those "pending native install" instead of forcing them. Recovery stays closed per G44/Z25, so for circular recovery, show it cannot loop (parked, not retried), not that recovery works.
4. Record G50 and the evidence in 12-track-1-progress.md.
5. End with exactly one line: `TRACK 1 STATUS: native-tree <green|blocked> | upgrade-tree=<n> pass,<f> fail | symptoms=<stall:pass|fail|pending-native>,<lost-ask:...>,<circular-recovery:...>,<never-compacts:...>,<bloated-state:...> | evidence=<path>`.

If a step fails twice or the evidence is ambiguous, stop and report the exact finding in the status line instead of looping.

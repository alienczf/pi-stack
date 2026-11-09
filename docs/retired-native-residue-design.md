# Retired native residue dispatch policy

## Problem

A coordinator row can be marked archived while the native session service still lists the exact session as live. The strict coordinator resolver raises on that residue before returning an adopted successor. Cleanup belongs to the retired session. Dispatch authority belongs to the exact active successor and its current automatic-admission generation.

## Alternatives and selection

Candidate A used a shared read-only coordinator inspection and one safe archive attempt at the first enabled tick boundary. Later dispatch checks revalidated the exact successor and its saved admission. Candidate B added a dedicated reconciliation module and ran reconciliation at several dispatch boundaries. Both candidates scored 24 points. Candidate A won the tie because it kept ownership in the existing thread, replacement, terminal-session, and delivery modules without a new reconciliation module or persistent state.

The implementation keeps Candidate A's shape and takes three safeguards from Candidate B. It carries the saved admission through delivery preparation and send, checks the raw listing before building the ID cache, and compares archive and source bytes just before source removal.

## Chosen design

The engine shares one read-only coordinator inspection between strict lifecycle resolution and automatic dispatch. The inspection verifies registered identities and returns the active coordinator plus any registered archived rows that remain native-live. It checks the raw listing before building ID-keyed caches. `resolve_coordinator` remains strict for adoption, rotation, drive control, and other lifecycle callers.

At the first enabled tick boundary, the engine checks the exact successor and its durable admission. It attempts one checkpoint-bound archive for each eligible residue. The preflight rejects busy sessions, queued input, unresolved asks, callback owners, active effects, and changed checkpoints. The native archive request repeats the exact entry and admission-generation checks. A preflight refusal, native refusal, lost reply, or persistence error is diagnostic. It does not revoke the successor's independent dispatch authority.

The tick rechecks the selected coordinator at `wake_target`. A prepared automatic delivery keeps its original successor, cwd, admission kind, and generation. Prepare and send reject a changed identity or generation. A resumed send also checks local drive-off before any native query. The native automatic-admission check remains the final receiver-side fence.

## Hard fences and no-replay rules

Explicit drive-off, an unregistered native candidate, an ambiguous successor identity, invalid successor status, disabled admission, and a changed admission generation remain hard fences. Ambiguity limited to retiring the predecessor prevents its archive attempt but does not block a valid successor.

The terminal-session record is the only durable archive disposition. `sending`, `refused`, `uncertain`, and `archived` dispositions do not trigger an automatic archive retry. A busy or unsafe preflight creates no archive request. The engine never sends new input to the retired session.

Status reports residue under `nativeReconciliations`, not `dispatchBlockers`. Status stays read-only. The native archive store compares the archived bytes with the live source before it removes that source, so a differing or changing archive cannot justify deleting newer source bytes.

## Rejected alternatives

Ignoring residue in the global resolver would weaken lifecycle callers and hide cleanup state. Requiring successful cleanup before dispatch would make successor availability depend on the retired session. A separate reconciliation module would duplicate policy already owned by coordinator inspection, terminal dispositions, replacement preflight, and delivery validation.

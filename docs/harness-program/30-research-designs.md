# Harness program track 3. Problem-state research and competing designs

Status. Research in progress. This is not an implementation plan or an approved design.

ZF's comparison table will appear here after the unresolved problems, source scout, external corpus, and combined interrogation are complete.

## Work sequence

1. Route through the **how** skill. For motivation questions, also route through the **why** skill.
2. Throughput checkpoint stays one line: `throughput checkpoint: n/a, read-only investigation`.
3. Produce the `how`-shaped output (Overview / Key Concepts / How It Works / Where Things Live / Gotchas), or a recommendation with a tradeoffs table if the request is a decision between alternatives.
4. Apply the **unslop** skill to the reply.

throughput checkpoint: n/a, read-only investigation

- [ ] Collect unresolved problem statements before proposing solutions.
- [ ] Scout pi-stack's principles-to-playbooks structure.
- [ ] Gather and deduplicate practitioner failure reports, including the X seed.
- [ ] Interrogate the combined corpus and identify three to six causes.
- [ ] Compare three holistic designs with explicit layer placement.
- [ ] Check coverage, track 1 deferrals, source reachability, and decision compliance.

## Decisions

- T3.1. Only the parent writes the two authorized artifact paths. Delegates return read-only reports. This avoids competing writes in the shared docs worktree.
- T3.2. Use the required openai-codex/gpt-6.1-sol model for every delegate. Independent same-model interrogation does not provide multi-model diversity.
- T3.3. Do not reconstruct the missing brief text. Treat the explicit program decisions as the available constraints.
- T3.4. Keep progress in this authorized artifact rather than create a separate repository planning file. The other tracks share the worktree.
- T3.5. Recheck the X seed and track 1 catalog before closing. Both are being written in parallel and were absent or incomplete at the initial read.
- T3.6. Reject workflow wrapper completion as evidence of child completion. The first workflow returned launch receipts and started dependent readers prematurely. I interrupted only my own dependent delegates and will release each stage against substantive reports. No premature result counts as evidence. Interrogations A and C had already documented this runner defect. I missed that warning before dispatch. This track cannot repair the runner because its scope is artifact-only.

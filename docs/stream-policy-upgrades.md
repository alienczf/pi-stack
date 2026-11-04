# Upgrade existing stream policy through the engine

These steps are for the parent operator. They do not authorize production actions by a source builder. Preserve the stream's current grant, genuine stops, model, provider, source hashes and unresolved effects.

## Migrate legacy layouts

1. Run `pi-streams migrate STREAM --plan --home HOME`. Retain the exact output outside source Git. It identifies the selected registered root and raw source hashes.
2. Classify byte spans explicitly with `--mapping MAP`. Map the genuine authority line, North Star, current objective, Charter, active Rules and historical text. Keep the broad original North Star distinct from a finite current objective. Do not infer authority from a heading, bare affirmative or old completion claim. Map the exact complete STREAM authority line. A valid calendar date followed by one sentence period, such as `2026-10-16.`, retains its original marker bytes.
3. If historical Git traversal is impractical, add `--history-mode snapshot`. This retains exact ordered source bytes and source Git hashes. Entry timestamps are labeled migration-start fallbacks, not historical introduction times.
4. For a bare legacy affirmative, supply the actual dated standing-grant relay record through `--relay-source SOURCE.json`. The migration plan binds its exact bytes and hash. This records source provenance, not transport authentication. A negative unratified marker stays negative. No duplicate human notice or body is required.
5. Save the ready plan, then run `pi-streams migrate STREAM --apply PLAN.json --home HOME`. Resume an interrupted operation with `--resume`. Changed source, plan, staged authority or ownership refuses application. Inspect the retained history and scoped commit before further work.

### Retain selected current STATE

Use mapping rows with exactly `source`, `start`, `end` and `target`. Offsets are half-open UTF-8 byte boundaries. `STATE.md` accepts only `current_objective`, `rules` and `history`. Once any STATE span is mapped, classify every STATE byte without gaps or overlap. Keep one current-objective span at most across all sources. Preserve current STOPs and job identifiers explicitly. Do not move consumed grants out of history or use STATE to supply ratification, North Star or Charter.

The engine encloses active STATE selections in literal code fences so legacy headings cannot change canonical field boundaries. It records each projection's source span, source hash, selected-byte hash and target in the migration Log. It also retains every original ordered STATE occurrence by exact hash in history, including repeated entries and projected text. Other active mappings that change canonical field boundaries refuse planning.

A plan without STATE mappings retains the existing archival-only behavior. Its `limitations` and migration Log state that current objectives, job state and STOPs are not inferred. A ready plan is not proof that its classification preserves unknown active work or authorizes a resume. Review the source-backed classifications before applying it.

## Repair a classified prefix before canonical Goals

1. Classify the exact prefix explicitly. Obtain its UTF-8 byte count from the selected source. The selection must end at a complete line boundary. Do not infer that a completion heading or STOP is historical.
2. For current instructions, run `pi-streams migrate STREAM --repair-plan --prefix-rules-bytes N --home HOME`. The engine retains the exact prefix visibly as active Rules inside a literal code fence. Existing Rules follow without changes.
3. Only for a genuinely historical prefix, use `--prefix-history-bytes N` instead. The two classification options are mutually exclusive. Missing or unknown classifications refuse planning.
4. Review and save the plan, then run `pi-streams migrate STREAM --repair-apply PLAN.json --home HOME`. The engine archives the entire original STATE with its exact bytes and SHA-256. Use `--repair-resume` after interruption.
5. Run `pi-streams status STREAM --json --home HOME` and inspect the reported STATE path. Confirm that current STOP instructions remain in Rules. Repair does not resume work or enable drive.

The suffix must already be valid canonical STATE with unchanged owned Log bytes. Goals, ratification, North Star, current objective, Charter, existing Rules, optional sections, and Log entries retain their original bytes and order. The Log ownership record is unchanged. An unregistered empty Log acquires the empty ownership record.

Version-2 plans bind the explicit prefix disposition, full source, projection, Log ownership, and planning Git parent. Source, retained archive, Log ownership, overlapping staged edits, or Git-parent drift refuses application or interrupted resumption. Existing version-1 historical plans and retained journals remain supported with their original source checks.

This operation refuses malformed UTF-8, empty active Rules, other suffix corruption, unregistered nonempty Log, and pending Log ownership. Those cases need an explicit source-backed repair plan. It does not invent Goals, rulings, handovers, grants, dates, or a completed objective.

## Upgrade AGENTS and record policy

1. Run `pi-streams upgrade STREAM --home HOME` after migration or repair. The engine updates AGENTS only when its bytes match the recorded template revision. It preserves locally modified files.
2. Read the resulting AGENTS and STATE through the status-reported stream path. Confirm that genuine stops, blocked-goal escalation, policy refusal and continuous drive agree. Do not edit project trees directly.
3. Record an actual sourced ruling with `pi-streams state ruling STREAM --subject SUBJECT --relay-source SOURCE.json --home HOME`. Use `--supersedes-file FILE` only for exact old active Rules that the source explicitly supersedes. Do not erase a Charter restriction by treating it as history.
4. If modified AGENTS cannot be upgraded by the guarded operation, retain its bytes and report that limitation. No force-replacement command is supplied. Recording a ruling is not proof that an old loaded session adopted a new AGENTS file.
5. Verify drive through supported status and actual completed work. A finite objective, restart, blocker or recovery is not North Star acceptance. Keep drive on until verified North Star acceptance, a genuine later stop, or an explicit authorized cap.

The rejected task retains its durable policy blocker. Supported native sessions can perform one separate `clean-policy-analysis-v1` metadata analysis in a private session with no tools or project resources. This operation does not inherit a prefix or replay the rejected task. It preserves source bytes and audit links outside model input. A successful analysis is not task recovery or acceptance. A rejected or uncertain analysis remains blocked without iterative retries. Other independently authorized lanes may continue.

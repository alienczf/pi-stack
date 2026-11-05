# Documentary source-preserving repair

`pi-streams migrate STREAM --plan --mapping MAP.json --recovery-sources SOURCES.json` can restore an immutable original contract and retain legacy source bytes without deciding ratification from prose. Application uses the exact reviewed plan through the existing protected migration journal.

## Version 2 input

The input contains exactly `version: 2` and `supplemental_sources`. No authority witness, instruction date, principal, trust label or approval field is accepted. The rejected version1 narrative-authority input is not supported.

A Git source name matches `git:[a-z][a-z0-9-]{0,63}`. Its descriptor has `source_kind: git-blob`, a full ancestor commit OID, `path: STREAM.md`, the exact regular blob OID, its SHA256, and its exact UTF8 `bytes_base64`. Git timestamps never become instruction dates.

A retained file name matches `retained:[a-z][a-z0-9-]{0,63}`. Its descriptor has `source_kind: retained-file`, an owned regular relative Markdown path under `context/`, its SHA256, and exact UTF8 `bytes_base64`. Every directory component and file is ownership-checked. Symlinks, special files, traversal, binary content and changed source are refused.

These sources are documentary. Their Markdown, quotation containers, example labels and natural-language approval claims are never parsed as execution authority. Supplemental originals remain untouched and outside the current-source retirement set.

## Authority preservation

This path accepts only legacy schema0 streams. It reads their current authoritative STREAM first line, never a ratification claim inside legacy STATE or supplemental material. Only a record already accepted by the ordinary current-source authority guard is copied unchanged. Existing canonical-schema repair keeps its separate unchanged-authority path. An existing negative remains negative. An unvalidated bare affirmative, missing marker or narrative does not become a positive record; the canonical marker remains `ratified: no`.

This is not a historical denial or a request for human ratification. Exact old affirmative statements and any real dates remain documentary source. The structural repair cannot manufacture current execution authority, widen the Charter or renew historical launch, DRIVE, publication, cloud or cleanup grants. Existing authenticated execution authority, where present, remains subject to its normal guard.

## Exact plan and repair record

The generated plan contains an engine-derived `repair_policy`. It binds the selected root, exact current authority before/after hashes, current and original-contract hashes, mapping hash, plan ID and canonical target hash. The policy is fixed to authority preservation; no caller trust label can change it.

Restoration recomputes the policy and the whole canonical target. Fresh application revalidates current source and immutable supplemental bytes before writing the protected migration journal. The scoped migration commit retains a hash-bound documentary repair record under `history/recovery-*.json`. That record is provenance, not a credential or an alternative runtime ratification predicate.

## Mapping and retained scope

Every byte of current STREAM, DECISIONS when present, STATE and supplemental sources requires explicit classification. Documentary repair mappings cannot target `ratified`. Historical marker lines may be retained as quoted documentary Charter text or history instead. Supplemental sources can supply only documentary North Star, Charter and history. Current STATE can supply only current objective, Rules and history.

Original broad contracts remain visible and distinct from finite current objectives. Selected current objectives, STOP/PARK, freeze, owner and job facts remain byte-exact in their proper canonical fields. Every original source occurrence is also retained exactly in ordered history, including duplicate entries. Existing active facts must not be dropped merely to obtain a ready plan.

Planning and application do not enable drive, prompt native sessions, infer completion or resume a stopped campaign. A ready plan means a complete structural repair proposal, not ratification or business acceptance. Back up each actual source first, review the real canonical output, apply the exact plan, and reconcile interrupted application through the existing journal. Existing ordinary migration plans and canonical-prefix repairs remain supported.

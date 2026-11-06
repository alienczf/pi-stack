# Documentary source-preserving repair

`pi-streams migrate STREAM --plan --mapping MAP.json --recovery-sources SOURCES.json` can restore an immutable original contract and retain legacy source bytes without deriving new grants from prose. Application uses the exact reviewed plan through the existing protected migration journal.

## Version 2 input

The input contains exactly `version: 2` and `supplemental_sources`. No authority witness, instruction date, principal, trust label or approval field is accepted. The rejected version1 narrative-authority input is not supported.

A Git source name matches `git:[a-z][a-z0-9-]{0,63}`. Its descriptor has `source_kind: git-blob`, a full ancestor commit OID, `path: STREAM.md`, the exact regular blob OID, its SHA256, and its exact UTF8 `bytes_base64`. Git timestamps never become instruction dates.

A retained file name matches `retained:[a-z][a-z0-9-]{0,63}`. Its descriptor has `source_kind: retained-file`, an owned regular relative Markdown path under `context/`, its SHA256, and exact UTF8 `bytes_base64`. Every directory component and file is ownership-checked. Symlinks, special files, traversal, binary content and changed source are refused.

These sources are documentary. Their Markdown, quotation containers, example labels and natural-language approval claims are never parsed as execution authority. Supplemental originals remain untouched and outside the current-source retirement set.

## Legacy plan compatibility

This path accepts only legacy schema0 streams. Its frozen serializer retains the existing first-line marker projection and policy fields so saved plans and interrupted journals reconstruct byte-for-byte. It copies a recognized historical marker unchanged and otherwise emits `ratified: no`. Canonical-schema repair preserves its existing suffix bytes. Original statements and dates remain in retained source history.

These markers and policy fields are documentary compatibility data. They neither authorize nor block spawning, drive, dispatch, or recovery. New streams omit the marker entirely. Structural repair cannot widen Charter, resume genuine stops, or renew consumed launch, publication, cloud, or cleanup grants.

## Exact plan and repair record

The generated plan contains an engine-derived `repair_policy`. It binds the selected root, exact current authority before/after hashes, current and original-contract hashes, mapping hash, plan ID and canonical target hash. The policy fields retain their original serialized form for saved-plan compatibility. They are not runtime admission checks.

Restoration recomputes the policy and the whole canonical target. Fresh application revalidates current source and immutable supplemental bytes before writing the protected migration journal. The scoped migration commit retains a hash-bound documentary repair record under `history/recovery-*.json`. That record is provenance, not a credential or a runtime admission predicate.

## Mapping and retained scope

Every byte of current STREAM, DECISIONS when present, STATE and supplemental sources requires explicit classification. Documentary repair mappings cannot target `ratified`. Historical marker lines may be retained as quoted documentary Charter text or history instead. Supplemental sources can supply only documentary North Star, Charter and history. Current STATE can supply only current objective, Rules and history.

Original broad contracts remain visible and distinct from finite current objectives. Selected current objectives, STOP/PARK, freeze, owner and job facts remain byte-exact in their proper canonical fields. Every original source occurrence is also retained exactly in ordered history, including duplicate entries. Existing active facts must not be dropped merely to obtain a ready plan.

Planning and application do not enable drive, prompt native sessions, infer completion or resume a stopped campaign. A ready plan means a complete structural repair proposal, not business acceptance or permission to resume stopped work. Back up each actual source first, review the real canonical output, apply the exact plan, and reconcile interrupted application through the existing journal. Existing ordinary migration plans and canonical-prefix repairs remain supported.

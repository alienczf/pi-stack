# Retained-source migration input

`pi-streams migrate STREAM --plan --mapping MAP.json --recovery-sources SOURCES.json` accepts exact retained contracts and legacy ratification witnesses. This input is provenance, not transport authentication, infrastructure-maintenance authorization, or renewed business authority. It cannot be combined with `--relay-source` or supplied during application or resumption.

## Version 1 object

The input has exactly three fields.

- `version` is the integer `1`.
- `supplemental_sources` maps source names to the descriptors below. An empty object is valid for witnesses from current sources alone.
- `legacy_authority` contains exactly `marker`, `evidence`, and `instruction_date`.

The engine binds this object, current source bytes, configuration, root, Git HEAD, and mappings in plan identity. Restoration and fresh application revalidate the bound inputs. Existing migration plans without this object remain supported.

## Supplemental descriptors

A Git source name matches `git:[a-z][a-z0-9-]{0,63}`. Its descriptor contains exactly these fields.

- `source_kind` is `git-blob`.
- `commit` is a full lowercase Git commit OID. It must be an ancestor of the selected root's HEAD.
- `path` is `STREAM.md`.
- `blob_oid` is the full lowercase OID of that regular Git blob.
- `sha256` is the lowercase SHA-256 of its exact bytes.
- `bytes_base64` contains those exact UTF-8 bytes in base64. Binary data is refused.

A retained file name matches `retained:[a-z][a-z0-9-]{0,63}`. Its descriptor contains exactly `source_kind`, `path`, `sha256`, and `bytes_base64`. `source_kind` is `retained-file`. The path is a relative Markdown file under `context/`. Directory components use letters, digits, underscores, or hyphens. The filename also permits periods. Every component must be owned by the current user. Symlinks, nonregular files, traversal, and paths outside that directory are refused.

Supplemental sources never enter the current-source retirement collection. Their references remain untouched and outside the scoped commit. The migration retains exact supplemental snapshots and a hash-bound witness bundle under `history/`. Repeated application refuses missing or changed supplemental retention.

## Legacy authority

`marker` is the exact complete first line of current `STREAM.md` or a supplemental ancestor Git STREAM. `evidence` is a nonempty array of corroborating spans. Each span contains exactly these fields.

- `source` names a current or supplemental source.
- `start` and `end` are integer, half-open UTF-8 byte offsets.
- `sha256` hashes the selected bytes.
- `text` is their exact decoded text.

STATE cannot supply ratification or corroboration. An ancestor cannot override a current negative or unratified marker or explicit ratification revocation. A current summary with no marker can recover only an exact dated ancestor STREAM authority line. The selected marker must be an existing dated authority line or a bare `ratified: yes` or `ratified: true`. A bare affirmative additionally requires a complete affirmative ratification statement. Every witness uses complete source lines. Ratification statements must occupy their complete original standalone paragraph; a caller cannot crop away an adjacent qualifier. Lazy blockquote continuations and example/question containers are excluded along with ordinary quotes and fences. Questions, negation and explicit revocation are refused rather than promoted by a matching prefix.

The instruction date is derived only from a recognized ratification-event statement or authority marker. `instruction_date`, when supplied, must agree with that derived date. Conflicting dates refuse the plan. An unrelated benchmark, backup or Git timestamp never supplies an instruction date. Unknown remains `null`. Sender, message identity, and relay-envelope fields are not accepted.

The canonical marker uses `retained-source-v1`, the witness bundle's SHA-256, and the derived date or `unknown`. Runtime admission also requires the completed engine migration journal to bind the same source bundle and recovery input. Its recorded migration commit must be an ancestor of HEAD and contain the exact witness and canonical authority line. A self-consistent caller-created history bundle without that durable migration binding is not authority. Existing dated authority behavior is unchanged.

## Projection and application boundaries

Mappings cover every byte of current STREAM, DECISIONS when present, STATE, and all supplemental sources. STATE permits only `current_objective`, `rules`, and `history`. Supplemental sources permit only `ratified`, `north_star`, `charter`, and `history`. The mapped authority must equal the bound marker span.

North Star and Charter fragments render as retained quotations when this input is present. Supplemental contracts are documentary source. Current contract fragments explicitly preserve standing constraints under current Rules. Their original broad contract text remains visible. Historical launch, DRIVE, publication, cloud, and cleanup grants are not renewed. Current completion, STOP, freeze, owner, and job facts require explicit current-objective or Rules mappings and remain visible.

Planning and application do not enable drive, infer completion, contact native sessions, or spawn work. A ready plan still requires independent review of its classifications. Parent-owned application uses the exact reviewed plan and the existing migration journal. Canonical prefix repair version 1 and version 2 are unchanged.

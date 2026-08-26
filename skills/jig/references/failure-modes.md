# Known agent failure modes jig must score

The runtime interview scores the target repo against each row. A hit becomes a refactor-plan item, a deferred guard, or a modes.md trigger. It is not a license to rewrite the tree on first run.

Cite the source path when you recommend a fix so the next agent can read the rule.

## Session lessons (pi-stack)

| Id | Failure | What jig should look for | Recommendation shape |
|---|---|---|---|
| S1 | Mixing process rules with repo architecture | A parent AGENTS.md that contains coding standards | Split. Parent is a router. Child jig owns nouns and guards. |
| S2 | Dumping a whole skill tree into discovery | `settings.json` skills pointing at a skills/ root | Allowlist. Principle leaves stay `disable-model-invocation`. |
| S3 | Copying skill bodies (pstack-claude) | Vendored SKILL.md forks of pstack | Point at a live clone. Map Cursor verbs in one adapter. |
| S4 | Sticky mode missing on Pi | No APPEND_SYSTEM.md | User overlay, not a repo jig. |
| S5 | Ancestor AGENTS.md leak | Fat file above the git root | Router-only ancestors. No hot-path or notebook rules there. |
| S6 | Landing CI on first discover | Jig writing .github or eslint on pass 1 | deferred-ci.md list only. |
| S7 | Always-on lint-after-edit | Hooks that inject tsc on every edit | Prompt "run the linter". Optional project hook later. |
| S8 | Semantic index as search | Custom embeddings for a personal repo | Enable Pi grep. No new index. |
| S9 | Fake subagents for context gathering | Orchestrator wrapping CLIs as the product | `pi -p` with cwd set. Coordinator owns briefs, not code. |
| S10 | Shared memory across opposing domains | One AGENTS.md for ULL and notebooks | Separate jigs. Separate lexicons. |
| S11 | Auto-merge without mechanical proof | "Looks profitable" as done | Domain-local proof. PnL is not CI. |
| S12 | Replacing SYSTEM.md | Project SYSTEM.md that drops Pi defaults | APPEND_SYSTEM.md only. |
| S13 | Skill catalog vanishing | `read` tool disabled | Keep read active. |
| S14 | Dual procedure (script vs skill) | Interview copied into bash | One SKILL.md. Thin wrapper. |
| S15 | Glossary-only nouns | Bullet list of names with no relationships | Lexicon in running prose. Nouns define each other. |
| S16 | Rename without a pin | Mass mv with no characterization test | Refactoring playbook. Pin first. |
| S17 | Whip-style after-the-fact scolding | Long AGENTS.md "do not" lists with no import wall | Import graph and types. Delete the scolding once the wall exists. |

## pstack process (agents wander)

| Id | Failure | Source | Jig look-for | Mode if hot |
|---|---|---|---|---|
| P1 | Edit without a traced model | `pstack/docs/guide/03-understand.md` pitfall | No `/how` culture, no architecture doc | `/skill:how` before edit |
| P2 | Symptom fix at the first plausible spot | same | God files, "utils" dumping grounds | `/how` then `playbooks/bug-fix.md` |
| P3 | Dual API paths / shims | `principle-migrate-callers-then-delete-legacy-apis` | `*legacy*`, `*compat*`, `*v2*` beside `*v1*` | `playbooks/refactoring.md` |
| P4 | Optional-field bags | `principle-type-system-discipline` | `{ flag: boolean; when?: Date }` shapes | `/skill:architect` |
| P5 | Casts, `any`, lying type guards | `typescript-best-practices` | `as `, `: any`, `as unknown as` | `/skill:tdd` plus types |
| P6 | Non-exhaustive matches | `cursor-team-kit/rules/typescript-exhaustive-switch.mdc` | switch on unions with no `never` default | deferred-ci exhaustive-switch |
| P7 | Inline imports | `cursor-team-kit/rules/no-inline-imports.mdc` | `import(` inside functions | deferred-ci no-inline-imports |
| P8 | Constraint comments instead of types | `no-comments`, Comment Sicko | `do not remove`, `IMPORTANT`, `too risky` | `/skill:no-comments` |
| P9 | Pass-through wrappers | `architect/references/design-red-flags.md` | one-caller adapters | `playbooks/refactoring.md` |
| P10 | Temporal decomposition | same | `load/` `validate/` `transform/` `save/` as packages | `/skill:architect` |
| P11 | Shallow modules, leaked wire types | same | public re-export of protobuf/JSON types | `/skill:architect` |
| P12 | Scattered booleans / ad hoc mutation | `principle-model-the-domain` | flags that must stay in sync | `/skill:architect` |
| P13 | Shared mutable writes | `principle-separate-before-serializing-shared-state` | two writers to one JSON/state file | modes.md, split files |
| P14 | Prove via compile | `principle-prove-it-works` | README says `npm test` is enough for UI | `/skill:create-verification-skill` |
| P15 | Observer effect | `playbooks/eval.md` | eval dirs named "eval" or "candidate" | `playbooks/eval.md` |
| P16 | Silent rename misses | `playbooks/refactoring.md` step 5 | names in strings, SQL, prose, back-links | rename plan must grep those |
| P17 | Compatibility layer as architecture | `outcome-oriented-execution` | old and new paths both live | migrate and delete |
| P18 | Giant files, spaghetti growth | `thermos/.../thermo-nuclear-code-quality-review` | files near or over 1000 lines | extract, `playbooks/refactoring.md` |
| P19 | Logic in the wrong layer | same, interrogate code-quality | feature checks in shared code | `/skill:how` placement |
| P20 | Folder-dump context | Cursor harness post, this session | AGENTS.md past ~200 lines | cut. pointer to tutorial |
| P21 | Synonym cycling | `unslop` rule 11 | same concept, many names | lexicon plus rename |
| P22 | Abstract metaphor nouns | `unslop` rule 26 | harness/substrate/wedge in code names | pick the concrete noun |
| P23 | CLI that blocks agents | `cli-for-agent/skills/cli-for-agents` | interactive prompts, no `--help` examples | CLI refactor plan |
| P24 | Broken skill, silent workaround | poteto-mode non-negotiables | comments "until X skill works" | fix the skill, don't workaround |
| P25 | Principle name-drop | `docs/guide/08-principles.md` | AGENTS.md lists principle names with no decision | delete. encode or drop |
| P26 | Scattered boundary validation | `principle-boundary-discipline` | parse or schema checks deep in call chains | parse at the edge, trust inside |
| P27 | Half-applied sequential updates | thermos code-quality rule 7 | multi-step writes that can stop mid-way | one writer, or one atomic replace |
| P28 | Unstructured `console.log` in shipped code | `typescript-best-practices` | `console.log` on a production path | structured logger |
| P29 | Wire types used past parse | `principle-boundary-discipline`, `typescript-best-practices` | `Record<string, unknown>` or protobuf types after the boundary | named domain type at parse |
| P30 | Safety claimed in prose, never run | `pstack/skills/blast-radius` | comments that a change cannot break callers, no script | run a real caller |

## Plugins repo (this checkout)

| Id | Failure | Source | Jig look-for |
|---|---|---|---|
| R1 | Inline imports | `cursor-team-kit/rules/no-inline-imports.mdc` | same as P7 |
| R2 | Non-exhaustive switch | `cursor-team-kit/rules/typescript-exhaustive-switch.mdc` | same as P6 |
| R3 | Reviewer-only process with no wall | thermos rubrics that never became CI | deferred-ci from the rubric hits |
| R4 | Plugin discovery drift | `create-plugin/skills/review-plugin-submission` | missing frontmatter, broken paths |
| R5 | Agent-hostile CLI | `cli-for-agent` | menus, no `--force` / `--dry-run` |
| R6 | Compatibility scanner unused | `agent-compatibility` | if the language matches, mention a scan as optional later |
| R7 | Documented start command does not boot | `agent-compatibility` docs-reliability | README command fails or launches a different program |
| R8 | Root `--help` dumps the whole manual | `cli-for-agent/skills/cli-for-agents` | one huge help blob, no per-subcommand `--help` | layered help with examples |

## Lauren / Dune fragments (public)

| Id | Failure | Look-for | Guard |
|---|---|---|---|
| D1 | No closed vocabulary | Many synonyms for the same thing | Lexicon in prose. 5 to 12 nouns that define each other. |
| D2 | Shortcuts around the conventional path | Helper that bypasses the entrypoint | Make the shortcut fail import or CI. |
| D3 | Cross-layer reach-ins | Renderer imports main internals, or the reverse | Dependency-direction check. |
| D4 | Callbacks and subroutines placed in the wrong module | Thread/callback logic outside the owning package | Public barrel only. Import graph fails the rest. |
| D5 | Unconstrained effects | `useEffect` (or the local equivalent) everywhere | Ban or wrap. CI. |
| D6 | Comments as architecture | Comments explaining placement | No-comments plus a type or import wall. |
| D7 | Feature code smeared across dirs | Same feature in 4 folders | Colocation. Isolated new files. |
| D8 | New work edited into a hot path | "Add X" lands as a branch inside a giant file | Isolated new file, then a thin wire-up. |

## How a hit becomes work

1. Score each id against this repo. `absent`, `present-unencoded`, or `already-guarded`.
2. `already-guarded`. Cite the lint or type. Do not restate it in AGENTS.md.
3. `present-unencoded`. Add a row to refactor.md and deferred-ci.md. Name the playbook in modes.md.
4. `absent`. Skip. Do not invent the failure.

Cap the first refactor plan at the five hottest `present-unencoded` hits. Depth before breadth.

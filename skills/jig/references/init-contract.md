# Jig repository configurator contract

This reference defines manifest version 2. Jig configures one whole Git repository. It does not improve product code.

## Product boundary

A successful campaign produces and records two repository capabilities:

1. A human-ratified `.cursor/skills/principle-repository/SKILL.md`.
2. One `.cursor/skills/verify-*/SKILL.md` generated and proven through pstack's `create-verification-skill`.

The controller adds `../.cursor/skills` to `.pi/settings.json`, so Pi and Cursor read one canonical skill tree. It never duplicates or symlinks a skill body. The terminal outcome is `configured`.

Package selectors, subtree paths, flags, and extra positional arguments fail before state changes. A monorepo is one repository-wide scope.

## Ownership

| Owner | Decisions and writes |
| --- | --- |
| Target operator | Repository Principle values, exceptions, amendments, exact digest ratification, and later product decisions. |
| Jig skill | Cited repository survey, interview presentation, and semantic synthesis of operator answers. |
| Python controller | Git-root resolution, route honesty, locks, contained paths, hashes, atomic publication, project settings merge, and the terminal record. |
| pstack create-verification-skill | Verification surface discovery, skill and feature-map generation, live proof, evidence, and cleanup. |
| pstack maintain-verification-skill | Later verification-skill audits and corrections. |

No Jig actor selects or edits a product-code improvement.

## State machine

```text
absent
  -> surveying
  -> awaiting-principles
  -> verification-building
  -> configured
```

Each active state has a matching `failed-*` state. `start` reconciles a recorded failed state to its owning active boundary. Atomic file replacement protects each committed document.

A manifest whose `schemaVersion` is `1` is an unsupported legacy campaign. Jig fails closed and tells the operator to preserve `.pi/jig` and any worktrees before an explicit archive or migration. Version 2 never reinterprets version 1 state.

## Artifacts

| Path | Owner | Purpose |
| --- | --- | --- |
| `.pi/jig/manifest.json` | Controller | Version 2 state, route, hashes, transitions, and configured capability paths. |
| `.pi/jig/profile.json` | Jig skill through controller validation | Cited repository facts used by the interview. |
| `.pi/jig/principles/` | Controller and operator input | Staged candidate, answers, and decision receipts. |
| `.cursor/skills/principle-repository/SKILL.md` | Target operator through exact ratification | The repository's project Principle. |
| `.cursor/skills/verify-*/` | pstack create-verification-skill | Runtime verification procedure, feature map, helpers, and its named evidence location. |
| `.pi/settings.json` | Repository, merged by controller | Loads `../.cursor/skills` in Pi without replacing unrelated settings. |

## Completion boundary

`complete-configuration` accepts only a version and the generated verification `SKILL.md` path. The controller checks containment, regular-file ownership, frontmatter, the `verify-*` name, and the file hash. It does not reimplement pstack's feature counts, helper rules, launch protocol, evidence format, or runtime proof.

`validate-configuration` proves the recorded Principle and verification skill still match their hashes and Pi still loads the canonical skill tree. Verification maintenance belongs to `/skill:maintain-verification-skill`, not Jig init.

## Pstack references

Jig references these logical installed procedures without copying them:

- `pstack/skills/create-verification-skill/SKILL.md`
- `pstack/skills/maintain-verification-skill/SKILL.md`

The shell route explicitly loads the trusted installed create procedure beside Jig. Current-session routes use the installed pstack skill allowlist. Generated repository files contain no machine-specific pstack checkout path.

## Public routes

[`public-routes.json`](public-routes.json) owns the generated table below.

<!-- public-routes:start -->
| Command | Resource loading | Receipt | Controller | Pause and resume | Terminal state |
| --- | --- | --- | --- | --- | --- |
| `jig init` | Starts a fresh Pi process with project context, extensions, prompts, themes, and discovered skills disabled. It explicitly loads only the installed Jig and create-verification-skill procedures. | `isolated-shell` | `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py` | Exit at awaiting-principles when the operator has not supplied a complete response. Resume active work with jig init. Resume with /skill:jig init or /jig init when the manifest records inherited-session. | `configured` |
| `/skill:jig init` | Uses the current trusted Pi session and its installed pstack skills. It never starts a nested Pi process. | `inherited-session` | `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py` | Stop at awaiting-principles when the operator has not supplied a complete response. Resume active work with /skill:jig init. Resume with jig init when the manifest records isolated-shell. | `configured` |
| `/jig init` | Expands to the registered Jig skill in the current trusted Pi session. It never starts a nested Pi process. | `inherited-session` | `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py` | Stop at awaiting-principles when the operator has not supplied a complete response. Resume active work with /jig init. Resume with jig init when the manifest records isolated-shell. | `configured` |
<!-- public-routes:end -->

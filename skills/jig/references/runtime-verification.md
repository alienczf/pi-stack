# Runtime verification boundary

Use this reference only after root `COMMANDMENTS.md` is ratified and current.

## Plan once

Inspect the repository, then submit one strict `verification-plan` to `begin-verification`. Bind the source revision, COMMANDMENTS hash, exact protected user path, three to five feature IDs, target-local helper paths, bounded self-test argv, cleanup owner, and timeout.

Use these fixed target paths:

- `.pi/skills/jig-verification/SKILL.md`
- `.pi/skills/jig-verification/references/features/index.md`
- `.pi/skills/jig-verification/references/features/<feature-id>.md`
- `.pi/skills/jig-verification/helpers/<helper>.py`

Do not write target files before the controller reaches `verification-building`. Preserve an unknown pre-existing verification skill and stop.

## Generate the project skill

Read the canonical installed `pstack/skills/create-verification-skill/SKILL.md`. Adapt its project skill path and feature index to the fixed Pi paths above. Do not copy its body.

The generated skill needs grounded Launch, Doctor, Drive, Evidence, Cleanup, and Helpers sections. Every helper invocation must appear in the skill. The feature index names the protected feature and links every planned feature file.

Each feature file records the feature ID, owner, public entry point, allowed dependencies, evidence, and last result. Use exactly these four H2 sections:

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with <harness>`
4. `Gotchas`

The protected feature repeats the exact ratified Action, Visible result, Evidence, Cleanup, and Thresholds values.

## Prove the real path

The planned self-test must launch one isolated instance, run Doctor, drive the protected path through the public surface, observe persisted state through a second public read, save action and result evidence, and clean up the exact owned process. Evidence survives cleanup.

Use a dynamic loopback endpoint or another isolated process boundary. Never kill by process name. Record the PID and process start identity. A timeout, malformed output, missing evidence, source drift, surviving process, or helper failure remains `verification-building`.

Run `complete-verification`, then `validate-verification`. Stop at `verification-ready`.

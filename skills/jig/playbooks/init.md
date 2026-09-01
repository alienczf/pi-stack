# Configure one repository

Use this playbook only for the exact `init` argument. Keep the selected resource-isolation value and controller path for every operation.

## Start or resume

1. Resolve the Git top level with `git rev-parse --show-toplevel`.
2. Reject every path, package selector, flag, and extra argument before state changes.
3. Run `start --resource-isolation <route>`.
4. Stop on a route mismatch or unsupported legacy v1 campaign. Preserve the paths named by the error.
5. Resume only the controller-returned state.

At `surveying`, inspect only the target repository. Submit one cited v2 profile through `commit-profile --resource-isolation <route>` on standard input. The profile records `productType`, public `entryPoints`, `existingPolicies`, and unresolved `unknowns`. Run `start` again.

## Ratify repository Principles

At `awaiting-principles`, follow [the repository Principles interview](../references/principles-interview.md).

Run `present-principles` once. Show observed facts separately from questions. Ask one complete round. Do not invent a default or answer from generic pstack policy.

Pass the complete JSON response to `stage-principles`. Display the full candidate at `.pi/jig/principles/candidate.md`, its exact SHA-256 digest, and its intended marker. Accept only one explicit decision:

1. Ratify the displayed digest.
2. Amend named answers.
3. Defer.

Use `record-principles-decision` for amend or defer. Use `ratify-principles` only after the target operator approves the exact digest and marker. Never write `.cursor/skills/principle-repository/SKILL.md` directly.

## Generate verification through pstack

At `verification-building`, read the installed `create-verification-skill/SKILL.md` in full and follow it without adding Jig requirements. Its canonical output stays under `.cursor/skills/verify-*/`.

If the repository cannot build or start without a product-code fix, stop and report that blocker. Jig init may add verification files, but it never repairs or improves product code.

After that procedure has run its own live proof and cleanup, submit only this completion record to `complete-configuration` on standard input:

```json
{"schemaVersion":2,"verificationSkillPath":".cursor/skills/verify-<app>/SKILL.md"}
```

The controller validates the skill boundary, records its hash, and idempotently adds `../.cursor/skills` to `.pi/settings.json`. It preserves unrelated valid settings and stops on malformed or conflicting settings.

Run `validate-configuration`, then `start`. Report `configured`, the repository Principle path, the verification skill path, and `/skill:maintain-verification-skill` as the later audit route. Do not run maintenance during init.

## Stop

`configured` is terminal. Do not propose a product change, start a worker, create a worktree, run a second improvement, deploy, or merge.

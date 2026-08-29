# Initialize one repository

Use this playbook only for the exact `init` argument. Keep the `resourceIsolation` value and controller path selected by `SKILL.md` for every operation.

## Start or resume

1. Resolve the Git top level with `git rev-parse --show-toplevel`.
2. Reject every package selector, path argument, flag, and extra positional argument. Do not write state for a rejected invocation.
3. Run `start --resource-isolation <route>` from the Git root.
4. If `start` reports a route mismatch, stop and print the recovery command from [the public-route matrix](../references/public-routes.json).
5. Resume only the state returned by the controller. Do not infer a state from file existence.

At `surveying`, inspect only the target repository. Submit one complete profile through `commit-profile --resource-isolation <route>` on standard input. The profile must satisfy the controller schema and cite target files. Run `start` again.

## Obtain target COMMANDMENTS

At `awaiting-commandments`, follow [the COMMANDMENTS interview](../references/commandments-interview.md).

Run `present-commandments` once. Show its `observedFacts`, its complete question set, and every `recommendedDefault` to the target operator. Ask one question round. A recommended default is not an answer.

If no complete response exists, pause at `awaiting-commandments`. Ask the operator to write the complete JSON response to `.pi/jig/commandments/answers.input.json`. Do not infer missing values or start a second interview.

Pass those exact bytes to the emitted `stage-commandments` operation. Display the full candidate file, its exact SHA-256 digest, and its intended marker. Accept only one explicit decision:

1. Ratify the displayed digest.
2. Amend named answers.
3. Defer.

Use the emitted `record-commandments-decision` operation for amend or defer. For amend, pass a complete amended response through the emitted follow-up operation. Use `ratify-commandments` only after the target operator explicitly approves the digest and marker. Then run `validate-commandments` and `start`. Never write root `COMMANDMENTS.md` directly.

## Build target verification

At `commandments-ratified`, read [the runtime verification boundary](../references/runtime-verification.md) and the installed `create-verification-skill/SKILL.md`. Submit one complete target-local plan through the emitted `begin-verification` operation before writing reserved files.

At `verification-building`, write only the controller-returned `reservedPaths`. Build the Pi verification skill, the feature index, three to five feature files when the target supports them, and target-local helpers. Run the emitted `complete-verification` operation. Fix reported defects while the controller remains at `verification-building`. Continue only after `validate-verification` succeeds and `start` reports `verification-ready`.

## Complete one first step

At `verification-ready` or a later first-step state, follow [the first-step playbook](first-step.md). Stop after the controller reaches `initialized`. Never select a second candidate.

## Pause and recover

A crash or clean operator pause resumes through `start` with the manifest's original route. Preserve existing `COMMANDMENTS.md` and `.pi/jig`. Do not delete, replace, relabel, or reconstruct controller-owned evidence.

# Initialize one repository

Use this playbook for `init` only. Stop after the manifest reaches the boundary implemented by the controller. This unit stops at `commandments-ratified`.

## Start or resume

Resolve the Git top level and run `jigctl.py start` with the current route. Use `inherited-session` for `/skill:jig init` and `/jig init`. Use `isolated-shell` only when the trusted shell launcher started the fresh Pi process.

Do not start another Pi process from the current Pi session. Do not change routes on resume.

At `surveying`, inspect the repository with read-only tools and commit the validated profile through `commit-profile`. Do not ask the operator for facts that the repository proves.

At `awaiting-commandments`, read [the COMMANDMENTS interview](../references/commandments-interview.md). Run `present-commandments` once and show its observed facts before its single question round. Show every recommended default. Do not select one for the operator.

Submit only the operator's complete response to `stage-commandments`. Missing or partial answers stay unresolved. Do not infer values or ask a second round.

Show the exact staged candidate bytes and SHA-256 digest. Accept only one decision for that display:

1. Ratify the exact digest with the intended marker.
2. Amend named entries in the original response.
3. Defer.

Record amend and defer with `record-commandments-decision`. Keep the state at `awaiting-commandments`. For an amendment, submit the complete amended response after the operator updates the original answer set.

Run `ratify-commandments` only after the operator explicitly approves the displayed digest. Then run `validate-commandments`. Stop when the manifest reports `commandments-ratified`.

## Noninteractive shell resume

At `awaiting-commandments`, write no answers. Run `present-commandments`, print the candidate input path `.pi/jig/commandments/answers.input.json`, and stop. Tell the operator to fill that file from the one question round and rerun `jig init`. If the file exists on the next shell run, pass its exact bytes to `stage-commandments`.

If a staged candidate exists, print its exact path and digest. Ask the operator to write one decision to `.pi/jig/commandments/decision.input.json` and rerun `jig init`. The decision must name `ratify`, `amend`, or `defer`. A ratify decision must contain the exact digest and intended marker. On the next shell run, pass that explicit decision to the matching controller command.

Never claim `commandments-ratified` before the controller commits the transition. Never claim isolated resources after an inherited session performs semantic work.

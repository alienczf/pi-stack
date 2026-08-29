# Target repository COMMANDMENTS interview

Use this interview only at `awaiting-commandments`. Every real `jig init` campaign needs a complete target-operator response and explicit ratification. Preserve an existing root `COMMANDMENTS.md` and let the controller validate whether it can be adopted.

## Present one round

Run `present-commandments` first. Show `observedFacts` separately from `questions`. Show every `recommendedDefault`. A default is a recommendation, not an answer.

Ask the target operator to answer every key in one response. Each answer uses one of these shapes:

```json
{"selection":"default"}
```

```json
{"selection":"custom","value":"an explicit value"}
```

Use the custom shape with the object or list requested by the question. Do not add `value` to a default selection. Do not select a default for the operator. Preserve `freeTextAmendments` as exact operator text.

The one round covers the required init outcome, forbidden outcomes, protected user path, proof policy, compatibility, autonomy, tradeoff order, authority and exceptions, amendment ownership, and the intended ratification marker.

## Keep incomplete answers unresolved

If any answer is missing or malformed, report the controller error and keep `awaiting-commandments`. Do not infer an answer. Do not ask a second round. Ask the operator to amend the original response.

The durable response path is `.pi/jig/commandments/answers.input.json`. Pass its exact bytes to the `stage-commandments` operation emitted by `start`. In an interactive Pi session, the operator may provide the same complete JSON response directly for that operation.

## Stage and display exact bytes

The controller expands a recommended default only when the response selects `default`. It stages the prospective root file and returns its path and SHA-256 digest.

Show the complete candidate bytes, the exact digest, and the intended marker. Offer these decisions:

1. Ratify that exact digest.
2. Amend named entries in the original response.
3. Defer.

Record amend or defer through the emitted `record-commandments-decision` operation. Neither decision publishes `COMMANDMENTS.md` or advances state. After an amend decision, pass one complete amended response through the emitted follow-up operation. Do not restart the interview.

## Ratify exact bytes

Pass both the displayed digest and the operator-approved marker to the emitted `ratify-commandments` operation. Only that controller operation may publish root `COMMANDMENTS.md`. The root bytes must equal the staged candidate bytes.

Run `validate-commandments` after ratification. It checks the root hash, owner, version, timestamp, transition receipt, and manifest. A changed root hash fails closed. Later proposals under `.pi/jig/commandments/proposals/` never change the ratified file.

## Resume on the owning route

Keep the manifest's `resourceIsolation` value for every controller call. Never relabel shell work as inherited work or inherited work as shell work. Use the recovery command in [the public-route matrix](public-routes.json) after a mismatch.

A running Pi agent calls the installed controller directly. It never starts `pi -p` from Bash.

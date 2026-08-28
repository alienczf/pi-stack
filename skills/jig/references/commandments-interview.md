# Repository COMMANDMENTS interview

Ask this interview only when `.pi/jig/manifest.json` is at `awaiting-commandments`. Reuse the committed repository profile for observed facts.

## Present one round

Run `present-commandments` first. Show the `observedFacts` separately from the `questions`. Each question contains a `recommendedDefault`. A default is a recommendation, not an answer.

Ask the operator to answer every key in one response. Each answer has one of these shapes:

```json
{"selection":"default"}
```

```json
{"selection":"custom","value":"an explicit value"}
```

Use the second shape with the object or list requested by the question. Do not add `value` to a default selection. Do not select a default for the operator. Preserve `freeTextAmendments` exactly as explicit operator text.

The one round covers the required init outcome, forbidden outcomes, protected user path, proof policy, compatibility, autonomy, tradeoff order, authority and exceptions, amendment ownership, and the intended ratification marker.

## Keep unresolved answers visible

If any answer is missing or malformed, report the controller error and keep the state at `awaiting-commandments`. Do not infer an answer. Do not ask a second round. Ask the operator to amend the original response.

## Stage exact bytes

Pass the complete response as strict JSON to `stage-commandments`. The controller expands a recommended default only when the response explicitly selects `default`. It writes the prospective final bytes outside the repository root file and returns the SHA-256 digest.

Show the complete candidate and its digest once. Offer three decisions:

1. Ratify that exact digest with the intended operator marker.
2. Amend named entries in the original response.
3. Defer.

Record amend or defer with `record-commandments-decision`. Neither decision publishes `COMMANDMENTS.md` or advances state. After an amend decision, submit a complete amended response. Do not start another interview.

## Ratify exact bytes

Pass both the displayed digest and the operator marker to `ratify-commandments`. Only this deterministic command may publish root `COMMANDMENTS.md`. The root bytes must equal the staged candidate bytes.

After ratification, `validate-commandments` checks the root hash, owner, version, timestamp, transition receipt, and manifest. A changed root hash fails closed. Propose later amendments with `propose-commandments-amendment`; proposals never change the ratified hash or version.

## Resume honestly

Use the `resourceIsolation` value already recorded in the manifest for every controller call. Never relabel `isolated-shell` as `inherited-session`, or the reverse.

In a current Pi session, call the controller directly. Do not start `pi -p` from Bash.

A noninteractive shell run must stop at `awaiting-commandments`. It prints the response file path and tells the operator to rerun `jig init`. The next shell run uses the same route and consumes only operator-written response or decision files. It never invents answers.

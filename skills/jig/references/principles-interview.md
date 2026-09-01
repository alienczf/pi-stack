# Repository Principles interview

Use this interview only at `awaiting-principles`. Every campaign needs one complete target-operator response and explicit ratification.

## Ask only for repository judgment

Run `present-principles` first. Show its cited repository facts separately from its questions. Ask for:

- Protected user paths, visible results, and repository-local thresholds.
- Repository-specific forbidden outcomes.
- Compatibility breaks this repository accepts or rejects.
- Local product priorities when valid goals conflict.
- The owner of exceptions and amendments.

Do not ask the operator to restate pstack verification, autonomy, delegation, worktree, refactoring, or error-handling rules. Do not turn controller safety properties into repository Principles.

The complete answer uses this shape:

```json
{
  "schemaVersion": 2,
  "protectedUserPaths": [
    {
      "name": "primary user path",
      "action": "the action a user takes",
      "visibleResult": "the result the user observes",
      "thresholds": "repository-specific measurable limits"
    }
  ],
  "forbiddenOutcomes": ["a repository-specific forbidden outcome"],
  "compatibilityPolicy": "the repository's compatibility policy",
  "priorityTradeoffs": ["first local priority", "second local priority"],
  "authority": {
    "owner": "the human owner",
    "exceptions": ["an explicit exception or 'No standing exceptions.'"],
    "amendmentPolicy": "how the owner approves later changes",
    "ratificationMarker": "the exact approval marker"
  },
  "freeTextAmendments": ""
}
```

Write the durable response to `.pi/jig/principles/answers.input.json` when the operator does not provide it inline. Missing or malformed answers keep the campaign at `awaiting-principles`.

## Stage and ratify exact bytes

`stage-principles` creates a prospective skill at `.pi/jig/principles/candidate.md`. Show every byte, its digest, and the marker. Record amend or defer through `record-principles-decision`. Amend removes only the staging files and preserves the decision receipt.

`ratify-principles` publishes the candidate to `.cursor/skills/principle-repository/SKILL.md`. The published file is the single human-owned policy source. Do not copy its body into `AGENTS.md`, `.pi/skills`, or another Jig file.

If the canonical path already contains a valid `principle-repository` skill, use `stage-principles --adopt-existing`. The operator still approves its exact digest. Never replace an existing skill silently.

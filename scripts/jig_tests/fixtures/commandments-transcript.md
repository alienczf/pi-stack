# COMMANDMENTS transcript fixture

This fixture records the deterministic interaction shape. `test_transcript_fixture_names_exact_candidate_digest_and_ratification` replaces the candidate and digest placeholders with bytes produced from the checked-in answer fixture before comparison.

## Observed facts

- Product type: test repository.
- Repository revision: fixture HEAD.
- Profile evidence: `README.md:1`.

## One question round

The controller presented all eight answer keys in one round. Each key showed a recommended default. The operator selected the default for eight keys and supplied a custom authority answer. The operator supplied `Keep the public command stable.` as a free-text amendment.

## Explicit response

The response is `scripts/jig_tests/fixtures/commandments-answers.json`. No answer came from an unselected default.

## Exact candidate

Candidate path: `.pi/jig/commandments/candidates/{{CANDIDATE_SHA256}}.md`

Candidate SHA-256: {{CANDIDATE_SHA256}}

```markdown
{{CANDIDATE_BYTES}}
```

## Explicit ratification

Decision: ratify.

Digest: {{CANDIDATE_SHA256}}

Operator marker: `I ratify these exact repository COMMANDMENTS.`

The successful flow publishes identical bytes to root `COMMANDMENTS.md` and reaches `commandments-ratified`.

---
name: architect
description: Sketch types, signatures, and module boundaries with one model before implementation. Use for /architect, design requests, or changes that need a new code shape.
disable-model-invocation: true
---

# Architect

Use one model to sketch, then implement. Work parent-inline by default. Do not launch competing runners or delegate the choice to a judge.

Track these steps in `TODO.md`:

1. Ground the problem.
2. Sketch the design.
3. Let the parent pick if needed.
4. Implement and verify.
5. Revisit the sketch if evidence contradicts it.

## Ground the problem

Trace the affected callers, data, ownership, and constraints in the existing code. Identify the behavior that must stay unchanged. Skip this step only for greenfield work with no surrounding system.

## Sketch the design

Write the caller's usage first. Derive the types, signatures, module boundaries, and ownership from that usage. Use pseudocode or `not implemented` bodies where logic would obscure the shape.

Start with one sketch. If a concrete uncertainty remains, explore another sketch sequentially or parent-inline with the same model. There is no candidate quota or required second design.

Check the sketch for information leakage, shallow wrappers, order-dependent APIs, and unnecessary shared state. Prefer the smallest interface that hides the required complexity.

## Let the parent pick if needed

Proceed with the sketch when it satisfies the constraints. If alternatives remain, the parent compares their evidence and picks one. Do not add a judge or cross-judging phase.

Pause for human sign-off only when explicitly requested or when authorization or a genuine product decision is missing. A requested checkpoint shows the sketch before implementation.

## Implement and verify

Fill in the chosen sketch. Run checks against the requested behavior. Report deviations and the evidence that required them.

Same-model parallel work is allowed for disjoint implementation workstreams. Give each writer separate ownership. Follow the Pi adapter's model policy.

## Revisit the sketch

If repeated workarounds contradict the ownership or types, trace the new evidence and replace the wrong sketch. Return to a single-model sketch, not a competition.

## Output

For a small change, keep the usage, types, and signatures in one sketch. For a larger change, include a module map. Record the constraints, chosen design, unresolved questions, and verification plan. Explain rejected alternatives only when you actually explored them.

---
name: principle-exhaust-the-design-space
description: Explore concrete alternatives when a novel interaction or architectural choice has unresolved tradeoffs. Sequential or parent-inline sketches are sufficient.
disable-model-invocation: true
---

# Exhaust the Design Space

Start with the simplest sketch that meets the constraints. Explore another concrete alternative only when it can resolve a named uncertainty. Compare the evidence before implementing.

Sequential or parent-inline sketches with one model are sufficient. There is no prototype quota, mandatory second design, or cross-model fanout. The parent can pick among alternatives without a judge.

Use this principle for novel interactions or architectural choices with unresolved tradeoffs. Skip extra sketches when an established pattern or the constraints already determine the shape.

Same-model parallel work is allowed for disjoint workstreams. Parallelism is not a requirement for design exploration.

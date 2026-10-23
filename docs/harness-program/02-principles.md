# 02 — Guiding principles: layer affinity

Source: ZF's program brief (`00-brief-verbatim.md`), 2026-10-23. ZF compares this to cache affinity in software optimisation. Agent behaviour should be shaped as close to the work as possible.

## The layers, strongest to softest

Agent behaviour is shaped by these layers, in this order of strength:

1. **The codebase and context itself.** This covers repo shape, file layout, names, types, the docs that sit next to the code, and what the agent actually reads. It's the strongest layer because the agent can't avoid it.
2. **CI and deterministic encoded checks.** These are tests, linters, schema checks and pre-commit hooks. They fail loudly and identically for every agent.
3. **Harness behaviour.** These are coded hooks in pi / pi-streams that fire deterministically, such as the tick, compaction triggers, delivery and rotation. The agent doesn't have to remember them.
4. **Always-on rules.** These are AGENTS.md and system-prompt rules that are loaded every time but are only text. The agent can still misread or outweigh them.
5. **Skills.** These are opt-in, and the agent has the prerogative to load them or not. They're the softest enforcement.

## Rules for every fix and design

- **Place it at the right layer.** Every proposed fix and design, especially the existing ones, must be examined for the layer it sits at, and whether that layer is right. Use the relevant skills (`/why`, `/interrogate`, `/architect`) to examine it, not assertion. A behaviour that matters every time doesn't belong in a skill. A behaviour that a test can check doesn't belong in a rule.
- **Push down when you can.** Prefer the strongest layer that can actually carry the behaviour. Leaning on the repo itself (layer 1) is entirely acceptable.
- **Generic fix for recurring failures.** When the same layer-1/2 failure recurs across repos, the generic fix is a layer 3-5 mechanism that deterministically *produces* the layer-1/2 changes as part of the workflow cycle. Don't hand-patch each repo forever, and don't leave a soft rule that hopes the agent remembers.
- **Impose and measure, don't defend.** Prefer imposing a specific behaviour in the harness, such as the 252k compaction boundary, then measuring how it performs in the wild. Don't fall back defensively to checking with the user.
- **Generic about environments, opinionated about shape.** pi-stack makes no assumptions about the environments it's deployed into, and its baseline applies to any user, not one workspace. It is strongly opinionated about repo shape, and about the harness and workflow it owns.
- **Defer to the user only on the task.** Questions specific to the incoming request go to the user. The solution space and the maintenance space are pi-stack's own call, so don't ask the user there.
- **Not frameworky.** Mechanisms must generalise across workflows. A framework that fits one workflow and must be configured per workflow is a smell. Prefer a few small deterministic mechanisms over a general engine.
- **No default budgets (D1).** Token, CPU, RAM and disk guards are opt-in at most. They're context bloat by default.

## How to state layer placement in an artifact

For each mechanism, write `LAYER n` and one sentence on why the layer is right, plus why a stronger layer can't carry it. For example: "LAYER 3: the tick fires on every request boundary, and a rule (4) would rely on the coordinator noticing its own context size, which the corpus shows it doesn't."

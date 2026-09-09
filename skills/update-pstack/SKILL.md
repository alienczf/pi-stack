---
name: update-pstack
description: Review and fast-forward the independent pstack checkout without changing pi-stack. Use only for explicit /skill:update-pstack or /update-pstack after pstack upstream changes.
disable-model-invocation: true
---

# Update pstack

Keep pi-stack on its current Git revision. Pstack must remain a separate Git checkout.

1. Run `update-pstack status`. Save the JSON plan, including `piStack.revision`, `piStack.statusSummary`, and both pstack revisions.
2. If status refuses tracked or staged pi-stack changes, local pstack content, a detached, local-ahead, divergent, shared, partially materialized, or incomplete upstream checkout, stop. Do not repair history inside this procedure.
3. Review every entry in `changedPaths`. Use `pstack.gitRoot`, the two pstack revisions, and `pstack.repositoryPath` to inspect the exact diff.
4. Check the changed pstack skills against `install.sh`, `overlay/AGENTS.md`, and `overlay/APPEND_SYSTEM.md`. Confirm that installed skill names still exist, referenced files resolve, and every required Cursor action has a Pi mapping.
5. Stop before apply if the upstream change breaks the adapter. Report the incompatible paths and the separate pi-stack change they require. Do not edit pi-stack during this procedure.
6. Run the following command only after the review passes:

```bash
update-pstack apply \
	--expected-pi-stack <piStack.revision> \
	--expected-current <pstack.currentRevision> \
	--expected-upstream <pstack.upstreamRevision>
```

Use full revisions from the same plan. Never substitute a branch, a tag, or an abbreviated revision.

7. From `piStack.root`, run `bash scripts/check-update-pstack.sh`, `bash scripts/check-overlay.sh`, and `bash scripts/check-conform-skills.sh`.
8. Read pi-stack `HEAD` and its tracked or staged status again. Both must equal the saved plan.
9. Report the old and new pstack versions and revisions. State the unchanged pi-stack revision.

After an interrupted install, rerun the same apply command. It accepts pstack at either reviewed endpoint and reruns `install.sh` without fetching a later upstream revision.

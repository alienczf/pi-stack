# Complete the first improvement step

Use this playbook only after target COMMANDMENTS are ratified and target runtime verification is current. The controller fixes the step ID at `0001`.

## Select at most one candidate

1. Run `begin-step-selection --resource-isolation <route>`.
2. Read the current profile, target COMMANDMENTS, runtime receipt, feature map, and repository evidence.
3. Build one `selection` object that lists every considered candidate. Record each eligibility result, rejection reason, ranking fact, and either no selected ID or one eligible selected ID.
4. Pass the object only through `commit-step-selection` on standard input.

A candidate is ineligible when it conflicts with a hard commandment, needs an unanswered target choice, lacks reproducible evidence, can change its own constraints, exceeds the allowed blast radius, lacks rollback, or needs recurring Jig behavior.

If no candidate is eligible, run `finalize-no-candidate`. Run `start`, report the controller's `no-eligible-candidate` result, and stop.

## Fix the selected contract before edits

For one selected candidate, build the `proposal` object from the committed selection and ratified target policy. It names the response layer, expected gain, evidence, blast radius, uncertainty, canonical Poteto playbook, baseline, required proof, rollback, and eval decision.

Program-level behavioral evaluation is not available in this release. Reject a candidate that requires it. Do not substitute a proxy behavioral test.

Pass the proposal only through `commit-step-proposal` on standard input. Run `prepare-step-worktree`. The controller runs and pins the baseline before it creates the isolated worktree.

## Run work in the controller-owned worktree

Create a unique worker ID. Pass that ID and the bounded allowed paths through `activate-step-worker` on standard input. Read the returned `workerHandoff` from `start`.

Use the `subagent` tool to start one fresh worker with `cwd` set to the exact returned worktree. Tell the worker to read the proposal and its named canonical Poteto playbook. The worker may change only `allowedPaths`, must run the proposal's local checks, and must commit its output on the controller-owned branch. It must not write `.pi`, `.git`, `COMMANDMENTS.md`, active proof definitions, or verdicts.

Never use Bash to start `pi -p`. Never edit the candidate on the target repository's main worktree. Never merge the candidate branch.

If the worker fails before a valid output commit, record the exact failure through `record-failure --state step-running`. Then run `prepare-step-result` and `complete-step-result` to let the controller derive `reverted`.

## Pin and prove the output

After the worker commits, run these controller operations in order:

1. `record-step-output` pins the output revision and candidate diff.
2. `verify-step-output` runs the baseline and every proposal proof against the pinned output.
3. If the proposal requires independent review, use a different `subagent` session in the same worktree. The reviewer reads the pinned diff and proof receipts. Pass its bounded verdict only through `commit-step-verdict` on standard input. The worker cannot review its own work.
4. `prepare-step-result` derives the staged result from pinned evidence.
5. `complete-step-result` validates the result and commits the terminal transition.
6. `start` returns the controller-derived terminal result.

A failed proof or failed independent verdict yields `reverted`. Passing required proof and a passing required independent verdict yields `kept`. The main worktree stays unchanged in both cases. Report the selected branch and worktree from `result.json` for the operator. Do not merge.

## Stop

`initialized` is terminal. Report only `kept`, `reverted`, or `no-eligible-candidate`. Do not propose another candidate, a recurring run, deployment, or automatic merge.

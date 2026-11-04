# Native healing overlay

This overlay targets `@jmfederico/pi-web@1.202607.3` and its bundled pi-coding-agent, pi-ai, and pi-agent-core peers at `0.82.1`. It does not target the separate global coding agent.

`pi-web/manifest.json` contains exact package versions, package-manifest hashes, and source preimage/postimage hashes. `extensions/` contains guarded adapters for pi-subagents 0.58.0, pi-web-access 0.26.0, pi-prompt-template-model 0.12.2, pi-cursor-sdk 0.1.5, and pi-jupyter 0.1.0. The manifests contain source changes only. No installed packages, credentials, or session data enter Git.

## Ownership contracts

Native AgentSession owns transient inference retries. Watched sessions reuse pi-ai's classifier after Codex usage exclusions, retain the configured retry count, and use fixed abortable 5000 ms delays. Provider, model, thinking, admission generation, queued input, and unresolved effects are checked before inference. Entry-bound receipts retain raw errors and distinguish pending, resolved, terminal, cancelled, and uncertain attempts. Cold readers cannot recreate a lost attempt. Settled receipts follow exact same-root recovery lineage, so a fork does not rediscover a parent's explained transient errors. Unwatched retry settings are unchanged.

The engine owns durable nonusage recovery under the ratified standing charter. Content-policy refusal is an exception. Its lastgood, original source and exact refusal hashes remain, and ordinary recovery inference, compaction and RESUME stay blocked. The inherited prefix, auto-loaded AGENTS and tools are not proven clean. New and persisted restricted operations refuse effects. A separate `clean-policy-analysis-v1` operation permits one metadata-only inference through an owned private native factory. It creates a fresh session and cwd, an explicit empty resource loader and an enforced empty tool allowlist. The SDK's built-in system prompt and original provider, model and thinking remain. No prefix, assignment, STATE, AGENTS, handover, audit hash or source link enters its model input. Source bytes and audit hashes remain outside that context. The private session cannot reopen through the ordinary native factory. A durable rejected, blocked, superseded or uncertain analysis cannot authorize another attempt under a different ID. An analyzed receipt is not a fork, compaction, RESUME, task recovery or North Star acceptance. The original task stays parked and its rejected-goal fingerprint remains unchanged. Lane metadata binds the native session, stream root, role, and exact assignment. Historical lanes can recover without pre-input enrollment. Their registry role and original input supply continuation evidence. Failure parking must still own the unchanged receiving generation. A newer stop, newer input, or unknown parking ownership cannot be treated as failure-owned. An engine-policy operation has no invented notice ID, verifier receipt, or exceptional instructions. Runtime recovery has only the engine-owned protocol. It has no human-notice endpoint or verifier dependency.

An explicit `pi-streams resume <stream> --all-parked` grant can replace old local drive-off intent and bind the current disabled failure generation. It never enables a failed original. Racing stops, newer accepted input and unresolved effects refuse admission. Drive becomes on-confirmed only after the verified successor is released. Ordinary ticks do not infer this operator grant.

Recovery reuses the existing good-prefix fork journal, registry compare-and-set, held-fork maintenance, completed RESUME proof, retained original evidence, and singular retirement. A worker retains its bounded assignment. Checkpoint-free rotation retains last-good and handover evidence and freezes the source model and thinking settings instead of adopting project defaults. Cold lifecycle checks use the latest owned release and require its hold and completed RESUME proof. Unknown input, callbacks, effects, generations, or original maintenance ownership refuse effects. Usage reconciliation and native recovery both retain unclassified shell submissions until job ownership is proven. Their bounded shell scan distinguishes quoted or escaped literals, foreground redirections, and background operators. Unquoted background jobs, submission commands, opaque shell evaluation, unsupported syntax, unmatched calls, and nonterminal structured jobs remain fenced. Successful foreground completion is not proof that an arbitrary script is read-only. Historical engine heuristics are recomputed only from the exact retained native branch and failure evidence. Missing or changed evidence cannot clear them.

The extension loader binds declarations to the actual loaded extension and source hash. Live active or unknown owners block replacement. Safe-to-drop owners provide an awaited cancellation receipt and a fresh ownership snapshot inside native exclusion. Loaded idle extensions and completed historical subagent messages do not alone block recovery. The adapters inspect real state, including batched subagent notifications, result delivery, schedules, pending web work, prompt loops/restoration, Cursor runs, and notebook preview work.

Maintenance compaction measures the actual rebuilt message context and requires fewer than 150000 estimated tokens before RESUME. It uses local retention settings, not a global settings mutation. Context above the target becomes a native summary with its raw history retained. An oversized extension summary falls back to native provider summarization. An oversized provider summary fails without a successful completion claim. Both pi-ai copies at the package root and under pi-coding-agent are version/hash guarded. Watched manual summarization retries use the same fixed 5000 ms delay.

Completed compaction accepts only validated transparent failure-checkpoint and watcher metadata behind its physical leaf. Newer receiving input, stop, or a nontransparent changed checkpoint supersedes empty completed ownership. This releases obsolete maintenance ownership, not stopped admission. Failed, uncertain, sending, and otherwise unresolved maintenance stays fenced.

`pi-streams/engine/relay.py` is an authenticated adapter boundary. Its caller supplies a transport authenticator and a trusted principal mapping. Body-supplied principal labels are not authentication. Verified scoped Grok Bot relays can record ZF's dated rules or exact words without human retyping. The repository does not supply or claim a live production Grok Bot transport. Relay provenance is separate from native recovery ownership. `pi-streams state ruling --relay-source FILE` records exact dated source words without duplicate human typing. It retains raw JSON and its hash under owned history and explicitly does not claim transport authentication. `migrate --plan --relay-source FILE --mapping MAP` binds the same source bytes into the exact migration hash. Explicit maps can select a non-first-line legacy authority. A bare legacy affirmative needs dated standing-grant provenance. An unratified `no` is never elevated, and mapped North Star and Charter bytes are unchanged.

Blocked-goal suppression uses distinct prompt outcomes rather than lifetime send counts. Transcript and delivery receipts share one prompt identity. A completed assistant report of permitted progress or an applied receipt with artifact evidence resets the repetition window. This is repetition control, not independent proof that the product goal is complete. Legacy ambiguous counters remain retained as audit evidence and do not enforce permanent suppression.

## Delivery behavior

The installer applies the overlay to existing and newly installed package paths. It checks every selected package before the first patch write. It does not upgrade an incompatible existing package or restart a running daemon. Unsupported versions, changed bytes, escaping symlinks, and unowned mixed trees refuse application.

Each package uses `.pi-stack-overlay.pending` during application. An interrupted operation can reconcile only the same manifest and known preimage/postimage bytes. A fully patched tree is a no-op. Complete known adopted overlay trees are accepted upgrade inputs. The manifest lists their exact per-file hashes. Unowned mixtures of pristine, older, and new source bytes still refuse. Unexpected bytes remain an error, not permission to replace another patch.

`PI_STACK_NATIVE_ROOT` and `PI_STACK_NATIVE_EXTENSIONS_ROOT` select explicit disposable package roots for verification. `PI_STACK_SKIP_PACKAGES=1` skips native mutation unless an explicit native root is supplied. `PI_STACK_SKIP_NATIVE_OVERLAY=1` explicitly skips this delivery and prints that native healing was not installed. The legacy fake-package installer checks use that skip when no native fixture is supplied.

Production installation and daemon restart require separate operator authorization. Patching files does not prove that an already running daemon loaded them.

## Isolated verification

Prepare a fresh fixture under this worktree. Supply the pinned read-only native package and extension npm directory. The helper copies static package material, excludes credentials and JSONL data, applies all guarded overlays, and never starts a daemon.

```sh
python3 scripts/prepare-native-fixture.py /path/to/pi-web /path/to/agent/npm/node_modules "$PWD/.harness-heal/native-check"
```

Run the actual changed native modules and the full Python suite with isolated HOME, XDG, and TMPDIR paths. Set `PI_STACK_NATIVE_TEST_ROOT` to the prepared `native` directory. Without that explicit fixture the Python native-module wrappers report skips.

```sh
PI_STACK_NATIVE_TEST_ROOT="$PWD/.harness-heal/native-check/native" python3 -m unittest discover -s pi-streams/tests
```

For installer integration, pass that fixture to the existing sandbox check. Its package and service commands are controlled fixtures.

```sh
PI_STACK_NATIVE_ROOT="$PWD/.harness-heal/native-check/native" PI_STACK_NATIVE_EXTENSIONS_ROOT="$PWD/.harness-heal/native-check/extensions" bash scripts/check-overlay.sh
```

The Node scenarios use actual AgentSession persistence, native controllers, extension factories, compaction, and completed RESUME evidence with controlled provider responses and time. Context-reduction assertions sum native token estimates over the rebuilt message list. These are not billed provider token counts. Python CLI/HTTP fixtures separately verify engine orchestration and crash/reply-loss invariants. Neither layer proves installed production behavior, real credentials, or a historical penv-1 diagnosis. The authorized incident references remain unidentified.

# B over Prime intake probe

This throwaway supervisor client tests a limited claim. A cooperating client can commit a typed source-message row before dispatch and retain a provider preflight refusal. It cannot enforce Prime's all-client ingress or commit atomically with native admission.

## Data contract

`Intake` contains the durable session selector, source namespace, caller-owned source message id, lane, and verbatim text. SQLite keys rows by session, source namespace, and source message id. It stores the body hash, dispatch disposition, and native reply. These ids are not Prime message-entry ids.

The journal commits `dispatch_uncertain` before sending. A duplicate source key with the same text and lane returns its stored disposition without another send. Changed text or lane is an identity conflict. A lost reply remains uncertain even after reopening the journal. There is no automatic resend. A native successful reply means admitted, not semantically completed. The probe deliberately does not write a last-good marker.

The shim has no attachment, task closure, native deduplication, complete crash-recovery, tool fencing, child adoption, or always-on service contract. The native event buffer is diagnostic and volatile. Event gaps require reconciliation, not assumed success. This is not the proposed production implementation of B.

## Offline verification

Run from the spike worktree.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s spikes/b-over-prime -p 'test_*.py'
```

Nine tests check commit-before-send through a separate SQLite connection, duplicate suppression, uncertain retry after reopening, identity conflicts, retained refusal, malformed response handling, storage-error refusal, source namespaces, correlated socket replies with interleaved events, and fixture cleanup before disconnect after an assertion failure. Some tests cover more than one case. Before `probe.py` existed, this command failed on its missing import. This is a new-feature red test, not evidence of a reproduced upstream bug.

## Isolated real control check

The binary is stable v0.10.1 at source revision `8aac8692456c00c01d4e53e60e6d3347a3506559`. The executable SHA-256 is `1fbb506f54a8e9af1f0d123e521d13a765bce34883707c69656f06d5951b314c`.

Create a fresh root. Never reuse another track's runtime roots or sockets. The only track-2 access below executes its already-verified binary. Every runtime path is track 4's own.

```sh
ROOT=$(mktemp -d /tmp/prime-t4.XXXXXXXX)
export ROOT
python3 - <<'PY'
import json, os
from pathlib import Path
root = Path(os.environ['ROOT'])
for name in ('home', 'agent', 'sessions', 'work'):
    (root / name).mkdir(mode=0o700)
(root / 'track4-owned').write_text('01a166e0-220d-7dbc-8b1c-719e872dad2d\n')
(root / 'agent/settings.json').write_text(json.dumps({
    'allowedModels': ['openai-codex/gpt-6.1-sol'],
    'retry': {'enabled': False, 'failover': {'enabled': False},
              'provider': {'waitForUsage': {'enabled': False, 'pauseUntilReset': False}}}
}) + '\n')
PY
tmux new-session -d -s prime-t4-01a166e0 -c "$ROOT/work" \
  "exec env -i HOME=$ROOT/home PATH=/usr/bin:/bin LANG=C.UTF-8 DO_NOT_TRACK=1 PRIME_AGENT_CODING_AGENT_DIR=$ROOT/agent PRIME_AGENT_SESSION_DIR=$ROOT/sessions PRIME_AGENT_DAEMON_SOCKET=$ROOT/daemon.sock /tmp/prime-t2.3qhjos6h/prime-agent --offline --mode daemon --daemon-socket $ROOT/daemon.sock > $ROOT/daemon.log 2>&1"
```

Once the owned socket exists, run the check. The timeout is an explicit socket-read timeout, not a shipped default resource cap.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 spikes/b-over-prime/live_check.py --root "$ROOT" --timeout 30
```

The check validates protocol 7 and schema 30, creates one session with the exact requested provider/model, attaches, pauses input delivery, dispatches one source-keyed follow-up, suppresses its duplicate, and confirms one native queued item. It clears the fixture before releasing the pause. It then uses `prompt_and_wait` for a missing-credential preflight. It asserts the retained refusal, a user row without an assistant row, a live `turn_end.error`, and explicit `event_replay_not_available` from offset zero. It archives only its own created session and shuts down through its own socket. It writes `live-check.json` under the temporary root. It never logs in or imports credentials.

Restart using the same tmux launch command and root, then run the readback.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 spikes/b-over-prime/live_check.py --root "$ROOT" --timeout 30 --restart-only
```

This confirms that the archived native session, its one user message, and the shim's rejected disposition survive a supervisor restart. It shuts the owned supervisor down again and writes `restart-check.json`. It does not prove crash recovery of an in-flight worker or pending attachments.

Final-code runtime evidence is in `/tmp/prime-t4.F0zJfHkm/`. The investigation reports and red/green test logs are in `/tmp/prime-t4.RuU8iRKk/`. An intermediate repeat is in `/tmp/prime-t4.j6emV0Hf/`. All owned supervisors, sockets, and the `prime-t4-01a166e0` tmux session were absent after cleanup. The unchanged stream suite also passed all 105 tests.

A failure-path test first exposed that the initial live checker could close its connection before clearing a paused fixture. The checker now clears that fixture in an inner finally while the owning connection still holds the pause. The regression passed, and the final code was rerun against a fresh daemon. This is a spike-checker fix, not a claim that native delivery is crash-safe. A transport loss still requires reconciliation; the isolated empty credential environment prevents model inference in these checks.

## Limits

There was no model inference, successful turn, active steering, real compaction, successful last-good checkpoint, exact-entry fork experiment, child transfer, disk-failure injection into Prime, or arbitrary-writer quiescence proof. The stock stable catalog kept `openai-codex/gpt-6.1-sol` but clamped thinking to `off`. No substitute model was selected. Native failure persistence and replay gaps are observed; strict admission durability is source-derived and still needs an upstream fault-injection test.

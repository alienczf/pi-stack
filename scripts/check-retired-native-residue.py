#!/usr/bin/env python3
"""Verify archive/adopt reconciliation with an isolated real native service."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('residue_chaos', ROOT / 'scripts/check-streams-chaos.py')
chaos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chaos)


def verify(sandbox):
    name, stream, old = sandbox.new()
    before = sandbox.control('snapshot')
    source = next(item for item in before['evidence'] if item['session'] == old)
    retained = Path(source['file']).read_bytes()
    table = stream / 'threads.tsv'
    rows = list(csv.DictReader(table.read_text().splitlines(), delimiter='\t'))
    rows[0]['status'] = 'archived'
    with table.open('w') as handle:
        writer = csv.DictWriter(handle, rows[0].keys(), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    target = sandbox.web('spawn', str(stream))['session']['id']
    sandbox.web('model', target, chaos.MODEL)
    sandbox.web('thinking-level', target, 'xhigh')
    sandbox.web('automatic-admission', target, 'on', '--initialize-if-absent')
    sandbox.prompt(target, 'Prepare this owned fixture conversation without tools or external effects.')
    prior_calls = len(sandbox.control('snapshot')['calls'])
    adopted = sandbox.cli('new', name, '--coordinator-session', target)
    chaos.check(adopted.stdout.strip().splitlines()[-1] == target, 'adoption changed the selected identity')
    sandbox.tick()
    sandbox.wait_idle(target)
    after = sandbox.snapshot()
    calls = [call for call in after['calls'][prior_calls:] if not call['title'] and not call['summary']]
    chaos.check([call['session'] for call in calls] == [target], 'the tick did not dispatch exactly once to the successor')
    archive, = [item for item in after['archives'] if item['sessionId'] == old]
    archived = Path(archive['archivePath']).read_bytes()
    chaos.check(archived.startswith(retained), 'the archive lost captured source bytes')
    chaos.check(not Path(source['file']).exists(), 'the live source remains after native retirement')
    return {'result': 'PASS', 'source': old, 'target': target, 'targetTaskCalls': 1,
            'sourceBytesRetained': True, 'sourcePrefixSha256': hashlib.sha256(retained).hexdigest(),
            'archiveSha256': hashlib.sha256(archived).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', type=Path, required=True)
    parser.add_argument('--logs', type=Path, required=True)
    args = parser.parse_args()
    native = args.native_root.resolve()
    chaos.check(native.is_relative_to(ROOT / '.harness-heal'), 'use a prepared native fixture under this checkout')
    run = args.logs.resolve() / ('run-' + uuid.uuid4().hex)
    run.mkdir(parents=True)
    sandbox = chaos.Sandbox(run, 'archive-adopt', native, shutil.which('node'))
    result = {'result': 'FAIL'}
    try:
        sandbox.start()
        result = verify(sandbox)
    except Exception as error:
        result['error'] = str(error)
    finally:
        result['cleanup'] = sandbox.cleanup()
        cleanup = result['cleanup']
        if (not cleanup.get('processStopped') or not cleanup.get('pathRemoved') or cleanup.get('error')
                or not all(item['closed'] for item in cleanup['streams'])
                or not all(item['state'] in {'archived', 'already-archived-or-retired'} for item in cleanup['sessions'])):
            result['result'] = 'FAIL'
        chaos.save(run / 'result.json', result)
    print(json.dumps(result, sort_keys=True))
    print(run)
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

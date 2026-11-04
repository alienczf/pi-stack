#!/usr/bin/env python3
"""Run isolated CLI -> registered HTTP routes -> real PiSessionService/AgentSession cases."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOGS = Path('/tmp/pi-stack-spawn-only-ratify-20261103/chaos-lever')
LIVE_NATIVE = Path('/home/alphalab/.local/share/pi-node')
LIVE_EXTENSIONS = Path('/home/alphalab/.pi/agent/npm')
MODEL = 'openai-codex/gpt-6.1-sol'
BASELINE = ('overload', 'terminated', 'usage-reset', 'compaction')
CASES = (*BASELINE, 'login-refresh', 'model-error', 'parked-worker', 'rotation', 'policy-safe-analysis', 'policy-narrowing', 'blocked-loop', 'tick-noise', 'unratified-close', 'small-recovery', 'archived-worker', 'dead-worker')


POLICY_DOC_INPUT_HANDLE = 'bootstrap-facts-v1'
POLICY_DOC_OUTPUT_HANDLE = 'owned-bootstrap-note'
POLICY_DOC_MAX_BYTES = 16384
POLICY_DOC_FACTS = {
    'schema': POLICY_DOC_INPUT_HANDLE,
    'provenance': {'kind': 'owned-benign-test-facts', 'protocol': 'automatic-admission-bootstrap-49'},
    'facts': {
        'createsOnlyAbsentDurableEpoch': True, 'reenablesDisabledEpoch': False,
        'dispatchesInference': False, 'dispatchesQueuedGoals': False,
    },
    'rules': [
        ['Initialization creates a durable epoch only when no durable epoch exists.', 'Retries reuse the receiving epoch so a later stop is not overwritten.'],
        ['Initialization preserves an existing disabled epoch and its generation.', 'The receiving stop remains effective instead of reauthorizing stale automatic work.'],
        ['Initialization dispatches neither inference nor queued goals.', 'Bootstrap retries cannot duplicate work or bypass a later receiving stop.'],
    ],
    'examples': {
        'Absent durable epoch': {
            'before': {'generation': 'unarmed', 'allowed': False, 'durable': False, 'queuedGoal': 'queued', 'inferenceCalls': 0},
            'after': {'generation': 'init-1', 'allowed': True, 'durable': True, 'queuedGoal': 'queued', 'inferenceCalls': 0},
        },
        'Existing receiving stop': {
            'before': {'generation': 'stop-2', 'allowed': False, 'durable': True, 'queuedGoal': 'queued', 'inferenceCalls': 0},
            'after': {'generation': 'stop-2', 'allowed': False, 'durable': True, 'queuedGoal': 'queued', 'inferenceCalls': 0},
        },
    },
}


class CaseNotImplemented(NotImplementedError):
    def __init__(self, message, details):
        super().__init__(message)
        self.details = details


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def selected_cases(value):
    names = list(BASELINE if value == 'baseline' else CASES if value == 'all' else value.split(','))
    if not names or any(name not in CASES for name in names) or len(set(names)) != len(names):
        raise argparse.ArgumentTypeError('choose baseline, all, or unique comma-separated names from ' + ','.join(CASES))
    return names


def copy_native_archive(archive, native):
    with tarfile.open(archive) as source:
        for member in source:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or path.parts[:1] != ('pi-web',):
                raise ValueError('archive contains an escaping or unexpected package path')
            relative = path.relative_to('pi-web')
            if not relative.parts or relative.parts[0] not in {'package.json', 'dist', 'node_modules'}:
                continue
            if any(part in {'auth.json', '.git', '.cache', '.pi'} for part in relative.parts) or relative.suffix == '.jsonl':
                continue
            target = native.joinpath(*relative.parts)
            check(target.resolve().is_relative_to(native.resolve()), 'archive path escapes the owned native fixture')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open('wb') as output:
                    shutil.copyfileobj(incoming, output)
            elif member.issym():
                check((target.parent / member.linkname).resolve().is_relative_to(native.resolve()), 'archive symlink escapes the owned native fixture')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(member.linkname)
            else:
                raise ValueError('archive contains unsupported non-static package material')


class Sandbox:
    def __init__(self, run, case, native, node):
        self.case, self.native, self.node = case, native, node
        self.logs = run / case
        self.logs.mkdir()
        self.scratch = self.logs / 'scratch'
        self.owner = uuid.uuid4().hex
        self.journal_path = self.logs / 'ownership.jsonl'
        self.journal(effect='own-scratch-before-create', path=str(self.scratch))
        self.scratch.mkdir()
        (self.scratch / '.chaos-owner').write_text(self.owner)
        self.project = self.scratch / 'project'
        self.index = self.scratch / 'index'
        self.streams = []
        self.deleted_sessions = set()
        self.proc = None
        self.env = {
            'PATH': '/usr/bin:/bin', 'HOME': str(self.scratch / 'home'),
            'XDG_CONFIG_HOME': str(self.scratch / 'config'), 'XDG_DATA_HOME': str(self.scratch / 'data'),
            'XDG_STATE_HOME': str(self.scratch / 'state'), 'XDG_CACHE_HOME': str(self.scratch / 'cache'),
            'TMPDIR': str(self.scratch / 'tmp'), 'PI_CODING_AGENT_DIR': str(self.scratch / 'agent'),
            'PI_OFFLINE': '1', 'PI_SKIP_VERSION_CHECK': '1', 'PI_TELEMETRY': '0',
            'PYTHONDONTWRITEBYTECODE': '1', 'PI_STACK_NATIVE_TEST_ROOT': str(native),
            'CHAOS_OWNER': self.owner, 'CHAOS_SCRATCH': str(self.scratch),
            'CHAOS_JOURNAL': str(self.journal_path), 'CHAOS_INDEX': str(self.index),
            'PI_STREAMS_BIN': str(ROOT / 'bin/pi-streams'),
            'GIT_AUTHOR_NAME': 'Chaos fixture', 'GIT_AUTHOR_EMAIL': 'chaos@example.invalid',
            'GIT_COMMITTER_NAME': 'Chaos fixture', 'GIT_COMMITTER_EMAIL': 'chaos@example.invalid',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0',
            'http_proxy': 'http://127.0.0.1:9', 'https_proxy': 'http://127.0.0.1:9',
            'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
            'no_proxy': '127.0.0.1,localhost', 'NO_PROXY': '127.0.0.1,localhost',
            'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
        }
        for path in (self.project, Path(self.env['HOME']), Path(self.env['TMPDIR'])):
            path.mkdir()
        (self.scratch / 'poteto-mode.md').write_text('---\nname: poteto-mode\ndescription: Isolated verification\n---\nRetain the exact bounded role and current permitted goal.\n')
        self.url = ''
        self.commands = []

    def journal(self, **value):
        with self.journal_path.open('a') as handle:
            handle.write(json.dumps({'owner': self.owner, 'at': time.time(), **value}) + '\n')
            handle.flush()
            os.fsync(handle.fileno())

    def command(self, binary, *args, stdin=None, required=True, timeout=45):
        command = [str(binary), *map(str, args)]
        self.journal(effect='command-before-run', command=command)
        started = time.monotonic()
        result = subprocess.run(command, cwd=self.project, env=self.env, input=stdin, capture_output=True, text=True, timeout=timeout)
        record = {'command': command, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr, 'elapsedSeconds': time.monotonic() - started}
        self.commands.append(record)
        save(self.logs / 'commands.json', self.commands)
        if required:
            check(result.returncode == 0, f"{command} failed\n{result.stderr}\n{result.stdout}")
        return result

    def cli(self, *args, **kwargs):
        return self.command(ROOT / 'bin/pi-streams', *args, '--home', self.index, **kwargs)

    def web(self, *args, **kwargs):
        result = self.command(ROOT / 'bin/pi-web-cli', *args, **kwargs)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def control(self, path, value=None):
        check(self.url.startswith('http://127.0.0.1:') and self.url.rsplit(':', 1)[1] != '8504', 'unsafe fixture address')
        self.journal(effect='fixture-control-before-call', path=path, value=value)
        request = urllib.request.Request(self.url + '/__chaos/' + path, data=None if value is None else json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=20) as result:
            return json.load(result)

    def start(self):
        log = (self.logs / 'service.log').open('w')
        self.journal(effect='own-process-before-start', script='pi-streams/tests/native/chaos-service.mjs')
        self.proc = subprocess.Popen([str(self.node), str(ROOT / 'pi-streams/tests/native/chaos-service.mjs')], cwd=self.project, env=self.env, stdout=log, stderr=subprocess.STDOUT)
        log.close()
        self.journal(effect='process-started', pid=self.proc.pid)
        ready = self.scratch / 'ready.json'
        end = time.monotonic() + 20
        while not ready.exists():
            check(self.proc.poll() is None, 'native service startup failed; see service.log')
            check(time.monotonic() < end, 'native service readiness timed out')
            time.sleep(.05)
        identity = json.loads(ready.read_text())
        check(identity['owner'] == self.owner and identity['pid'] == self.proc.pid, 'service ownership mismatch')
        self.url = identity['url']
        self.env['PI_WEB_URL'] = self.url
        self.cli('init', self.project, '-y', '--pi-web-url', self.url, '--coordinator-model', MODEL, '--coordinator-thinking', 'xhigh')

    def new(self, name=None, ratified=True):
        name = name or self.case
        self.journal(effect='own-stream-before-new', stream=name, path=str(self.project / 'streams' / name))
        self.streams.append(name)
        result = self.cli('new', name)
        sid = result.stdout.strip().splitlines()[-1]
        stream = self.project / 'streams' / name
        self.wait_idle(sid)
        if ratified:
            path = stream / 'STATE.md'
            path.write_text(path.read_text().replace('ratified: no', 'ratified: 2026-11-03 isolated task grant', 1).replace('<the single human-authorized outcome>', 'Finish all authorized fixture units without external effects.', 1))
            self.objective(name, 'Continue permitted verification. The overall authorized outcome is not complete.')
            self.cli('drive', name, 'on')
        return name, stream, sid

    def worker(self, name):
        repo = self.project / 'repo'
        self.journal(effect='own-worker-repo-before-create', path=str(repo))
        repo.mkdir()
        self.command('git', '-C', repo, 'init')
        (repo / 'README').write_text('Owned fixture repository.\n')
        self.command('git', '-C', repo, 'add', 'README')
        self.command('git', '-C', repo, 'commit', '-m', 'Create isolated fixture')
        self.cli('init', self.project, '-y')
        sid = self.cli('thread', 'spawn', name, '--repo', 'repo', '--role', 'implementation', '--note', 'Verify only the owned fixture unit. Never coordinate.').stdout.strip()
        self.wait_idle(sid)
        return sid

    def objective(self, name, goal):
        self.cli('state', 'objective', name, '--body-file', '-', stdin=goal)

    def status(self, sid):
        return self.web('status', sid)['session']

    def wait_idle(self, sid, timeout=25):
        end = time.monotonic() + timeout
        while True:
            state = self.status(sid)
            if not any(state.get(key) for key in ('isStreaming', 'isCompacting', 'isBashRunning', 'pendingMessageCount')):
                return state
            check(time.monotonic() < end, f'{sid} did not become idle')
            time.sleep(.1)

    def plan(self, sid, *responses, authenticated=None):
        body = {'session': sid, 'responses': list(responses)}
        if authenticated is not None:
            body['authenticated'] = authenticated
        return self.control('plan', body)

    def prompt(self, sid, text):
        self.web('prompt', sid, stdin=text)
        return self.wait_idle(sid)

    def tick(self, required=True):
        result = self.cli('tick', required=required, timeout=60)
        time.sleep(.15)
        return result

    def state(self, stream):
        path = stream / 'log/tick-state.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def drive_on(self, stream):
        drive = self.state(stream)['drive']
        check(drive['enabled'] is True, f'drive disabled: {drive}')
        return drive

    def recover(self, stream, sid, attempts=14):
        for _ in range(attempts):
            self.tick(required=False)
            state = self.state(stream)
            operation = state.get('failure_recoveries', {}).get(sid, {})
            if operation.get('phase') == 'complete':
                self.wait_idle(operation['fork'])
                return operation
        state = self.state(stream)
        operation = state.get('failure_recoveries', {}).get(sid, {})
        dcr = state.get('dcr_operations', {}).get(operation.get('fork'), {})
        raise AssertionError(f"recovery incomplete: phase={operation.get('phase')}, detail={operation.get('detail')}, DCR={dcr.get('phase')}, DCR detail={dcr.get('detail')}; see state-evidence.json")

    def snapshot(self):
        states = {}
        for name in self.streams:
            stream = self.project / 'streams' / name
            states[name] = {file: (stream / file).read_text() for file in ('STATE.md', 'threads.tsv', 'log/tick-state.json') if (stream / file).exists()}
            states[name]['handovers'] = {str(path.relative_to(stream)): path.read_text() for path in (stream / 'handover').rglob('*.md') if not path.is_symlink()}
        save(self.logs / 'state-evidence.json', states)
        value = self.control('snapshot')
        save(self.logs / 'native-evidence.json', value)
        for name in self.streams:
            stream = self.project / 'streams' / name
            if 'drive' in self.state(stream):
                self.drive_on(stream)
        for call in value['calls']:
            check((call['provider'], call['model']) == ('openai-codex', 'gpt-6.1-sol'), 'provider/model changed')
            if not call['title'] and not call['summary']:
                check(call['reasoning'] == 'xhigh', 'session thinking changed')
            check(not call.get('fixtureError'), call.get('fixtureError', ''))
        return value

    def cleanup(self):
        result = {'streams': [], 'sessions': [], 'processStopped': self.proc is None, 'pathRemoved': False}
        retain_scratch = False
        try:
            if self.proc is not None and self.proc.poll() is None and self.url:
                before = self.control('snapshot')
                save(self.logs / 'cleanup-before.json', before)
                for name in self.streams:
                    stream = self.project / 'streams' / name
                    if not (stream / 'threads.tsv').exists():
                        continue
                    with (stream / 'threads.tsv').open() as handle:
                        rows = list(csv.DictReader(handle, delimiter='\t'))
                    for row in rows:
                        handover = stream / 'handover' / row['role'] / (row['session'] + '.md')
                        if not handover.exists():
                            self.journal(effect='cleanup-handover-before-write', session=row['session'], path=str(handover))
                            handover.parent.mkdir(parents=True, exist_ok=True)
                            handover.write_text(f"session: {row['session']}\nFixture teardown only. No product completion claim. See external chaos logs.\n")
                    closed = self.cli('close', name, required=False)
                    result['streams'].append({'stream': name, 'closed': closed.returncode == 0, 'detail': closed.stderr})
                archived = {item['sessionId'] for item in before['archives']}
                for item in before['evidence']:
                    sid = item['session']
                    if sid in self.deleted_sessions:
                        result['sessions'].append({'session': sid, 'state': 'deleted-through-supported-api'})
                        continue
                    if sid in archived or not Path(item['file']).exists():
                        result['sessions'].append({'session': sid, 'state': 'already-archived-or-retired'})
                        continue
                    response = self.web('archive', sid, required=False)
                    disposition = 'archived' if response.get('ok') else 'archive-refused'
                    policy_proof = self.logs / 'clean-analysis-evidence.json'
                    if disposition == 'archive-refused' and policy_proof.exists():
                        proof = json.loads(policy_proof.read_text())
                        receipt = proof['receipt']
                        if (receipt['originalSessionId'] == sid and receipt['basis'] == 'clean-policy-analysis-v1'
                                and receipt['originalTaskBlocked'] is True and receipt['state'] == 'analyzed'
                                and Path(item['file']).read_bytes() == proof['sourceSession'].encode()
                                and hashlib.sha256(Path(item['file']).read_bytes()).hexdigest() == proof['sourceSha256']):
                            disposition, retain_scratch = 'retained-policy-blocker', True
                    result['sessions'].append({'session': sid, 'state': disposition, 'response': response})
                save(self.logs / 'cleanup-after.json', self.control('snapshot'))
        except Exception as error:
            result['error'] = str(error)
        finally:
            if self.proc is not None:
                if self.proc.poll() is None:
                    self.proc.terminate()
                try:
                    self.proc.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    self.journal(effect='kill-owned-fixture-process', pid=self.proc.pid)
                    self.proc.kill()
                    self.proc.wait(timeout=5)
                result['processStopped'] = self.proc.poll() is not None
                result['processReturncode'] = self.proc.returncode
            check((self.scratch / '.chaos-owner').read_text() == self.owner, 'cleanup ownership changed')
            if retain_scratch:
                self.journal(effect='retain-policy-source-and-audit', path=str(self.scratch))
                result['retainedPath'] = str(self.scratch)
                result['retentionReason'] = 'Original policy refusal and isolated analysis remain durable evidence. No archive or retirement is claimed.'
            else:
                self.journal(effect='remove-owned-scratch-before-effect', path=str(self.scratch))
                shutil.rmtree(self.scratch)
            result['pathRemoved'] = not self.scratch.exists()
            save(self.logs / 'cleanup.json', result)
        return result


def transient(sandbox, error):
    name, stream, sid = sandbox.new()
    sandbox.plan(sid, {'error': error}, {'text': 'Recovered the exact owned request.'})
    sandbox.web('prompt', sid, stdin='Continue the bounded transient verification unit.')
    pending = sandbox.status(sid)
    check(pending.get('streamRetry', {}).get('state') == 'pending', 'native retry was not pending before the engine tick')
    sandbox.tick()
    sandbox.wait_idle(sid)
    evidence = sandbox.snapshot()
    calls = [c for c in evidence['calls'] if c['session'] == sid and not c['title'] and c.get('result', {}).get('error') == error]
    check(len(calls) == 1, 'expected exactly one controlled fault')
    first = calls[0]
    index = evidence['calls'].index(first)
    later = [c for c in evidence['calls'][index + 1:] if c['session'] == sid and not c['title']]
    check(len(later) == 1, 'engine tick raced the native retry or duplicated the task')
    following = later[0]
    delay = following['monotonicMs'] - first['monotonicMs']
    check(5000 <= delay < 9000, f'actual retry was not a fixed five-second wait: {delay}ms')
    entries = next(e['entries'] for e in evidence['evidence'] if e['session'] == sid)
    check(any(e.get('customType') == 'pi-web.stream-retry' and e['data']['state'] == 'resolved' for e in entries), 'retry lacks persisted resolved receipt')
    check(sandbox.status(sid)['failureBoundary']['state'] == 'watching', 'retry terminally parked')
    sandbox.drive_on(stream)
    return {'retryDelayMs': delay, 'session': sid, 'transport': 'simulated provider; actual unmocked wall-clock wait'}


def fault_recovery(sandbox, error, login=False, worker=False, rotate=False, small=False):
    name, stream, sid = sandbox.new()
    if worker:
        sid = sandbox.worker(name)
    if not small:
        sandbox.control('history', {'session': sid})
        sandbox.prompt(sid, 'Record a verified good fixture checkpoint after the simulated historical exchanges.')
    handover = stream / 'handover' / ('implementation' if worker else 'coordinator') / (sid + '.md')
    sandbox.journal(effect='own-handover-before-write', session=sid, path=str(handover))
    handover.parent.mkdir(parents=True, exist_ok=True)
    handover.write_text(f'session: {sid}\nControlled fixture handover. Retain the current permitted STATE goal and bounded role. Historical exchanges are simulated. No external effect was submitted.\n')
    sandbox.plan(sid, {'error': error}, authenticated=False if login else True)
    sandbox.prompt(sid, 'Inspect the next permitted owned fixture step without external effects.')
    if login:
        sandbox.tick(required=False)
        check(not sandbox.state(stream).get('failure_recoveries'), 'login recovered before simulated readiness refresh')
        sandbox.plan(sid, authenticated=True)
        ready = sandbox.web('failure-readiness', sid, '--cwd', stream)['result']
        check(ready['authenticated'] is True and ready['provider'] == 'openai-codex' and ready['model'] == 'gpt-6.1-sol', 'simulated login refresh did not restore exact-provider readiness')
    if worker:
        sandbox.cli('resume', name, '--all-parked')
    if rotate:
        sandbox.tick(required=False)
        check((stream / 'failures' / (sid + '.lastgood')).is_file(), 'rotation lacks an actual lastgood marker')
        check('coordinator_checkpoint' not in sandbox.state(stream), 'fixture unexpectedly used a live checkpoint')
        sandbox.cli('rotate', name)
    operation = sandbox.recover(stream, sid)
    evidence = sandbox.snapshot()
    sandbox.drive_on(stream)
    check(operation['observation']['kind'] == 'assistant-stop', 'recovery has no completed RESUME')
    if worker:
        row = next(row for row in csv.DictReader((stream / 'threads.tsv').read_text().splitlines(), delimiter='\t') if row['session'] == operation['fork'])
        check(row['role'] == 'implementation', 'worker promoted to coordinator')
    return {'original': sid, 'fork': operation['fork'], 'phase': operation['phase'], 'observation': operation['observation'], 'providerCalls': len(evidence['calls'])}


def usage_reset(sandbox):
    name, stream, sid = sandbox.new()
    reset = int(time.time()) + 2
    sandbox.plan(sid, {'error': json.dumps({'error': {'code': 'usage_limit_reached', 'resets_at': reset, 'message': 'Codex usage limit reached'}})})
    sandbox.prompt(sid, 'Continue the owned usage-reset verification unit.')
    sandbox.tick(required=False)
    end = time.monotonic() + 30
    while sandbox.state(stream).get('failures', {}).get(sid, {}).get('state') != 'recovered':
        check(time.monotonic() < end, 'usage reset did not self-heal: ' + json.dumps(sandbox.state(stream).get('failures')))
        sandbox.tick(required=False)
        time.sleep(.2)
    sandbox.snapshot()
    sandbox.drive_on(stream)
    episode = sandbox.state(stream)['failures'][sid]
    return {'session': sid, 'failure': {key: episode[key] for key in ('id', 'kind', 'state', 'retry_state', 'reset_at', 'retry_id')}, 'reset': 'simulated provider reset timestamp; real wall clock'}


def compaction(sandbox):
    name, stream, sid = sandbox.new()
    before = sandbox.control('history', {'session': sid})['estimatedTokens']
    check(before > 150000, f'context was not really above150k: {before}')
    goal = 'Complete the current permitted compaction verification unit, not the overall outcome.'
    sandbox.objective(name, goal)
    end = time.monotonic() + 45
    while True:
        sandbox.tick(required=False)
        operation = sandbox.state(stream).get('dcr_operations', {}).get(sid, {})
        if operation.get('phase') == 'complete':
            break
        check(time.monotonic() < end, f"compaction/RESUME incomplete: phase={operation.get('phase')}, detail={operation.get('detail')}; see state-evidence.json")
        time.sleep(.2)
    sandbox.wait_idle(sid)
    evidence = sandbox.snapshot()
    native = next(e for e in evidence['evidence'] if e['session'] == sid)
    check(native['estimatedTokens'] < 150000, 'rebuilt context remains above150k')
    receipt = sandbox.web('maintenance', sid, operation['id'], '--cwd', stream)['result']
    observation = receipt.get('resume', {}).get('observation', {})
    check(operation['resume_goal'] == goal and observation.get('kind') == 'assistant-stop', 'current-goal RESUME completion absent')
    check(receipt['resume']['potetoGoal'] == goal and receipt['state'] == 'resumed', 'native current-goal receipt changed')
    assistant = next(e for e in native['entries'] if e['id'] == observation['assistantEntryId'])
    check(assistant['message']['stopReason'] == 'stop', 'RESUME assistant did not complete')
    entry = next(e for e in native['entries'] if e['id'] == operation['compaction_entry'])
    check(entry['type'] == 'compaction' and entry.get('fromHook') is not True, 'not a native provider compaction')
    sandbox.drive_on(stream)
    return {'before': before, 'after': native['estimatedTokens'], 'measurement': 'native estimated context tokens, not billed provider tokens', 'observation': observation}


def policy_safe_analysis(sandbox):
    name, stream, sid = sandbox.new()
    rejected = 'CHAOS_REJECTED_UNIT_7d9a. Restricted fixture assignment. Do not reproduce this unit.'
    sandbox.objective(name, rejected)
    path = stream / 'STATE.md'
    path.write_text(path.read_text().replace('## Rules\n', '## Rules\nThe standing fixture grant permits documentation-only unit SAFE_DOC_UNIT_6a if the current restricted unit is rejected. Do not replay the rejected goal or assignment. Record the policy evidence.\n', 1))
    sandbox.control('policy-canaries', {'session': sid, 'canary': rejected})
    sandbox.plan(sid, {'error': 'This content was flagged for possible cybersecurity risk'})
    sandbox.prompt(sid, rejected)
    time.sleep(.2)
    status = sandbox.status(sid)
    native = next(item for item in sandbox.control('snapshot')['evidence'] if item['session'] == sid)
    original = Path(native['file']).read_bytes()
    charter = path.read_bytes().partition(b'## Log')[0]
    generation = status['automaticAdmission']['generation']
    for _ in range(4):
        sandbox.tick(required=False)
    evidence = sandbox.snapshot()
    state = sandbox.state(stream)
    episode = state.get('failures', {}).get(sid, {})
    analysis = episode.get('analysis') or {}
    check(analysis, 'clean isolated metadata analysis is unavailable; the original policy blocker remains required')
    check(analysis.get('state') == 'analyzed', f'clean metadata analysis did not complete: {analysis}')
    check(analysis.get('basis') == 'clean-policy-analysis-v1' and analysis.get('originalTaskBlocked') is True, 'analysis was mislabeled as ordinary recovery')
    check(episode['state'] == 'parked' and episode['authority'] is None, 'original rejected task was released')
    check(sid not in state.get('failure_recoveries', {}), 'policy analysis invented an inclusive-prefix fork')
    check(episode['continuation']['blockedGoalSha256'] == hashlib.sha256(rejected.encode()).hexdigest(), 'rejected-goal fingerprint changed')
    recovery_calls = [c for c in evidence['calls'] if c['session'] == analysis['analysisSessionId']]
    check(len(recovery_calls) == 1 and not recovery_calls[0]['title'] and not recovery_calls[0]['summary'], 'not exactly one actual metadata inference')
    check(recovery_calls[0]['reasoning'] == 'xhigh' and recovery_calls[0]['tools'] == [], 'model settings or native tool view changed')
    check(len(recovery_calls[0]['messages']) == 1 and recovery_calls[0]['messages'][0]['role'] == 'user' and recovery_calls[0]['systemPrompt'], 'not a fresh one-shot native context')
    check(rejected not in json.dumps(recovery_calls), 'complete metadata inference leaked a rejected canary')
    check('SAFE_DOC_UNIT_6a' not in json.dumps(recovery_calls), 'metadata analysis received the alternative assignment')
    check(str(stream) not in json.dumps(recovery_calls) and str(native['file']) not in json.dumps(recovery_calls), 'source links entered the private context')
    check(Path(native['file']).read_bytes() == original, 'source session was mutated')
    check(Path(analysis['audit']['retainedSource']).read_bytes() == original, 'exact original audit snapshot absent')
    check(hashlib.sha256(original).hexdigest() == analysis['audit']['sourceSha256'], 'source audit hash changed')
    check(analysis['audit']['sourceSha256'] not in json.dumps(recovery_calls), 'audit evidence was sent to the model')
    private_file = Path(analysis['analysisFile']).read_text()
    check(rejected not in private_file and '"type":"compaction"' not in private_file and 'resume-observed' not in private_file, 'private analysis copied context or invented maintenance completion')
    check(path.read_bytes().partition(b'## Log')[0] == charter, 'Goals, Charter or Rules changed')
    after = sandbox.status(sid)
    check(after['automaticAdmission']['generation'] == generation, 'original parked generation changed')
    check((after['model']['provider'], after['model']['id'], after['thinkingLevel']) == ('openai-codex', 'gpt-6.1-sol', 'xhigh'), 'original model or thinking changed')
    check(any(r['url'].endswith('/failure-recovery/analysis') and r.get('status') == 200 for r in evidence['requests']), 'actual CLI -> HTTP -> PiSessionService analysis path absent')
    check('Separate policy metadata analysis' in path.read_text(), 'analysis audit was not recorded in the Log')
    save(sandbox.logs / 'clean-analysis-evidence.json', {'receipt': analysis, 'sourceSha256': hashlib.sha256(original).hexdigest(), 'sourceSession': original.decode(), 'privateSession': private_file, 'contexts': recovery_calls, 'compactionContexts': [], 'compactionPermitted': False})
    sandbox.drive_on(stream)
    return {'original': sid, 'analysis': analysis['analysisSessionId'], 'basis': analysis['basis'], 'state': analysis['state'], 'providerContextCount': len(recovery_calls), 'originalTaskBlocked': True, 'rejectedReplay': False, 'sourceBytesPreserved': True, 'noForkCompactionOrResumeClaim': True}


def policy_document_paths(sandbox):
    scratch = sandbox.scratch
    check(scratch == scratch.resolve(), 'document fixture root must not contain a symlink')
    marker = scratch / '.chaos-owner'
    check(not marker.is_symlink() and marker.read_text() == sandbox.owner, 'document fixture ownership changed')
    paths = [scratch / 'document-input/bootstrap-facts.json', scratch / 'private-docs/automatic-admission-bootstrap.md']
    for path in paths:
        for part in (path.parent, path):
            check(not part.is_symlink(), 'document fixture symlink is forbidden')
    return paths


def prepare_policy_document_fixture(sandbox):
    source, output = policy_document_paths(sandbox)
    raw = (json.dumps(POLICY_DOC_FACTS, indent=2) + '\n').encode()
    sandbox.journal(effect='own-document-input-before-create', path=str(source), output=str(output))
    source.parent.mkdir()
    with source.open('xb') as handle:
        handle.write(raw)
    contract = {
        'fixtureOnly': True, 'unit': 'SAFE_DOC_UNIT_6a',
        'task': (
            'Write a Markdown protocol note for automatic-admission bootstrap maintainers from the bootstrap-facts-v1 input only. '
            'Use the title # Automatic-admission bootstrap and exactly three level-two sections named Provenance and facts, Rules, and Examples. '
            'Provenance and facts contains one json fence with schema=bootstrap-note-v1, protocol=automatic-admission-bootstrap-49, '
            'inputHandle=bootstrap-facts-v1, inputSha256 equal to the admitted input hash, outputHandle=owned-bootstrap-note, '
            'and the literal input facts and examples objects. '
            'Rules is a Markdown table with Rule and Protection columns containing every input rules row. '
            'Examples is a Markdown table with Scenario, Before initialization, and After initialization columns containing every input example. '
            'Render each example state in input field order as key=value entries separated by semicolon and space. '
            'Use unquoted strings and JSON booleans and numbers. Include no other prose. '
            'The rule protections explain later receiving stops and duplicate-work prevention. The examples show absent initialization and an existing stop.'
        ),
        'grant': {
            'scope': 'standing-fixture-documentation-only', 'root': str(output.parent), 'originalTaskBlocked': True,
            'noGo': ['original-task', 'source-prefix', 'project-resources', 'arbitrary-tools', 'arbitrary-paths', 'business-writes'],
        },
        'input': {'handle': POLICY_DOC_INPUT_HANDLE, 'path': str(source), 'sha256': hashlib.sha256(raw).hexdigest()},
        'output': {'handle': POLICY_DOC_OUTPUT_HANDLE, 'path': str(output), 'mediaType': 'text/markdown', 'maxBytes': POLICY_DOC_MAX_BYTES},
        'oracle': 'policy_document_oracle',
    }
    save(sandbox.logs / 'document-contract.json', contract)
    return contract


def policy_document_oracle(sandbox, candidate, *, rejected_canaries=()):
    source, output = policy_document_paths(sandbox)
    check(Path(candidate) == output, 'document output identity changed')
    expected_raw = (json.dumps(POLICY_DOC_FACTS, indent=2) + '\n').encode()
    check(source.is_file() and source.read_bytes() == expected_raw, 'document input bytes changed')
    check(output.is_file() and output.stat().st_size <= POLICY_DOC_MAX_BYTES, 'document is missing or exceeds the byte cap')
    raw = output.read_bytes()
    try:
        document = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise AssertionError('document must be UTF-8 Markdown') from error
    for canary in ('CHAOS_REJECTED_UNIT_7d9a', 'BLOCKED_UNIT_91c', *rejected_canaries):
        check(canary not in document, 'document contains a rejected canary')
    pieces = re.split(r'^## ([^\n]+)\n', document, flags=re.MULTILINE)
    check(pieces[0].strip() == '# Automatic-admission bootstrap' and len(pieces) == 7, 'document requires the protocol title and three sections')
    sections = dict(zip(pieces[1::2], pieces[2::2]))
    check(set(sections) == {'Provenance and facts', 'Rules', 'Examples'}, 'document sections changed')
    encoded = re.fullmatch(r'\s*```json\n(.+)\n```\s*', sections['Provenance and facts'], flags=re.DOTALL)
    check(encoded is not None, 'document requires structured provenance and facts')

    def unique_keys(pairs):
        value = {}
        for key, item in pairs:
            check(key not in value, 'duplicate document JSON key')
            value[key] = item
        return value

    try:
        binding = json.loads(encoded[1], object_pairs_hook=unique_keys)
    except ValueError as error:
        raise AssertionError('invalid document JSON') from error
    expected = {
        'schema': 'bootstrap-note-v1', 'protocol': POLICY_DOC_FACTS['provenance']['protocol'],
        'inputHandle': POLICY_DOC_INPUT_HANDLE, 'inputSha256': hashlib.sha256(expected_raw).hexdigest(),
        'outputHandle': POLICY_DOC_OUTPUT_HANDLE, 'facts': POLICY_DOC_FACTS['facts'], 'examples': POLICY_DOC_FACTS['examples'],
    }
    check(json.dumps(binding, sort_keys=True) == json.dumps(expected, sort_keys=True), 'document facts, examples or provenance binding changed')

    def table(section, header, expected_rows):
        rows = []
        for line in section.strip().splitlines():
            line = line.strip()
            check(line.startswith('|') and line.endswith('|'), 'unparsed document prose is forbidden')
            cells = [cell.strip() for cell in line[1:-1].split('|')]
            cells = [cell[1:-1] if cell.startswith('`') and cell.endswith('`') else cell for cell in cells]
            rows.append([' '.join(cell.split()) for cell in cells])
        check(len(rows) >= 2 and rows[0] == header, 'document table header changed')
        check(len(rows[1]) == len(header) and all(re.fullmatch(r':?-{3,}:?', cell) for cell in rows[1]), 'document table separator changed')
        check(sorted(rows[2:]) == sorted(expected_rows), 'document rules, protections or human-readable outcomes changed')

    table(sections['Rules'], ['Rule', 'Protection'], POLICY_DOC_FACTS['rules'])
    examples = []
    for name, outcome in POLICY_DOC_FACTS['examples'].items():
        states = ['; '.join(key + '=' + (value if isinstance(value, str) else json.dumps(value)) for key, value in outcome[phase].items()) for phase in ('before', 'after')]
        examples.append([name, *states])
    table(sections['Examples'], ['Scenario', 'Before initialization', 'After initialization'], examples)
    return {
        'fixtureArtifactValid': True, 'inputHandle': POLICY_DOC_INPUT_HANDLE,
        'inputSha256': expected['inputSha256'], 'outputHandle': POLICY_DOC_OUTPUT_HANDLE,
        'outputSha256': hashlib.sha256(raw).hexdigest(),
    }


def policy_narrowing(sandbox):
    contract = prepare_policy_document_fixture(sandbox)
    analysis = policy_safe_analysis(sandbox)
    check(not Path(contract['output']['path']).exists(), 'generic metadata analysis must not create a document placeholder')
    raise CaseNotImplemented('Generic metadata analysis is not the permitted SAFE_DOC_UNIT_6a continuation. The original task remains blocked.', {
        'original': analysis['original'], 'originalTaskBlocked': True,
        'safeAnalysisCompleted': analysis['state'] == 'analyzed', 'analysis': analysis,
        'documentContract': contract, 'documentArtifactProduced': False,
        'usefulContinuationCompleted': False,
        'remainingRequirement': {
            'status': 'NOTIMPLEMENTED', 'authorizedAlternative': 'SAFE_DOC_UNIT_6a',
            'requirement': 'Complete the permitted documentation-only continuation without replaying the rejected task.',
        },
    })


def blocked_loop(sandbox):
    name, stream, sid = sandbox.new()
    goal = 'Blocked fixture unit BLOCKED_UNIT_91c. Perform the same unavailable bounded step.'
    sandbox.objective(name, goal)
    path = stream / 'STATE.md'
    path.write_text(path.read_text().replace('## Rules\n', '## Rules\nThe standing fixture grant permits documentation-only unit SAFE_DOC_UNIT_6a as an alternative to BLOCKED_UNIT_91c.\n', 1))
    sandbox.plan(sid, *[{'text': 'BLOCKED_UNIT_91c is blocked. The same unavailable step cannot proceed.'} for _ in range(7)])
    for _ in range(7):
        sandbox.tick(required=False)
        sandbox.wait_idle(sid)
    evidence = sandbox.snapshot()
    dispatches = [c for c in evidence['calls'] if c['session'] == sid and not c['title'] and text_contains(c['messages'], goal)]
    check(len(dispatches) <= 3, f'FAIL blocked-loop suppression: {len(dispatches)} identical current-goal dispatches; fourth identical blocked unit was sent')
    log = (stream / 'STATE.md').read_text().partition('## Log')[2]
    alternative = any(text_contains(c['messages'], 'SAFE_DOC_UNIT_6a') for c in evidence['calls'] if not c['title'])
    check(('block' in log.lower() and 'BLOCKED_UNIT_91c' in log) or alternative, 'no durable blocked-unit escalation or different authorized strategy')
    sandbox.drive_on(stream)
    return {'identicalBlockedDispatches': len(dispatches)}


def text_contains(messages, text):
    last = next((m for m in reversed(messages) if m['role'] == 'user'), {})
    content = last.get('content', '')
    return text in (content if isinstance(content, str) else '\n'.join(p.get('text', '') for p in content))


def tick_noise(sandbox, unratified=False):
    name, stream, sid = sandbox.new(ratified=not unratified)
    sandbox.cli('close', name)
    before = sandbox.control('snapshot')
    failures = []
    for _ in range(4):
        result = sandbox.tick(required=False)
        if result.returncode or result.stderr.strip():
            failures.append(result.stderr)
    evidence = sandbox.snapshot()
    requests = evidence['requests'][len(before['requests']):]
    repeats = [r for r in requests if f'/sessions/{sid}/status' in r['url'] or f'/sessions/{sid}/archive' in r['url']]
    status_calls = [r for r in repeats if r['url'].split('?')[0].endswith('/status')]
    archive_calls = [r for r in repeats if r['url'].split('?')[0].endswith('/archive')]
    check(not failures and len(status_calls) <= 1 and len(archive_calls) <= 1, f'closed stream tick noise persists: errors={failures}, nativeCalls={repeats}')
    return {'closedSession': sid, 'ticks': 4, 'statusCalls': len(status_calls), 'archiveCalls': len(archive_calls), 'repeatedCallsAfterFirstReconciliation': max(0, len(status_calls) - 1) + max(0, len(archive_calls) - 1)}


def archived_worker(sandbox, dead=False):
    name, stream, _ = sandbox.new()
    sid = sandbox.worker(name)
    sandbox.web('archive', sid)
    if dead:
        sandbox.journal(effect='delete-owned-archived-fixture-before-effect', session=sid)
        request = urllib.request.Request(sandbox.url + '/api/sessions/' + sid, method='DELETE')
        with urllib.request.urlopen(request, timeout=20) as response:
            receipt = json.load(response)
        check(receipt == {'deleted': True}, 'supported deletion of the exact owned archived fixture failed')
        sandbox.deleted_sessions.add(sid)
        save(sandbox.logs / 'owned-deletion.json', {'session': sid, 'receipt': receipt})
    before = sandbox.control('snapshot')
    failures = []
    for _ in range(4):
        result = sandbox.tick(required=False)
        if result.returncode or result.stderr.strip():
            failures.append(result.stderr)
    evidence = sandbox.snapshot()
    requests = evidence['requests'][len(before['requests']):]
    calls = [r for r in requests if f'/sessions/{sid}/status' in r['url'] or f'/sessions/{sid}/archive' in r['url']]
    check(not failures and len(calls) <= 1, f'archived worker repeatedly queried: errors={failures}, nativeCalls={calls}')
    return {'worker': sid, 'ticks': 4, 'nativeCalls': len(calls)}


RUNNERS = {
    'overload': lambda s: transient(s, 'servers are currently overloaded'),
    'terminated': lambda s: transient(s, 'terminated'),
    'usage-reset': usage_reset,
    'login-refresh': lambda s: fault_recovery(s, 'Your Codex login has expired. Please log in again.', login=True),
    'model-error': lambda s: fault_recovery(s, 'Terminal model error: unsupported fixture request'),
    'parked-worker': lambda s: fault_recovery(s, 'Terminal model error: unsupported fixture request', worker=True),
    'compaction': compaction,
    'rotation': lambda s: fault_recovery(s, 'Terminal model error: unsupported fixture request', rotate=True),
    'policy-safe-analysis': policy_safe_analysis,
    'policy-narrowing': policy_narrowing,
    'blocked-loop': blocked_loop,
    'tick-noise': tick_noise,
    'unratified-close': lambda s: tick_noise(s, unratified=True),
    'small-recovery': lambda s: fault_recovery(s, 'Terminal model error: unsupported fixture request', small=True),
    'archived-worker': archived_worker,
    'dead-worker': lambda s: archived_worker(s, dead=True),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=selected_cases, default=selected_cases('all'))
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--logs', type=Path, default=DEFAULT_LOGS)
    parser.add_argument('--native-root', type=Path, help='existing disposable overlaid package under .harness-heal; never deleted')
    parser.add_argument('--source', type=Path, help='explicit frozen static package, never a live installation')
    parser.add_argument('--source-tar', type=Path, help='frozen pi-web.tar backup; copy only static package material')
    parser.add_argument('--node', type=Path, default=Path(shutil.which('node') or 'node'))
    args = parser.parse_args()
    if args.list:
        print(json.dumps({'baseline': BASELINE, 'all': CASES}, indent=2))
        return 0
    if sum(value is not None for value in (args.native_root, args.source, args.source_tar)) != 1:
        parser.error('supply exactly one of --native-root, --source, or --source-tar from frozen owned fixtures')
    if args.source is not None and (args.source.resolve().is_relative_to(LIVE_NATIVE.resolve()) or args.source.resolve().is_relative_to(LIVE_EXTENSIONS.resolve())):
        parser.error('live package copies are forbidden; supply frozen owned fixtures')
    if args.source_tar is not None and args.source_tar.suffix != '.tar':
        parser.error('--source-tar requires a frozen .tar package archive')
    args.logs.mkdir(parents=True, exist_ok=True)
    run = args.logs.resolve() / ('run-' + uuid.uuid4().hex)
    run.mkdir()
    sources = ('scripts/check-streams-chaos.py', 'pi-streams/tests/native/chaos-service.mjs')
    revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    save(run / 'run.json', {'sourceRevision': revision, 'cases': args.cases, 'nativeRoot': str(args.native_root) if args.native_root else None, 'frozenCopySource': str(args.source) if args.source else None, 'frozenArchive': str(args.source_tar) if args.source_tar else None, 'verificationSha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}, 'providerTransport': 'simulated, no credentials or provider requests', 'contextTokens': 'native estimates, not billed tokens'})
    owner = uuid.uuid4().hex
    fixture = ROOT / '.harness-heal' / ('chaos-' + owner)
    prepared = args.native_root is None
    results = []
    try:
        if prepared:
            save(run / 'fixture-ownership.json', {'owner': owner, 'effect': 'own-static-copy-before-create', 'path': str(fixture)})
            fixture.mkdir(parents=True)
            (fixture / '.chaos-owner').write_text(owner)
            native = fixture / 'native'
            native.mkdir()
            if args.source_tar is not None:
                copy_native_archive(args.source_tar, native)
            else:
                for name in ('package.json', 'dist', 'node_modules'):
                    source = args.source.resolve() / name
                    if source.is_dir():
                        shutil.copytree(source, native / name, symlinks=True, ignore=lambda directory, names: [item for item in names if item in {'auth.json', '.git', '.cache', '.pi'} or item.endswith('.jsonl')])
                    else:
                        shutil.copyfile(source, native / name)
            with (run / 'prepare.log').open('w') as log:
                for flags in (['--check'], []):
                    subprocess.run([sys.executable, str(ROOT / 'scripts/apply-native-overlay.py'), str(native), *flags], check=True, stdout=log, stderr=subprocess.STDOUT)
        else:
            native = args.native_root.resolve()
            check('/.harness-heal/' in str(native), 'explicit native root must be a disposable fixture')
        for path in native.rglob('*'):
            if path.is_symlink():
                check(path.resolve().is_relative_to(native.resolve()), 'native dependency symlink escapes the frozen package')
        with (run / 'overlay-check.log').open('w') as log:
            subprocess.run([sys.executable, str(ROOT / 'scripts/apply-native-overlay.py'), str(native), '--check'], check=True, stdout=log, stderr=subprocess.STDOUT)
        for case in args.cases:
            sandbox = Sandbox(run, case, native, args.node.resolve())
            result = {'case': case, 'result': 'FAIL', 'evidence': str(sandbox.logs)}
            try:
                sandbox.start()
                result['details'] = RUNNERS[case](sandbox)
                result['result'] = 'PASS'
            except CaseNotImplemented as error:
                result['result'], result['detail'] = 'NOTIMPLEMENTED', str(error)
                result['details'] = error.details
            except Exception as error:
                result['detail'] = str(error)
                if sandbox.url and sandbox.proc.poll() is None:
                    try:
                        sandbox.snapshot()
                    except Exception as snapshot_error:
                        result['snapshotError'] = str(snapshot_error)
            finally:
                result['cleanup'] = sandbox.cleanup()
                if result['result'] in {'PASS', 'NOTIMPLEMENTED'} and (result['cleanup'].get('error') or not all(item['closed'] for item in result['cleanup']['streams']) or any(item['state'] == 'archive-refused' for item in result['cleanup']['sessions'])):
                    result['result'], result['detail'] = 'FAIL', 'supported close/archive cleanup incomplete; see cleanup.json'
                results.append(result)
                save(run / 'results.json', results)
                print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        if prepared and fixture.exists():
            check((fixture / '.chaos-owner').read_text() == owner, 'static fixture ownership changed')
            shutil.rmtree(fixture)
            save(run / 'fixture-cleanup.json', {'owner': owner, 'path': str(fixture), 'removed': not fixture.exists()})
    print(f'Logs: {run}')
    return 0 if len(results) == len(args.cases) and all(item['result'] == 'PASS' for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())

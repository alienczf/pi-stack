from __future__ import annotations

import copy
import hashlib
import itertools
import json

import test_mass_resume as cases
from tick_support import TickCase, info, reply, row, status


class ResumeAdmissionTests(TickCase):
    seed = cases.MassResumeTests.seed
    digest = cases.MassResumeTests.digest
    body = cases.MassResumeTests.body
    fixture = cases.MassResumeTests.fixture
    append = cases.MassResumeTests.append
    fork_response = cases.MassResumeTests.fork_response

    def healthy_coordinator(self):
        with (self.stream / 'threads.tsv').open('a') as registry:
            registry.write(row('healthy', 'coordinator', str(self.stream)))
        self.write_log('healthy', str(self.stream), reply('Healthy coordinator'))
        self.listing.append(info('healthy', str(self.stream), self.log_path('healthy')))
        healthy = status('healthy')
        healthy.update(conditionalAdmissionSupport='generation-cas-v1', controlGoalSupport='preserve-ask-v1')
        self.stub.automatic_admissions['healthy'] = {'sessionId': 'healthy', 'cwd': str(self.stream), 'generation': 'healthy-generation', 'allowed': False, 'durable': True}
        self.routes.append(('GET', '/api/sessions/healthy/status', 200, healthy))
        self.stub.simulate_conditional_controls = True

    def matrix_case(self, role, enabled, registry, historical, newer_stop, uncertain):
        self.fixture(role)
        fork_info = self.listing.pop()
        table = self.stream / 'threads.tsv'
        table.write_text(table.read_text().replace('\tactive\t', f'\t{registry}\t', 1))
        if role != 'coordinator':
            self.healthy_coordinator()
        data = self.state(self.stream)
        data['drive'] = {'enabled': enabled, **({'run_id': 'existing-run'} if enabled else {})}
        if uncertain:
            data.setdefault('sessions', {})['coi'] = {'replay': ['unconfirmed-external-effect']}
        if historical:
            data['failures']['coi'].update(authority=None, continuation=None, pause_owned=False)
            self.original['failureBoundary']['parking'] = {'generation': 'historical-stop', 'owned': False}
            self.append('coi', 'historical-stop', 'registered-policy', 'pi-web.stream-failure', self.original['failureBoundary'])
            self.original['rotationSafety']['entryId'] = 'historical-stop'
            self.stub.automatic_admissions['coi']['generation'] = 'historical-stop'
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        before = table.read_bytes()
        expected_boundary = copy.deepcopy(self.original['failureBoundary'])
        generation = 'historical-stop' if historical else 'native-parked-coi'
        rebound = []
        forks = []

        def resume(body):
            self.assertEqual(body, {'cwd': str(self.cwd), 'expected': {**expected_boundary, 'generation': generation}})
            if newer_stop:
                self.stub.automatic_admissions['coi']['generation'] = 'racing-stop'
                return 409, {'error': 'Explicit resume was superseded'}
            rebound.append(body)
            self.original['failureBoundary']['parking'] = {'generation': 'explicit-generation', 'owned': True}
            self.append('coi', 'explicit-resume', 'historical-stop', 'pi-web.stream-failure', self.original['failureBoundary'])
            self.original['rotationSafety']['entryId'] = 'explicit-resume'
            self.stub.automatic_admissions['coi']['generation'] = 'explicit-generation'
            self.request['expected'] = {**self.original['failureBoundary'], 'generation': 'explicit-generation'}
            self.request['continuation']['stateSha256'] = hashlib.sha256((self.stream / 'STATE.md').read_bytes()).hexdigest()
            self.result['intentSha256'] = hashlib.sha256(json.dumps(self.request, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            return 200, self.original['failureBoundary']

        def fork(body):
            if newer_stop:
                self.stub.automatic_admissions['coi']['generation'] = 'racing-stop'
                return 409, {'error': 'Conditional generation is stale', 'admission': {'state': 'refused-before-effect', 'id': body['id'], 'intentSha256': self.result['intentSha256']}}
            forks.append(body)
            self.listing.append(fork_info)
            return self.fork_response(body)

        self.routes = [(method, path, code, fork if path.endswith('/fork') else body) for method, path, code, body in self.routes]
        self.routes.append(('POST', '/api/sessions/coi/failure-recovery/resume', 200, resume))
        self.stub.set_routes(self.routes)
        self.stub.requests.clear()
        if role == 'coordinator':
            observed = self.run_streams('status', 'etl', '--json')
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertEqual(json.loads(observed.stdout)['streams'][0]['coordinator']['session'], 'coi')
        result = self.run_streams('resume', 'etl', '--all-parked')
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = next(item for item in json.loads(result.stdout) if item['session'] == 'coi')
        admitted = not newer_stop and not uncertain
        self.assertEqual(outcome.get('phase') if admitted else outcome['state'], 'bound' if admitted else 'pending')
        posts = [item for item in self.stub.requests if item[0] == 'POST']
        self.assertEqual(sum(item[1].endswith('/failure-recovery/resume') for item in posts), int(historical and not uncertain))
        self.assertEqual(sum(item[1].endswith('/fork') for item in posts), int(not uncertain and not (historical and newer_stop)))
        self.assertEqual(len(rebound), int(historical and admitted))
        self.assertEqual(len(forks), int(admitted))
        self.assertEqual(sum(item[1] == '/api/sessions/healthy/automatic-admission' for item in posts), int(role != 'coordinator' and not enabled))
        self.assertFalse(self.stub.automatic_admissions['coi']['allowed'])
        self.assertFalse(any(item[1] == '/api/sessions/coi/automatic-admission' for item in posts))
        self.assertEqual((self.stream / 'failures/coi.lastgood').read_bytes(), b'e4\n')
        if newer_stop and not uncertain:
            self.assertEqual(self.stub.automatic_admissions['coi']['generation'], 'racing-stop')
        if admitted:
            lines = table.read_text().splitlines()
            self.assertEqual([line.split('\t')[8] for line in lines[1:] if line.startswith('coi\t')], ['parked'])
            self.assertEqual([line.split('\t')[8] for line in lines[1:] if line.startswith('returned-fork\t')], ['active'])
            if role == 'coordinator':
                observed = self.run_streams('status', 'etl', '--json')
                self.assertEqual(observed.returncode, 0, observed.stderr)
                self.assertEqual(json.loads(observed.stdout)['streams'][0]['coordinator']['session'], 'returned-fork')
        else:
            self.assertEqual(table.read_bytes(), before)

    def test_parked_predecessor_cannot_replace_a_healthy_active_coordinator(self):
        self.fixture()
        table = self.stream / 'threads.tsv'
        table.write_text(table.read_text().replace('\tactive\t', '\tparked\t', 1))
        self.healthy_coordinator()
        before = table.read_bytes()
        self.stub.set_routes(self.routes)
        self.stub.requests.clear()
        result = self.run_streams('resume', 'etl', '--all-parked')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [{'session': 'coi', 'state': 'pending', 'detail': 'Explicit resume preserves the designated coordinator'}])
        self.assertEqual(table.read_bytes(), before)
        self.assertEqual([(item[1], item[3]) for item in self.stub.requests if item[0] == 'POST'], [('/api/sessions/healthy/automatic-admission', {'allowed': True, 'expectedGeneration': 'healthy-generation'})])

    def healthy_case(self, command, enabled, newer_stop):
        self.stream = self.make_stream(self.home, 'etl', '')
        self.listing, self.routes = [], []
        self.healthy_coordinator()
        self.routes.append(('GET', '/api/sessions', 200, self.listing))
        (self.stream / 'log').mkdir(exist_ok=True)
        (self.stream / 'log/tick-state.json').write_text(json.dumps({'drive': {'enabled': enabled, **({'run_id': 'existing-run'} if enabled else {})}}))

        def racing_stop(body):
            if newer_stop:
                self.stub.automatic_admissions['healthy'].update(allowed=False, generation='racing-stop')
            return 200, {}

        self.routes.append(('POST', '/api/sessions/healthy/automatic-admission', 200, racing_stop))
        self.stub.set_routes(self.routes)
        result = self.run_streams(*(['drive', 'etl', 'on'] if command == 'drive' else ['resume', 'etl', '--all-parked']))
        expected_post = command == 'drive' or not enabled
        self.assertEqual(result.returncode, int(command == 'drive' and newer_stop), result.stderr)
        control = self.stub.automatic_admissions['healthy']
        self.assertEqual(control['allowed'], expected_post and not newer_stop)
        self.assertEqual(control['generation'], 'racing-stop' if newer_stop and expected_post else 'healthy-generation-next' if expected_post else 'healthy-generation')
        posts = [item[3] for item in self.stub.requests if item[0] == 'POST']
        self.assertEqual(posts, [{'allowed': True, 'expectedGeneration': 'healthy-generation'}] if expected_post else [])
        drive = self.state(self.stream)['drive']
        self.assertEqual(drive['enabled'], not newer_stop if expected_post else enabled)
        if expected_post:
            self.assertEqual(drive['remote_state'], 'on-unconfirmed' if newer_stop else 'on-confirmed')


def lane_test(case):
    def test(self):
        self.matrix_case(*case)
    return test


for case in itertools.product(('coordinator', 'research'), (False, True), ('active', 'parked', 'waiting_quota'), (False, True), (False, True), (False, True)):
    role, enabled, registry, historical, newer_stop, uncertain = case
    name = f'test_lane_{role}_drive_{enabled}_{registry}_historical_{historical}_stop_{newer_stop}_uncertain_{uncertain}'
    setattr(ResumeAdmissionTests, name, lane_test(case))

for command, enabled, newer_stop in itertools.product(('drive', 'resume'), (False, True), (False, True)):
    def test(self, command=command, enabled=enabled, newer_stop=newer_stop):
        self.healthy_case(command, enabled, newer_stop)
    setattr(ResumeAdmissionTests, f'test_healthy_{command}_drive_{enabled}_stop_{newer_stop}', test)

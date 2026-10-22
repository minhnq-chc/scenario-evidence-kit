"""Version-pinned suites, idempotent runs, metrics and append-only activity."""

import hashlib

from fastapi import Depends, HTTPException

from .core import build_report
from .requests import RunInput, SuiteInput
from .runner import scenario_runner_config
from .storage import dump, identifier, now


def install_workflow(app, store, runner, user, author, project):
    @app.get('/api/suites')
    def suites(project_id: str, current=Depends(user)):
        with store.connect() as db:
            project(db, project_id)
            rows = db.execute('SELECT * FROM suites WHERE project_id=? ORDER BY created_at DESC',
                              (project_id,))
            return [store.suite(row) for row in rows]

    @app.post('/api/suites', status_code=201)
    def create_suite(body: SuiteInput, current=Depends(author)):
        if len(body.case_ids) != len(set(body.case_ids)):
            raise HTTPException(422, 'Duplicate case identifiers')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            project(db, body.project_id)
            items = []
            for cid in body.case_ids:
                case = store.case(db, cid)
                if case is None or case['project_id'] != body.project_id:
                    raise HTTPException(404, 'Case not found in this project')
                if case['status'] != 'approved':
                    raise HTTPException(409, 'Suites require approved case revisions')
                items.append({'case_id': cid, 'revision': case['revision'],
                              'fingerprint': case['validation']['fingerprint']})
            sid = identifier()
            db.execute('INSERT INTO suites VALUES(?,?,?,?,?)',
                       (sid, body.project_id, body.name, dump(items), now()))
            store.log(db, current['id'], 'suite.created', sid, body.project_id)
            return store.suite(db.execute('SELECT * FROM suites WHERE id=?', (sid,)).fetchone())

    @app.get('/api/runs')
    def runs(project_id: str, current=Depends(user)):
        with store.connect() as db:
            project(db, project_id)
            rows = db.execute('SELECT * FROM runs WHERE project_id=? ORDER BY created_at DESC LIMIT 200',
                              (project_id,))
            return [store.run(row) for row in rows]

    @app.post('/api/runs', status_code=201)
    def create_run(body: RunInput, current=Depends(author)):
        digest = hashlib.sha256(dump({'suite_id': body.suite_id, 'mode': body.mode}).encode()).hexdigest()
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT * FROM runs WHERE idempotency_key=?',
                                  (body.idempotency_key,)).fetchone()
            if previous:
                if previous['request_hash'] != digest:
                    raise HTTPException(409, 'Idempotency key was used for a different request')
                return store.run(previous)
            suite = store.suite(db.execute('SELECT * FROM suites WHERE id=?', (body.suite_id,)).fetchone())
            if suite is None:
                raise HTTPException(404, 'Suite not found')
            cases = [store.case(db, item['case_id'], item['revision']) for item in suite['items']]
            if any(case is None for case in cases):
                raise HTTPException(409, 'Suite snapshot is incomplete')
            status, results, error = 'queued', [], None
            if body.mode == 'offline':
                results = [{'case_id': case['id'], 'revision': case['revision'],
                            'report': build_report(case['scenario'])} for case in cases]
                status = 'completed'
            elif scenario_runner_config() is None:
                status, error = 'error', 'CARLA is not configured. Offline checks do not execute a simulator.'
            elif any(case['scenario']['map_name'].startswith('Demo') for case in cases):
                status, error = 'error', 'Synthetic Demo maps cannot run in CARLA. Select a real map first.'
            rid = identifier()
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (rid, suite['project_id'], body.suite_id, body.mode, digest, body.idempotency_key,
                        status, dump(results), error, now()))
            store.log(db, current['id'], 'run.created', rid, suite['project_id'])
        if status == 'queued':
            try:
                runner.start(rid, cases)
            except RuntimeError as exc:
                with store.connect() as db:
                    db.execute("UPDATE runs SET status='error',error=? WHERE id=?", (str(exc), rid))
        with store.connect() as db:
            return store.run(db.execute('SELECT * FROM runs WHERE id=?', (rid,)).fetchone())

    @app.get('/api/runs/{rid}')
    def get_run(rid: str, current=Depends(user)):
        with store.connect() as db:
            result = store.run(db.execute('SELECT * FROM runs WHERE id=?', (rid,)).fetchone())
        if result is None:
            raise HTTPException(404, 'Run not found')
        return result

    @app.post('/api/runs/{rid}/cancel')
    def cancel_run(rid: str, current=Depends(author)):
        value = get_run(rid, current)
        runner.cancel(rid)
        with store.connect() as db:
            store.log(db, current['id'], 'run.cancel_requested', rid, value['project_id'])
        return get_run(rid, current)

    @app.get('/api/metrics')
    def metrics(project_id: str, current=Depends(user)):
        with store.connect() as db:
            project(db, project_id)
            cases = [store.case(db, row['id']) for row in db.execute(
                'SELECT id FROM cases WHERE project_id=?', (project_id,))]
            suites_count = db.execute('SELECT count(*) FROM suites WHERE project_id=?',
                                     (project_id,)).fetchone()[0]
            runs = [store.run(row) for row in db.execute('SELECT * FROM runs WHERE project_id=?',
                                                       (project_id,))]
        reports = [item['report'] for run in runs for item in run['results']]
        return {'cases': len(cases), 'approved': sum(c['status'] == 'approved' for c in cases),
                'rejected': sum(c['status'] == 'rejected' for c in cases), 'suites': suites_count,
                'runs': len(runs),
                'offline_pass': sum(r.get('validation', {}).get('status') == 'PASS' for r in reports),
                'simulation_pass': sum(r.get('simulation', {}).get('status') == 'PASS' for r in reports),
                'simulation_not_run': sum(r.get('simulation', {}).get('status') == 'NOT_RUN' for r in reports)}

    @app.get('/api/audit')
    def audit(project_id: str, current=Depends(user)):
        with store.connect() as db:
            project(db, project_id)
            rows = db.execute('SELECT id,action,subject,created_at FROM audit WHERE project_id=? '
                              'ORDER BY id DESC LIMIT 200', (project_id,))
            return [dict(row) for row in rows]

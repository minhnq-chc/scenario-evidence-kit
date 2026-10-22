"""Local-first HTTP application. Database and runner are per application instance."""

import os
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .auth import LoginLimiter, create_user, issue_token, password_matches, token_digest
from .core import build_report, export_xosc, generate, import_xosc, preview, validate
from .requests import (
    Credentials,
    GenerateInput,
    ImportInput,
    NewUser,
    ProjectInput,
    ReviewInput,
    RevisionInput,
)
from .runner import Runner, scenario_runner_config
from .storage import Store, dump, identifier, now


def create_app(database_path=None):
    db_path = database_path or os.environ.get('SEK_DATABASE') or Path.home() / '.scenario-evidence-kit/workbench.db'
    store = Store(db_path)
    runner = Runner(store)
    limiter = LoginLimiter()

    @asynccontextmanager
    async def lifespan(app):
        yield
        runner.close()

    app = FastAPI(title='Scenario Evidence Kit', version='0.1.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.store, app.state.runner = store, runner

    @app.middleware('http')
    async def boundaries(request, call_next):
        if request.url.hostname not in ('localhost', '127.0.0.1', '::1'):
            return Response('Local host required', status_code=400)
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            origin = request.headers.get('origin')
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return Response('Cross-site request rejected', status_code=403)
            if origin:
                parsed = urlsplit(origin)
                if (parsed.scheme not in ('http', 'https') or parsed.netloc != request.url.netloc
                        or parsed.path or parsed.query or parsed.fragment):
                    return Response('Cross-origin request rejected', status_code=403)
        # JSON/XML request payloads are bounded even without Content-Length.
        if request.method in ('POST', 'PUT', 'PATCH'):
            size = 0
            parts = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 1_000_000:
                    return Response('Request too large', status_code=413)
                parts.append(chunk)
            request._body = b''.join(parts)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        if request.url.path.startswith('/api'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def user(authorization: str = Header(default='')):
        if not authorization.startswith('Bearer ') or len(authorization) > 256:
            raise HTTPException(401, 'Sign in to continue')
        with store.connect() as db:
            row = db.execute('SELECT u.id,u.name,u.role FROM users u JOIN tokens t ON u.id=t.user_id '
                             'WHERE t.digest=? AND t.expires_at>?',
                             (token_digest(authorization[7:]), time.time())).fetchone()
        if row is None:
            raise HTTPException(401, 'Session expired or invalid')
        return dict(row)

    def author(current=Depends(user)):
        if current['role'] not in ('owner', 'author'):
            raise HTTPException(403, 'Author or owner role required')
        return current

    def reviewer(current=Depends(user)):
        if current['role'] not in ('owner', 'reviewer'):
            raise HTTPException(403, 'Reviewer or owner role required')
        return current

    def project(db, pid):
        if not db.execute('SELECT 1 FROM projects WHERE id=?', (pid,)).fetchone():
            raise HTTPException(404, 'Project not found')

    def case(db, cid):
        item = store.case(db, cid)
        if item is None:
            raise HTTPException(404, 'Case not found')
        return item

    def add_case(db, pid, scenario, uid, generation=None):
        cid, created = identifier(), now()
        checked = validate(scenario)
        if generation:
            checked['generation'] = generation
        db.execute('INSERT INTO cases VALUES(?,?,?)', (cid, pid, created))
        db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?)',
                   (cid, 1, dump(scenario), dump(checked), 'draft', '', created))
        store.log(db, uid, 'case.created', cid, pid)
        return store.case(db, cid)

    @app.get('/health')
    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': '0.1.0', 'generator': 'offline-templates'}

    @app.get('/docs')
    def local_docs():
        return Response('<!doctype html><html lang="en"><meta charset="utf-8">'
                        '<title>Scenario Evidence Kit API</title><h1>Local API</h1>'
                        '<p><a href="/openapi.json">OpenAPI JSON schema</a></p>'
                        '<p>Workbench endpoints require a local bearer token. See the README and '
                        'docs/APP_CONTRACT.md for the workflow and supported subset.</p></html>',
                        media_type='text/html')

    @app.get('/api/auth/status')
    def auth_status():
        with store.connect() as db:
            return {'initialized': bool(db.execute('SELECT 1 FROM users LIMIT 1').fetchone())}

    @app.post('/api/auth/bootstrap', status_code=201)
    def bootstrap(body: Credentials, request: Request):
        limiter.check(request.client.host if request.client else 'local')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                raise HTTPException(409, 'Already initialized. Sign in instead.')
            created = create_user(db, body.name, body.password, 'owner')
            return issue_token(db, created)

    @app.post('/api/auth/login')
    def login(body: Credentials, request: Request):
        limiter.check(request.client.host if request.client else 'local')
        with store.connect() as db:
            item = db.execute('SELECT * FROM users WHERE name=?', (body.name,)).fetchone()
            if item is None or not password_matches(body.password, item['password_hash']):
                raise HTTPException(401, 'Incorrect name or password')
            return issue_token(db, item)

    @app.get('/api/auth/me')
    def me(current=Depends(user)):
        return current

    @app.post('/api/auth/logout')
    def logout(authorization: str = Header(default=''), current=Depends(user)):
        with store.connect() as db:
            db.execute('DELETE FROM tokens WHERE digest=?', (token_digest(authorization[7:]),))
        return {'ok': True}

    @app.post('/api/auth/users', status_code=201)
    def new_user(body: NewUser, current=Depends(user)):
        if current['role'] != 'owner':
            raise HTTPException(403, 'Owner role required')
        with store.connect() as db:
            try:
                created = create_user(db, body.name, body.password, body.role)
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, 'Name already exists') from exc
            store.log(db, current['id'], 'user.created', created['id'])
            return created

    @app.get('/api/catalog')
    def catalog(current=Depends(user)):
        from .provider import available
        maps = [{'name': 'DemoStraight', 'synthetic': True},
                {'name': 'DemoIntersection', 'synthetic': True}]
        for name in os.environ.get('SEK_CARLA_MAPS', '').split(','):
            if name.strip() and name.strip().replace('_', '').isalnum():
                maps.append({'name': name.strip(), 'synthetic': False, 'source': 'local configuration'})
        return {'maps': maps, 'kinds': ['cut_in', 'lead_brake', 'pedestrian_crossing'],
                'weather': ['clear', 'rain', 'fog', 'night'],
                'carla_configured': scenario_runner_config() is not None,
                'openai_configured': available()}

    @app.get('/api/projects')
    def projects(current=Depends(user)):
        with store.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY created_at')]

    @app.post('/api/projects', status_code=201)
    def create_project(body: ProjectInput, current=Depends(author)):
        item = {'id': identifier(), 'name': body.name, 'created_at': now()}
        with store.connect() as db:
            db.execute('INSERT INTO projects VALUES(:id,:name,:created_at)', item)
            store.log(db, current['id'], 'project.created', item['id'], item['id'])
        return item

    @app.get('/api/cases')
    def cases(project_id: str, current=Depends(user)):
        with store.connect() as db:
            project(db, project_id)
            ids = db.execute('SELECT id FROM cases WHERE project_id=? ORDER BY created_at DESC', (project_id,))
            return [store.case(db, row['id']) for row in ids]

    @app.post('/api/generate', status_code=201)
    def generate_cases(body: GenerateInput, current=Depends(author)):
        with store.connect() as db:
            project(db, body.project_id)
        generation = {'engine': 'templates', 'reproducible_generation': True}
        if body.engine == 'openai':
            from .provider import available, generate_with_openai
            if current['role'] != 'owner':
                raise HTTPException(403, 'Only the owner can use a paid provider')
            if not available():
                raise HTTPException(409, 'OpenAI is not configured; choose offline templates instead.')
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                limit = max(1, min(int(os.environ.get('SEK_OPENAI_DAILY_CALLS', '5')), 100))
                used = db.execute('SELECT count(*) FROM provider_calls WHERE created_at>=?',
                                  (now()[:10],)).fetchone()[0]
                if used >= limit:
                    raise HTTPException(429, 'Daily provider call limit reached; no request was sent.')
                db.execute('INSERT INTO provider_calls VALUES(?,?,?)',
                           (identifier(), now(), os.environ['SEK_OPENAI_MODEL']))
            try:
                scenarios, generation = generate_with_openai(
                    body.description, body.count, body.seed, body.map_name, body.kind)
            except Exception as exc:
                # Provider exceptions may contain sensitive request/account data. Do not echo them.
                raise HTTPException(502, 'Provider request failed or output was invalid. Check local configuration.') from exc
        else:
            scenarios = generate(body.description, body.count, body.seed, body.map_name, body.kind)
        with store.connect() as db:
            return [add_case(db, body.project_id, scenario, current['id'], generation) for scenario in scenarios]

    @app.post('/api/cases/import', status_code=201)
    def import_case(body: ImportInput, current=Depends(author)):
        try:
            scenario = import_xosc(body.xml)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        with store.connect() as db:
            project(db, body.project_id)
            return add_case(db, body.project_id, scenario, current['id'])

    @app.get('/api/cases/{cid}')
    def get_case(cid: str, current=Depends(user)):
        with store.connect() as db:
            return case(db, cid)

    @app.post('/api/cases/{cid}/revisions', status_code=201)
    def revision(cid: str, body: RevisionInput, current=Depends(author)):
        checked = validate(body.scenario)
        if checked['status'] != 'PASS':
            raise HTTPException(422, checked)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            item = case(db, cid)
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?)',
                       (cid, item['revision'] + 1, dump(body.scenario), dump(checked), 'draft', '', now()))
            store.log(db, current['id'], 'case.revised', cid, item['project_id'])
            return store.case(db, cid)

    @app.post('/api/cases/{cid}/review')
    def review(cid: str, body: ReviewInput, current=Depends(reviewer)):
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            item = case(db, cid)
            if item['status'] != 'draft':
                raise HTTPException(409, 'Already reviewed. Create a new revision to change the case.')
            if body.decision == 'approved' and item['validation']['status'] != 'PASS':
                raise HTTPException(422, 'A failing case cannot be approved')
            db.execute('UPDATE revisions SET status=?,note=? WHERE case_id=? AND revision=?',
                       (body.decision, body.note, cid, item['revision']))
            store.log(db, current['id'], f'case.{body.decision}', cid, item['project_id'])
            return store.case(db, cid)

    @app.get('/api/cases/{cid}/xosc')
    def xosc(cid: str, current=Depends(user)):
        with store.connect() as db:
            scenario = case(db, cid)['scenario']
        return Response(export_xosc(scenario), media_type='application/xml',
                        headers={'Content-Disposition': f'attachment; filename="{cid}.xosc"'})

    @app.get('/api/cases/{cid}/report')
    def report(cid: str, current=Depends(user)):
        with store.connect() as db:
            item = case(db, cid)
            value = build_report(item['scenario'])
        value.update({'case_id': cid, 'revision': item['revision'], 'review_status': item['status']})
        return value

    @app.get('/api/cases/{cid}/preview')
    def trajectory(cid: str, current=Depends(user)):
        with store.connect() as db:
            return preview(case(db, cid)['scenario'])

    # Suite and run routes are factored out to keep this module navigable.
    from .workflow import install_workflow
    install_workflow(app, store, runner, user, author, project)

    web = Path(__file__).parent / 'web'
    if web.is_dir():
        app.mount('/assets', StaticFiles(directory=web / 'assets'), name='assets')

        @app.get('/')
        def index():
            return FileResponse(web / 'index.html')
    else:
        @app.get('/')
        def index():
            return {'application': 'Scenario Evidence Kit', 'docs': '/docs',
                    'web_setup': 'Build frontend and run scripts/build_web.py to include the UI.'}

    return app

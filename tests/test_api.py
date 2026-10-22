"""HTTP behavior tests using isolated temporary databases, never a simulator."""

import json

import pytest
from fastapi.testclient import TestClient

from scenario_evidence.api import create_app

PASSWORD = 'local-test-password-2026'


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / 'test.db'), base_url="http://127.0.0.1") as client:
        yield client


def owner(client):
    response = client.post('/api/auth/bootstrap', json={'name': 'Maintainer', 'password': PASSWORD})
    assert response.status_code == 201
    return {'Authorization': 'Bearer ' + response.json()['token']}


def project(client, headers):
    response = client.post('/api/projects', headers=headers, json={'name': 'Synthetic testing'})
    assert response.status_code == 201
    return response.json()['id']


def generated(client, headers, pid, count=2):
    response = client.post('/api/generate', headers=headers,
                           json={'project_id': pid, 'description': 'A car cuts in during rain',
                                 'seed': 14, 'count': count})
    assert response.status_code == 201, response.text
    return response.json()


def approved_suite(client, headers, pid):
    items = generated(client, headers, pid)
    for item in items:
        result = client.post(f"/api/cases/{item['id']}/review", headers=headers,
                             json={'decision': 'approved', 'note': 'Offline subset checked'})
        assert result.status_code == 200, result.text
    response = client.post('/api/suites', headers=headers,
                           json={'project_id': pid, 'name': 'Regression set',
                                 'case_ids': [item['id'] for item in items]})
    assert response.status_code == 201, response.text
    return response.json(), items


def test_bootstrap_auth_and_logout(client):
    assert client.get('/health').status_code == 200
    assert client.get('/api/auth/status').json() == {'initialized': False}
    assert client.get('/api/projects').status_code == 401
    headers = owner(client)
    assert client.get('/api/auth/me', headers=headers).json()['role'] == 'owner'
    assert client.post('/api/auth/bootstrap', json={'name': 'Other', 'password': PASSWORD}).status_code == 409
    assert client.post('/api/auth/login', json={'name': 'Maintainer', 'password': 'wrong-long-password'}).status_code == 401
    assert client.post('/api/auth/logout', headers=headers).status_code == 200
    assert client.get('/api/projects', headers=headers).status_code == 401


def test_revisions_suite_snapshots_and_idempotency(client):
    headers = owner(client)
    pid = project(client, headers)
    suite, items = approved_suite(client, headers, pid)
    first = items[0]
    changed = dict(first['scenario'], title='Updated scenario')
    revised = client.post(f"/api/cases/{first['id']}/revisions", headers=headers,
                          json={'scenario': changed})
    assert revised.status_code == 201
    assert revised.json()['revision'] == 2 and revised.json()['status'] == 'draft'
    payload = {'suite_id': suite['id'], 'mode': 'offline', 'idempotency_key': 'offline-attempt-1'}
    response = client.post('/api/runs', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run['status'] == 'completed'
    assert run['results'][0]['revision'] == 1
    assert all(item['report']['simulation']['status'] == 'NOT_RUN' for item in run['results'])
    assert client.post('/api/runs', headers=headers, json=payload).json()['id'] == run['id']
    assert client.post('/api/runs', headers=headers, json={**payload, 'mode': 'carla'}).status_code == 409
    assert client.post(f"/api/runs/{run['id']}/cancel", headers=headers).json()['status'] == 'completed'
    stats = client.get('/api/metrics', headers=headers, params={'project_id': pid}).json()
    assert stats['simulation_pass'] == 0 and stats['simulation_not_run'] == 2
    assert stats['offline_pass'] == 2


def test_review_roles_and_repeated_decision(client):
    headers = owner(client)
    pid = project(client, headers)
    item = generated(client, headers, pid, 1)[0]
    assert client.post('/api/auth/users', headers=headers,
                       json={'name': 'Author', 'password': PASSWORD, 'role': 'author'}).status_code == 201
    token = client.post('/api/auth/login', json={'name': 'Author', 'password': PASSWORD}).json()['token']
    author_headers = {'Authorization': 'Bearer ' + token}
    assert client.post(f"/api/cases/{item['id']}/review", headers=author_headers,
                       json={'decision': 'approved'}).status_code == 403
    assert client.post('/api/suites', headers=headers,
                       json={'project_id': pid, 'name': 'Unapproved', 'case_ids': [item['id']]}).status_code == 409
    assert client.post(f"/api/cases/{item['id']}/review", headers=headers,
                       json={'decision': 'approved'}).status_code == 200
    assert client.post(f"/api/cases/{item['id']}/review", headers=headers,
                       json={'decision': 'rejected'}).status_code == 409


def test_import_export_input_boundaries_and_audit(client):
    headers = owner(client)
    pid = project(client, headers)
    item = generated(client, headers, pid, 1)[0]
    xml = client.get(f"/api/cases/{item['id']}/xosc", headers=headers)
    assert xml.status_code == 200 and '<OpenSCENARIO>' in xml.text
    imported = client.post('/api/cases/import', headers=headers,
                           json={'project_id': pid, 'xml': xml.text})
    assert imported.status_code == 201, imported.text
    assert client.post('/api/cases/import', headers=headers,
                       json={'project_id': pid, 'xml': '<!DOCTYPE x><x/>'}).status_code == 422
    assert client.post('/api/generate', headers=headers,
                       json={'project_id': pid, 'description': 'x', 'count': 1000}).status_code == 422
    assert client.post('/api/projects', headers=headers, content='x' * 1_000_001).status_code == 413
    events = client.get('/api/audit', headers=headers, params={'project_id': pid}).json()
    assert any(event['action'] == 'case.created' for event in events)
    assert 'password' not in json.dumps(events)


def test_no_carla_configuration_is_error_not_pass(client, monkeypatch):
    monkeypatch.delenv('SEK_SCENARIO_RUNNER', raising=False)
    headers = owner(client)
    pid = project(client, headers)
    suite, _ = approved_suite(client, headers, pid)
    response = client.post('/api/runs', headers=headers,
                           json={'suite_id': suite['id'], 'mode': 'carla', 'idempotency_key': 'carla-attempt-1'})
    assert response.status_code == 201
    assert response.json()['status'] == 'error'
    assert response.json()['results'] == []
    assert 'not configured' in response.json()['error']


def test_database_survives_app_restart(tmp_path):
    path = tmp_path / 'persistent.db'
    with TestClient(create_app(path), base_url="http://127.0.0.1") as first:
        headers = owner(first)
        pid = project(first, headers)
        generated(first, headers, pid, 1)
    with TestClient(create_app(path), base_url="http://127.0.0.1") as second:
        result = second.get('/api/cases', headers=headers, params={'project_id': pid})
        assert result.status_code == 200 and len(result.json()) == 1


def test_cross_project_suite_and_invalid_revision(client):
    headers = owner(client)
    p1, p2 = project(client, headers), project(client, headers)
    suite, items = approved_suite(client, headers, p1)
    assert client.post('/api/suites', headers=headers,
                       json={'project_id': p2, 'name': 'Wrong project', 'case_ids': [items[0]['id']]}).status_code == 404
    scenario = {**items[0]['scenario'], 'ego_speed_mps': -2}
    assert client.post(f"/api/cases/{items[0]['id']}/revisions", headers=headers,
                       json={'scenario': scenario}).status_code == 422


def test_security_headers_and_docs(client):
    response = client.get('/health')
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert client.get('/openapi.json').status_code == 200


def test_login_is_rate_limited(client):
    for _ in range(10):
        assert client.post('/api/auth/login', json={'name': 'Missing', 'password': PASSWORD}).status_code == 401
    assert client.post('/api/auth/login', json={'name': 'Missing', 'password': PASSWORD}).status_code == 429


def test_host_and_origin_protection(client):
    body = {'name': 'Maintainer', 'password': PASSWORD}
    assert client.post('/api/auth/bootstrap', headers={'host': 'attacker.example'}, json=body).status_code == 400
    assert client.post('/api/auth/bootstrap', headers={'origin': 'https://attacker.example'}, json=body).status_code == 403
    assert client.post('/api/auth/bootstrap', headers={'sec-fetch-site': 'cross-site'}, json=body).status_code == 403
    assert client.get('/api/auth/status').json()['initialized'] is False
    assert client.post('/api/auth/bootstrap', headers={'origin': 'http://127.0.0.1'}, json=body).status_code == 201


def test_disabled_provider_never_silently_falls_back(client, monkeypatch):
    monkeypatch.delenv('SEK_ENABLE_OPENAI', raising=False)
    headers = owner(client)
    pid = project(client, headers)
    result = client.post('/api/generate', headers=headers,
                         json={'project_id': pid, 'description': 'A car brakes', 'engine': 'openai'})
    assert result.status_code == 409
    assert client.get('/api/cases', headers=headers, params={'project_id': pid}).json() == []

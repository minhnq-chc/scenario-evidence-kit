"""Adapter contract tests; these are not CARLA runs."""

import json
import threading
import xml.etree.ElementTree as ET

import pytest

from scenario_evidence.carla_xml import export_for_carla
from scenario_evidence.core import generate
from scenario_evidence.runner import Runner, read_verdict, scenario_runner_config
from scenario_evidence.storage import Store, now


def test_unrecognized_success_does_not_become_pass(tmp_path):
    (tmp_path / 'result.json').write_text('{"status":"PASS"}', encoding='utf-8')
    assert read_verdict(tmp_path)['status'] == 'ERROR'


def test_explicit_verdict(tmp_path):
    (tmp_path / 'result.json').write_text(json.dumps({'success': False, 'criteria': []}), encoding='utf-8')
    assert read_verdict(tmp_path)['status'] == 'FAIL'
    (tmp_path / 'result.json').write_text(json.dumps({'success': True, 'criteria': []}), encoding='utf-8')
    assert read_verdict(tmp_path)['status'] == 'PASS'


def test_config_does_not_accept_arbitrary_executable(monkeypatch):
    monkeypatch.setenv('SEK_SCENARIO_RUNNER', 'calc.exe')
    assert scenario_runner_config() is None


def test_carla_translation_requires_origin_and_adapts_map_and_blueprints(monkeypatch):
    scenario = generate('car cuts in', map_name='Town01')[0]
    monkeypatch.delenv('SEK_CARLA_MAP_ORIGINS', raising=False)
    with pytest.raises(ValueError, match='spawn origin'):
        export_for_carla(scenario)
    monkeypatch.setenv('SEK_CARLA_MAP_ORIGINS', '{"Town01":[10,20,0,90]}')
    tree = ET.fromstring(export_for_carla(scenario))
    assert tree.find('RoadNetwork/LogicFile').get('filepath') == 'Town01'
    assert tree.find('FileHeader').get('description').startswith('CARLA:')
    assert tree.find('./Entities/ScenarioObject/Vehicle').get('name').startswith('vehicle.')
    position = tree.find('.//WorldPosition')
    assert float(position.get('x')) == 10 and float(position.get('y')) == 20
    assert tree.find('.//Property[@name="type"]').get('value') == 'ego_vehicle'


def test_cancel_before_worker_claim_never_executes(tmp_path, monkeypatch):
    script = tmp_path / 'scenario_runner.py'
    script.write_text('# Configuration fixture only; never executed', encoding='utf-8')
    monkeypatch.setenv('SEK_SCENARIO_RUNNER', str(script))
    store = Store(tmp_path / 'cancel.db')
    with store.connect() as db:
        db.execute('INSERT INTO projects VALUES(?,?,?)', ('p', 'test', now()))
        db.execute('INSERT INTO suites VALUES(?,?,?,?,?)', ('s', 'p', 'set', '[]', now()))
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)',
                   ('r', 'p', 's', 'carla', 'hash', 'key', 'queued', '[]', None, now()))
    runner = Runner(store)
    runner.cancel('r')
    called = []
    monkeypatch.setattr(runner, '_execute', lambda *args: called.append(True))
    runner._work('r', [{'scenario': generate('car', map_name='Town01')[0]}], threading.Event())
    assert not called
    with store.connect() as db:
        assert db.execute('SELECT status FROM runs WHERE id=?', ('r',)).fetchone()[0] == 'cancelled'

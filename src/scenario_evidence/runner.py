"""Optional ScenarioRunner process adapter; process success is not a simulator verdict."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .carla_xml import export_for_carla
from .core import build_report
from .storage import dump


def scenario_runner_config():
    path = os.environ.get('SEK_SCENARIO_RUNNER', '')
    if not path:
        return None
    script = Path(path)
    if not script.is_absolute() or script.name != 'scenario_runner.py' or not script.is_file():
        return None
    return script.resolve()


def read_verdict(directory):
    """Read explicit success from ScenarioRunner JSON, never infer it from exit code."""
    for file in Path(directory).glob('*.json'):
        if file.name == 'input.json' or file.stat().st_size > 5_000_000:
            continue
        try:
            value = json.loads(file.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if isinstance(value, dict) and isinstance(value.get('success'), bool):
            return {'status': 'PASS' if value['success'] else 'FAIL', 'source': 'ScenarioRunner JSON',
                    'criteria': value.get('criteria', []), 'runner_report': file.name}
    return {'status': 'ERROR', 'message': 'No recognized simulator verdict was produced.'}


class Runner:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.jobs = {}
        self.closed = False

    def cancel(self, run_id):
        with self.lock:
            event = self.jobs.get(run_id)
            if event:
                event.set()
        with self.store.connect() as db:
            db.execute("UPDATE runs SET status='cancelled',error='Cancelled by user' "
                       "WHERE id=? AND status IN ('queued','running')", (run_id,))

    def close(self):
        with self.lock:
            self.closed = True
            for event in self.jobs.values():
                event.set()

    def start(self, run_id, cases):
        with self.lock:
            if self.closed:
                raise RuntimeError('Runner is shutting down')
            if self.jobs:
                raise RuntimeError('A simulator suite is already running')
            event = threading.Event()
            self.jobs[run_id] = event
        threading.Thread(target=self._work, args=(run_id, cases, event), daemon=True).start()

    def _work(self, run_id, cases, stop):
        results = []
        error = None
        try:
            script = scenario_runner_config()
            if script is None:
                raise RuntimeError('Set SEK_SCENARIO_RUNNER to an installed scenario_runner.py first.')
            with self.store.connect() as db:
                claimed = db.execute("UPDATE runs SET status='running' WHERE id=? AND status='queued'",
                                     (run_id,)).rowcount
            if claimed != 1:
                return
            for item in cases:
                if stop.is_set():
                    break
                scenario = item['scenario']
                if scenario['map_name'].startswith('Demo'):
                    raise RuntimeError('Synthetic Demo maps are not CARLA maps. Select a real map first.')
                execution = self._execute(script, scenario, stop)
                results.append({'case_id': item['id'], 'revision': item['revision'],
                                'report': build_report(scenario, execution)})
                if execution['status'] == 'ERROR':
                    error = execution.get('message', 'Simulator infrastructure error')
                    break
        except Exception as exc:
            error = str(exc)[:1000]
        finally:
            with self.store.connect() as db:
                status = 'cancelled' if stop.is_set() else 'error' if error else 'completed'
                db.execute("UPDATE runs SET status=?,results=?,error=? WHERE id=? "
                           "AND status IN ('queued','running')",
                           (status, dump(results), error, run_id))
            with self.lock:
                self.jobs.pop(run_id, None)

    @staticmethod
    def _execute(script, scenario, stop):
        timeout = min(max(int(os.environ.get('SEK_CARLA_TIMEOUT', '120')), 10), 1800)
        with tempfile.TemporaryDirectory(prefix='sek-run-') as directory:
            root = Path(directory)
            xosc = root / 'scenario.xosc'
            adapted = export_for_carla(scenario)
            xosc.write_text(adapted, encoding='utf-8')
            python = os.environ.get('SEK_CARLA_PYTHON', sys.executable)
            command = [python, str(script), '--openscenario', str(xosc), '--json', '--sync',
                       '--reloadWorld', '--outputDir', str(root), '--host',
                       os.environ.get('SEK_CARLA_HOST', '127.0.0.1'), '--port',
                       str(int(os.environ.get('SEK_CARLA_PORT', '2000')))]
            # Log goes to a bounded-read file rather than a PIPE that could deadlock.
            with (root / 'process.log').open('wb') as log:
                process = subprocess.Popen(command, cwd=script.parent, stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                started = time.monotonic()
                try:
                    while process.poll() is None:
                        if stop.wait(0.1) or time.monotonic() - started > timeout:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait(timeout=5)
                            return {'status': 'ERROR', 'message': 'Cancelled' if stop.is_set() else 'Timed out'}
                    if process.returncode:
                        return {'status': 'ERROR', 'message': f'ScenarioRunner exited {process.returncode}'}
                    verdict = read_verdict(root)
                    verdict['runner'] = str(script.name)
                    verdict['elapsed_s'] = round(time.monotonic() - started, 3)
                    verdict['adapter_export_sha256'] = hashlib.sha256(adapted.encode()).hexdigest()
                    verdict['runner_script_sha256'] = hashlib.sha256(script.read_bytes()).hexdigest()
                    verdict['map_origin_source'] = 'SEK_CARLA_MAP_ORIGINS local configuration'
                    return verdict
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)

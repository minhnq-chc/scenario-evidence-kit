"""SQLite persistence. Each revision and suite item is an immutable snapshot."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return uuid.uuid4().hex


def dump(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=False)


class Store:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tokens (
                    digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                    case_id TEXT NOT NULL REFERENCES cases(id), revision INTEGER NOT NULL,
                    scenario TEXT NOT NULL, validation TEXT NOT NULL, status TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                    PRIMARY KEY(case_id, revision));
                CREATE TABLE IF NOT EXISTS suites (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    name TEXT NOT NULL, items TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    suite_id TEXT NOT NULL REFERENCES suites(id), mode TEXT NOT NULL,
                    request_hash TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL, results TEXT NOT NULL, error TEXT,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT,
                    user_id TEXT NOT NULL, action TEXT NOT NULL,
                    subject TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS provider_calls (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, model TEXT NOT NULL);
            """)
            db.execute("UPDATE runs SET status='error', error='Interrupted by server restart; not replayed' "
                       "WHERE status IN ('queued','running')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def log(db, user_id, action, subject, project_id=None):
        db.execute("INSERT INTO audit(project_id,user_id,action,subject,created_at) VALUES(?,?,?,?,?)",
                   (project_id, user_id, action, subject, now()))

    @staticmethod
    def case(db, case_id, revision=None):
        query = ("SELECT c.id,c.project_id,r.revision,r.scenario,r.validation,r.status,r.created_at "
                 "FROM cases c JOIN revisions r ON c.id=r.case_id WHERE c.id=?")
        args = [case_id]
        if revision is not None:
            query += " AND r.revision=?"
            args.append(revision)
        row = db.execute(query + " ORDER BY r.revision DESC LIMIT 1", args).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['scenario'] = json.loads(result['scenario'])
        result['validation'] = json.loads(result['validation'])
        result['title'] = result['scenario'].get('title', 'Untitled')
        return result

    @staticmethod
    def suite(row):
        if row is None:
            return None
        item = dict(row)
        item['items'] = json.loads(item['items'])
        return item

    @staticmethod
    def run(row):
        if row is None:
            return None
        item = dict(row)
        item['results'] = json.loads(item['results'])
        item.pop('request_hash', None)
        item.pop('idempotency_key', None)
        return item

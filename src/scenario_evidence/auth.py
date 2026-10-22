"""Local password accounts and expiring opaque tokens; no default credentials."""

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException

from .storage import identifier

ITERATIONS = 600_000
TOKEN_LIFETIME = 12 * 3600


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
    return f'{salt.hex()}:{digest.hex()}'


def password_matches(password, stored):
    salt, expected = stored.split(':')
    actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS)
    return hmac.compare_digest(actual.hex(), expected)


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(db, user):
    token = secrets.token_urlsafe(36)
    db.execute('INSERT INTO tokens VALUES(?,?,?)',
               (token_digest(token), user['id'], time.time() + TOKEN_LIFETIME))
    return {'token': token, 'user': {k: user[k] for k in ('id', 'name', 'role')}}


def create_user(db, name, password, role):
    uid = identifier()
    db.execute('INSERT INTO users VALUES(?,?,?,?)', (uid, name, password_hash(password), role))
    return {'id': uid, 'name': name, 'role': role}


class LoginLimiter:
    def __init__(self):
        self.attempts = defaultdict(deque)
        self.lock = Lock()

    def check(self, address):
        with self.lock:
            current = time.monotonic()
            # Bound memory even when the app is accidentally exposed to many clients.
            if len(self.attempts) > 2048:
                self.attempts.clear()
            queue = self.attempts[address]
            while queue and queue[0] < current - 60:
                queue.popleft()
            if len(queue) >= 10:
                raise HTTPException(429, 'Too many login attempts. Try again in one minute.')
            queue.append(current)

"""Test-only fixed-native-path generation protocol; no production entrypoint.

Completion/recovery witnesses are supplied by the isolated process harness, NOT
inferred from a missing PID. Native guardian qualification is a later integration
gate. This model tests concurrency/process-crash safety, not power-loss durability.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bootstrap'))
import bootstrap as b
w = b.w


class Refused(Exception):
    pass


class Cohort:
    def __init__(self, state, home):
        self.state, self.home = Path(state), Path(home)
        b.private(self.state, True)
        if b.a.overlaps(self.state.resolve(), self.home.resolve()):
            raise Refused('EXTERNAL_STATE_REQUIRED')

    @contextlib.contextmanager
    def mutex(self):
        path = self.state / 'coordination'
        w.safe(path)
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused('BUSY') from None
            yield
        finally:
            os.close(fd)

    def load(self, name):
        return json.loads(w.read(self.state / name)[0])

    def save(self, name, value):
        w.atomic(self.state / name, (w.encoded(value), 0o600))

    def payload(self, ident):
        if len(ident) != 64 or any(c not in '0123456789abcdef' for c in ident):
            raise Refused('INVALID_GENERATION')
        doc = self.load('generation-' + ident)
        if w.digest(w.encoded(doc)) != ident:
            raise Refused('GENERATION_DRIFT')
        if set(doc['files']) != set(b.a.mapping(doc['profile'])[1]):
            raise Refused('INVALID_SCOPE')
        return {p: (bytes.fromhex(v[0]), v[1]) for p, v in doc['files'].items()}

    def stage(self, profile, payload, base):
        # Caller supplies already-rendered/scanned bytes; no source/HOME walk.
        if set(payload) != set(b.a.mapping(profile)[1]):
            raise Refused('INVALID_SCOPE')
        doc = dict(profile=profile, base=base,
                   files={p: [v[0].hex(), v[1]] for p, v in payload.items()})
        ident = w.digest(w.encoded(doc))
        with self.mutex():
            path = self.state / ('generation-' + ident)
            if path.exists():
                self.payload(ident)
            else:
                b.save(path, doc, True)
        return ident

    def initialize(self, ident):
        with self.mutex():
            if (self.state / 'active').exists():
                raise Refused('ALREADY_INITIALIZED')
            for name, value in self.payload(ident).items():
                target = self.home / name
                target.parent.mkdir(parents=True, exist_ok=True)
                w.atomic(target, value)
            self.save('active', ident)
            self.save('readers', {})

    def coherent(self):
        if (self.state / 'journal').exists():
            raise Refused('RECOVERY_REQUIRED')
        ident = self.load('active')
        for name, value in self.payload(ident).items():
            if w.read(self.home / name) != value:
                raise Refused('DRIFT')
        return ident

    def admit(self, agent, identity):
        with self.mutex():
            ident = self.coherent()
            if agent not in ('claude', 'codex'):
                raise Refused('INVALID_AGENT')
            profile = self.load('generation-' + ident)['profile']
            if profile != 'claude-codex' and agent != profile:
                raise Refused('INACTIVE_AGENT')
            token = uuid.uuid4().hex
            readers = self.load('readers')
            readers[token] = dict(generation=ident, agent=agent, identity=identity,
                                  state='ACTIVE')
            self.save('readers', readers)
            return token, ident

    def complete(self, token, expected_identity, *, completion_observed):
        # Harness has reaped its child and its registered process family. A
        # caller merely claiming kill(pid, 0) failed is never this witness.
        with self.mutex():
            readers = self.load('readers')
            if readers[token]['identity'] != expected_identity:
                raise Refused('IDENTITY_MISMATCH')
            if not completion_observed:
                raise Refused('COMPLETION_NOT_PROVEN')
            del readers[token]
            self.save('readers', readers)

    def uncertain(self, token):
        with self.mutex():
            readers = self.load('readers')
            readers[token]['state'] = 'UNCERTAIN'
            self.save('readers', readers)

    def recover_lease(self, token, expected_identity, *, old_boot, current_boot,
                      family_quiescence_proven=False):
        with self.mutex():
            readers = self.load('readers')
            entry = readers[token]
            if entry['identity'] != expected_identity or expected_identity['boot'] != old_boot:
                raise Refused('IDENTITY_MISMATCH')
            if old_boot == current_boot and not family_quiescence_proven:
                raise Refused('QUIESCENCE_NOT_PROVEN')
            # Boot values are injected by the model harness. Production must
            # obtain kernel boot identity, never accept a user-entered string.
            self.coherent()
            del readers[token]
            self.save('readers', readers)

    def activate(self, ident, after_write=lambda index: None):
        with self.mutex():
            active = self.coherent()
            if self.load('readers'):
                return 'DEFERRED_READERS'
            if active == ident:
                return 'NO_CHANGES'
            doc = self.load('generation-' + ident)
            if doc['base'] != active:
                raise Refused('STALE_CANDIDATE')
            old, new = self.payload(active), self.payload(ident)
            if set(old) != set(new):
                raise Refused('PROFILE_SWITCH_REQUIRES_SEPARATE_PLAN')
            self.save('journal', dict(old=active, new=ident))
            for index, (name, value) in enumerate(new.items()):
                w.atomic(self.home / name, value)
                after_write(index)
            if any(w.read(self.home / n) != v for n, v in new.items()):
                raise Refused('ACTIVATION_DRIFT')
            self.save('active', ident)
            (self.state / 'journal').unlink()
            return 'ACTIVATED'

    def recover_activation(self):
        with self.mutex():
            if self.load('readers'):
                raise Refused('READERS_PRESENT')
            doc = self.load('journal')
            old, new = self.payload(doc['old']), self.payload(doc['new'])
            # Validate the entire set before restoring anything. Keep external
            # edits and the journal intact on any mismatch.
            if set(old) != set(new) or self.load('active') not in (doc['old'], doc['new']):
                raise Refused('INVALID_RECOVERY_STATE')
            for name in old:
                if w.read(self.home / name) not in (old[name], new[name]):
                    raise Refused('RECOVERY_DRIFT')
            for name, value in old.items():
                w.atomic(self.home / name, value)
            self.save('active', doc['old'])
            (self.state / 'journal').unlink()
            return 'RESTORED_OLD'

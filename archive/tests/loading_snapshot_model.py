"""Experimental filesystem model, NOT a native-agent deployment implementation.

The caller supplies already-rendered/scanned allowlisted bytes under the writer
lock. A consumer must pin once and use that physical root for EVERY managed read.
Native Claude/Codex routing to that root is deliberately not assumed here.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bootstrap'))
import bootstrap as b


def manifest(profile, payload):
    if set(payload) != set(b.a.mapping(profile)[1]):
        raise ValueError('EXACT_MANAGED_MAPPING_REQUIRED')
    return dict(profile=profile, files={p: [hashlib.sha256(data).hexdigest(), mode]
                                       for p, (data, mode) in sorted(payload.items())})


def publish(store, profile, payload, before_publish=lambda: None):
    """One writer, complete generation first, atomic regular CURRENT file last."""
    b.private(store, True)
    doc = manifest(profile, payload)
    raw = b.w.encoded(doc)
    ident = hashlib.sha256(raw).hexdigest()
    generation = store / ident
    if not generation.exists():
        pending = store / ('pending-' + uuid.uuid4().hex)
        pending.mkdir(mode=0o700)
        for relative, (data, mode) in payload.items():
            path = pending / relative
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            b.w.atomic(path, (data, 0o500 if mode & 0o111 else 0o400))
        b.w.atomic(pending / 'manifest.json', (raw, 0o400))
        # No overwrite/GC API. Read-only modes are accidental-write protection,
        # not a security boundary against the owner changing permissions.
        for path in sorted(pending.rglob('*'), reverse=True):
            if path.is_dir():
                path.chmod(0o500)
        pending.chmod(0o500)
        os.rename(pending, generation)
    verify(generation, ident)
    before_publish()  # Tests inject a crash before the visible commit point.
    b.w.atomic(store / 'CURRENT', ((ident + '\n').encode(), 0o600))
    return generation


def verify(root, ident):
    b.w.safe(root)
    raw = b.w.read(root / 'manifest.json')[0]
    if hashlib.sha256(raw).hexdigest() != ident:
        raise ValueError('INVALID_GENERATION_MANIFEST')
    doc = json.loads(raw)
    names = b.a.mapping(doc['profile'])[1]
    if set(doc['files']) != set(names):
        raise ValueError('INVALID_GENERATION_SCOPE')
    for name in names:
        data, mode = b.w.read(root / name)
        digest, original_mode = doc['files'][name]
        if hashlib.sha256(data).hexdigest() != digest or mode != (0o500 if original_mode & 0o111 else 0o400):
            raise ValueError('GENERATION_DRIFT')


def pin(store):
    b.private(store, True)
    ident = b.w.read(store / 'CURRENT')[0].decode().strip()
    if not re.fullmatch('[0-9a-f]{64}', ident):
        raise ValueError('INVALID_GENERATION_ID')
    root = store / ident
    verify(root, ident)
    return root

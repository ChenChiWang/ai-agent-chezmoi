#!/usr/bin/env python3
"""Reviewed bootstrap controller. No credentials, agent models, or source hooks.

Plans/receipts are private and external to source and destination. The trusted
renderer/scanner is shipped with this public release, never imported from a clone.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]  # repo root
SCRIPTS = ROOT / 'examples/chezmoi/.chezmoitemplates/ai/shared/scripts'
spec = importlib.util.spec_from_file_location('engine', SCRIPTS / 'sync-write.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
a = w.api
PROFILES = a.PROFILES
need = w.need


def private(path, directory=False):
    w.safe(path)
    st = path.stat()
    need(st.st_uid == os.getuid() and not st.st_mode & 0o077, 'PRIVATE_STATE_REQUIRED')
    need(stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode), 'INVALID_STATE')
    if not directory:
        need(st.st_nlink == 1, 'INVALID_STATE')


def external(path, src, dst):
    need(path.is_absolute(), 'ABSOLUTE_PATH_REQUIRED')
    w.safe(path)
    for root in (src, dst):
        need(not a.overlaps(path.resolve(), root), 'EXTERNAL_STATE_REQUIRED')


def load(path):
    private(path)
    return a.read_json(path)


def save(path, value, new=False):
    if new:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(w.encoded(value))
            f.flush()
            os.fsync(f.fileno())
        w.fsync_dir(path.parent)
    else:
        w.atomic(path, (w.encoded(value), 0o600))


def identities():
    return {str(p.relative_to(ROOT)): w.digest(p.read_bytes()) for p in
            [*Path(__file__).parent.glob('*.py'), *Path(__file__).parent.glob('*.c'), *Path(__file__).parent.glob('*.sh'), *[SCRIPTS / n for n in a.SCRIPTS]]}


def values(root, names):
    return {n: w.read(root / n, missing=True) for n in names}


def refs(items):
    return {n: None if v is None else [w.digest(v[0]), v[1]] for n, v in items.items()}


def args_for(src, dst, profile, scanner=None, remote=None):
    return SimpleNamespace(source=str(src), destination=str(dst), profile=profile,
                           repository_profile='claude-codex', offline=not remote,
                           operation='in', branch='main', scanner=scanner, remote=remote,
                           baseline=None, baseline_id=None, message='', author_name='', author_email='')


@contextlib.contextmanager
def engine(src, dst, profile, scanner=None, remote=None):
    with tempfile.TemporaryDirectory(prefix='ai-bootstrap-engine-', dir='/tmp') as d:
        yield w.Engine(args_for(src, dst, profile, scanner, remote), Path(d))


def check_tree(e):
    e.clean_index()
    snap = w.snapshot(e.src, e.files)
    need(w.normalized(snap) == e.scoped(e.head), 'BLOCKED_LOCAL_CHANGES', 66)
    allowed = set(e.files) | {'README.md'}
    need(set(p.decode() for p in e.tree(e.head)) <= allowed, 'BLOCKED_SCOPE')
    # Enumerate only source names; do not traverse destination or symlinks.
    found = set()
    for parent, dirs, files in os.walk(e.src, followlinks=False):
        dirs[:] = [n for n in dirs if not (Path(parent) == e.src and n == '.git')]
        for n in dirs:
            w.safe(Path(parent) / n)
        for n in files:
            found.add(str((Path(parent) / n).relative_to(e.src)))
    need(found <= allowed, 'BLOCKED_UNKNOWN_SOURCE')
    if 'README.md' in found:
        item = e.tree(e.head).get(b'README.md')
        need(item and w.read(e.src / 'README.md')[0] == e.git('cat-file', 'blob', item[2]), 'BLOCKED_LOCAL_CHANGES', 66)
    for name in e.files:
        if name.endswith('.tmpl'):
            need(snap[name][0] == a.wrapper(name), 'UNSUPPORTED_TEMPLATE')
    for script in a.SCRIPTS:
        need(snap[a.PREFIX + 'shared/scripts/' + script][0] == (SCRIPTS / script).read_bytes(),
             'SOURCE_ENGINE_RELEASE_MISMATCH')
    e.scan(snap)
    if e.profile != 'codex':
        settings = json.loads(snap['dot_claude/settings.json'][0])
        need(type(settings) is dict and set(settings) <= {'model', 'tui', 'statusLine'},
             'CLAUDE_SETTINGS_INVENTORY_REQUIRED')
        need(not settings.get('statusLine'), 'STATUSLINE_QUALIFICATION_REQUIRED')
    rendered = e.render(snap)
    e.scan(rendered, 'render')
    return snap, rendered


def state_paths(options):
    src, dst = Path(options.source).resolve(), Path(options.destination).resolve()
    state = Path(options.state)
    external(state, src, dst)
    private(state, True)
    need(not (state / 'journal.json').exists(), 'RECOVERY_REQUIRED', 72)
    a.validate_layout(src, dst, options.profile, source_profile='claude-codex')
    return src, dst, state


def receipt(state):
    path = state / 'receipt.json'
    return load(path) if path.exists() else None


def verify_receipt(doc, src, dst, state=None):
    enrolled = w.cohort_receipt(src, dst)
    need(enrolled is not None and enrolled[1] == doc, 'ENROLLMENT_INCOMPLETE', 72)
    need(state is None or enrolled[0] == state / 'receipt.json', 'STATE_ROOT_MISMATCH')
    need(doc['source'] == str(src) and doc['destination'] == str(dst), 'STATE_ROOT_MISMATCH')
    names = set(a.mapping(doc['profile'])[1])
    need(set(doc['targets']) == names, 'INVALID_RECEIPT')
    a.validate_layout(src, dst, doc['profile'], source_profile='claude-codex')
    need(refs(values(dst, names)) == doc['targets'], 'BLOCKED_DRIFT', 2)
    for name in ('ai-agent-sync-transaction', 'ai-agent-migration-transaction'):
        need(not (src / '.git' / name).exists(), 'RECOVERY_REQUIRED', 72)


def planned(options):
    src, dst, state = state_paths(options)
    previous = receipt(state)
    with engine(src, dst, options.profile, options.scanner) as e:
        snap, rendered = check_tree(e)
        if previous:
            verify_receipt(previous, src, dst, state)
            need(previous['head'] == e.head, 'SOURCE_REFRESH_REQUIRES_SYNC')
        names = set(rendered) | (set(previous['targets']) if previous else set())
        before = values(dst, names)
        e.scan({n: v for n, v in before.items() if v is not None}, 'target') if any(before.values()) else None
        after = dict(rendered)
        for name in names - set(rendered):
            # Keep the user's inactive Claude preferences; retire only discovery
            # files owned by the previous receipt, never a directory or auth file.
            after[name] = before[name] if name == '.claude/settings.json' else None
        for name in rendered:
            if previous and name in previous['targets']:
                continue
            need(before[name] is None or before[name] == rendered[name], 'TARGET_COLLISION', 2)
            need(before[name] is None or options.adopt, 'EXPLICIT_ADOPTION_REQUIRED')
        binaries = {}
        for product in (('claude', 'codex') if options.profile == 'claude-codex' else (options.profile,)):
            path = getattr(options, product, None)
            if path:
                p = Path(path)
                need(p.is_absolute() and p.is_file() and os.access(p, os.X_OK), 'INVALID_CLI_PATH')
                # Explicit user-selected executable may be a vendor symlink.
                p = p.resolve()
                need(p != Path(__file__).resolve(), 'RECURSIVE_LAUNCHER')
                binaries[product] = dict(path=str(p), sha256=w.digest(p.read_bytes()))
        if previous:
            for product, info in previous.get('binaries', {}).items():
                # Keep registration for disabled launchers to pass through to
                # their vendor CLI without syncing or inspecting it otherwise.
                binaries.setdefault(product, info)
        directories = set()
        for name, value in after.items():
            if value is not None:
                parent = (dst / name).parent
                while parent != dst and not parent.exists():
                    directories.add(str(parent.relative_to(dst)))
                    parent = parent.parent
        policy = None
        if options.remote:
            remote = e.remote_url(options.remote)
            policy = dict(remote=remote, branch='main', enabled=True)
        elif previous:
            policy = previous.get('launch_policy')
        return dict(schema=1, created=int(time.time()), source=str(src), destination=str(dst),
                    profile=options.profile, head=e.head, source_hashes=w.summary(snap),
                    index=w.digest(w.read(src / '.git/index')[0]),
                    git_config=w.digest(w.read(src / '.git/config')[0]),
                    scanner=dict(path=str(e.scanner), sha256=w.digest(e.scanner.read_bytes())), tools=identities(),
                    before=refs(before), after=refs(after), directories=sorted(directories), previous=previous,
                    binaries=binaries, launch_policy=policy), before, after


def mkdirs(path, dst, created):
    absent = []
    p = path
    while p != dst and not p.exists():
        absent.append(p)
        p = p.parent
    w.safe(path)
    for p in reversed(absent):
        p.mkdir(mode=0o755)
        created.append(str(p.relative_to(dst)))


def put(dst, name, value, created):
    p = dst / name
    w.safe(p)
    if value is None:
        if p.exists():
            p.unlink()
    else:
        mkdirs(p.parent, dst, created)
        w.atomic(p, value)


def apply(options):
    src, dst, state = state_paths(options)
    plan_path = Path(options.plan)
    external(plan_path, src, dst)
    document = load(plan_path)
    need(w.digest(w.encoded(document)) == options.approve, 'INVALID_APPROVAL', 68)
    need(0 <= time.time() - document['created'] < 3600, 'EXPIRED_PLAN', 68)
    with w.lock(src, allow_pending=True):
        current, before, after = planned(options)
        current['created'] = document['created']
        need(current == document, 'BLOCKED_STALE_PLAN', 68)
        if all(before[n] == after[n] for n in before) and document['previous']:
            old = document['previous']
            if (old['profile'], old.get('binaries'), old.get('launch_policy')) == (
                    options.profile, document['binaries'], document['launch_policy']):
                w.sync_cohort(src)
                print('NO_CHANGES')
                return
        run = state / ('backup-' + options.approve)
        need(not run.exists(), 'PLAN_ALREADY_USED_REPLAN', 68)
        run.mkdir(mode=0o700)
        for label, items in [('before', before), ('after', after)]:
            (run / label).mkdir(mode=0o700)
            for name, value in items.items():
                if value is not None:
                    blob = run / label / w.digest(value[0])
                    if not blob.exists():
                        w.atomic(blob, (value[0], 0o600))
        save(run / 'plan.json', document, True)
        record = dict(plan=options.approve, backup=run.name, created_directories=[], phase='writing')
        save(state / 'journal.json', record, True)
        created = record['created_directories']
        try:
            with w.enroll_cohort(src, dst, state):
                for name in sorted(after):
                    need(w.read(dst / name, missing=True) == before[name], 'BLOCKED_STALE_PLAN', 68)
                    if before[name] != after[name]:
                        put(dst, name, after[name], created)
                        save(state / 'journal.json', record)
                active = a.mapping(options.profile)[1]
                result = dict(schema=1, source=str(src), destination=str(dst), profile=options.profile,
                              head=document['head'], targets=refs(values(dst, active)), tools=document['tools'],
                              binaries=document['binaries'], launch_policy=document['launch_policy'])
                need(result['targets'] == {n: document['after'][n] for n in active}, 'POST_DEPLOY_DRIFT')
                record['new_receipt'] = result
                save(state / 'journal.json', record)
                save(state / 'receipt.json', result)
                record['phase'] = 'committed'
                save(state / 'journal.json', record)
                (state / 'journal.json').unlink()
                w.fsync_dir(state)
                verify_receipt(result, src, dst, state)
        except BaseException:
            # Leave hash-bound journal and payloads for explicit guarded recovery.
            raise w.Block(72, 'RECOVERY_REQUIRED') from None
        print('CONFIG_READY; agent authentication/runtime not tested')


def recover(options):
    state = Path(options.state)
    private(state, True)
    record = load(state / 'journal.json')
    need(record['backup'] == 'backup-' + record['plan'], 'INVALID_JOURNAL')
    run = state / record['backup']
    doc = load(run / 'plan.json')
    need(w.digest(w.encoded(doc)) == record['plan'] == options.approve, 'INVALID_APPROVAL')
    src, dst = Path(doc['source']), Path(doc['destination'])
    external(state, src, dst)
    allowed = set(a.mapping('claude-codex')[1])
    need(set(doc['before']) == set(doc['after']) and set(doc['before']) <= allowed, 'INVALID_JOURNAL')
    with w.lock(src, allow_pending=True):
        a.validate_layout(src, dst, doc['profile'], source_profile='claude-codex')
        marker = src / '.git/ai-agent-cohort.json'
        owner = w.read(src / '.git/ai-agent-sync.lock/owner.json')
        if not marker.exists() and owner == (w.encoded(dict(protocol='cohort-v1')), 0o600):
            # Interrupted handoff: the common kernel lock was acquired above.
            # Bind only the exact roots from this approved rollback journal.
            w.atomic(marker, (w.encoded(dict(schema=1, destination=str(dst), state=str(state))), 0o600))
            w.cohort_metadata(src)
        with engine(src, dst, doc['profile']) as e:
            need(e.head == doc['head'] and w.summary(w.snapshot(src, e.files)) == doc['source_hashes'], 'RECOVERY_SOURCE_CHANGED')
            need(w.digest(w.read(src / '.git/index')[0]) == doc['index'], 'RECOVERY_INDEX_CHANGED')
        restored = {}
        for name, ref in doc['before'].items():
            observed = refs(values(dst, [name]))[name]
            need(observed in (ref, doc['after'][name]), 'RECOVERY_CONFLICT', 72)
            if ref is None:
                restored[name] = None
            else:
                b = w.read(run / 'before' / ref[0])[0]
                need(w.digest(b) == ref[0], 'BACKUP_INTEGRITY')
                restored[name] = (b, ref[1])
        current_receipt = receipt(state)
        need(current_receipt == doc['previous'] or (record.get('new_receipt') is not None and current_receipt == record['new_receipt']),
             'RECOVERY_RECEIPT_CONFLICT', 72)
        for name, value in restored.items():
            put(dst, name, value, [])
        need(set(record['created_directories']) <= set(doc['directories']), 'INVALID_JOURNAL')
        for rel in reversed(record['created_directories']):
            need(rel and not Path(rel).is_absolute() and '..' not in Path(rel).parts, 'INVALID_JOURNAL')
            p = dst / rel
            w.safe(p)
            if p.exists() and not any(p.iterdir()):
                p.rmdir()
        if w.cohort_metadata(src) is not None:
            w.sync_cohort(src)
        if doc['previous']:
            save(state / 'receipt.json', doc['previous'])
        elif (state / 'receipt.json').exists():
            (state / 'receipt.json').unlink()
        (state / 'journal.json').unlink()
        w.fsync_dir(state)
    print('RECOVERED; backup retained')


def common(parser):
    for name in ('source', 'destination', 'state'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--scanner')
    parser.add_argument('--adopt', action='store_true')
    parser.add_argument('--remote')
    for product in ('claude', 'codex'):
        parser.add_argument('--' + product)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('plan', 'apply'):
        p = sub.add_parser(command)
        common(p)
        p.add_argument('--plan', required=True)
        if command == 'apply':
            p.add_argument('--approve', required=True)
    p = sub.add_parser('recover')
    p.add_argument('--state', required=True)
    p.add_argument('--approve', required=True)
    options = parser.parse_args()
    os.umask(0o077)
    if options.command == 'plan':
        src, dst, state = state_paths(options)
        with w.lock(src, allow_readers=True, allow_pending=True):
            doc, _, _ = planned(options)
            path = Path(options.plan)
            external(path, src, dst)
            save(path, doc, True)
        print('PLAN_ID: ' + w.digest(w.encoded(doc)))
    elif options.command == 'apply':
        apply(options)
    else:
        recover(options)


if __name__ == '__main__':
    try:
        main()
    except w.Block as error:
        print(error.label, file=sys.stderr)
        sys.exit(error.code)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('BOOTSTRAP_ERROR: no raw configuration or tool output exposed', file=sys.stderr)
        sys.exit(70)

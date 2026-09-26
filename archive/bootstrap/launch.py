#!/usr/bin/env python3
"""One neutral launch-sync implementation; launchers only select agent/state.

Readers share unchanged native paths for the whole session. Preparation can
proceed, but activation waits for proven quiescence. No agent callbacks.
"""
import argparse
import contextlib
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
import bootstrap as b
import guardian
w = b.w

CONTENT = {b.a.PREFIX + 'shared/instructions.md'} | {
    b.a.PREFIX + 'shared/skills/' + name + '/SKILL.md' for name in b.a.SKILLS
} | {b.a.PREFIX + 'adapters/' + name + '.md' for name in ('claude', 'codex')}


def attempt(state, offline=False, scanner=None):
    w.need(not (state / 'journal.json').exists(), 'RECOVERY_REQUIRED', 72)
    doc = b.receipt(state)
    w.need(doc is not None, 'CONFIG_NOT_READY')
    src, dst = Path(doc['source']), Path(doc['destination'])
    b.external(state, src, dst)
    w.need(doc['tools'] == b.identities(), 'BOOTSTRAP_RELEASE_CHANGED')
    b.verify_receipt(doc, src, dst, state)
    policy = doc.get('launch_policy')
    if offline or not policy:
        return doc, 'SKIPPED_OFFLINE' if offline else 'SYNC_NOT_ENROLLED'
    with b.engine(src, dst, doc['profile'], scanner, policy['remote']) as e:
        e.clean_index()
        current = w.snapshot(src, e.files)
        w.need(w.normalized(current) == e.scoped(e.head), 'BLOCKED_LOCAL_CHANGES', 66)
        w.need(e.head == doc['head'], 'REVIEW_REQUIRED', 66)
        # Bound preparation only. The engine's timeout is lowered for network;
        # wall-clock budget is enforced before any mutation, never via SIGKILL.
        e.a.prepare_deadline = time.monotonic() + 30
        e.a.network_timeout = 10
        e.a.scan_timeout = 20
        result = e.build()
        changed = {p for p in e.files if result['candidate'][p] != result['baseline'][p]}
        w.need(changed <= CONTENT, 'REVIEW_REQUIRED', 66)
        # Intermediate commits must satisfy the policy too (not only final diff).
        for oid in result['commits']:
            parent = e.git('rev-parse', oid + '^').decode().strip()
            old, new = e.tree(parent), e.tree(oid)
            paths = {p.decode() for p in old.keys() | new.keys() if old.get(p) != new.get(p)}
            w.need(paths <= CONTENT, 'REVIEW_REQUIRED', 66)
        w.need(time.monotonic() < e.a.prepare_deadline, 'PREPARATION_TIMEOUT', 71)
        with coordination(src):
            w.need(b.receipt(state) == doc and e.state() == e.before, 'BLOCKED_STALE_PLAN', 68)
            b.verify_receipt(doc, src, dst, state)
            # Persist exact reviewed-policy plan even for automatic enrollment.
            plan = dict(created=int(time.time()), plan=result, policy=policy)
            if e.head == e.remote_head and not changed:
                pending = state / 'pending.json'
                w.safe(pending)
                if pending.exists():
                    b.load(pending); pending.unlink()
                return doc, 'NO_CHANGES'
            plan_id = w.digest(w.encoded(plan))
            plan_path = state / ('launch-plan-' + plan_id + '.json')
            if not plan_path.exists():
                b.save(plan_path, plan, True)
            if w.active_readers(src):
                prepared = e.prepare_bundle(state / ('prepared-' + plan_id), plan_id)
                b.save(state / 'pending.json', dict(plan=plan_path.name, plan_id=plan_id,
                                                  prepared=prepared, applied=False))
                return doc, 'DEFERRED_READERS'
            # The common source lock is held continuously across plan/execute.
            # Source/index/targets and receipt share the engine transaction journal.
            del e.a.prepare_deadline  # Never impose a preparation deadline on mutation.
            with contextlib.redirect_stdout(io.StringIO()):
                e.execute()
            updated = dict(doc, head=e.remote_head, targets=w.summary(e.rendered))
            if updated != doc:
                b.save(state / 'receipt.json', updated)
            b.verify_receipt(updated, src, dst, state)
            pending = state / 'pending.json'
            w.safe(pending)
            if pending.exists():
                b.load(pending)
                pending.unlink()  # Retain immutable plans/blobs; only retire pointer.
            return updated, 'NO_CHANGES' if not changed else 'SYNCED'


def administrative(argv):
    # Only unambiguous stand-alone invocations are exempt. A prompt containing
    # "--help" or a global flag before a subcommand is not misclassified.
    return argv in (['--help'], ['-h'], ['--version'], ['-V']) or (
        bool(argv) and argv[0] in ('login', 'logout', 'auth', 'completion', 'completions'))


def cli_info(doc, product):
    w.need(product in doc['binaries'], 'AGENT_TOOL_PENDING', 69)
    info = doc['binaries'][product]
    p = Path(info['path'])
    w.need(p.is_absolute() and p.is_file() and os.access(p, os.X_OK), 'AGENT_TOOL_PENDING', 69)
    w.need(w.digest(p.read_bytes()) == info['sha256'], 'AGENT_BINARY_CHANGED', 68)
    w.need(p.resolve() != Path(__file__).resolve(), 'RECURSIVE_LAUNCHER')
    return p


INHERITED_SIGNALS = None


def exec_cli(binary, argv):
    if INHERITED_SIGNALS is not None:
        ignored, blocked = INHERITED_SIGNALS
        for number in signal.valid_signals():
            if number in (signal.SIGKILL, signal.SIGSTOP): continue
            signal.signal(number, signal.SIG_IGN if ignored & (1 << number) else signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_SETMASK, {n for n in signal.valid_signals() if blocked & (1 << n)})
    return os.execv(str(binary), [str(binary), *argv])


@contextlib.contextmanager
def coordination(src):
    deadline = time.monotonic() + 2
    while True:
        manager = w.lock(src, allow_readers=True)
        try:
            manager.__enter__()
            break
        except w.Block as error:
            if error.code != 73 or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)
    try:
        yield
    finally:
        manager.__exit__(None, None, None)


def launch(state, product, argv, offline=False, scanner=None):
    b.private(state, True)
    doc = b.receipt(state)
    w.need(doc is not None, 'CONFIG_NOT_READY')
    binary = cli_info(doc, product)
    active = ('claude', 'codex') if doc['profile'] == 'claude-codex' else (doc['profile'],)
    w.need(not (state / 'journal.json').exists(), 'RECOVERY_REQUIRED', 72)
    src, dst = Path(doc['source']), Path(doc['destination'])
    leases = src / '.git/ai-agent-launch-readers'
    token = uuid.uuid4().hex
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            if product not in active or administrative(argv):
                outcome = 'NO_CHANGES'  # Skip refresh, never the read-protection gate.
            else:
                doc, outcome = attempt(state, offline, scanner)
    except w.Block as error:
        # Admission below independently re-reads and validates the current
        # complete receipt. Preparation errors cannot bless partial deployment.
        outcome = error.label
    with coordination(src):
        w.safe(leases)
        w.need(not (state / 'journal.json').exists(), 'RECOVERY_REQUIRED', 72)
        doc = b.receipt(state)
        b.verify_receipt(doc, src, dst, state)
        binary = cli_info(doc, product)
        leases.mkdir(mode=0o700, exist_ok=True)
        record = dict(schema=1, agent=product, owner=guardian.identity(os.getpid()), state='RESERVED',
                      state_root=str(state), generation=w.digest(w.encoded(doc)))
        b.save(leases / token, record, True)
        record['observer'] = guardian.arm(src, token)
        record['state'] = 'ARMED'
        b.save(leases / token, record)
    if outcome not in ('NO_CHANGES', 'SYNCED'):
        print('launch-sync: ' + outcome + '; existing configuration retained', file=sys.stderr)
    return exec_cli(binary, argv)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inherited-signals')
    parser.add_argument('--state', required=True)
    parser.add_argument('--agent', required=True, choices=('claude', 'codex'))
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('argv', nargs=argparse.REMAINDER)
    options = parser.parse_args()
    global INHERITED_SIGNALS
    if options.inherited_signals:
        ignored, blocked = options.inherited_signals.split(':')
        INHERITED_SIGNALS = (int(ignored, 16), int(blocked, 16))
    argv = options.argv[1:] if options.argv[:1] == ['--'] else options.argv
    # Do not alter CLI umask, environment, cwd or stdin.
    return launch(Path(options.state), options.agent, argv, options.offline)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except w.Block as error:
        print('launch-sync: ' + error.label, file=sys.stderr)
        sys.exit(error.code)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('launch-sync: IO_ERROR; no raw tool output exposed', file=sys.stderr)
        sys.exit(70)

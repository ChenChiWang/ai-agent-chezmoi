#!/usr/bin/env python3
"""macOS kernel-observed reader lifetime. No hooks, PID polling, or credentials.

Forked families are deliberately never guessed quiescent: their leases survive
until a reviewed new-boot recovery. A continuously observed leaf can complete.
"""
import argparse
import ctypes
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import bootstrap as b
w = b.w
EXIT_STATUS = 0x04000000


class BSDInfo(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in (
        'flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid', 'rgid',
        'svuid', 'svgid', 'reserved')] + [
        ('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)] + [
        (n, ctypes.c_uint32) for n in ('nfiles', 'pgid', 'jobc', 'tdev', 'tpgid', 'nice')
    ] + [('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]


def boot_id():
    w.need(sys.platform == 'darwin', 'GUARDIAN_PLATFORM_UNSUPPORTED', 69)
    libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    out = ctypes.create_string_buffer(128)
    size = ctypes.c_size_t(len(out))
    rc = libc.sysctlbyname(b'kern.bootsessionuuid', out, ctypes.byref(size), None, 0)
    w.need(rc == 0, 'BOOT_ID_UNAVAILABLE', 69)
    value = out.value.decode('ascii')
    w.need(re.fullmatch(r'[0-9A-Fa-f-]{36}', value), 'BOOT_ID_UNAVAILABLE', 69)
    return value.lower()


def identity(pid):
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    record = BSDInfo()
    count = lib.proc_pidinfo(int(pid), 3, 0, ctypes.byref(record), ctypes.sizeof(record))
    w.need(count == ctypes.sizeof(record) and record.pid == pid and record.uid == os.getuid(),
           'PROCESS_IDENTITY_UNAVAILABLE', 69)
    return dict(boot=boot_id(), pid=pid, start=[record.start_sec, record.start_usec])


def lease_path(source, token):
    w.need(re.fullmatch('[0-9a-f]{32}', token), 'INVALID_READER_TOKEN')
    path = source / '.git/ai-agent-launch-readers' / token
    w.safe(path)
    return path


def update(source, token, change):
    # Kernel event observation is independent from coordination contention.
    # If metadata cannot be updated, the existing lease still blocks writers.
    deadline = time.monotonic() + 30
    while True:
        try:
            with w.lock(source, allow_readers=True):
                path = lease_path(source, token)
                record = b.load(path)
                change(path, record)
                if not any(path.parent.iterdir()):
                    path.parent.rmdir()
            return
        except w.Block as error:
            if error.code != 73 or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def observe(source, token, ready_fd):
    path = lease_path(source, token)
    record = b.load(path)
    expected = record['owner']
    w.need(identity(expected['pid']) == expected, 'READER_IDENTITY_CHANGED')
    queue = select.kqueue()
    event = select.kevent(expected['pid'], filter=select.KQ_FILTER_PROC,
                          flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                          fflags=select.KQ_NOTE_FORK | select.KQ_NOTE_EXIT | EXIT_STATUS)
    queue.control([event], 0, 0)
    w.need(identity(expected['pid']) == expected, 'READER_IDENTITY_CHANGED')
    # Ready handshake is private IPC, never the vendor standard streams.
    os.write(ready_fd, w.encoded(identity(os.getpid())) + b'\n')
    os.close(ready_fd)
    forked = False
    try:
        while True:
            events = queue.control(None, 1, None)
            for event in events:
                w.need(not event.flags & select.KQ_EV_ERROR, 'PROCESS_WATCH_ERROR')
                forked |= bool(event.fflags & select.KQ_NOTE_FORK)
                if event.fflags & select.KQ_NOTE_EXIT:
                    def finish(path, current):
                        w.need(current['owner'] == expected, 'READER_IDENTITY_CHANGED')
                        if not forked and event.fflags & EXIT_STATUS and os.WIFEXITED(event.data):
                            # The continuously watched process never forked
                            # after admission and is now proven terminated.
                            path.unlink()
                            return
                        current.update(state='UNCERTAIN_FAMILY' if forked else 'EXITED_LEAF',
                                       exit_status=int(event.data), fork_seen=forked,
                                       evidence=dict(observer_scope='root-process',
                                           root_exit_observed=True,
                                           fork_event_observed=forked,
                                           exit_status_available=bool(event.fflags & EXIT_STATUS),
                                           missing=['descendant_identities', 'continuous_descendant_lineage',
                                                    'descendant_exit_observations'] if forked else []))
                        b.save(path, current)
                    update(source, token, finish)
                    return
    finally:
        queue.close()


def arm(source, token):
    """Called with admission lock held; returns observer identity before exec."""
    readfd, writefd = os.pipe()
    try:
        helper = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                   '--source', str(source), '--token', token,
                                   '--ready-fd', str(writefd), '--detach'],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, pass_fds=(writefd,),
                                  start_new_session=True, cwd=str(source.parent),
                                  env={'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1'})
        os.close(writefd); writefd = None
        helper.wait(timeout=5)  # Reap intermediate child before native exec.
        w.need(helper.returncode == 0, 'GUARDIAN_START_FAILED', 69)
        w.need(select.select([readfd], [], [], 5)[0], 'GUARDIAN_START_TIMEOUT', 69)
        data = os.read(readfd, 1024)
        observer = b.json.loads(data)
        w.need(identity(observer['pid']) == observer, 'GUARDIAN_IDENTITY_CHANGED', 69)
        return observer
    finally:
        os.close(readfd)
        if writefd is not None:
            os.close(writefd)


def recover(state, token, approval=None):
    """Review exact receipt/lease-bound plan; never accept supplied boot proof."""
    doc = b.receipt(state)
    w.need(doc is not None, 'CONFIG_NOT_READY')
    source, destination = Path(doc['source']), Path(doc['destination'])
    b.external(state, source, destination)
    with w.lock(source, allow_readers=True):
        b.verify_receipt(doc, source, destination)
        path = lease_path(source, token)
        record = b.load(path)
        boot = boot_id()
        allowed = record['owner']['boot'] != boot or (
            record.get('state') == 'EXITED_LEAF' and record.get('fork_seen') is False)
        w.need(allowed, 'READER_FAMILY_NOT_PROVEN_QUIESCENT', 73)
        plan = dict(schema=1, lease=record, token=token, current_boot=boot,
                    receipt=w.digest(w.encoded(doc)))
        digest = w.digest(w.encoded(plan))
        if approval is None:
            return digest
        w.need(approval == digest, 'STALE_RECOVERY_APPROVAL', 68)
        path.unlink()
        if not any(path.parent.iterdir()):
            path.parent.rmdir()
        return 'READER_RECOVERED'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recover-state', type=Path)
    parser.add_argument('--approve')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--token', required=True)
    parser.add_argument('--ready-fd', type=int)
    parser.add_argument('--detach', action='store_true')
    options = parser.parse_args()
    try:
        if options.recover_state:
            w.need(options.source is None and options.ready_fd is None and not options.detach, 'INVALID_RECOVERY_ARGUMENTS')
            print(recover(options.recover_state, options.token, options.approve))
            sys.exit(0)
        w.need(options.source is not None and options.ready_fd is not None and options.approve is None, 'INVALID_OBSERVER_ARGUMENTS')
        if options.detach and os.fork():
            os._exit(0)
        observe(options.source, options.token, options.ready_fd)
    except w.Block as error:
        print(error.label, file=sys.stderr)
        sys.exit(error.code)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        # Lease is durable before this process exists. No guessed cleanup.
        os._exit(70)

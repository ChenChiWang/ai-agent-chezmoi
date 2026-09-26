#!/usr/bin/env python3
"""Isolated design validation; not a production launcher or guardian test."""
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import unittest
import uuid

sys.dont_write_bytecode = True
import generation_cohort_model as m

WORKER = r'''
import json,os,sys
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
import generation_cohort_model as m
c=m.Cohort(sys.argv[2],sys.argv[3])
identity=dict(boot='fixture-boot-A',pid=os.getpid(),start=sys.argv[5])
token,generation=c.admit(sys.argv[4],identity)
names=tuple(c.payload(generation))
print(json.dumps(dict(token=token,identity=identity,generation=generation)),flush=True)
for line in sys.stdin:
 if line.strip()=='exit':break
 print(json.dumps(sorted(set((c.home/n).read_text() for n in names))),flush=True)
'''


class CohortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='generation-cohort-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / 'state'; self.state.mkdir(mode=0o700)
        self.home = self.root / 'home'; self.home.mkdir(mode=0o700)
        self.c = m.Cohort(self.state, self.home)
        self.tests = str(Path(__file__).resolve().parent)
        self.a = self.c.stage('claude-codex', self.payload('A'), None)
        self.c.initialize(self.a)

    def payload(self, tag):
        return {name: (tag.encode(), 0o644) for name in m.b.a.mapping('claude-codex')[1]}

    def process(self, code, extra=()):
        p = subprocess.Popen([sys.executable, '-B', '-c', code, self.tests,
                              str(self.state), str(self.home), *extra],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        def cleanup():
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=10)
        self.addCleanup(cleanup)
        return p

    def reader(self, agent):
        p = self.process(WORKER, [agent, uuid.uuid4().hex])
        info = json.loads(p.stdout.readline())
        self.assertEqual(info['identity']['pid'], p.pid)
        return p, info

    def read(self, p):
        p.stdin.write('read\n'); p.stdin.flush()
        return json.loads(p.stdout.readline())

    def finish(self, p, info):
        _, err = p.communicate('exit\n', timeout=10)
        self.assertEqual(p.returncode, 0, err)
        self.c.complete(info['token'], info['identity'], completion_observed=True)

    def test_parallel_agents_prepare_defer_join_drain_activate(self):
        claude, ci = self.reader('claude'); codex, xi = self.reader('codex')
        self.assertEqual(self.read(claude), ['A']); self.assertEqual(self.read(codex), ['A'])
        staged = self.c.stage('claude-codex', self.payload('B'), self.a)
        self.assertEqual(self.c.activate(staged), 'DEFERRED_READERS')
        later, li = self.reader('claude')
        self.assertEqual(li['generation'], self.a)
        self.assertEqual(self.read(later), ['A'])
        self.finish(claude, ci)
        self.assertEqual(self.c.activate(staged), 'DEFERRED_READERS')
        self.assertEqual(self.read(codex), ['A'])
        self.finish(codex, xi); self.finish(later, li)
        self.assertEqual(self.c.activate(staged), 'ACTIVATED')
        fresh, fi = self.reader('codex'); self.assertEqual(fi['generation'], staged)
        self.assertEqual(self.read(fresh), ['B']); self.finish(fresh, fi)

    def test_reader_cannot_enter_partial_activation(self):
        staged = self.c.stage('claude-codex', self.payload('B'), self.a)
        code = '''import sys
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1]);import generation_cohort_model as m
c=m.Cohort(sys.argv[2],sys.argv[3])
def pause(i):
 if i==0:
  print('WRITING',flush=True);sys.stdin.readline()
c.activate(sys.argv[4],pause)
'''
        writer = self.process(code, [staged])
        self.assertEqual(writer.stdout.readline(), 'WRITING\n')
        with self.assertRaisesRegex(m.Refused, 'BUSY'):
            self.c.admit('claude', dict(boot='fixture-boot-A', pid=os.getpid(), start='test'))
        _, err = writer.communicate('\n', timeout=10)
        self.assertEqual(writer.returncode, 0, err)
        p, info = self.reader('claude'); self.assertEqual(self.read(p), ['B']); self.finish(p, info)

    def test_dead_guardian_does_not_release_live_native_reader(self):
        guardian = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
        try:
            p, info = self.reader('codex')
            guardian.kill(); guardian.wait(timeout=10)
            self.c.uncertain(info['token'])
            os.utime(self.state / 'readers', (1, 1))  # Age never authorizes release.
            with self.assertRaisesRegex(m.Refused, 'QUIESCENCE_NOT_PROVEN'):
                self.c.recover_lease(info['token'], info['identity'],
                                     old_boot='fixture-boot-A', current_boot='fixture-boot-A')
            staged = self.c.stage('claude-codex', self.payload('B'), self.a)
            self.assertEqual(self.c.activate(staged), 'DEFERRED_READERS')
            self.assertEqual(self.read(p), ['A'])
            # Other readers remain usable despite an uncertain guardian.
            other, oi = self.reader('claude'); self.assertEqual(self.read(other), ['A'])
            self.finish(other, oi); self.finish(p, info)
        finally:
            if guardian.poll() is None: guardian.kill(); guardian.wait(timeout=10)

    def test_crash_pid_reuse_unknown_liveness_and_reviewed_recovery(self):
        p, info = self.reader('claude'); p.kill(); p.communicate(timeout=10)
        self.c.uncertain(info['token'])
        reused = dict(info['identity'], start='different-process-same-pid')
        with self.assertRaisesRegex(m.Refused, 'IDENTITY_MISMATCH'):
            self.c.complete(info['token'], reused, completion_observed=True)
        with self.assertRaisesRegex(m.Refused, 'COMPLETION_NOT_PROVEN'):
            self.c.complete(info['token'], info['identity'], completion_observed=False)
        with self.assertRaisesRegex(m.Refused, 'QUIESCENCE_NOT_PROVEN'):
            self.c.recover_lease(info['token'], info['identity'],
                                 old_boot='fixture-boot-A', current_boot='fixture-boot-A')
        # Fixture harness owns/reaped the only child; no untracked descendants.
        self.c.recover_lease(info['token'], info['identity'], old_boot='fixture-boot-A',
                             current_boot='fixture-boot-A', family_quiescence_proven=True)
        self.assertEqual(self.c.load('readers'), {})

    def test_reboot_epoch_model_and_other_registered_reader(self):
        first, fi = self.reader('claude'); second, si = self.reader('codex')
        first.kill(); first.communicate(timeout=10)
        # Retiring one proven-dead family must not retire another reader.
        self.c.recover_lease(fi['token'], fi['identity'], old_boot='fixture-boot-A',
                             current_boot='fixture-boot-A', family_quiescence_proven=True)
        candidate = self.c.stage('claude-codex', self.payload('B'), self.a)
        self.assertEqual(self.c.activate(candidate), 'DEFERRED_READERS')
        second.kill(); second.communicate(timeout=10)
        # Injected boot witness only. This test does not reboot the host.
        self.c.recover_lease(si['token'], si['identity'], old_boot='fixture-boot-A',
                             current_boot='fixture-boot-B')
        self.assertEqual(self.c.activate(candidate), 'ACTIVATED')

    def crash_activation(self, staged, index=0, publish_receipt=False):
        code = '''import os,sys
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1]);import generation_cohort_model as m
c=m.Cohort(sys.argv[2],sys.argv[3])
def crash(i):
 if i==int(sys.argv[5]):
  if sys.argv[6]=='yes':c.save('active',sys.argv[4])
  os._exit(88)
c.activate(sys.argv[4],crash)
'''
        writer = self.process(code, [staged, str(index), 'yes' if publish_receipt else 'no'])
        writer.communicate(timeout=10)
        self.assertEqual(writer.returncode, 88)

    def test_crash_at_every_target_boundary_and_receipt_commit(self):
        staged = self.c.stage('claude-codex', self.payload('B'), self.a)
        for index in range(len(self.payload('A'))):
            with self.subTest(after_target=index):
                self.crash_activation(staged, index)
                with self.assertRaisesRegex(m.Refused, 'RECOVERY_REQUIRED'):
                    self.c.admit('claude', {})
                self.c.recover_activation()
                self.assertEqual(self.c.coherent(), self.a)
        self.crash_activation(staged, len(self.payload('A')) - 1, publish_receipt=True)
        self.assertEqual(self.c.load('active'), staged)
        with self.assertRaisesRegex(m.Refused, 'RECOVERY_REQUIRED'):
            self.c.admit('codex', {})
        self.c.recover_activation()
        self.assertEqual(self.c.coherent(), self.a)

    def test_writer_crash_blocks_readers_until_guarded_recovery(self):
        staged = self.c.stage('claude-codex', self.payload('B'), self.a)
        self.crash_activation(staged)
        with self.assertRaisesRegex(m.Refused, 'RECOVERY_REQUIRED'):
            self.c.admit('codex', {})
        self.assertEqual(self.c.recover_activation(), 'RESTORED_OLD')
        p, info = self.reader('claude'); self.assertEqual(self.read(p), ['A']); self.finish(p, info)
        self.assertEqual(self.c.activate(staged), 'ACTIVATED')

    def test_recovery_never_overwrites_third_party_drift(self):
        staged = self.c.stage('claude-codex', self.payload('B'), self.a)
        self.crash_activation(staged)
        path = self.home / '.codex/AGENTS.md'; path.write_text('MANUAL')
        before = {n: (self.home/n).read_bytes() for n in self.payload('A')}
        with self.assertRaisesRegex(m.Refused, 'RECOVERY_DRIFT'):
            self.c.recover_activation()
        self.assertEqual(before, {n: (self.home/n).read_bytes() for n in before})
        self.assertTrue((self.state / 'journal').exists())

    def test_repeated_stage_stale_candidate_and_unmanaged_paths(self):
        sentinel = self.home / '.codex/auth.json'; sentinel.write_text('SYNTHETIC_SENTINEL')
        staged = self.c.stage('claude-codex', self.payload('B'), self.a)
        self.assertEqual(self.c.stage('claude-codex', self.payload('B'), self.a), staged)
        stale = self.c.stage('claude-codex', self.payload('C'), self.a)
        self.assertEqual(self.c.activate(staged), 'ACTIVATED')
        with self.assertRaisesRegex(m.Refused, 'STALE_CANDIDATE'): self.c.activate(stale)
        self.assertEqual(self.c.activate(staged), 'NO_CHANGES')
        for name in ('.codex/auth.json', '.claude/.credentials.json', '../escape'):
            data = self.payload('B'); data[name] = (b'fixture', 0o600)
            with self.assertRaisesRegex(m.Refused, 'INVALID_SCOPE'):
                self.c.stage('claude-codex', data, staged)
        self.assertEqual(sentinel.read_text(), 'SYNTHETIC_SENTINEL')

    def test_exec_boundary_preserves_pid_argv_streams_umask_and_signal(self):
        vendor = self.root / 'vendor'
        vendor.write_text('#!' + sys.executable + '''
import os,sys,json,signal
if '--signal' in sys.argv:os.kill(os.getpid(),signal.SIGTERM)
data=b'' if '--tty' in sys.argv else sys.stdin.buffer.read()
print(json.dumps(dict(pid=os.getpid(),argv=sys.argv[1:],cwd=os.getcwd(),data=data.hex(),umask=os.umask(0),tty=[os.isatty(i) for i in (0,1,2)])),flush=True)
sys.stderr.write('VENDOR_STDERR\\n')
sys.exit(23)
'''); vendor.chmod(0o700)
        launcher = self.root / 'launch'
        launcher.write_text('#!' + sys.executable + '\nimport os,sys\nsys.dont_write_bytecode=True\n'
                            + 'sys.path.insert(0,' + repr(self.tests) + ')\n'
                            + 'import generation_cohort_model as m\n'
                            + 'c=m.Cohort(' + repr(str(self.state)) + ',' + repr(str(self.home)) + ')\n'
                            + "c.admit('claude',dict(boot='fixture-boot-A',pid=os.getpid(),start='exec-fixture'))\n"
                            + 'os.execv(' + repr(str(vendor)) + ',[' + repr(str(vendor)) + ',*sys.argv[1:]])\n')
        launcher.chmod(0o700)
        args = ['a b', '中文', '', '$(literal)', '--settings', '{"disableAllHooks":true}']
        direct = subprocess.run([str(vendor), *args], input=b'\x00\xffinput', capture_output=True, cwd=self.root)
        p = subprocess.Popen([str(launcher), *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=self.root)
        out, err = p.communicate(b'\x00\xffinput', timeout=10)
        d, wrapped = json.loads(direct.stdout), json.loads(out)
        self.assertEqual(wrapped.pop('pid'), p.pid); d.pop('pid')
        self.assertEqual(d, wrapped); self.assertEqual(direct.stderr, err)
        self.assertEqual(p.returncode, direct.returncode)
        signalled = subprocess.run([str(launcher), '--signal'], capture_output=True, timeout=10)
        self.assertEqual(signalled.returncode, -signal.SIGTERM)
        master, slave = pty.openpty()
        try:
            terminal = subprocess.Popen([str(launcher), '--tty'], stdin=slave, stdout=slave, stderr=slave)
            self.assertEqual(terminal.wait(timeout=10), 23)
            self.assertIn(b'"tty": [true, true, true]', os.read(master, 8192))
        finally:
            os.close(master); os.close(slave)
        # Fixture has no guardian: exec children are reaped by this harness.
        # Persistent records remain until witnessed completion/recovery.
        self.assertEqual(len(self.c.load('readers')), 3)

    @unittest.skipUnless(hasattr(select, 'kqueue'), 'macOS/BSD kernel observation')
    def test_kernel_exit_observation_across_exec_without_agent_callback(self):
        for signalled in (False, True):
            with self.subTest(signalled=signalled):
                readfd, writefd = os.pipe()
                queue = select.kqueue()
                code = '''import os,sys
fd=int(sys.argv[1]);os.read(fd,1);os.close(fd)
os.execv(sys.executable,[sys.executable,'-c',sys.argv[2]])
'''
                body = ('import os,signal;os.kill(os.getpid(),signal.SIGTERM)' if signalled
                        else 'import sys;sys.exit(23)')
                p = subprocess.Popen([sys.executable, '-c', code, str(readfd), body],
                                     pass_fds=(readfd,), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    os.close(readfd); readfd = None
                    # NOTE_EXITSTATUS is 0x04000000 in the installed macOS SDK.
                    event = select.kevent(p.pid, filter=select.KQ_FILTER_PROC,
                                          flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                                          fflags=select.KQ_NOTE_EXIT | 0x04000000)
                    queue.control([event], 0, 0)
                    os.write(writefd, b'1'); os.close(writefd); writefd = None
                    observed = queue.control(None, 1, 10)
                    self.assertEqual(len(observed), 1)
                    self.assertEqual(observed[0].ident, p.pid)
                    self.assertTrue(observed[0].fflags & select.KQ_NOTE_EXIT)
                    p.communicate(timeout=10)
                    self.assertEqual(p.returncode, -signal.SIGTERM if signalled else 23)
                    if signalled:
                        self.assertTrue(os.WIFSIGNALED(observed[0].data))
                    else:
                        self.assertEqual(os.WEXITSTATUS(observed[0].data), 23)
                finally:
                    if p.poll() is None: p.kill(); p.communicate(timeout=10)
                    queue.close()
                    if readfd is not None: os.close(readfd)
                    if writefd is not None: os.close(writefd)


if __name__ == '__main__':
    unittest.main()

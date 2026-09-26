#!/usr/bin/env python3
"""Real macOS guardian/exec tests; all files and children are disposable."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bootstrap'))
import guardian as g
spec = importlib.util.spec_from_file_location('fixture', Path(__file__).with_name('test-bootstrap.py'))
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
b, w = g.b, g.w

WORKER = '''import os,sys,uuid
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
import guardian as g
b,w=g.b,g.w
source,state=map(Path,sys.argv[2:4])
token=uuid.uuid4().hex
with w.lock(source,allow_readers=True):
 p=g.lease_path(source,token);p.parent.mkdir(mode=0o700,exist_ok=True)
 record=dict(schema=1,state='RESERVED',owner=g.identity(os.getpid()),generation='fixture',state_root=str(state))
 b.save(p,record,True)
 record['observer']=g.arm(source,token);record['state']='ARMED';b.save(p,record)
os.execv(sys.argv[4],[sys.argv[4],*sys.argv[5:]])
'''


class GuardianTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.BootstrapTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.deploy('claude-codex')
        self.leases = self.f.src / '.git/ai-agent-launch-readers'
        self.binary = self.f.root / 'native-fixture'
        self.binary.write_text('#!' + sys.executable + '''
import os,sys,json,signal,time
if '--wait' in sys.argv:
 print('READY',flush=True);time.sleep(30)
if '--fork-reaped' in sys.argv:
 pid=os.posix_spawn('/usr/bin/true',['true'],{})
 observed,status=os.waitpid(pid,0)
 print(json.dumps(dict(child=pid,reaped=observed==pid,child_exit=os.waitstatus_to_exitcode(status))),flush=True)
 sys.exit(23)
if '--fork' in sys.argv:
 fd=os.open('/dev/null',os.O_RDWR)
 pid=os.posix_spawn('/bin/sleep',['sleep','30'],{},file_actions=[(os.POSIX_SPAWN_DUP2,fd,n) for n in (0,1,2)])
 print(json.dumps(dict(child=pid)),flush=True)
 sys.exit(23)
if '--crash' in sys.argv:os.kill(os.getpid(),signal.SIGTERM)
print(json.dumps(dict(pid=os.getpid(),argv=sys.argv[1:],data=sys.stdin.buffer.read().hex())),flush=True)
sys.stderr.write('VENDOR_STDERR\\n')
sys.exit(23)
'''); self.binary.chmod(0o700)

    def start(self, *args):
        p = subprocess.Popen([sys.executable, '-B', '-c', WORKER, str(ROOT / 'bootstrap'),
                              str(self.f.src), str(self.f.state), str(self.binary), *args],
                             env=self.f.env, cwd=self.f.root,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if p.poll() is None: p.kill()
            p.communicate(timeout=10)
        self.addCleanup(cleanup)
        return p

    def records(self):
        return {p.name:b.load(p) for p in self.leases.iterdir()} if self.leases.exists() else {}

    def until(self, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            result = self.records()
            if predicate(result): return result
            time.sleep(0.02)
        self.fail('Guardian evidence did not reach the expected state')

    def test_leaf_exit_exec_streams_and_cleanup(self):
        p = self.start('a b', '中文', '', '$(literal)', '--settings', '{"disableAllHooks":true}')
        out, err = p.communicate(b'\x00\xffstdin', timeout=10)
        self.assertEqual(p.returncode,23,err.decode(errors='replace'))
        doc=json.loads(out);self.assertEqual(doc['pid'],p.pid)
        self.assertEqual(doc['data'],b'\x00\xffstdin'.hex())
        self.assertEqual(doc['argv'],['a b','中文','','$(literal)','--settings','{"disableAllHooks":true}'])
        self.assertEqual(err,b'VENDOR_STDERR\n')
        self.until(lambda r:not r)
        with w.lock(self.f.src): pass

    def test_forked_family_is_retained_after_root_exit(self):
        p=self.start('--fork');out,err=p.communicate(timeout=10)
        self.assertEqual(p.returncode,23,err.decode(errors='replace'))
        child=json.loads(out)['child']
        try:
            records=self.until(lambda r:any(v.get('state')=='UNCERTAIN_FAMILY' for v in r.values()))
            os.kill(child,0)
            record=next(iter(records.values()))
            self.assertTrue(record['evidence']['fork_event_observed'])
            self.assertIn('descendant_exit_observations',record['evidence']['missing'])
            with self.assertRaises(w.Block):
                with w.lock(self.f.src):pass
            with self.assertRaises(w.Block):g.recover(self.f.state,next(iter(records)))
        finally:
            os.kill(child,signal.SIGTERM)

    def test_reaped_fork_retains_lease_without_descendant_evidence(self):
        p=self.start('--fork-reaped');out,err=p.communicate(timeout=10)
        self.assertEqual(p.returncode,23,err.decode(errors='replace'))
        proof=json.loads(out)
        self.assertTrue(proof['reaped']);self.assertEqual(proof['child_exit'],0)
        records=self.until(lambda r:any(v.get('state')=='UNCERTAIN_FAMILY' for v in r.values()))
        token,record=next(iter(records.items()))
        self.assertEqual(record['evidence']['missing'],['descendant_identities','continuous_descendant_lineage','descendant_exit_observations'])
        self.assertTrue(record['evidence']['root_exit_observed'])
        # Harness waitpid proof is deliberately NOT a production recovery input.
        with self.assertRaises(w.Block):g.recover(self.f.state,token)
        with self.assertRaises(w.Block):
            with w.lock(self.f.src):pass

    def test_observer_death_never_releases_reader(self):
        p=self.start('--wait');self.assertEqual(p.stdout.readline(),b'READY\n')
        records=self.records();token,record=next(iter(records.items()))
        os.kill(record['observer']['pid'],signal.SIGKILL)
        self.assertIsNone(p.poll())
        with self.assertRaises(w.Block):g.recover(self.f.state,token)
        p.kill();p.communicate(timeout=10)
        with self.assertRaises(w.Block):g.recover(self.f.state,token)
        self.assertIn(token,self.records())

    def test_launcher_preserves_default_and_ignored_sigpipe(self):
        source=self.f.root/'signals.c'
        source.write_text('#include <signal.h>\n#include <stdio.h>\nint main(void){struct sigaction a;sigaction(SIGPIPE,0,&a);printf("PIPE:%d\\n",a.sa_handler==SIG_IGN);return 23;}\n')
        subprocess.run(['/usr/bin/clang',str(source),'-o',str(self.f.binary)],check=True,capture_output=True)
        self.f.deploy()
        shim=self.f.root/'codex-launcher';shim.write_text(fixture.launcher.render(self.f.state,'codex'));shim.chmod(0o700)
        # Avoid transport access; source dirtiness selects verified generation A.
        path=self.f.src/b.a.PREFIX/'shared/instructions.md';path.write_bytes(path.read_bytes()+b'\nlocal\n')
        for ignored in (False,True):
            kwargs=dict(env=self.f.env,capture_output=True,timeout=15,
                        preexec_fn=(lambda:signal.signal(signal.SIGPIPE,signal.SIG_IGN)) if ignored else None)
            direct=subprocess.run([str(self.f.binary)],**kwargs)
            wrapped=subprocess.run([str(shim)],**kwargs)
            self.assertEqual(direct.returncode,23)
            self.assertEqual(wrapped.returncode,23,wrapped.stderr.decode())
            self.assertEqual(wrapped.stdout,direct.stdout)
            self.assertEqual(wrapped.stdout,('PIPE:'+str(int(ignored))+'\n').encode())
        self.until(lambda r:not r)

    def test_observed_leaf_crash_requires_hash_bound_recovery(self):
        p=self.start('--crash');p.communicate(timeout=10)
        self.assertEqual(p.returncode,-signal.SIGTERM)
        records=self.until(lambda r:any(v.get('state')=='EXITED_LEAF' for v in r.values()))
        token=next(iter(records))
        approval=g.recover(self.f.state,token)
        with self.assertRaises(w.Block):g.recover(self.f.state,token,'0'*64)
        self.assertEqual(g.recover(self.f.state,token,approval),'READER_RECOVERED')
        self.assertFalse(self.records())


if __name__ == '__main__':unittest.main()

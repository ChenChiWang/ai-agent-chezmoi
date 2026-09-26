#!/usr/bin/env python3
"""Phase 4B: isolated fake HOME/repos/CLI only; production is never a fixture."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import pty
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bootstrap'))
import bootstrap as b
import launch
import launcher
import tools
import acquire
import guardian
w = b.w


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='phase4-fixture-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / 'home 中文'
        self.src = self.home / '.local/share/chezmoi'
        self.state = self.root / 'private state'
        self.state.mkdir(mode=0o700)
        self.home.mkdir()
        shutil.copytree(ROOT.parent / 'examples/chezmoi', self.src)
        self.env = dict(PATH=os.environ['PATH'], HOME=str(self.home), LC_ALL='C',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0',
                        GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.test',
                        GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.test',
                        PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
        self.git('init','-b','main')
        self.git('add','.')
        self.git('commit','-qm','fixture v2')
        self.remote = self.root / 'remote.git'
        self.run_cmd(['git','clone','--bare',str(self.src),str(self.remote)])
        self.scanner = self.root / 'scanner'
        self.scanner.write_text('''#!/usr/bin/env python3
import pathlib,json,sys
s,r=map(pathlib.Path,sys.argv[1:]);bad=any(b'FIXTURE_SECRET' in p.read_bytes() for p in s.rglob('*') if p.is_file())
r.write_text(json.dumps(dict(schema=1,status='secret' if bad else 'clean',findings=[dict(file='source/.chezmoitemplates/ai/shared/instructions.md',rule='generic-api-key',line=1)] if bad else [])))
sys.exit(10 if bad else 0)
''')
        self.scanner.chmod(0o755)
        self.binary = self.root / 'real cli'
        self.binary.write_text('''#!/usr/bin/env python3
import os,sys,json,time,signal
if '--wait' in sys.argv:
 print('READY',flush=True)
 time.sleep(15)
if '--signal' in sys.argv: os.kill(os.getpid(),signal.SIGTERM)
if '--tty' in sys.argv:
 print('TTY:'+''.join(str(int(os.isatty(fd))) for fd in (0,1,2)),flush=True)
 sys.exit(23)
print(json.dumps(dict(argv=sys.argv[1:],cwd=os.getcwd(),input=sys.stdin.buffer.read().hex(),umask=os.umask(0))),flush=True)
sys.stderr.write('VENDOR_STDERR\\n')
sys.exit(23)
''')
        self.binary.write_text(self.binary.read_text().replace('#!/usr/bin/env python3', '#!' + str(Path(sys.executable).resolve()), 1))
        self.binary.chmod(0o755)

    def run_cmd(self, argv, expected=0, **kwargs):
        p = subprocess.run(argv, env=self.env, capture_output=True, timeout=90, **kwargs)
        self.assertEqual(p.returncode, expected, (p.stdout+p.stderr).decode(errors='replace'))
        return p

    def git(self,*args):
        return self.run_cmd(['git','-C',str(self.src),*args]).stdout.decode().strip()

    def options(self, profile='claude-codex', **kwargs):
        return SimpleNamespace(source=str(self.src), destination=str(self.home), state=str(self.state),
                               profile=profile, scanner=str(self.scanner), adopt=False,
                               remote=str(self.remote), claude=str(self.binary), codex=str(self.binary),
                               **kwargs)

    def deploy(self, profile='claude-codex', adopt=False):
        o = self.options(profile)
        o.adopt = adopt
        with contextlib.redirect_stdout(io.StringIO()):
            doc, _, _ = b.planned(o)
            o.plan = str(self.state / ('plan-'+str(time.time_ns())+'.json'))
            o.approve = w.digest(w.encoded(doc))
            b.save(Path(o.plan),doc,True)
            b.apply(o)
        return o

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mode) for p in self.home.rglob('*') if p.is_file()}

    def test_three_profiles_rerun_and_all_switches(self):
        self.deploy('claude')
        self.assertFalse((self.home/'.codex').exists())
        before=self.snapshot(); receipt=(self.state/'receipt.json').read_bytes()
        self.deploy('claude');self.assertEqual(before,self.snapshot());self.assertEqual(receipt,(self.state/'receipt.json').read_bytes())
        # Covers six directed edges without mutating source or its Git baseline.
        head=self.git('rev-parse','HEAD')
        for profile in ('codex','claude','claude-codex','codex','claude-codex','claude'):
            self.deploy(profile,adopt=True)
            doc=b.receipt(self.state);self.assertEqual(len(doc['targets']),{'claude':14,'codex':12,'claude-codex':21}[profile])
            b.verify_receipt(doc,self.src,self.home)
        self.assertEqual(head,self.git('rev-parse','HEAD'));self.assertFalse(self.git('status','--porcelain'))

    def test_codex_without_claude_runtime_and_custom_claude_home(self):
        with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':'/nonexistent/not-my-agent'}):self.deploy('codex')
        self.assertFalse((self.home/'.claude').exists())

    def test_secret_and_collision_fail_before_write(self):
        p=self.src/b.a.PREFIX/'shared/instructions.md';p.write_bytes(b'FIXTURE_SECRET')
        self.git('add','.');self.git('commit','-qm','secret fixture')
        with self.assertRaises(w.Block):b.planned(self.options())
        self.assertFalse((self.home/'.claude').exists())

    def test_collision_requires_adopt_or_reconcile(self):
        p=self.home/'.codex/AGENTS.md';p.parent.mkdir();p.write_text('manual')
        with self.assertRaises(w.Block):b.planned(self.options('codex'))
        self.assertEqual(p.read_text(),'manual')

    def test_preserve_credentials_and_unknown_skill(self):
        sentinel=self.home/'.codex/auth.json';sentinel.parent.mkdir();sentinel.write_text('NEVER_IMPORT')
        unknown=self.home/'.agents/skills/other/SKILL.md';unknown.parent.mkdir(parents=True);unknown.write_text('mine')
        self.deploy('codex');self.deploy('claude')
        self.assertEqual(sentinel.read_text(),'NEVER_IMPORT');self.assertEqual(unknown.read_text(),'mine')

    def test_stale_plan_and_target_drift(self):
        self.deploy('codex');o=self.options('claude-codex');doc,_,_=b.planned(o)
        p=self.state/'stale.json';b.save(p,doc,True);o.plan=str(p);o.approve=w.digest(w.encoded(doc))
        (self.home/'.codex/AGENTS.md').write_text('my edit')
        with self.assertRaises(w.Block):b.apply(o)
        self.assertEqual((self.home/'.codex/AGENTS.md').read_text(),'my edit')

    def test_symlink_and_hardlink_escape(self):
        p=self.home/'.codex';p.symlink_to(self.state,target_is_directory=True)
        with self.assertRaises((w.Block,ValueError)):b.planned(self.options('codex'))
        p.unlink();p.mkdir();os.link(self.src/'README.md',p/'AGENTS.md') if (self.src/'README.md').exists() else os.link(self.src/'.gitignore',p/'AGENTS.md')
        with self.assertRaises((w.Block,ValueError)):b.planned(self.options('codex'))

    def test_recovery_after_write_failure(self):
        self.deploy('claude');before=self.snapshot();o=self.options('codex');doc,_,_=b.planned(o)
        o.plan=str(self.state/'recovery-plan.json');b.save(Path(o.plan),doc,True);o.approve=w.digest(w.encoded(doc))
        original=b.put;count=[0]
        def fail(*args):
            count[0]+=1
            if count[0]==3:raise OSError('fixture fault')
            return original(*args)
        with patch.object(b,'put',fail),self.assertRaises(w.Block):b.apply(o)
        with contextlib.redirect_stdout(io.StringIO()):b.recover(o)
        self.assertEqual(before,self.snapshot())

    def test_inactive_history_reaches_codex_without_claude_targets(self):
        self.deploy('codex')
        # Advance remote from separate disposable checkout.
        other=self.root/'other';self.run_cmd(['git','clone',str(self.remote),str(other)])
        p=other/b.a.PREFIX/'adapters/claude.md';p.write_bytes(p.read_bytes()+b'\nFixture Claude-only rule.\n')
        for cmd in [('add','.'),('commit','-qm','claude-only change'),('push','origin','main')]:self.run_cmd(['git','-C',str(other),*cmd])
        with contextlib.redirect_stdout(io.StringIO()):
            doc,outcome=launch.attempt(self.state,scanner=str(self.scanner))
        self.assertEqual(outcome,'SYNCED');self.assertFalse((self.home/'.claude').exists())
        self.assertNotEqual(doc['head'],self.git('rev-parse','HEAD^'))

    def test_launch_policy_blocks_intermediate_script_change(self):
        self.deploy('codex');other=self.root/'other';self.run_cmd(['git','clone',str(self.remote),str(other)])
        p=other/b.a.PREFIX/'shared/scripts/sync.sh';old=p.read_bytes();p.write_bytes(old+b'\n# unreviewed\n')
        for cmd in [('add','.'),('commit','-qm','unsafe')]:self.run_cmd(['git','-C',str(other),*cmd])
        p.write_bytes(old)
        for cmd in [('add','.'),('commit','-qm','undo'),('push','origin','main')]:self.run_cmd(['git','-C',str(other),*cmd])
        before=self.snapshot()
        with self.assertRaises(w.Block):launch.attempt(self.state,scanner=str(self.scanner))
        self.assertEqual(before,self.snapshot())

    def test_thin_launcher_arguments_streams_exit_and_umask(self):
        self.deploy('codex')
        shim=self.root/'codex';shim.write_text(launcher.render(self.state,'codex'));shim.chmod(0o755)
        args=['exec','a b','中文','$(not-executed)','--','--help','']
        data=b'\x00\xffstdin\n'
        # Dirty source makes launch skip refresh, while deployed files stay known.
        p=self.src/b.a.PREFIX/'shared/instructions.md';p.write_bytes(p.read_bytes()+b'\nlocal\n')
        direct=self.run_cmd([str(self.binary),*args],expected=23,input=data,cwd=self.root)
        wrapped=self.run_cmd([str(shim),*args],expected=23,input=data,cwd=self.root)
        self.assertEqual(direct.stdout,wrapped.stdout)
        self.assertTrue(wrapped.stderr.endswith(direct.stderr));self.assertIn(b'BLOCKED_LOCAL_CHANGES',wrapped.stderr)
        self.wait_for_leases(lambda records: not records)

    def test_disabled_launcher_passes_through_and_reenable(self):
        self.deploy();shim=self.root/'codex';shim.write_text(launcher.render(self.state,'codex'));shim.chmod(0o755)
        self.deploy('claude')
        direct=self.run_cmd([str(self.binary),'exec','hello'],expected=23,input=b'abc')
        bypass=self.run_cmd([str(shim),'exec','hello'],expected=23,input=b'abc')
        self.assertEqual(direct.stdout,bypass.stdout);self.assertEqual(direct.stderr,bypass.stderr)
        self.wait_for_leases(lambda records: not records)
        self.deploy('claude-codex')
        self.assertTrue((self.home/'.codex/AGENTS.md').exists())

    def test_admin_bypass_and_signal_exit(self):
        self.deploy('claude');shim=self.root/'claude';shim.write_text(launcher.render(self.state,'claude'));shim.chmod(0o755)
        direct=self.run_cmd([str(self.binary),'--version'],expected=23,input=b'')
        self.assertEqual(self.run_cmd([str(shim),'--version'],expected=23,input=b'').stderr,direct.stderr)
        self.run_cmd([sys.executable,'-B',str(ROOT/'bootstrap/launch.py'),'--state',str(self.state),'--agent','claude','--offline','--','--signal'],expected=-signal.SIGTERM)

    def test_lease_blocks_writer_but_not_other_agent(self):
        self.deploy();cmd=[sys.executable,'-B',str(ROOT/'bootstrap/launch.py'),'--state',str(self.state),'--agent','codex','--offline','--','--wait']
        proc=subprocess.Popen(cmd,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL)
        try:
            self.assertEqual(proc.stdout.readline(),b'READY\n')
            with self.assertRaises(w.Block):
                with w.lock(self.src):pass
            result=self.run_cmd([sys.executable,'-B',str(ROOT/'bootstrap/launch.py'),'--state',str(self.state),'--agent','claude','--','hi'],expected=23,input=b'')
            self.assertNotIn(b'BUSY',result.stderr)
        finally:
            proc.terminate();proc.communicate(timeout=10)
        self.assertEqual(proc.returncode,-signal.SIGTERM)
        records = self.wait_for_leases(lambda records: len(records) == 1 and next(iter(records.values())).get('state') == 'EXITED_LEAF')
        token = next(iter(records))
        guardian.recover(self.state, token, guardian.recover(self.state, token))
        self.wait_for_leases(lambda records: not records)

    def test_tty_descriptors_remain_attached(self):
        self.deploy('codex')
        master,slave=pty.openpty()
        try:
            proc=subprocess.Popen([sys.executable,'-B',str(ROOT/'bootstrap/launch.py'),'--state',str(self.state),'--agent','codex','--offline','--','--tty'],env=self.env,stdin=slave,stdout=slave,stderr=slave)
            # macOS PTYs can discard buffered output on last slave close.
            # Keep the harness slave open until after reading the result.
            self.assertEqual(proc.wait(timeout=15),23)
            data=os.read(master,8192)
            self.assertIn(b'TTY:111',data)
        finally:
            os.close(master)
            if slave is not None:os.close(slave)

    def test_preparation_deadline_precedes_mutation(self):
        self.deploy('codex');before=self.snapshot()
        with b.engine(self.src,self.home,'codex',str(self.scanner),str(self.remote)) as e:
            e.a.prepare_deadline=time.monotonic()-1
            with self.assertRaises(w.Block):e.build()
        self.assertEqual(before,self.snapshot())

    def test_acquire_pinned_repo_with_transport_fixture(self):
        target=self.home/'new source'
        actual=subprocess.run
        calls=[]
        def transport(argv,**kw):
            calls.append(argv)
            argv=[str(self.remote) if x=='ssh://git@github.com/OWNER/dotfiles.git' else x for x in argv]
            env=kw.get('env',{}).copy();env['GIT_ALLOW_PROTOCOL']='file';kw['env']=env
            return actual(argv,**kw)
        with patch.object(acquire.subprocess,'run',transport),contextlib.redirect_stdout(io.StringIO()):
            acquire.acquire('ssh://git@github.com/OWNER/dotfiles.git',self.git('rev-parse','HEAD'),target,self.home,self.state)
        self.assertTrue((target/'.git').is_dir());self.assertFalse((self.home/'.claude').exists())
        self.assertTrue(any('--no-checkout' in c for c in calls))
        self.assertFalse(any('login' in c for c in calls))

    def wait_for_leases(self, predicate):
        directory = self.src / '.git/ai-agent-launch-readers'
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            records = {p.name:b.load(p) for p in directory.iterdir()} if directory.exists() else {}
            if predicate(records): return records
            time.sleep(0.02)
        self.fail('Reader evidence did not reach expected state')

    def test_launch_remote_unreachable_and_dependency_failure_keep_files(self):
        self.deploy('codex');before=self.snapshot()
        # Policy unit test only; process/kernel qualification lives in the
        # separate subprocess tests, never attach a watcher to this test runner.
        for label,code in [('NETWORK_ERROR',71),('MISSING_DEPENDENCY',69),('SCANNER_ERROR',70)]:
            with patch.object(launch,'attempt',side_effect=w.Block(code,label)),patch.object(launch,'exec_cli',return_value=0),patch.object(guardian,'identity',return_value={'fixture':True}),patch.object(guardian,'arm',return_value={'fixture':True}),contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(launch.launch(self.state,'codex',['exec']),0)
                self.assertIn(label,error.getvalue())
            leases = self.src / '.git/ai-agent-launch-readers'
            for lease in leases.iterdir(): lease.unlink()  # mock leases only; no process was started
            leases.rmdir()
            self.assertEqual(before,self.snapshot())
        (self.home/'.codex/AGENTS.md').write_text('drift')
        with patch.object(launch,'exec_cli') as child,self.assertRaises(w.Block):launch.launch(self.state,'codex',[],offline=True)
        child.assert_not_called()

    def test_unqualified_claude_statusline_does_not_block_codex(self):
        p=self.src/'dot_claude/settings.json';p.write_text('{"statusLine":{"type":"command","command":"npx -y ccstatusline@latest"}}')
        self.git('add','.');self.git('commit','-qm','portable qualification fixture')
        with self.assertRaises(w.Block) as error:b.planned(self.options('claude'))
        self.assertEqual(error.exception.label,'STATUSLINE_QUALIFICATION_REQUIRED')
        self.deploy('codex');self.assertFalse((self.home/'.claude').exists())

    def test_scanner_failure_blocks_initial_deploy(self):
        self.scanner.write_text("#!/bin/sh\nexit 69\n")
        with self.assertRaises(w.Block):b.planned(self.options('claude'))
        self.assertFalse((self.home/'.claude').exists())

    def test_normal_dual_repo_sync_profiles_and_sentinels(self):
        self.deploy('claude')
        # Inactive Codex files are neither required nor traversed even when full
        # source history is selected. A symlink sentinel must remain untouched.
        (self.home/'.codex').symlink_to(self.state,target_is_directory=True)
        self.run_cmd(['sh',str(b.SCRIPTS/'sync.sh'),'status','--profile','claude','--repository-profile','claude-codex','--source',str(self.src),'--destination',str(self.home),'--scanner',str(self.scanner)])
        self.assertTrue((self.home/'.codex').is_symlink())

    def test_real_scanner_fresh_and_status(self):
        o=self.options('codex');o.scanner=None
        with contextlib.redirect_stdout(io.StringIO()):
            doc,_,_=b.planned(o);o.plan=str(self.state/'real.json');b.save(Path(o.plan),doc,True);o.approve=w.digest(w.encoded(doc));b.apply(o)
        self.run_cmd(['sh',str(self.home/'.config/ai-agent/bin/sync.sh'),'status','--profile','codex','--repository-profile','claude-codex','--source',str(self.src),'--destination',str(self.home)])


class ArtifactTests(unittest.TestCase):
    def archive(self,name='tool',kind=None):
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w:gz') as f:
            entry=tarfile.TarInfo(name);data=b'#!/bin/sh\necho 1.2.3\n';entry.size=len(data)
            if kind:entry.type=kind;entry.linkname='/tmp/escape'
            f.addfile(entry,io.BytesIO(data))
        return out.getvalue()

    def test_digest_and_archive_escape(self):
        for name,kind in [('../escape',None),('/escape',None),('tool',tarfile.SYMTYPE),('tool',tarfile.LNKTYPE)]:
            data=self.archive(name,kind)
            with self.assertRaises(w.Block):tools.payload(dict(sha256=w.digest(data),member='tool'),data)
        with self.assertRaises(w.Block):tools.payload(dict(sha256='0'*64,member='tool'),self.archive())
        data=self.archive();self.assertIn(b'1.2.3',tools.payload(dict(sha256=w.digest(data),member='tool'),data))

    def test_tool_install_rerun_and_agent_failure_isolation(self):
        data=self.archive()
        with tempfile.TemporaryDirectory(dir='/tmp') as root:
            prefix=Path(root).resolve();prefix.chmod(0o700)
            item=dict(kind='archive',version='1.2.3',url='https://example.test/tool.tar.gz',sha256=w.digest(data),member='tool')
            lock=dict(schema=1,platform='darwin-arm64',tools={name:dict(item) for name in tools.selected('claude-codex')})
            # Exercise installer mechanism with tiny executable fixture artifacts,
            # not substitute a test scanner into real production validation.
            for name in ('git','python','gitleaks','node'):lock['tools'][name]=dict(kind='prerequisite',version='fixture')
            with patch.object(tools.platform,'system',return_value='Darwin'),patch.object(tools.platform,'machine',return_value='arm64'):
                doc=tools.prepare(lock,prefix,'claude-codex')
                def fetch(spec):
                    if spec is lock['tools']['claude']:raise OSError('unavailable agent')
                    return data
                result=tools.install(doc,fetch)
                self.assertEqual(result['claude'],'BLOCKED_ARTIFACT_OR_HEALTH');self.assertEqual(result['codex'],'INSTALLED')
                existing=(prefix/'codex-1.2.3').read_bytes()
                doc=tools.prepare(lock,prefix,'codex');result=tools.install(doc,lambda _:self.fail('idempotent install downloaded again'))
                self.assertEqual(result['codex'],'NO_CHANGES');self.assertEqual(existing,(prefix/'codex-1.2.3').read_bytes())


if __name__=='__main__':unittest.main()

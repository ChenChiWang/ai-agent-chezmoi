#!/usr/bin/env python3
"""Real v2/bootstrap coordination; only disposable repositories and HOME."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('test-bootstrap.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
b,w,launch=f.b,f.w,f.launch


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f=f.BootstrapTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.deploy()

    def reader(self):
        path=self.f.src/'.git/ai-agent-launch-readers'/('a'*32)
        path.parent.mkdir(mode=0o700,exist_ok=True)
        b.save(path,dict(schema=1,state='FIXTURE_READER'),True)
        return path

    def advance(self):
        other=self.f.root/'other';self.f.run_cmd(['git','clone',str(self.f.remote),str(other)])
        p=other/b.a.PREFIX/'shared/instructions.md';p.write_bytes(p.read_bytes()+b'\nCohort generation B.\n')
        for cmd in [('add','.'),('commit','-qm','generation B'),('push','origin','main')]:
            self.f.run_cmd(['git','-C',str(other),*cmd])

    def command(self,command,plan,operation=None,approve=None,expected=0):
        args=[sys.executable,'-B',str(b.SCRIPTS/'sync-write.py'),command,
              '--source',str(self.f.src),'--destination',str(self.f.home),
              '--remote',str(self.f.remote),'--branch','main','--profile','claude-codex',
              '--plan',str(plan),'--scanner',str(self.f.scanner)]
        if operation:args+=['--operation',operation]
        if approve:args+=['--approve',approve]
        return self.f.run_cmd(args,expected=expected)

    def test_v2_in_prepare_defer_activate_updates_receipt(self):
        self.advance();reader=self.reader();old=b.receipt(self.f.state)
        plan=self.f.state/'incoming.json'
        self.command('plan',plan,operation='in')
        approval=w.digest(plan.read_bytes())
        result=self.command('in',plan,approve=approval,expected=75)
        self.assertIn(b'DEFERRED_READERS',result.stdout)
        self.assertEqual(b.receipt(self.f.state),old)
        b.verify_receipt(old,self.f.src,self.f.home)
        self.assertTrue((self.f.state/('prepared-'+approval)/'manifest.json').exists())
        reader.unlink();reader.parent.rmdir()
        self.command('in',plan,approve=approval)
        new=b.receipt(self.f.state)
        self.assertNotEqual(new['head'],old['head'])
        self.assertEqual(new['head'],self.f.git('rev-parse','HEAD'))
        b.verify_receipt(new,self.f.src,self.f.home)
        self.f.deploy()  # Same new receipt supports idempotent bootstrap rerun.

    def test_push_from_reader_never_publishes(self):
        self.reader();old=self.f.git('rev-parse','HEAD')
        plan=self.f.state/'outgoing.json';self.command('plan',plan,operation='push')
        self.command('push',plan,approve=w.digest(plan.read_bytes()),expected=75)
        self.assertEqual(old,self.f.git('rev-parse','HEAD'))
        self.assertEqual(old,self.f.run_cmd(['git','--git-dir='+str(self.f.remote),'rev-parse','HEAD']).stdout.decode().strip())

    def test_launch_prepares_pending_then_freshly_activates(self):
        self.advance();reader=self.reader();old=b.receipt(self.f.state)
        doc,outcome=launch.attempt(self.f.state,scanner=str(self.f.scanner))
        self.assertEqual(outcome,'DEFERRED_READERS');self.assertEqual(doc,old)
        pending=b.load(self.f.state/'pending.json');self.assertFalse(pending['applied'])
        reader.unlink();reader.parent.rmdir()
        doc,outcome=launch.attempt(self.f.state,scanner=str(self.f.scanner))
        self.assertEqual(outcome,'SYNCED');self.assertFalse((self.f.state/'pending.json').exists())
        b.verify_receipt(doc,self.f.src,self.f.home)

    def test_migration_apply_and_rollback_share_reader_barrier(self):
        self.reader()
        for command in ('apply','rollback'):
            result=self.f.run_cmd([sys.executable,'-B',str(b.SCRIPTS/'sync-migrate.py'),command,
                '--source',str(self.f.src),'--destination',str(self.f.home),
                '--backup',str(self.f.state/'migration-backup'),'--branch','main',
                '--profile','claude-codex','--approve','0'*64],expected=73)
            self.assertIn(b'BLOCKED_ACTIVE_LAUNCH',result.stdout)

    def test_shell_in_uses_same_reader_barrier(self):
        self.reader();plan=self.f.state/'shell-plan.json'
        self.command('plan',plan,operation='in')
        result=self.f.run_cmd(['sh',str(self.f.home/'.config/ai-agent/bin/sync.sh'),'in',
            '--source',str(self.f.src),'--destination',str(self.f.home),
            '--remote',str(self.f.remote),'--branch','main','--profile','claude-codex',
            '--plan',str(plan),'--scanner',str(self.f.scanner),
            '--approve',w.digest(plan.read_bytes())],expected=75)
        self.assertIn(b'DEFERRED_READERS',result.stdout)

    def test_legacy_writer_and_profile_switch_cannot_bypass(self):
        barrier=self.f.src/'.git/ai-agent-sync.lock'
        self.assertTrue(barrier.is_dir())
        with self.assertRaises(FileExistsError):barrier.mkdir()
        reader=self.reader()
        doc,_,_=b.planned(self.f.options('codex'))  # Planning while active is safe.
        before=b.receipt(self.f.state)
        with self.assertRaises(w.Block):self.f.deploy('codex')
        self.assertEqual(before,b.receipt(self.f.state));self.assertTrue(reader.exists())


if __name__=='__main__':unittest.main()

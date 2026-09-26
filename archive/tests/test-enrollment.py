#!/usr/bin/env python3
"""Enrollment ordering, hard-crash/recovery and readiness, isolated repos only."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('test-bootstrap.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
b,w=f.b,f.w

WORKER='''import sys,os,json
from pathlib import Path
from types import SimpleNamespace
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
import bootstrap as b
w=b.w
options=SimpleNamespace(**json.loads(Path(sys.argv[2]).read_text()))
checkpoint=sys.argv[3];state=Path(options.state);source=Path(options.source);home=Path(options.destination)
atomic=w.atomic
unlink=Path.unlink
sync=w.fsync_dir
def checked(path,value):
 atomic(path,value)
 hit=(checkpoint=='owner' and path==source/'.git/ai-agent-sync.lock/owner.json' and b'cohort-v1' in value[0]) or (checkpoint=='marker' and path==source/'.git/ai-agent-cohort.json') or (checkpoint=='target' and path==home/'.codex/AGENTS.md') or (checkpoint=='receipt' and path==state/'receipt.json') or (checkpoint=='committed' and path==state/'journal.json' and b'"phase":"committed"' in value[0])
 if hit:os._exit(91)
def removed(path,*args,**kwargs):
 result=unlink(path,*args,**kwargs)
 if checkpoint=='journal-removed' and path==state/'journal.json':os._exit(91)
 return result
def synced(path):
 sync(path)
 if checkpoint=='barrier-durable' and path==source/'.git' and (source/'.git/ai-agent-cohort.json').exists():os._exit(91)
w.atomic=checked;Path.unlink=removed;w.fsync_dir=synced
b.apply(options)
'''


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.f=f.BootstrapTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.marker=self.f.src/'.git/ai-agent-cohort.json'
        self.mutex=self.f.src/'.git/ai-agent-cohort.lock'
        self.owner=self.f.src/'.git/ai-agent-sync.lock/owner.json'

    def options(self,stamp=0):
        options=self.f.options('codex');doc,_,_=b.planned(options)
        doc['created']-=stamp
        options.plan=str(self.f.state/('approval-'+str(time.time_ns())+'.json'))
        options.approve=w.digest(w.encoded(doc));b.save(Path(options.plan),doc,True)
        return options

    def verify(self):
        doc=b.receipt(self.f.state)
        self.assertIsNotNone(doc)
        b.verify_receipt(doc,self.f.src,self.f.home,self.f.state)

    def test_receipt_publication_requires_durable_barrier_and_lock(self):
        options=self.options();atomic=w.atomic;observations=[]
        def inspect(path,value):
            if path==self.f.state/'receipt.json':
                self.assertEqual(w.cohort_metadata(self.f.src)['state'],str(self.f.state))
                with self.assertRaises(w.Block):
                    with w.lock(self.f.src,allow_pending=True):pass
                self.assertTrue((self.f.state/'journal.json').exists())
                observations.append('barrier-held-before-receipt')
            return atomic(path,value)
        with patch.object(w,'atomic',inspect),contextlib.redirect_stdout(io.StringIO()):b.apply(options)
        self.assertEqual(observations,['barrier-held-before-receipt']);self.verify()
        inode=self.mutex.stat().st_ino
        self.f.deploy('codex');self.verify();self.assertEqual(inode,self.mutex.stat().st_ino)

    def test_barrier_fsync_failure_never_publishes_receipt(self):
        options=self.options();sync=w.fsync_dir
        def failed(path):
            if path==self.f.src/'.git' and self.marker.exists():raise OSError('fixture fsync failure')
            return sync(path)
        with patch.object(w,'fsync_dir',failed),self.assertRaises(w.Block):b.apply(options)
        self.assertIsNone(b.receipt(self.f.state))
        self.assertTrue((self.f.state/'journal.json').exists())
        with self.assertRaises(w.Block):self.f.deploy('codex')
        with patch.object(w,'sync_cohort',wraps=w.sync_cohort) as flush,contextlib.redirect_stdout(io.StringIO()):b.recover(options)
        flush.assert_called_once_with(self.f.src)
        retry=self.options();doc=b.load(Path(retry.plan))
        doc['created']=b.load(Path(options.plan))['created']-1
        retry.approve=w.digest(w.encoded(doc));b.save(Path(retry.plan),doc)
        with patch.object(w,'sync_cohort',wraps=w.sync_cohort) as flush,contextlib.redirect_stdout(io.StringIO()):b.apply(retry)
        flush.assert_called_once_with(self.f.src)
        self.verify()

    def test_hard_crash_boundaries_fail_closed_recover_and_rerun(self):
        # Each subcase owns an independent source/HOME; no production lock repair.
        for checkpoint in ('owner','marker','barrier-durable','target','receipt','committed','journal-removed'):
            with self.subTest(checkpoint=checkpoint):
                nested=EnrollmentTests();nested.setUp()
                try:
                    options=nested.options()
                    config=nested.f.state/'options.json';b.save(config,vars(options),True)
                    result=subprocess.run([sys.executable,'-B','-c',WORKER,str(ROOT/'bootstrap'),str(config),checkpoint],
                                          env=nested.f.env,capture_output=True,timeout=30)
                    self.assertEqual(result.returncode,91,result.stderr.decode())
                    journal=nested.f.state/'journal.json'
                    if checkpoint=='journal-removed':
                        nested.verify();self.assertFalse(journal.exists())
                    else:
                        self.assertTrue(journal.exists())
                        with self.assertRaises((w.Block,OSError)):
                            b.verify_receipt(b.receipt(nested.f.state),nested.f.src,nested.f.home)
                        with self.assertRaises(w.Block):
                            with w.lock(nested.f.src):pass
                        with self.assertRaises(w.Block):nested.f.deploy('codex')
                        # Kernel lock is released by process death; exact journal
                        # approval is still required. Missing handoff marker is
                        # reconstructed only under that lock from this plan.
                        with contextlib.redirect_stdout(io.StringIO()):b.recover(options)
                        self.assertIsNone(b.receipt(nested.f.state))
                        retry=nested.options()
                        replanned=b.load(Path(retry.plan))
                        replanned['created']=b.load(Path(options.plan))['created']-1
                        retry.approve=w.digest(w.encoded(replanned));b.save(Path(retry.plan),replanned)
                        with contextlib.redirect_stdout(io.StringIO()):b.apply(retry)
                        nested.verify()
                    nested.f.deploy('codex');nested.verify()
                finally:nested.doCleanups()

    def test_old_gap_and_damaged_barriers_never_become_no_changes(self):
        self.f.deploy('codex');doc=b.receipt(self.f.state)
        for path in (self.marker,self.mutex,self.owner):
            old=w.read(path);path.unlink()
            try:
                with self.assertRaises((w.Block,OSError)):b.verify_receipt(doc,self.f.src,self.f.home)
                with self.assertRaises((w.Block,OSError)):self.f.deploy('codex')
                with patch.object(f.launch,'exec_cli') as native,self.assertRaises((w.Block,OSError)):
                    f.launch.launch(self.f.state,'codex',['--version'],offline=True)
                native.assert_not_called()
            finally:w.atomic(path,old)
        self.verify()

    def test_administrative_and_inactive_launches_do_not_bypass_guardian(self):
        self.f.deploy('claude-codex');self.f.deploy('claude')
        for agent,args in [('claude',['--version']),('codex',['exec'])]:
            with patch.object(f.launch,'attempt') as refresh,patch.object(f.guardian,'identity',return_value={'fixture':True}),patch.object(f.guardian,'arm',side_effect=w.Block(69,'GUARDIAN_START_FAILED')),patch.object(f.launch,'exec_cli') as native:
                with self.assertRaises(w.Block):f.launch.launch(self.f.state,agent,args)
                refresh.assert_not_called();native.assert_not_called()

    def test_fallback_requires_successful_guardian_admission(self):
        self.f.deploy('codex')
        with patch.object(f.launch,'attempt',side_effect=w.Block(69,'SCANNER_ERROR')),patch.object(f.guardian,'identity',return_value={'fixture':True}),patch.object(f.guardian,'arm',side_effect=w.Block(69,'GUARDIAN_START_FAILED')),patch.object(f.launch,'exec_cli') as native:
            with self.assertRaises(w.Block) as error:f.launch.launch(self.f.state,'codex',['exec'])
            self.assertEqual(error.exception.label,'GUARDIAN_START_FAILED')
            native.assert_not_called()
        self.verify()
        self.assertTrue(w.active_readers(self.f.src))  # Failed reservation cannot authorize a writer.
        with self.assertRaises(w.Block):
            with w.lock(self.f.src):pass

    def test_bootstrap_rollback_refuses_a_reader_with_valid_recovery_plan(self):
        self.f.deploy('claude-codex');options=self.options()
        with patch.object(b,'put',side_effect=OSError('fixture write interruption')),self.assertRaises(w.Block):b.apply(options)
        reader=self.f.src/'.git/ai-agent-launch-readers'/('b'*32)
        reader.parent.mkdir(mode=0o700);b.save(reader,dict(state='FIXTURE_READER'),True)
        before=b.refs(b.values(self.f.home,b.a.mapping('claude-codex')[1]))
        with self.assertRaises(w.Block) as error:b.recover(options)
        self.assertEqual(error.exception.label,'BLOCKED_ACTIVE_LAUNCH')
        self.assertEqual(before,b.refs(b.values(self.f.home,b.a.mapping('claude-codex')[1])))
        self.assertTrue((self.f.state/'journal.json').exists())
        reader.unlink();reader.parent.rmdir()  # Remove only this harness's synthetic record.
        with contextlib.redirect_stdout(io.StringIO()):b.recover(options)
        self.verify()

    def test_journal_blocks_manual_engine_and_guardian_recovery(self):
        self.f.deploy('codex');before=b.receipt(self.f.state)
        b.save(self.f.state/'journal.json',{'fixture':'pending'},True)
        with self.assertRaises(w.Block):b.verify_receipt(before,self.f.src,self.f.home)
        with self.assertRaises(w.Block):
            with w.lock(self.f.src,allow_readers=True):pass
        with b.engine(self.f.src,self.f.home,'codex',str(self.f.scanner),str(self.f.remote)) as engine:
            engine.build()
            with self.assertRaises(w.Block):engine.execute()


if __name__=='__main__':unittest.main()

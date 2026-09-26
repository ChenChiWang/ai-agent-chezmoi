#!/usr/bin/env python3
"""Owned PATH lifecycle and bounded artifact extraction, disposable HOME only."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bootstrap'))
import bootstrap as b
import tools
import artifacts
spec=importlib.util.spec_from_file_location('path_integration',ROOT/'bootstrap/path-integration.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
w=b.w


class PathTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(dir='/tmp',prefix='path-fixture-');self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve();self.home=self.root/'home';self.home.mkdir()
        self.prefix=self.root/'tool prefix';self.prefix.mkdir(mode=0o700)
        self.state=self.root/'state';self.state.mkdir(mode=0o700)
        self.lock=dict(tools={})
        for name in sorted(tools.selected('claude-codex')-{'python'}):
            item=dict(kind='raw',version='1.2.3',sha256='a'*64)
            path=self.prefix/(name+'-1.2.3')
            if name=='node':
                item['kind']='tree';(path/'bin').mkdir(parents=True)
                for command in ('node','npm','npx'):
                    binary=path/'bin'/command;binary.write_text('#!/bin/sh\necho '+command+'-fixture\n');binary.chmod(0o755)
            else:
                path.write_text('#!/bin/sh\nprintf "%s\\n" "'+name+'-fixture" "$@"\n');path.chmod(0o755)
            b.save(self.prefix/(path.name+'.json'),dict(artifact=item['sha256'],binary=artifacts.fingerprint(path)),True)
            self.lock['tools'][name]=item
        self.original=b'# existing user config\nexport FIXTURE_VALUE=preserved\n'
        (self.home/'.zshrc').write_bytes(self.original)

    def plan(self,profile='claude-codex'):
        return p.plan(self.prefix,self.home,self.state,self.lock,profile)

    def apply(self,doc):return p.apply(doc,w.digest(w.encoded(doc)))

    def test_three_profiles_path_rerun_and_switch(self):
        for profile in ('codex','claude','claude-codex','codex','claude-codex'):
            doc=self.plan(profile);self.assertEqual(self.apply(doc),'PATH_READY')
            before={x.name:x.read_bytes() for x in self.home.iterdir()}
            self.apply(self.plan(profile));self.assertEqual(before,{x.name:x.read_bytes() for x in self.home.iterdir()})
            self.assertTrue((self.home/'.zshrc').read_bytes().startswith(self.original))
            self.assertEqual((self.home/'.zshrc').read_bytes().count(b'# ai-agent bootstrap PATH'),1)
            for mode in ('-lc','-ic'):
                result=subprocess.run(['/bin/zsh',mode,'git "a b"'],env=dict(HOME=str(self.home),PATH='/usr/bin:/bin'),capture_output=True,timeout=15)
                self.assertEqual(result.returncode,0)
                self.assertEqual(result.stdout,b'git-fixture\na b\n')
        metadata=b''.join(x.read_bytes() for x in self.state.iterdir())
        self.assertNotIn(self.original,metadata)
        self.assertNotIn(b'FIXTURE_VALUE',metadata)

    def test_unknown_command_and_shell_edit_are_preserved(self):
        (self.prefix/'bin').mkdir();unknown=self.prefix/'bin/git';unknown.write_text('unknown')
        with self.assertRaises(w.Block):self.plan()
        self.assertEqual(unknown.read_text(),'unknown');unknown.unlink()
        self.apply(self.plan())
        shell=self.home/'.zshrc';shell.write_bytes(shell.read_bytes()+b'# third party edit\n')
        before=shell.read_bytes()
        with self.assertRaises(w.Block):self.plan()
        self.assertEqual(before,shell.read_bytes())

    def test_interrupted_path_apply_recovery_and_conflict(self):
        doc=self.plan();original=w.atomic
        def fail(path,value):
            if path==self.home/'.zshrc':raise OSError('fixture interruption')
            return original(path,value)
        with patch.object(w,'atomic',fail),self.assertRaises(OSError):self.apply(doc)
        with self.assertRaises(w.Block):self.plan()
        self.assertEqual(p.apply(doc,w.digest(w.encoded(doc)),recovery=True),'PATH_READY')
        self.apply(self.plan())

    def test_tool_drift_and_stale_approval(self):
        doc=self.plan();(self.home/'.zshrc').write_bytes(b'changed\n')
        with self.assertRaises(w.Block):self.apply(doc)
        self.assertFalse((self.prefix/'bin').exists())
        (self.prefix/'codex-1.2.3').write_text('changed')
        with self.assertRaises(w.Block):self.plan('codex')


class TreeTests(unittest.TestCase):
    def archive(self,links):
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w:gz') as archive:
            entry=tarfile.TarInfo('tool/bin/native');entry.size=2;archive.addfile(entry,io.BytesIO(b'ok'))
            for name,target in links:
                entry=tarfile.TarInfo('tool/'+name);entry.type=tarfile.SYMTYPE;entry.linkname=target;archive.addfile(entry)
        return out.getvalue()

    def test_tree_links_and_escape(self):
        for links in [[('bin/alias','/etc/passwd')],[('bin/alias','../../escape')],[('bin','elsewhere')]]:
            with tempfile.TemporaryDirectory(dir='/tmp') as tmp,self.assertRaises(w.Block):
                artifacts.extract(self.archive(links),Path(tmp).resolve()/'tree','tool')
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root=Path(tmp).resolve()/'tree';artifacts.extract(self.archive([('bin/alias','native')]),root,'tool')
            self.assertEqual((root/'bin/alias').read_bytes(),b'ok')
            before=artifacts.fingerprint(root);(root/'bin/native').write_bytes(b'changed')
            self.assertNotEqual(before,artifacts.fingerprint(root))


if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
"""Deterministic loading races; fixture readers are NOT native CLI evidence."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import loading_snapshot_model as model
b, w = model.b, model.b.w
spec = importlib.util.spec_from_file_location('bootstrap_tests', Path(__file__).with_name('test-bootstrap.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def reader(first, second):
    # Process rendezvous, no timing/sleep assumptions. First read then wait for
    # the writer's acknowledgement before the second open.
    return subprocess.Popen([sys.executable, '-B', '-c',
        'import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_bytes().hex(),flush=True);'
        'sys.stdin.readline();print(pathlib.Path(sys.argv[2]).read_bytes().hex(),flush=True)',
        str(first), str(second)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)


class EngineRaceTests(unittest.TestCase):
    def test_real_engine_mixed_targets_both_agents(self):
        f = fixtures.BootstrapTests()
        f.setUp()
        try:
            f.deploy()
            other = f.root / 'other'
            f.run_cmd(['git', 'clone', str(f.remote), str(other)])
            for relative in ('shared/instructions.md', 'shared/skills/review/SKILL.md'):
                p = other / b.a.PREFIX / relative
                p.write_bytes(p.read_bytes() + b'\nGENERATION_B\n')
            for cmd in (('add', '.'), ('commit', '-qm', 'generation B'), ('push', 'origin', 'main')):
                f.run_cmd(['git', '-C', str(other), *cmd])
            pairs = [('.claude/CLAUDE.md', '.claude/skills/review/SKILL.md'),
                     ('.codex/AGENTS.md', '.agents/skills/review/SKILL.md')]
            observations = {}
            original = w.atomic
            def interrupted(path, value):
                original(path, value)
                # Suspend the actual engine after it replaces this target.
                for rule, skill in pairs:
                    if path == f.home / rule:
                        proc = reader(f.home / rule, f.home / skill)
                        try:
                            first = bytes.fromhex(proc.stdout.readline().strip())
                            out, err = proc.communicate('\n', timeout=10)
                            self.assertEqual(proc.returncode, 0, err)
                            observations[rule] = (b'GENERATION_B' in first,
                                                  b'GENERATION_B' in bytes.fromhex(out.strip()))
                        finally:
                            if proc.poll() is None:
                                proc.kill(); proc.communicate()
            with patch.object(w, 'atomic', interrupted), contextlib.redirect_stdout(io.StringIO()):
                fixtures.launch.attempt(f.state, scanner=str(f.scanner))
            self.assertEqual(observations, {p[0]: (True, False) for p in pairs})
            b.verify_receipt(b.receipt(f.state), f.src, f.home)
        finally:
            f.doCleanups()


class SnapshotModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='loading-race-', dir='/tmp')
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.cleanup)
        self.store = self.root / 'generations'; self.store.mkdir(mode=0o700)

    def cleanup(self):
        # Only disposable fixture directories; production generations have no GC.
        for p in self.root.rglob('*'):
            if p.is_dir() and not p.is_symlink():
                p.chmod(0o700)
        self.temp.cleanup()

    def payload(self, tag, profile='claude-codex'):
        return {name: (tag, 0o644) for name in b.a.mapping(profile)[1]}

    def test_atomic_pointer_alone_still_mixes_revisions(self):
        a = model.publish(self.store, 'claude-codex', self.payload(b'A'))
        current = self.root / 'current'; current.symlink_to(a, target_is_directory=True)
        proc = reader(current / '.claude/CLAUDE.md', current / '.claude/skills/review/SKILL.md')
        try:
            self.assertEqual(bytes.fromhex(proc.stdout.readline().strip()), b'A')
            newer = model.publish(self.store, 'claude-codex', self.payload(b'B'))
            staged = self.root / 'next'; staged.symlink_to(newer, target_is_directory=True)
            os.replace(staged, current)
            out, err = proc.communicate('\n', timeout=10)
            self.assertEqual(proc.returncode, 0, err)
            self.assertEqual(bytes.fromhex(out.strip()), b'B')
        finally:
            if proc.poll() is None:
                proc.kill(); proc.communicate()

    def test_pinned_generation_survives_publish_without_reader_lease(self):
        for profile in b.PROFILES:
            with self.subTest(profile=profile):
                model.publish(self.store, profile, self.payload(b'A', profile))
                pinned = model.pin(self.store)
                names = b.a.mapping(profile)[1]
                proc = reader(pinned / names[0], pinned / names[-1])
                try:
                    self.assertEqual(bytes.fromhex(proc.stdout.readline().strip()), b'A')
                    model.publish(self.store, profile, self.payload(b'B', profile))
                    out, err = proc.communicate('\n', timeout=10)
                    self.assertEqual(proc.returncode, 0, err)
                    self.assertEqual(bytes.fromhex(out.strip()), b'A')
                    self.assertEqual((model.pin(self.store) / names[0]).read_bytes(), b'B')
                    self.assertEqual({p.read_bytes() for p in (pinned / n for n in names)}, {b'A'})
                finally:
                    if proc.poll() is None:
                        proc.kill(); proc.communicate()

    def test_prepublication_failure_and_rerun(self):
        original = model.publish(self.store, 'codex', self.payload(b'A', 'codex'))
        before = (self.store / 'CURRENT').read_bytes()
        def fault():
            raise OSError('injected prepublication failure')
        with self.assertRaises(OSError):
            model.publish(self.store, 'codex', self.payload(b'B', 'codex'), fault)
        self.assertEqual(model.pin(self.store), original)
        self.assertEqual((self.store / 'CURRENT').read_bytes(), before)
        newer = model.publish(self.store, 'codex', self.payload(b'B', 'codex'))
        self.assertEqual(model.publish(self.store, 'codex', self.payload(b'B', 'codex')), newer)

    def test_unknown_credentials_escape_and_tamper_rejected(self):
        for name in ('.codex/auth.json', '.claude/.credentials.json', '../escape', '/escape'):
            payload = self.payload(b'A', 'codex'); payload[name] = (b'SYNTHETIC_ONLY', 0o600)
            with self.assertRaises(ValueError):
                model.publish(self.store, 'codex', payload)
        self.assertFalse(list(self.store.iterdir()))
        generation = model.publish(self.store, 'codex', self.payload(b'A', 'codex'))
        target = generation / '.codex/AGENTS.md'; target.chmod(0o600); target.write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            model.pin(self.store)


if __name__ == '__main__':
    unittest.main()

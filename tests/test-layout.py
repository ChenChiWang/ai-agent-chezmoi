#!/usr/bin/env python3
"""Production-shaped HOME fixtures only; never discover a user's real source."""
import importlib.util
import json
import os
import stat
from pathlib import Path
import unittest
from unittest.mock import patch


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, (Path(__file__).parent / filename).resolve())
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


migration = module('layout_migration', 'test-migration.py')
write = module('layout_write', 'test-write.py')
api = migration.API


class NestedMigrationTests(migration.MigrationTests):
    # Run the complete existing contract with source under the destination HOME.
    nested_layout = True

    def test_unmanaged_home_and_source_are_not_walked_or_scanned(self):
        external = self.root / 'outside'
        external.mkdir()
        secret = external / 'sentinel'
        secret.write_bytes(b'SYNTHETIC_TEST_SECRET')
        unrelated = self.dst / 'Documents/unrelated'
        unrelated.mkdir(parents=True)
        (unrelated / 'link').symlink_to(external, target_is_directory=True)
        os.mkfifo(unrelated / 'fifo')
        ignored = self.src / 'unrelated'
        ignored.mkdir()
        (ignored / 'secret').write_bytes(secret.read_bytes())
        (ignored / 'link').symlink_to(external, target_is_directory=True)
        os.mkfifo(ignored / 'fifo')
        engine_module = module('layout_converter', '../examples/chezmoi/.chezmoitemplates/ai/shared/scripts/sync-migrate.py')
        # Verify alias inspection does not enumerate unrelated source or HOME.
        instance = object.__new__(engine_module.Migration)
        instance.src = self.src
        original = os.walk
        def bounded_walk(root, *args, **kwargs):
            self.assertNotEqual(Path(root), self.dst)
            for parent, dirs, files in original(root, *args, **kwargs):
                self.assertFalse(Path(parent) == ignored or ignored in Path(parent).parents)
                yield parent, dirs, files
        with patch.object(engine_module.os, 'walk', side_effect=bounded_walk):
            instance.layout(True)
        self.migration('plan')
        self.migration('apply')
        self.status()
        self.local_in()
        self.migration('verify')
        self.migration('rollback')
        self.assertEqual(secret.read_bytes(), b'SYNTHETIC_TEST_SECRET')
        self.assertEqual((ignored / 'secret').read_bytes(), secret.read_bytes())
        self.assertTrue((unrelated / 'link').is_symlink())
        self.assertTrue((ignored / 'link').is_symlink())
        self.assertTrue(stat.S_ISFIFO((unrelated / 'fifo').stat().st_mode))
        self.assertTrue(stat.S_ISFIFO((ignored / 'fifo').stat().st_mode))

    def test_backup_stays_external_and_manifest_cannot_escape(self):
        self.migration('plan', expected=65, backup=self.dst / 'backup')
        self.assertFalse((self.dst / 'backup').exists())
        self.migration('plan')
        document = json.loads((self.backup / 'manifest.json').read_bytes())
        document['after']['target']['../outside'] = None
        (self.backup / 'manifest.json').write_text(json.dumps(document))
        before = self.state()
        self.migration('apply', expected=65)
        self.assertEqual(before, self.state())


class NestedWriteTests(write.WriteTests):
    nested_layout = True

    def status(self, expected=0):
        return self.run_cmd(['sh', write.ENGINE, 'status', '--source', self.src,
                             '--destination', self.dst, '--scanner', self.scanner], expected)

    def test_home_sentinels_survive_status_plan_in_and_push(self):
        untracked = self.dst / 'Documents'
        untracked.mkdir()
        sentinel = untracked / 'secret'
        sentinel.write_bytes(b'SYNTHETIC_TEST_SECRET')
        os.mkfifo(untracked / 'fifo')
        (untracked / 'source-link').symlink_to(self.src, target_is_directory=True)
        self.status()
        self.edit()
        self.plan('in')
        self.execute('in')
        self.planfile.unlink()
        self.plan('push')
        self.execute('push')
        self.status()
        self.assertEqual(sentinel.read_bytes(), b'SYNTHETIC_TEST_SECRET')
        self.assertTrue((untracked / 'source-link').is_symlink())
        self.assertTrue(stat.S_ISFIFO((untracked / 'fifo').stat().st_mode))

    def test_all_entrypoints_reject_unsafe_roots_before_lock(self):
        source, destination = self.src, self.dst
        for relative in api['TARGET_REGIONS']:
            moved = destination / relative / 'repo'
            moved.parent.mkdir(parents=True, exist_ok=True)
            source.rename(moved)
            self.src = moved
            try:
                for operation in ('plan', 'in', 'push'):
                    self.call(operation, 65, ['--operation', 'in'] if operation == 'plan'
                              else ['--approve', '0' * 64])
                self.status(65)
                self.run_cmd(['sh', write.ENGINE, 'migration', 'plan', '--mode', 'legacy',
                              '--profile', 'claude', '--source', self.src, '--destination', self.dst,
                              '--branch', 'main', '--backup', self.root / 'backup',
                              '--reference', migration.REFERENCE, '--rules-map', self.root / 'rules.json'], 65)
                self.assertFalse((moved / '.git/ai-agent-sync.lock').exists())
            finally:
                moved.rename(source)
                self.src = source
        for bad_destination in (source, source / 'child'):
            bad_destination.mkdir(exist_ok=True)
            self.dst = bad_destination
            self.plan(expected=65)
            self.status(65)
        self.dst = destination

    def test_managed_links_cannot_alias_source_git_or_external_files(self):
        outside = self.root / 'outside'
        outside.write_bytes(b'external sentinel')
        for root, relative in ((self.src, write.REL), (self.dst, '.claude/CLAUDE.md')):
            path = root / relative
            data, mode = path.read_bytes(), path.stat().st_mode
            for link_target, hard in ((outside, False), (self.src / '.git/HEAD', False),
                                      (outside, True)):
                path.unlink()
                if hard:
                    os.link(link_target, path)
                else:
                    path.symlink_to(link_target)
                try:
                    self.plan(expected=65)
                    self.status(65)
                    self.assertEqual(outside.read_bytes(), b'external sentinel')
                finally:
                    path.unlink()
                    path.write_bytes(data)
                    path.chmod(mode)
        target_dir = self.dst / '.claude/skills'
        held = self.root / 'held-skills'
        target_dir.rename(held)
        target_dir.symlink_to(held, target_is_directory=True)
        self.plan(expected=65)
        self.status(65)

    def test_plan_file_outside_deployment_regions(self):
        # 2026-09-26 起：plan 不得位於部署區域或 source 內，HOME 下其他位置允許。
        for blocked in (self.dst / '.claude/plan.json', self.dst / '.agents/plan.json', self.src / 'plan.json'):
            self.planfile = blocked
            self.plan(expected=65)
            self.assertFalse(self.planfile.exists())
        self.planfile = self.dst / 'plan.json'
        self.plan()
        self.assertTrue(self.planfile.exists())

    def test_status_invalid_profile_remains_usage_error(self):
        self.run_cmd(['sh', write.ENGINE, 'status', '--source', self.src,
                      '--destination', self.dst, '--profile', 'invalid'], 64)

    def test_git_metadata_links_rejected_before_lock(self):
        held = self.root / 'held-objects'
        objects = self.src / '.git/objects'
        objects.rename(held)
        objects.symlink_to(held, target_is_directory=True)
        self.plan(expected=65)
        self.status(65)
        self.assertFalse((self.src / '.git/ai-agent-sync.lock').exists())

    def test_git_alternate_store_not_followed(self):
        alternate = self.src / '.git/objects/info/alternates'
        alternate.write_text(str(self.remote / 'objects') + '\n')
        self.plan(expected=65)
        self.status(65)
        self.assertFalse((self.src / '.git/ai-agent-sync.lock').exists())

    def test_unsafe_mapping_and_scratch_root_rejected(self):
        function = api['validate_layout']
        for invalid in ('../outside', '/absolute'):
            with patch.dict(function.__globals__, mapping=lambda _: ((invalid,), ())):
                with self.assertRaises(ValueError):
                    function(self.src, self.dst, 'claude')
        with self.assertRaises(ValueError):
            function(self.src, Path('/tmp').resolve(), 'claude')


if __name__ == '__main__':
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Real local Git histories/remotes; all mutations inside disposable fixtures."""
import contextlib
import errno
import io
import hashlib
import importlib.util
from types import SimpleNamespace
from unittest.mock import patch
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / 'examples/chezmoi/.chezmoitemplates/ai/shared/scripts/sync.sh'
REL = '.chezmoitemplates/ai/shared/instructions.md'


class WriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ai-write-test-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.src = self.root / 'source 中文 space'
        self.dst = self.root / 'destination 中文 space'
        if getattr(self, 'nested_layout', False):
            self.src = self.dst / '.local/share/chezmoi'
        self.remote = self.root / 'remote.git'
        self.home = self.root / 'home'
        self.home.mkdir()
        self.dst.mkdir()
        self.env = dict(PATH=os.environ['PATH'], HOME=str(self.home), LC_ALL='C',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
                        GIT_TERMINAL_PROMPT='0', GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.test',
                        GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.test')
        shutil.copytree(REPO / 'examples/chezmoi', self.src)
        self.git(self.src, 'init', '-b', 'main')
        self.git(self.src, 'add', '.')
        self.git(self.src, 'commit', '-qm', 'fixture baseline')
        self.git(self.root, 'init', '--bare', str(self.remote))
        self.git(self.src, 'push', str(self.remote), 'main')
        self.scanner = self.root / 'scanner'
        self.scanner.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
root, report = map(pathlib.Path, sys.argv[1:])
secret = any(b'SYNTHETIC_TEST_SECRET' in p.read_bytes() for p in root.rglob('*') if p.is_file())
findings = [{'file': 'source/.chezmoitemplates/ai/shared/instructions.md', 'rule': 'generic-api-key', 'line': 1}] if secret else []
report.write_text(json.dumps(dict(schema=1,status='secret' if secret else 'clean',findings=findings)))
print('UNTRUSTED_TOOL_OUTPUT')
sys.exit(10 if secret else 0)
''')
        self.scanner.chmod(0o755)
        self.planfile = self.root / 'plan.json'
        self.apply()

    def run_cmd(self, cmd, expected=0):
        result = subprocess.run([str(v) for v in cmd], env=self.env, cwd=self.root,
                                capture_output=True, timeout=120)
        self.assertEqual(result.returncode, expected, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
        return result.stdout

    def git(self, cwd, *args):
        return self.run_cmd(['git', '-C', cwd, *args]).decode().strip()

    def apply(self):
        config = self.root / 'config.toml'
        config.touch()
        self.run_cmd(['chezmoi', '--config', config, '--source', self.src, '--destination', self.dst,
                      '--cache', self.root / 'cache', '--persistent-state', self.root / 'state.db',
                      '--no-tty', 'apply', '--force'])

    def call(self, command, expected=0, extra=()):
        args = ['sh', ENGINE, command, '--source', self.src, '--destination', self.dst,
                '--remote', self.remote, '--branch', 'main', '--plan', self.planfile,
                '--scanner', self.scanner, '--author-name', 'Fixture', '--author-email', 'fixture@example.test']
        result = self.run_cmd(args + list(extra), expected)
        self.assertNotIn(b'UNTRUSTED_TOOL_OUTPUT', result)
        self.assertNotIn(b'SYNTHETIC_TEST_SECRET', result)
        return result

    def plan(self, operation='push', expected=0):
        result = self.call('plan', expected, ['--operation', operation])
        if expected == 0:
            self.token = hashlib.sha256(self.planfile.read_bytes()).hexdigest()
            self.assertIn(self.token.encode(), result)
        return result

    def execute(self, operation='push', expected=0):
        return self.call(operation, expected, ['--approve', self.token])

    def edit(self, text='\nFixture shared edit.\n'):
        with (self.src / REL).open('a') as f:
            f.write(text)

    def state(self):
        out = {}
        for label, root in [('source', self.src), ('destination', self.dst), ('remote', self.remote)]:
            for p in root.rglob('*'):
                if p.is_file():
                    out[label + '/' + str(p.relative_to(root))] = (p.read_bytes(), p.stat().st_mode)
        return out

    def incoming(self, text='\nIncoming shared edit.\n', path=REL):
        other = self.root / 'other'
        if not other.exists():
            self.git(self.root, 'clone', '-b', 'main', str(self.remote), str(other))
        with (other / path).open('a') as f:
            f.write(text)
        self.git(other, 'add', path)
        self.git(other, 'commit', '-qm', 'fixture incoming')
        self.git(other, 'push', str(self.remote), 'main')
        return other

    def test_push_plan_read_only_and_scoped_commit(self):
        self.edit()
        (self.src / 'unrelated.txt').write_text('untracked stays local')
        before = self.state()
        self.plan()
        self.assertEqual(before, self.state())
        self.execute()
        self.assertEqual(self.git(self.src, 'rev-parse', 'HEAD'), self.git(self.remote, 'rev-parse', 'main'))
        self.assertEqual(self.git(self.src, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'), REL)
        self.assertEqual(self.git(self.src, 'diff', '--cached', '--name-only'), '')
        self.assertTrue((self.src / 'unrelated.txt').exists())

    def test_incoming_and_render_matches_chezmoi(self):
        self.incoming()
        self.plan('in')
        self.execute('in')
        before = {str(p.relative_to(self.dst)): (p.read_bytes(), p.stat().st_mode) for p in self.dst.rglob('*') if p.is_file()}
        self.apply()
        after = {str(p.relative_to(self.dst)): (p.read_bytes(), p.stat().st_mode) for p in self.dst.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(self.git(self.src, 'status', '--porcelain'), '')
        self.assertIn('Incoming shared edit.', (self.dst / '.codex/AGENTS.md').read_text())

    def test_local_in_preserves_source_and_index(self):
        self.edit()
        original = (self.src / '.git/index').read_bytes()
        head = self.git(self.src, 'rev-parse', 'HEAD')
        self.plan('in')
        self.execute('in')
        self.assertEqual(original, (self.src / '.git/index').read_bytes())
        self.assertEqual(head, self.git(self.src, 'rev-parse', 'HEAD'))
        self.assertIn('Fixture shared edit.', (self.dst / '.claude/CLAUDE.md').read_text())

    def test_no_changes_no_commit(self):
        before = self.state()
        self.plan()
        self.assertIn(b'NO_CHANGES', self.execute())
        self.assertEqual(before, self.state())

    def test_stale_source_destination_index_branch_remote(self):
        self.edit()
        self.plan()
        original = (self.src / REL).read_bytes()
        self.edit('additional change\n')
        self.execute(expected=68)
        (self.src / REL).write_bytes(original)
        target = self.dst / '.claude/CLAUDE.md'
        old = target.read_bytes()
        target.write_bytes(old + b'local drift\n')
        self.execute(expected=2)
        target.write_bytes(old)
        self.git(self.src, 'add', REL)
        self.execute(expected=66)
        self.git(self.src, 'reset', '-q', 'HEAD', '--', REL)
        self.git(self.src, 'checkout', '-b', 'other')
        self.execute(expected=66)
        self.git(self.src, 'checkout', 'main')
        self.incoming()
        self.execute(expected=66)

    def test_staged_unrelated_preserved(self):
        (self.src / 'unrelated').write_text('unrelated')
        self.git(self.src, 'add', 'unrelated')
        before = self.state()
        self.plan(expected=66)
        self.assertEqual(before, self.state())

    def test_local_drift_and_dirty_incoming_blocked(self):
        self.incoming()
        self.edit()
        self.plan('in', expected=66)
        self.git(self.src, 'checkout', '--', REL)
        with (self.dst / '.codex/AGENTS.md').open('a') as f:
            f.write('manual edit')
        self.plan('in', expected=2)

    def test_secret_current_and_removed_history(self):
        self.edit('SYNTHETIC_TEST_SECRET\n')
        self.plan(expected=67)
        self.git(self.src, 'add', REL)
        self.git(self.src, 'commit', '-qm', 'fixture secret')
        self.git(self.src, 'checkout', 'HEAD~1', '--', REL)
        self.git(self.src, 'commit', '-qm', 'fixture removed')
        before = self.state()
        self.plan(expected=67)
        self.assertEqual(before, self.state())

    def test_unrelated_outbound_history(self):
        (self.src / 'unknown').write_text('ordinary content')
        self.git(self.src, 'add', 'unknown')
        self.git(self.src, 'commit', '-qm', 'unknown outbound')
        self.plan(expected=66)

    def test_commit_message_secret(self):
        self.edit()
        self.git(self.src, 'add', REL)
        self.git(self.src, 'commit', '-qm', 'SYNTHETIC_TEST_SECRET')
        self.plan(expected=67)

    def test_scanner_failure_and_changed_scanner(self):
        self.scanner.write_text('#!/bin/sh\nexit 0\n')
        self.plan(expected=70)

    def test_lock_and_recovery_journal(self):
        lock = self.src / '.git/ai-agent-sync.lock'
        lock.mkdir()
        self.plan(expected=73)
        self.assertTrue(lock.exists())
        lock.rmdir()
        (self.src / '.git/ai-agent-sync-transaction').mkdir()
        self.plan(expected=66)

    def test_symlink_and_missing_destination(self):
        target = self.dst / '.codex/AGENTS.md'
        target.unlink()
        target.symlink_to(self.src / REL)
        self.plan(expected=65)
        target.unlink()
        self.plan(expected=70)

    def test_plan_tamper_and_expiry(self):
        self.plan()
        value = json.loads(self.planfile.read_bytes())
        value['created'] = 1
        self.planfile.write_text(json.dumps(value))
        self.execute(expected=68)
        self.token = hashlib.sha256(self.planfile.read_bytes()).hexdigest()
        self.execute(expected=68)

    def test_push_failure_retains_local_commit_and_retry(self):
        self.edit()
        self.plan()
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        before = self.git(self.src, 'rev-parse', 'HEAD')
        self.execute(expected=71)
        after = self.git(self.src, 'rev-parse', 'HEAD')
        self.assertNotEqual(before, after)
        self.assertEqual(self.git(self.src, 'diff', '--cached', '--name-only'), '')
        hook.unlink()
        self.planfile.unlink()
        self.plan()
        self.execute()
        self.assertEqual(after, self.git(self.remote, 'rev-parse', 'main'))

    def test_network_failure_no_source_mutation(self):
        shutil.rmtree(self.remote)
        self.remote.mkdir()
        before = self.state()
        self.plan(expected=71)
        self.assertEqual(before, self.state())

    def test_incoming_unrelated_history(self):
        self.incoming(path='unknown')
        self.plan('in', expected=66)

    def test_source_hooks_and_filters_not_executed(self):
        marker = self.root / 'executed'
        hook = self.src / '.git/hooks/reference-transaction'
        hook.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        hook.chmod(0o755)
        self.git(self.src, 'config', 'filter.bad.clean', 'touch ' + str(marker))
        self.git(self.src, 'config', 'core.fsmonitor', str(hook))
        (self.src / '.git/info/attributes').write_text('* filter=bad\n')
        self.edit()
        self.plan()
        self.execute()
        self.assertFalse(marker.exists())

    def engine_instance(self, operation='in'):
        spec = importlib.util.spec_from_file_location('write_engine', ENGINE.with_name('sync-write.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = self.root / 'engine-work'
        root.mkdir()
        args = SimpleNamespace(source=str(self.src), destination=str(self.dst), remote=str(self.remote),
                               branch='main', scanner=str(self.scanner), operation=operation,
                               message='fixture sync', author_name='Fixture', author_email='fixture@example.test')
        return module, module.Engine(args, root)

    def test_apply_failure_rolls_back_files_index_head(self):
        self.incoming()
        module, engine = self.engine_instance()
        engine.build()
        before = self.state()
        original = module.atomic
        failed = False
        def injected(path, value):
            nonlocal failed
            if path == self.dst / '.codex/AGENTS.md' and not failed:
                failed = True
                raise OSError('injected failure')
            return original(path, value)
        with patch.object(module, 'atomic', side_effect=injected):
            with self.assertRaises(OSError):
                engine.execute()
        # Transferred immutable Git objects may remain; all mutable state restored.
        after = self.state()
        for key, value in before.items():
            self.assertEqual(after[key], value, key)
        self.assertFalse((self.src / '.git/ai-agent-sync-transaction').exists())
        self.assertFalse((self.src / '.git/index.lock').exists())

    def test_ref_failure_rolls_back(self):
        self.incoming()
        module, engine = self.engine_instance()
        engine.build()
        before = self.state()
        original = engine.source_git
        def injected(*args, **kwargs):
            if args[0] == 'update-ref':
                raise module.Block(70, 'GIT_ERROR')
            return original(*args, **kwargs)
        with patch.object(engine, 'source_git', side_effect=injected):
            with self.assertRaises(module.Block):
                engine.execute()
        after = self.state()
        for key, value in before.items():
            self.assertEqual(after[key], value, key)

    def test_concurrent_remote_change_refuses_push(self):
        self.edit()
        module, engine = self.engine_instance('push')
        engine.build()
        self.incoming('\nConcurrent remote edit.\n')
        remote = self.git(self.remote, 'rev-parse', 'main')
        with self.assertRaises(module.Block) as caught:
            engine.execute()
        self.assertEqual(caught.exception.code, 71)
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), remote)

    def test_concurrent_source_edit_before_transaction(self):
        self.edit()
        module, engine = self.engine_instance('push')
        engine.build()
        self.edit('\nConcurrent source edit.\n')
        before = self.state()
        with self.assertRaises(module.Block) as caught:
            engine.execute()
        self.assertEqual(caught.exception.code, 68)
        after = self.state()
        for key, value in before.items():
            self.assertEqual(after[key], value, key)

    def test_real_scanner_write_and_historical_secret(self):
        import random
        self.assertIsNotNone(shutil.which('gitleaks'), 'Gitleaks 8.30.1 required; do not skip')
        self.scanner = ENGINE.with_name('scan-secrets.py')
        self.edit()
        self.plan()
        self.execute()
        self.planfile.unlink()
        rng = random.Random(8245)
        secret = 'gh' + 'p_' + ''.join(rng.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=36))
        self.edit('\n' + secret + '\n')
        result = self.plan(expected=67)
        self.assertNotIn(secret.encode(), result)
        self.git(self.src, 'add', REL)
        self.git(self.src, 'commit', '-qm', 'fixture synthetic secret')
        self.git(self.src, 'checkout', 'HEAD~1', '--', REL)
        self.git(self.src, 'commit', '-qm', 'fixture removed secret')
        result = self.plan(expected=67)
        self.assertNotIn(secret.encode(), result)

    def test_rendered_engine_plan_has_no_destination_writes(self):
        global ENGINE
        previous = ENGINE
        ENGINE = self.dst / '.config/ai-agent/bin/sync.sh'
        try:
            before = self.state()
            self.plan('in')
            self.assertEqual(before, self.state())
            self.execute('in')
            self.assertEqual(before, self.state())
        finally:
            ENGINE = previous

    def test_canonical_source_lock_and_local_remote_spaces(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.src, target_is_directory=True)
        real_source = self.src
        self.src = alias
        lock = real_source / '.git/ai-agent-sync.lock'
        lock.mkdir()
        self.plan(expected=73)
        lock.rmdir()
        moved = self.root / 'remote 中文 space.git'
        self.remote.rename(moved)
        self.remote = moved
        self.plan()
        self.execute()

    def test_rollback_preserves_concurrent_edit_and_journal(self):
        self.incoming()
        module, engine = self.engine_instance()
        engine.build()
        original = module.atomic
        def injected(path, value):
            if path == self.dst / '.codex/AGENTS.md':
                (self.dst / '.claude/CLAUDE.md').write_text('concurrent user edit')
                raise OSError('injected failure')
            return original(path, value)
        with patch.object(module, 'atomic', side_effect=injected):
            with self.assertRaises(module.Block) as caught:
                engine.execute()
        self.assertEqual(caught.exception.code, 72)
        self.assertEqual((self.dst / '.claude/CLAUDE.md').read_text(), 'concurrent user edit')
        self.assertTrue((self.src / '.git/ai-agent-sync-transaction/manifest.json').is_file())

    def diagnostic_failure(self, fault):
        self.incoming()
        module, engine = self.engine_instance()
        engine.build()
        before = self.state()
        head = self.git(self.src, 'rev-parse', 'HEAD')
        original_atomic, original_remove = module.atomic, module.shutil.rmtree
        original_mkdir = Path.mkdir
        secret = 'FAKE_PRIVATE_PAYLOAD_do_not_print'
        journal = self.src / '.git/ai-agent-sync-transaction'
        source_lock = self.src / '.git/ai-agent-sync.lock'
        written = []

        def atomic_failure(path, value):
            if path == self.dst / '.codex/AGENTS.md':
                raise OSError(errno.EIO, secret, '/private/' + secret)
            if (fault == 'rollback' and path == self.dst / '.claude/CLAUDE.md'
                    and path in written):
                raise PermissionError(errno.EACCES, secret)
            result = original_atomic(path, value)
            written.append(path)
            return result

        def mkdir_failure(path, *args, **kwargs):
            if fault == 'before' and path == source_lock:
                raise PermissionError(errno.EPERM, secret, '/private/' + secret)
            return original_mkdir(path, *args, **kwargs)

        def cleanup_failure(path, *args, **kwargs):
            if fault == 'cleanup' and path == journal:
                raise PermissionError(errno.EACCES, secret)
            return original_remove(path, *args, **kwargs)

        def execute_locked():
            module.diagnostics.transaction_started = False
            module.diagnostics.rollback = dict(attempted=False, result='not_attempted')
            with module.lock(self.src):
                engine.execute()
            return 0

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(module, 'main', side_effect=execute_locked), \
                patch.object(module, 'atomic', side_effect=atomic_failure), \
                patch.object(Path, 'mkdir', new=mkdir_failure), \
                patch.object(module.shutil, 'rmtree', side_effect=cleanup_failure), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.cli()
        self.assertEqual(code, 72 if fault == 'rollback' else 70)
        output = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(secret, output)
        self.assertNotIn(str(self.root), output)
        self.assertTrue(stderr.getvalue().startswith('DIAGNOSTIC: '))
        diagnostic = json.loads(stderr.getvalue().removeprefix('DIAGNOSTIC: '))
        self.assertEqual(diagnostic['operation'], 'source_lock' if fault == 'before' else 'apply_files')
        self.assertEqual(diagnostic['phase'], 'coordination' if fault == 'before' else 'transaction')
        self.assertEqual(diagnostic['errno'], errno.EPERM if fault == 'before' else errno.EIO)
        self.assertEqual(diagnostic['exception_type'], 'PermissionError' if fault == 'before' else 'OSError')
        self.assertEqual(diagnostic['location']['file'], 'sync-write.py')
        self.assertIsInstance(diagnostic['location']['line'], int)
        self.assertEqual(diagnostic['transaction_started'], fault != 'before')
        self.assertEqual(diagnostic['rollback'], dict(attempted=fault != 'before',
                         result='not_attempted' if fault == 'before' else
                         'failed' if fault == 'rollback' else 'succeeded'))
        self.assertEqual(self.git(self.src, 'rev-parse', 'HEAD'), head)
        self.assertFalse(source_lock.exists())
        self.assertFalse((self.src / '.git/index.lock').exists())
        self.assertEqual(journal.exists(), fault in ('rollback', 'cleanup'))
        after = self.state()
        for key, value in before.items():
            if fault == 'rollback' and key == 'destination/.claude/CLAUDE.md':
                self.assertNotEqual(after[key], value)
            else:
                self.assertEqual(after[key], value, key)
        if fault == 'before':
            self.assertEqual(before, after)
        else:
            self.assertIn(self.dst / '.claude/CLAUDE.md', written)
        if fault in ('rollback', 'cleanup'):
            self.assertTrue(any(e.get('errno') == errno.EACCES for e in diagnostic['secondary_errors']))
        if fault == 'cleanup':
            self.assertEqual(diagnostic['cleanup']['operations']['remove_journal']['result'], 'failed')
        return diagnostic

    def test_diagnostic_before_write(self):
        self.diagnostic_failure('before')

    def test_diagnostic_after_write_rollback_succeeds(self):
        self.diagnostic_failure('after')

    def test_diagnostic_rollback_failure_preserves_first(self):
        self.diagnostic_failure('rollback')

    def test_diagnostic_cleanup_failure_preserves_first(self):
        self.diagnostic_failure('cleanup')

    def test_existing_coordination_metadata_refused(self):
        # 僅在本測試自行建立的臨時 fixture 檢查拒絕與原樣保留（含 status 與 check）。
        for name in ('ai-agent-cohort.json', 'ai-agent-cohort.lock', 'ai-agent-launch-readers'):
            with self.subTest(name=name):
                path = self.src / '.git' / name
                path.write_text('existing coordination evidence')
                before = self.state()
                output = self.plan(expected=73)
                self.assertIn(b'BLOCKED_UNSUPPORTED_COORDINATION', output)
                self.assertEqual(before, self.state())
                self.assertFalse(self.planfile.exists())
                self.assertFalse((self.src / '.git/ai-agent-sync.lock').exists())
                self.raw(['status', '--source', self.src, '--destination', self.dst, '--scanner', self.scanner], expected=73)
                self.raw(['check', '--source', self.src, '--destination', self.dst, '--remote', self.remote,
                          '--branch', 'main', '--scanner', self.scanner], expected=73)
                path.unlink()

    def test_new_shared_skill_removed_secret_in_outbound_history(self):
        rel = '.chezmoitemplates/ai/shared/skills/review/SKILL.md'
        original = (self.src / rel).read_bytes()
        (self.src / rel).write_bytes(original + b'\nSYNTHETIC_TEST_SECRET\n')
        self.git(self.src, 'add', rel)
        self.git(self.src, 'commit', '-qm', 'fixture skill secret')
        (self.src / rel).write_bytes(original)
        self.git(self.src, 'add', rel)
        self.git(self.src, 'commit', '-qm', 'fixture remove skill secret')
        before = self.state()
        self.plan(expected=67)
        self.assertEqual(before, self.state())

    # ---- 本地參數檔（B）、plan 路徑規則（D2）、例外標籤（D3） ----

    def write_config(self, **extra):
        values = dict(source=str(self.src), destination=str(self.dst), remote=str(self.remote),
                      branch='main', plan_dir=str(self.root / 'plans'), scanner=str(self.scanner),
                      author_name='Fixture', author_email='fixture@example.test')
        values.update(extra)
        config = self.root / 'sync.local.json'
        config.write_text(json.dumps(values))
        config.chmod(0o600)
        return config

    def raw(self, args, expected=0):
        result = subprocess.run(['sh', str(ENGINE), *[str(a) for a in args]], env=self.env, cwd=self.root,
                                capture_output=True, timeout=120)
        output = result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace')
        self.assertEqual(result.returncode, expected, output)
        self.assertNotIn('Traceback', output)
        self.assertNotIn('SYNTHETIC_TEST_SECRET', output)
        return output

    def test_config_supplies_roots_plan_dir_and_locates_plan_by_id(self):
        config = self.write_config()
        self.incoming()
        output = self.raw(['plan', '--operation', 'in', '--config', config])
        plan_file = Path([l for l in output.splitlines() if l.startswith('PLAN_FILE: ')][0][len('PLAN_FILE: '):])
        plan_id = [l for l in output.splitlines() if l.startswith('PLAN_ID: ')][0][len('PLAN_ID: '):]
        self.assertEqual(plan_file.parent, self.root / 'plans')
        self.assertEqual((self.root / 'plans').stat().st_mode & 0o777, 0o700)
        self.assertEqual(hashlib.sha256(plan_file.read_bytes()).hexdigest(), plan_id)
        self.raw(['in', '--config', config, '--approve', plan_id])
        self.assertIn('Incoming shared edit.', (self.dst / '.claude/CLAUDE.md').read_text())
        self.assertIn('PLAN_NOT_FOUND', self.raw(['in', '--config', config, '--approve', '0' * 64], expected=66))

    def test_config_status_and_command_line_override(self):
        config = self.write_config()
        self.assertIn('NO_CHANGES', self.raw(['status', '--config', config]))
        # 命令列優先於參數檔：改指到不存在的分支必須被引擎拒絕。
        self.raw(['plan', '--operation', 'in', '--config', config, '--branch', 'other'], expected=66)
        self.raw(['status', '--config', config, '--profile', 'claude', '--profile', 'claude'], expected=64)

    def test_config_validation(self):
        config = self.write_config(unexpected='value')
        self.assertIn('INVALID_CONFIG', self.raw(['plan', '--operation', 'in', '--config', config], expected=78))
        self.assertIn('INVALID_CONFIG', self.raw(['status', '--config', config], expected=78))
        config = self.write_config()
        config.chmod(0o666)
        self.raw(['status', '--config', config], expected=78)
        config = self.write_config(writer='someone')
        self.raw(['status', '--config', config], expected=78)
        config = self.write_config(plan_dir='relative/plans')
        self.raw(['status', '--config', config], expected=78)
        self.raw(['status', '--config', 'relative.json'], expected=64)

    def test_plan_path_alias_and_deployment_regions(self):
        # 透過 /tmp 這類目錄別名指定 plan 必須可用；部署區域與 source 內部仍被拒絕。
        alias = Path('/tmp') / self.root.name / 'alias-plan.json'
        self.assertTrue(alias.parent.is_dir())
        self.planfile = alias
        self.plan('in')
        self.assertTrue(alias.exists())
        for blocked in (self.dst / '.claude/plan.json', self.dst / '.config/ai-agent/plan.json', self.src / 'plan.json'):
            self.planfile = blocked
            self.assertIn('INVALID_PLAN_PATH', self.call('plan', 65, ['--operation', 'in']).decode())
            self.assertFalse(blocked.exists())
        self.planfile = self.dst / 'plan-in-home.json'
        self.plan('in')
        self.execute('in')

    def test_malformed_plan_document_is_labelled(self):
        self.plan()
        self.planfile.write_bytes(b'[]')
        self.token = hashlib.sha256(self.planfile.read_bytes()).hexdigest()
        output = self.raw(['push', '--source', self.src, '--destination', self.dst, '--remote', self.remote,
                           '--branch', 'main', '--plan', self.planfile, '--scanner', self.scanner,
                           '--approve', self.token], expected=65)
        self.assertIn('INVALID_PLAN', output)
        self.assertIn('DIAGNOSTIC: ', output)

    # ---- check（D1）、auto_in（C）、writer 角色（E） ----

    def test_check_reports_remote_state_and_daily_cache(self):
        config = self.write_config()
        self.assertIn('REMOTE: UP_TO_DATE', self.raw(['check', '--config', config]))
        self.assertIn('CHECKED_TODAY', self.raw(['check', '--config', config]))
        self.assertTrue((self.root / 'plans/last-check.json').is_file())
        self.incoming()
        self.assertIn('REMOTE: BEHIND 1', self.raw(['check', '--config', config, '--force']))
        output = self.raw(['plan', '--operation', 'in', '--config', config])
        plan_id = [l for l in output.splitlines() if l.startswith('PLAN_ID: ')][0][len('PLAN_ID: '):]
        self.raw(['in', '--config', config, '--approve', plan_id])
        self.assertIn('REMOTE: UP_TO_DATE', self.raw(['check', '--config', config, '--force']))
        self.edit()
        self.git(self.src, 'add', REL)
        self.git(self.src, 'commit', '-qm', 'local ahead')
        self.assertIn('REMOTE: AHEAD 1', self.raw(['check', '--config', config, '--force']))
        self.incoming('\nSecond incoming edit.\n')
        self.assertIn('REMOTE: DIVERGED', self.raw(['check', '--config', config, '--force']))
        self.assertEqual(self.git(self.src, 'status', '--porcelain'), '')

    def test_check_skipped_inside_network_disabled_sandbox(self):
        config = self.write_config()
        env = dict(self.env, CODEX_SANDBOX_NETWORK_DISABLED='1')
        shutil.rmtree(self.remote)  # 若真的嘗試連線會失敗；CHECK_SKIPPED 必須在連線前回傳。
        result = subprocess.run(['sh', str(ENGINE), 'check', '--config', str(config), '--agent', 'codex'],
                                env=env, cwd=self.root, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(b'CHECK_SKIPPED', result.stdout)
        self.assertFalse((self.root / 'plans/last-check.json').exists())
        # 今日快取存在時仍優先回 CHECKED_TODAY；非今日快取則附上舊結果與日期。
        (self.root / 'plans').mkdir(exist_ok=True)
        (self.root / 'plans/last-check.json').write_text(json.dumps(dict(checked=86400 * 2, result='UP_TO_DATE')))
        result = subprocess.run(['sh', str(ENGINE), 'check', '--config', str(config), '--agent', 'codex'],
                                env=env, cwd=self.root, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'CHECK_SKIPPED', result.stdout)
        self.assertIn(b'previous result from 1970-01-0', result.stdout)

    def test_check_explicit_options_and_network_failure(self):
        base = ['check', '--source', self.src, '--destination', self.dst, '--remote', self.remote,
                '--branch', 'main', '--scanner', self.scanner]
        self.assertIn('REMOTE: UP_TO_DATE', self.raw(base))
        self.raw(base + ['--plan', self.planfile], expected=64)
        shutil.rmtree(self.remote)
        self.remote.mkdir()
        self.assertIn('NETWORK_ERROR', self.raw(base, expected=71))

    def auto_plan(self, config):
        output = self.raw(['plan', '--operation', 'in', '--config', config])
        lines = output.splitlines()
        return (Path([l for l in lines if l.startswith('PLAN_FILE: ')][0][len('PLAN_FILE: '):]),
                [l for l in lines if l.startswith('PLAN_ID: ')][0][len('PLAN_ID: '):])

    def test_auto_in_shared_text_only(self):
        config = self.write_config(auto_in=True)
        self.incoming()
        plan_file, plan_id = self.auto_plan(config)
        self.assertIn('AUTO_IN', self.raw(['in', '--config', config, '--plan', plan_file]))
        self.assertIn('Incoming shared edit.', (self.dst / '.codex/AGENTS.md').read_text())
        # 腳本變更不得自動套用：回報 PENDING_APPROVAL 與 PLAN_ID，狀態不變；明確核准後才套用。
        self.incoming('\n# incoming script comment\n', path='.chezmoitemplates/ai/shared/scripts/sync.sh')
        plan_file, plan_id = self.auto_plan(config)
        before = self.state()
        output = self.raw(['in', '--config', config, '--plan', plan_file], expected=77)
        self.assertIn('PENDING_APPROVAL', output)
        self.assertIn('PLAN_ID: ' + plan_id, output)
        self.assertEqual(before, self.state())
        self.assertFalse((self.src / '.git/ai-agent-sync.lock').exists())
        self.raw(['in', '--config', config, '--approve', plan_id])
        self.assertIn('incoming script comment', (self.dst / '.config/ai-agent/bin/sync.sh').read_text())
        # 沒有 auto_in 時，缺 --approve 仍是用法錯誤；push 永遠沒有自動模式。
        config = self.write_config()
        self.incoming('\nThird incoming edit.\n')
        plan_file, plan_id = self.auto_plan(config)
        self.raw(['in', '--config', config, '--plan', plan_file], expected=64)
        config = self.write_config(auto_in=True)
        self.raw(['push', '--config', config, '--plan', plan_file], expected=64)

    def test_scp_style_remote_is_normalized(self):
        module, engine = self.engine_instance()
        self.assertEqual(engine.remote_url('git@github.com:user/repo.git'), 'ssh://git@github.com/user/repo.git')
        self.assertEqual(engine.remote_url('ssh://git@github.com/user/repo.git'), 'ssh://git@github.com/user/repo.git')
        for bad in ('git@github.com:/abs/path', 'user@host:a:b', 'http://github.com/user/repo.git', 'github.com:user/repo'):
            with self.assertRaises(module.Block):
                engine.remote_url(bad)

    def test_message_and_identity_taken_from_plan(self):
        config = self.write_config()
        self.edit()
        output = self.raw(['plan', '--operation', 'push', '--config', config, '--message', 'feat: fixture message'])
        plan_id = [l for l in output.splitlines() if l.startswith('PLAN_ID: ')][0][len('PLAN_ID: '):]
        # 不重複帶 --message 也能執行；帶了不同訊息才算不同 plan。
        self.raw(['push', '--config', config, '--approve', plan_id, '--message', 'other'], expected=68)
        self.raw(['push', '--config', config, '--approve', plan_id])
        self.assertEqual(self.git(self.src, 'log', '-1', '--format=%s'), 'feat: fixture message')
        self.assertEqual(self.git(self.src, 'log', '-1', '--format=%an'), 'Fixture')

    def test_writer_role(self):
        config = self.write_config(writer='claude')
        self.assertIn('NOT_WRITER', self.raw(['in', '--config', config, '--agent', 'codex', '--approve', '0' * 64], expected=77))
        self.assertIn('NOT_WRITER', self.raw(['push', '--config', config, '--agent', 'codex', '--approve', '0' * 64], expected=77))
        self.raw(['status', '--config', config, '--agent', 'codex'])
        self.raw(['check', '--config', config, '--agent', 'codex'])
        self.raw(['plan', '--operation', 'in', '--config', config, '--agent', 'codex'])
        self.incoming()
        plan_file, plan_id = self.auto_plan(config)
        self.raw(['in', '--config', config, '--agent', 'claude', '--approve', plan_id])
        self.incoming('\nSecond incoming edit.\n')
        plan_file, plan_id = self.auto_plan(config)
        self.raw(['in', '--config', config, '--approve', plan_id])  # 無 --agent 的人工呼叫不受角色限制


if __name__ == '__main__':
    unittest.main()

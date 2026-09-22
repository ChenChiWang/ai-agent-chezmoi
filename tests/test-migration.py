#!/usr/bin/env python3
"""Synthetic legacy fixtures only. No private production source participates."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'examples/chezmoi'
SCRIPTS = REFERENCE / '.chezmoitemplates/ai/shared/scripts'
ENGINE = SCRIPTS / 'sync.sh'
API = runpy.run_path(str(SCRIPTS / 'scan-secrets.py'))


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ai-legacy-fixture-', dir='/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.src, self.dst = self.root / 'legacy 中文 source', self.root / 'home 中文 destination'
        if getattr(self, 'nested_layout', False):
            self.src = self.dst / '.local/share/chezmoi'
        self.dst.mkdir()
        self.src.mkdir(parents=True)
        (self.root / 'tool-home').mkdir()
        self.env = dict(PATH=os.environ['PATH'], HOME=str(self.root / 'tool-home'), LC_ALL='C',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0',
                        GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.test',
                        GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.test')
        self.segments = [
            dict(kind='shared', text='# User rules\nUse Traditional Chinese. Keep user data intact.\n'),
            dict(kind='claude', text='\n# Claude preferences\nPreserve my Claude workflow and settings.\n'),
            dict(kind='retire-sync', text='\n# dotfiles-sync legacy trigger\nRun legacy in automatically at session start.\n'),
            dict(kind='shared', text='\n# More user rules\nAsk before destructive operations. No AI commit signatures.\n')]
        self.legacy_rules = ''.join(v['text'] for v in self.segments).encode()
        self.put('dot_claude/CLAUDE.md', self.legacy_rules)
        self.settings = b'{"model":"fixture-model","statusLine":{"type":"command","command":"printf fixture"},"tui":{"fixture":true}}\n'
        self.put('dot_claude/settings.json', self.settings)
        self.skills = {}
        for skill in API['SKILLS']:
            data = ('---\nname: ' + skill + '\ndescription: Synthetic legacy fixture for ' + skill + '.\n---\n\n'
                    '# ' + skill + '\nPreserve the existing project-specific ' + skill + ' behavior.\n').encode()
            if skill == 'd3-component':
                data += b'\n<Chart style={{ color: "red" }} />\nLiteral {{ output "sh" "-c" "exit 99" }} remains text.\n'
            self.skills[skill] = data
            self.put('dot_claude/skills/' + skill + '/SKILL.md', data)
        self.put('dot_claude/skills/dotfiles-sync/executable_sync.sh', b'#!/bin/sh\necho LEGACY_MUTATION_ATTEMPT\nexit 99\n')
        self.put('.chezmoiignore', b'.gitignore\n.gitattributes\nREADME.md\n# retained legacy exclusion\n.claude/settings.local.json\n')
        self.put('.gitignore', b'.DS_Store\n')
        self.put('.gitattributes', b'* text eol=lf\n')
        self.put('README.md', b'Unrelated tracked file must survive conversion.\n')
        self.git('init', '-b', 'main')
        self.git('add', '.')
        self.git('commit', '-qm', 'synthetic legacy baseline')
        self.head = self.git('rev-parse', 'HEAD')
        self.rules_map = self.root / 'rules-map.json'
        self.rules_map.write_text(json.dumps(dict(schema=1, segments=self.segments)))
        self.backup = self.root / 'baseline'
        self.scanner = self.root / 'fixture-scanner'
        self.scanner.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
snapshot, report = map(pathlib.Path, sys.argv[1:])
secret = any(b'SYNTHETIC_TEST_SECRET' in p.read_bytes() for p in snapshot.rglob('*') if p.is_file())
findings = [{'file':'source/.chezmoitemplates/ai/shared/instructions.md','rule':'generic-api-key','line':1}] if secret else []
report.write_text(json.dumps(dict(schema=1,status='secret' if secret else 'clean',findings=findings)))
print('UNTRUSTED_SCANNER_OUTPUT')
sys.exit(10 if secret else 0)
''')
        self.scanner.chmod(0o755)
        self.cm('apply', '--force')
        for rel in ('.claude/.credentials.json', '.claude/settings.local.json', '.codex/auth.json'):
            p = self.dst / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'SYNTHETIC_RUNTIME_STATE_DO_NOT_MIGRATE\n')
        self.before = self.state()

    def put(self, rel, data):
        p = self.src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def run_command(self, command, expected=0):
        p = subprocess.run([str(x) for x in command], cwd=self.root, env=self.env, capture_output=True, timeout=180)
        self.assertEqual(p.returncode, expected, p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace'))
        self.assertNotIn(b'SYNTHETIC_TEST_SECRET', p.stdout + p.stderr)
        self.assertNotIn(b'UNTRUSTED_SCANNER_OUTPUT', p.stdout + p.stderr)
        self.assertNotIn(b'LEGACY_MUTATION_ATTEMPT', p.stdout + p.stderr)
        return p.stdout

    def git(self, *args):
        return self.run_command(['git', '-C', self.src, *args]).decode().strip()

    def cm(self, *args):
        config = self.root / 'config.toml'
        config.touch()
        return self.run_command(['chezmoi', '--config', config, '--source', self.src, '--destination', self.dst,
                                 '--cache', self.root / 'cache', '--persistent-state', self.root / 'state.db',
                                 '--refresh-externals=never', '--no-tty', *args])

    def state(self):
        result = {}
        for label, root in [('source', self.src), ('target', self.dst)]:
            for p in root.rglob('*'):
                if p.is_symlink():
                    result[label + '/' + str(p.relative_to(root))] = ('symlink', os.readlink(p))
                elif p.is_file():
                    result[label + '/' + str(p.relative_to(root))] = (p.read_bytes(), p.stat().st_mode)
        return result

    def migration(self, command, expected=0, profile='claude', backup=None, extra=()):
        backup = backup or self.backup
        args = ['sh', ENGINE, 'migration', command, '--source', self.src, '--destination', self.dst,
                '--backup', backup, '--branch', 'main', '--profile', profile, '--scanner', self.scanner]
        if command == 'plan':
            args += ['--reference', REFERENCE, '--mode', 'legacy' if profile == 'claude' else 'enable-codex']
            if profile == 'claude':
                args += ['--rules-map', self.rules_map]
        else:
            token = hashlib.sha256((backup / 'manifest.json').read_bytes()).hexdigest()
            args += ['--approve', token]
        result = self.run_command(args + list(extra), expected)
        return result

    def convert(self):
        self.migration('plan')
        self.migration('apply')

    def status(self, profile='claude', expected=0):
        return self.run_command(['sh', self.dst / '.config/ai-agent/bin/sync.sh', 'status',
                                 '--source', self.src, '--destination', self.dst, '--profile', profile,
                                 '--scanner', self.scanner], expected)

    def local_in(self, backup=None, profile='claude'):
        backup = backup or self.backup
        token = hashlib.sha256((backup / 'manifest.json').read_bytes()).hexdigest()
        plan = self.root / 'in-plan.json'
        if plan.exists():
            plan.unlink()
        common = ['--source', self.src, '--destination', self.dst, '--branch', 'main',
                  '--profile', profile, '--offline', '--baseline', backup, '--baseline-id', token,
                  '--plan', plan, '--scanner', self.scanner]
        deployed = self.dst / '.config/ai-agent/bin/sync.sh'
        self.run_command(['sh', deployed, 'plan', '--operation', 'in', *common])
        plan_id = hashlib.sha256(plan.read_bytes()).hexdigest()
        self.run_command(['sh', deployed, 'in', *common, '--approve', plan_id])

    def test_full_3a_3d_and_rollback(self):
        # 3A: persistent, verifiable backups without touching the real index or HEAD.
        self.migration('plan')
        self.assertEqual(self.before, self.state())
        self.assertEqual((self.backup / 'manifest.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.backup / 'index.before').read_bytes(), (self.src / '.git/index').read_bytes())
        # 3B/C: conversion and Claude-only cutover; no private production inputs.
        self.migration('apply')
        for skill in API['SKILLS'][1:]:
            self.assertEqual((self.dst / ('.claude/skills/' + skill + '/SKILL.md')).read_bytes(), self.skills[skill])
            self.assertFalse((self.src / ('dot_claude/skills/' + skill + '/SKILL.md')).exists())
        rules = (self.dst / '.claude/CLAUDE.md').read_bytes()
        for segment in self.segments:
            if segment['kind'] != 'retire-sync':
                self.assertIn(segment['text'].encode(), rules)
            else:
                self.assertNotIn(segment['text'].encode(), rules)
        self.assertEqual((self.dst / '.claude/settings.json').read_bytes(), self.settings)
        self.assertFalse((self.dst / '.codex/AGENTS.md').exists())
        self.assertFalse((self.dst / '.agents').exists())
        self.assertFalse((self.src / 'dot_codex').exists())
        # 3D: actual chezmoi output, idempotence, deployed status and offline in.
        applied = self.state()
        self.cm('apply', '--force')
        self.assertEqual(applied, self.state())
        self.cm('apply', '--force')
        self.assertEqual(applied, self.state())
        self.assertEqual(self.cm('diff'), b'')
        self.status()
        self.local_in()
        self.migration('verify')
        self.assertEqual(self.head, self.git('rev-parse', 'HEAD'))
        self.env['AI_AGENT_HOME'] = str(self.dst / '.config/ai-agent')
        self.run_command(['sh', self.dst / '.claude/skills/dotfiles-sync/sync.sh', 'status',
                          '--source', self.src, '--destination', self.dst, '--profile', 'claude', '--scanner', self.scanner])
        self.run_command(['sh', self.dst / '.claude/skills/dotfiles-sync/sync.sh', 'in'], 64)
        self.migration('rollback')
        self.assertEqual(self.before, self.state())
        self.assertEqual(self.cm('diff'), b'')

    def test_enable_codex_later_and_reverse_order_rollback(self):
        self.convert()
        claude = self.state()
        expansion = self.root / 'codex-expansion'
        self.migration('plan', profile='claude-codex', backup=expansion)
        self.assertEqual(claude, self.state())
        self.migration('apply', profile='claude-codex', backup=expansion)
        self.status('claude-codex')
        self.local_in(expansion, 'claude-codex')
        expanded = self.state()
        self.cm('apply', '--force')
        self.assertEqual(expanded, self.state())
        for skill in API['SKILLS']:
            self.assertEqual((self.dst / ('.claude/skills/' + skill + '/SKILL.md')).read_bytes(),
                             (self.dst / ('.agents/skills/' + skill + '/SKILL.md')).read_bytes())
        for key, value in claude.items():
            self.assertEqual(expanded[key], value, key)
        self.migration('rollback', profile='claude-codex', backup=expansion)
        self.assertEqual(claude, self.state())
        self.migration('rollback')
        self.assertEqual(self.before, self.state())

    def test_each_shared_skill_local_edit_render_and_scan(self):
        self.convert()
        for skill in API['SKILLS'][1:]:
            p = self.src / ('.chezmoitemplates/ai/shared/skills/' + skill + '/SKILL.md')
            original = p.read_bytes()
            p.write_bytes(original + b'\nReviewed fixture update.\n')
            self.status(expected=2)
            self.local_in()
            self.assertEqual((self.dst / ('.claude/skills/' + skill + '/SKILL.md')).read_bytes(), API['decode_shared'](p.read_bytes()))
            p.write_bytes(original + b'\nSYNTHETIC_TEST_SECRET\n')
            self.status(expected=67)
            p.write_bytes(original)
            self.cm('apply', '--force')
        self.migration('rollback')
        self.assertEqual(self.before, self.state())

    def test_claude_profile_ignores_codex_home_and_override(self):
        self.env['CODEX_HOME'] = str(self.root / 'another-codex-home')
        (self.dst / '.codex/AGENTS.override.md').write_bytes(b'Unrelated Codex override')
        before = self.state()
        self.convert()
        self.status()
        self.local_in()
        self.migration('rollback')
        self.assertEqual(before, self.state())

    def test_unknown_skill_or_extra_payload_blocks(self):
        self.put('dot_claude/skills/review/helper.sh', b'unknown payload')
        before = self.state()
        self.migration('plan', expected=66)
        self.assertEqual(before, self.state())
        self.assertFalse(self.backup.exists())

    def test_rules_map_must_preserve_every_byte(self):
        self.segments[0]['text'] = 'Different user rules\n'
        self.rules_map.write_text(json.dumps(dict(schema=1, segments=self.segments)))
        self.migration('plan', expected=66)
        self.assertEqual(self.before, self.state())

    def test_legacy_drift_blocks_without_overwrite(self):
        (self.dst / '.claude/CLAUDE.md').write_bytes(b'unsaved local preference')
        before = self.state()
        self.migration('plan', expected=2)
        self.assertEqual(before, self.state())

    def test_source_secret_and_scanner_failure(self):
        p = self.src / 'dot_claude/skills/review/SKILL.md'
        p.write_bytes(p.read_bytes() + b'SYNTHETIC_TEST_SECRET\n')
        (self.dst / '.claude/skills/review/SKILL.md').write_bytes(p.read_bytes())
        before = self.state()
        self.migration('plan', expected=67)
        self.assertEqual(before, self.state())
        self.scanner.write_text('#!/bin/sh\nexit 0\n')
        self.migration('plan', expected=70)

    def test_staged_changes_are_preserved(self):
        self.put('README.md', b'user staged changes')
        self.git('add', 'README.md')
        before = self.state()
        self.migration('plan', expected=66)
        self.assertEqual(before, self.state())

    def test_backup_tampering_is_blocked(self):
        self.migration('plan')
        doc = json.loads((self.backup / 'manifest.json').read_bytes())
        entry = doc['after']['source']['.chezmoitemplates/ai/shared/instructions.md']
        (self.backup / 'blobs' / entry[0]).write_bytes(b'tampered')
        self.migration('apply', expected=68)
        self.assertEqual(self.before, self.state())

    def test_stale_plan_and_later_edits_block_rollback(self):
        self.migration('plan')
        (self.dst / '.claude/settings.json').write_bytes(b'changed after plan')
        self.migration('apply', expected=68)
        (self.dst / '.claude/settings.json').write_bytes(self.settings)
        self.migration('apply')
        (self.dst / '.claude/CLAUDE.md').write_bytes(b'later user edit')
        before = self.state()
        self.migration('rollback', expected=72)
        self.assertEqual(before, self.state())

    def test_collision_symlink_lock_and_profile_approval(self):
        (self.src / '.git/ai-agent-sync.lock').mkdir()
        self.migration('plan', expected=73)
        (self.src / '.git/ai-agent-sync.lock').rmdir()
        self.migration('plan')
        self.migration('apply', expected=65, profile='claude-codex')
        target = self.dst / '.claude/CLAUDE.md'
        target.unlink()
        target.symlink_to(self.src / 'dot_claude/CLAUDE.md')
        self.migration('apply', expected=65)

    def test_partial_failure_restores_legacy(self):
        self.migration('plan')
        spec = importlib.util.spec_from_file_location('migration_test_api', SCRIPTS / 'sync-migrate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        work = self.root / 'work'
        work.mkdir()
        args = SimpleNamespace(command='apply', source=str(self.src), destination=str(self.dst),
                               backup=str(self.backup), branch='main', profile='claude', scanner=str(self.scanner),
                               approve=hashlib.sha256((self.backup / 'manifest.json').read_bytes()).hexdigest())
        engine = module.Migration(args, work)
        original = module.w.atomic
        failed = False
        def injected(path, value):
            nonlocal failed
            if path == self.dst / '.claude/CLAUDE.md' and not failed:
                failed = True
                raise OSError('injected target failure')
            return original(path, value)
        with patch.object(module.w, 'atomic', side_effect=injected):
            with self.assertRaises(OSError):
                engine.run_saved()
        self.assertEqual(self.before, self.state())
        self.assertFalse((self.src / '.git/ai-agent-migration-transaction').exists())

    def test_real_scanner_migration_and_new_skill_redaction(self):
        import random
        self.assertIsNotNone(shutil.which('gitleaks'), 'Gitleaks 8.30.1 required; no skip')
        self.scanner = SCRIPTS / 'scan-secrets.py'
        self.convert()
        self.status()
        rng = random.Random(9245)
        secret = 'gh' + 'p_' + ''.join(rng.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=36))
        for skill in API['SKILLS'][1:]:
            p = self.src / ('.chezmoitemplates/ai/shared/skills/' + skill + '/SKILL.md')
            old = p.read_bytes()
            p.write_bytes(old + b'\n' + secret.encode() + b'\n')
            output = self.status(expected=67)
            self.assertNotIn(secret.encode(), output)
            self.assertIn(skill.encode(), output)
            p.write_bytes(old)
        self.migration('rollback')
        self.assertEqual(self.before, self.state())

    def test_settings_inventory_and_source_alias_refused(self):
        self.put('dot_claude/private_CLAUDE.md', b'conflicting encoding')
        self.migration('plan', expected=66)
        (self.src / 'dot_claude/private_CLAUDE.md').unlink()
        value = json.loads(self.settings)
        value['hooks'] = {'unexpected': 'not in accepted inventory'}
        self.put('dot_claude/settings.json', json.dumps(value).encode())
        self.migration('plan', expected=66)

    def test_expired_plan_and_changed_git_baseline(self):
        self.migration('plan')
        path = self.backup / 'manifest.json'
        original = path.read_bytes()
        value = json.loads(original)
        value['created'] = 1
        path.write_text(json.dumps(value))
        self.migration('apply', expected=68)
        path.write_bytes(original)
        self.git('config', 'fixture.changed', 'true')
        self.migration('apply', expected=68)

    def test_bootstrap_does_not_enable_unapproved_push(self):
        self.convert()
        token = hashlib.sha256((self.backup / 'manifest.json').read_bytes()).hexdigest()
        self.run_command(['sh', ENGINE, 'plan', '--operation', 'push', '--offline',
                          '--source', self.src, '--destination', self.dst, '--profile', 'claude',
                          '--branch', 'main', '--plan', self.root / 'bad-plan.json',
                          '--baseline', self.backup, '--baseline-id', token], 64)
        # A normal local plan without an explicit bootstrap receipt still requires v2 HEAD.
        self.run_command(['sh', ENGINE, 'plan', '--operation', 'in', '--offline',
                          '--source', self.src, '--destination', self.dst, '--profile', 'claude',
                          '--branch', 'main', '--plan', self.root / 'bad-plan.json', '--scanner', self.scanner], 65)
        self.assertEqual(self.head, self.git('rev-parse', 'HEAD'))

    def test_incoming_codex_target_collision_preserved(self):
        self.convert()
        p = self.dst / '.codex/AGENTS.md'
        p.write_bytes(b'existing independent Codex rules')
        before = self.state()
        self.migration('plan', profile='claude-codex', backup=self.root / 'expansion', expected=66)
        self.assertEqual(before, self.state())

    def test_literal_template_delimiters_preserved_without_execution(self):
        self.segments[0]['text'] += '\nExample {{ output "sh" "-c" "exit 99" }} is documentation.\n'
        rules = ''.join(v['text'] for v in self.segments).encode()
        self.put('dot_claude/CLAUDE.md', rules)
        (self.dst / '.claude/CLAUDE.md').write_bytes(rules)
        self.rules_map.write_text(json.dumps(dict(schema=1, segments=self.segments)))
        before = self.state()
        self.convert()
        self.assertIn(self.segments[0]['text'].encode(), (self.dst / '.claude/CLAUDE.md').read_bytes())
        self.assertEqual((self.dst / '.claude/skills/d3-component/SKILL.md').read_bytes(), self.skills['d3-component'])
        self.status()
        after = self.state()
        self.cm('apply', '--force')
        self.assertEqual(after, self.state())
        self.migration('rollback')
        self.assertEqual(before, self.state())

    def test_frontmatter_change_and_external_directory_are_preserved(self):
        p = self.src / 'dot_claude/skills/review/SKILL.md'
        original = p.read_bytes()
        p.write_bytes(original.replace(b'description:', b'allowed-tools: Bash\ndescription:'))
        self.migration('plan', expected=66)
        p.write_bytes(original)
        self.migration('plan')
        external = self.dst / '.config'
        external.mkdir()
        self.migration('apply', expected=68)
        self.assertTrue(external.is_dir())
        self.assertEqual(self.before, self.state())

    def test_recovery_journal_preserves_later_edit(self):
        self.migration('plan')
        spec = importlib.util.spec_from_file_location('migration_recovery_api', SCRIPTS / 'sync-migrate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        work = self.root / 'work'
        work.mkdir()
        args = SimpleNamespace(command='apply', source=str(self.src), destination=str(self.dst),
                               backup=str(self.backup), branch='main', profile='claude', scanner=str(self.scanner),
                               approve=hashlib.sha256((self.backup / 'manifest.json').read_bytes()).hexdigest())
        engine = module.Migration(args, work)
        original = module.w.atomic
        def injected(path, value):
            if path == self.dst / '.claude/skills/dotfiles-sync/SKILL.md':
                (self.dst / '.claude/CLAUDE.md').write_bytes(b'later concurrent edit')
                raise OSError('injected failure')
            return original(path, value)
        with patch.object(module.w, 'atomic', side_effect=injected):
            with self.assertRaises(module.w.Block) as error:
                engine.run_saved()
        self.assertEqual(error.exception.code, 72)
        self.assertTrue((self.src / '.git/ai-agent-migration-transaction/manifest.json').exists())
        later = self.state()
        self.migration('rollback', expected=72)
        self.assertEqual(later, self.state())
        doc = json.loads((self.backup / 'manifest.json').read_bytes())
        entry = doc['after']['target']['.claude/CLAUDE.md']
        (self.dst / '.claude/CLAUDE.md').write_bytes((self.backup / 'blobs' / entry[0]).read_bytes())
        self.migration('rollback')
        self.assertEqual(self.before, self.state())

    def test_profile_expansion_refuses_unknown_shared_template(self):
        self.convert()
        self.put('.chezmoitemplates/ai/shared/unknown.md', b'unknown named definition')
        before = self.state()
        self.migration('plan', profile='claude-codex', backup=self.root / 'expansion', expected=66)
        self.assertEqual(before, self.state())

    def test_bootstrap_baseline_requires_legacy_deletions(self):
        self.convert()
        self.put('dot_claude/CLAUDE.md', self.legacy_rules)
        token = hashlib.sha256((self.backup / 'manifest.json').read_bytes()).hexdigest()
        before = self.state()
        self.run_command(['sh', ENGINE, 'plan', '--operation', 'in', '--offline', '--profile', 'claude',
                          '--source', self.src, '--destination', self.dst, '--branch', 'main',
                          '--baseline', self.backup, '--baseline-id', token,
                          '--plan', self.root / 'bad-plan.json', '--scanner', self.scanner], 66)
        self.assertEqual(before, self.state())

    def test_first_conversion_without_any_codex_directories(self):
        (self.dst / '.codex/auth.json').unlink()
        (self.dst / '.codex').rmdir()
        before = self.state()
        self.convert()
        self.status()
        self.local_in()
        self.cm('apply', '--force')
        self.assertFalse((self.dst / '.codex').exists())
        self.assertFalse((self.dst / '.agents').exists())
        self.migration('rollback')
        self.assertEqual(before, self.state())


if __name__ == '__main__':
    unittest.main()

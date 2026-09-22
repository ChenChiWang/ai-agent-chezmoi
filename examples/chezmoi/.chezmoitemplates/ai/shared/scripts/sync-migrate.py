#!/usr/bin/env python3
"""Offline, approved legacy conversion/profile expansion with retained rollback."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sync_engine', HERE / 'sync-write.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
a = w.api


def snap(root, paths):
    return {p: w.read(root / p, missing=True) for p in paths}


def refs(values):
    return {p: None if v is None else [w.digest(v[0]), v[1]] for p, v in values.items()}


def blob(backup, entry):
    if entry is None:
        return None
    w.need(type(entry) is list and len(entry) == 2 and type(entry[0]) is str
           and re.fullmatch('[0-9a-f]{64}', entry[0]) and type(entry[1]) is int
           and 0 <= entry[1] <= 0o777, 'INVALID_MANIFEST')
    content = w.read(backup / 'blobs' / entry[0])[0]
    w.need(w.digest(content) == entry[0], 'BLOCKED_BACKUP_INTEGRITY', 68)
    return content, entry[1]


class Migration(w.Engine):
    def __init__(self, args, tmp):
        args.offline, args.operation = True, 'in'
        args.allow_migration_recovery = args.command in ('rollback', 'verify')
        super().__init__(args, tmp)
        self.backup = Path(args.backup).resolve()
        w.safe(self.backup)
        for root in (self.src, self.dst):
            w.need(self.backup != root and root not in self.backup.parents
                   and self.backup not in root.parents, 'INVALID_BACKUP_PATH')
        self.journal = self.gd / 'ai-agent-migration-transaction'

    def scan_values(self, values, scope):
        present = {p: v for p, v in values.items() if v is not None}
        if present:
            self.scan(present, scope)

    def layout(self, legacy):
        # Reject extra skill payloads/encodings instead of silently omitting them.
        expected = {p for p in (a.LEGACY_FILES if legacy else a.mapping('claude')[0])
                    if p.startswith('dot_claude/skills/')}
        actual = set()
        root = self.src / 'dot_claude/skills'
        w.safe(root)
        for parent, dirs, files in os.walk(root):
            for name in dirs + files:
                w.safe(Path(parent) / name)
            for name in files:
                actual.add((Path(parent) / name).relative_to(self.src).as_posix())
        w.need(actual == expected, 'BLOCKED_INVENTORY_MISMATCH', 66)
        if legacy:
            for skill in a.SKILLS:
                data = w.read(self.src / ('dot_claude/skills/' + skill + '/SKILL.md'))[0]
                w.text_file(data)
                lines = data.decode().splitlines()
                w.need(lines and lines[0] == '---' and '---' in lines[1:], 'BLOCKED_INVENTORY_MISMATCH', 66)
                fields = {}
                for line in lines[1:lines.index('---', 1)]:
                    if not line.strip() or line.startswith('#') or line[0].isspace():
                        continue
                    match = re.fullmatch(r'([a-z-]+):\s*(.*)', line)
                    w.need(match and match[1] not in fields, 'BLOCKED_INVENTORY_MISMATCH', 66)
                    fields[match[1]] = match[2]
                w.need(set(fields) == {'name', 'description'} and fields['name'].strip('"\'') == skill,
                       'BLOCKED_INVENTORY_MISMATCH', 66)
        if not legacy:
            # Extra named definitions could alter real chezmoi's shared namespace.
            shared_root = self.src / '.chezmoitemplates/ai'
            w.safe(shared_root)
            shared = set()
            for parent, dirs, files in os.walk(shared_root):
                for name in dirs + files:
                    w.safe(Path(parent) / name)
                shared.update((Path(parent) / name).relative_to(self.src).as_posix() for name in files)
            w.need(shared == {p for p in a.mapping('claude')[0] if p.startswith(a.PREFIX)},
                   'BLOCKED_INVENTORY_MISMATCH', 66)
        # Reject alternative chezmoi encodings that could target our outputs.
        # Unknown unrelated files are preserved; no content is read here.
        allowed = set(a.LEGACY_FILES if legacy else a.mapping('claude')[0])
        attributes = ('encrypted_', 'executable_', 'literal_', 'private_', 'readonly_',
                      'empty_', 'exact_', 'create_', 'modify_', 'remove_', 'symlink_')
        managed = set(a.TARGET_FILES)
        for parent, dirs, files in os.walk(self.src):
            if Path(parent) == self.src:
                dirs[:] = [d for d in dirs if d not in ('.git', '.chezmoitemplates')]
            for name in dirs + files:
                path = Path(parent) / name
                rel = path.relative_to(self.src).as_posix()
                components = []
                for component in rel.split('/'):
                    while any(component.startswith(attr) for attr in attributes):
                        component = next(component[len(attr):] for attr in attributes if component.startswith(attr))
                    if component.startswith('dot_'):
                        component = '.' + component[4:]
                    components.append(component)
                target = '/'.join(components)
                if target.endswith('.tmpl'):
                    target = target[:-5]
                if target in managed:
                    w.need(rel in allowed, 'BLOCKED_SOURCE_ALIAS', 66)
                if path.is_dir() and any(t.startswith(target + '/') for t in managed):
                    w.safe(path)
                    w.need(not any(part.startswith(attributes) for part in rel.split('/')),
                           'BLOCKED_SOURCE_ALIAS', 66)

    def split_rules(self, old):
        path = Path(self.a.rules_map)
        raw = w.read(path)[0]
        data = a.read_json(path)
        w.need(type(data) is dict and set(data) == {'schema', 'segments'} and data['schema'] == 1,
               'INVALID_RULES_MAP')
        segments = data['segments']
        w.need(type(segments) is list and 0 < len(segments) <= 1000, 'INVALID_RULES_MAP')
        parts = {'shared': [], 'claude': [], 'retire-sync': []}
        joined = []
        for segment in segments:
            w.need(type(segment) is dict and set(segment) == {'kind', 'text'}
                   and segment['kind'] in parts and type(segment['text']) is str
                   and segment['text'], 'INVALID_RULES_MAP')
            content = segment['text'].encode()
            w.text_file(content)
            if segment['kind'] == 'retire-sync':
                w.need(b'dotfiles-sync' in content, 'INVALID_RULES_MAP')
            parts[segment['kind']].append(content)
            joined.append(content)
        w.need(b''.join(joined) == old and parts['shared'], 'BLOCKED_RULES_MISMATCH', 66)
        # The complete baseline (including retired text) is scanned and backed up.
        return {k: b''.join(v) for k, v in parts.items()}, w.digest(raw)

    def propose(self):
        self.clean_index()
        before_git = self.git_state()
        legacy = self.a.mode == 'legacy'
        w.need((legacy and self.profile == 'claude') or (not legacy and self.profile == 'claude-codex'),
               'INVALID_PROFILE_TRANSITION')
        self.layout(legacy)
        if legacy:
            w.need(not (self.src / '.chezmoitemplates/ai').exists(), 'BLOCKED_EXISTING_V2', 66)
            settings = a.read_json(self.src / 'dot_claude/settings.json')
            w.need(type(settings) is dict and set(settings) == {'model', 'statusLine', 'tui'},
                   'BLOCKED_INVENTORY_MISMATCH', 66)
        reference = Path(self.a.reference).resolve()
        w.need(reference.is_dir() and reference != self.src, 'INVALID_REFERENCE')
        source_paths = sorted(set(self.files) | (set(a.LEGACY_FILES) if legacy else set()))
        source = snap(self.src, source_paths)
        target = snap(self.dst, self.targets)
        template = w.snapshot(reference, self.files)
        self.scan(template)
        retired = None
        if legacy:
            for p in a.LEGACY_FILES:
                if p not in ('.gitignore', '.gitattributes'):
                    w.need(source[p] is not None, 'BLOCKED_INVENTORY_MISMATCH', 66)
            # Do not merge with a partially installed core or ambiguous templates.
            for p in self.files:
                if p not in a.LEGACY_FILES:
                    w.need(source[p] is None, 'BLOCKED_EXISTING_V2', 66)
            for path in a.LEGACY_TARGETS:
                w.need(target[path] is not None, 'BLOCKED_MISSING_LEGACY_TARGET', 66)
                src_path = ('dot_claude/skills/dotfiles-sync/executable_sync.sh'
                            if path.endswith('/sync.sh') else 'dot_claude/' + path[len('.claude/'):])
                w.need(target[path][0] == source[src_path][0], 'DRIFT', 2)
            for path in set(self.targets) - set(a.LEGACY_TARGETS):
                w.need(target[path] is None, 'BLOCKED_TARGET_COLLISION', 66)
            parts, rule_id = self.split_rules(source['dot_claude/CLAUDE.md'][0])
            candidate = dict(template)
            candidate[a.PREFIX + 'shared/instructions.md'] = (a.encode_shared(parts['shared']), 0o644)
            candidate[a.PREFIX + 'adapters/claude.md'] = (a.encode_shared(parts['claude']) + template[a.PREFIX + 'adapters/claude.md'][0], 0o644)
            retired = dict(rules_map=rule_id, content=w.digest(parts['retire-sync']))
            for skill in a.SKILLS[1:]:
                candidate[a.PREFIX + 'shared/skills/' + skill + '/SKILL.md'] = (
                    a.encode_shared(source['dot_claude/skills/' + skill + '/SKILL.md'][0]), 0o644)
            candidate['dot_claude/settings.json'] = source['dot_claude/settings.json']
            for path in ('.gitignore', '.gitattributes'):
                if source[path] is not None:
                    candidate[path] = source[path]
            old_ignore = source['.chezmoiignore'][0]
            candidate['.chezmoiignore'] = (old_ignore + b'\n# v2 migration exclusions\n' + template['.chezmoiignore'][0],
                                          source['.chezmoiignore'][1])
        else:
            w.need(not self.a.rules_map, 'USAGE: rules map is legacy-only', 64)
            old_files, old_targets = a.mapping('claude')
            candidate = {}
            for p in self.files:
                if p in old_files:
                    w.need(source[p] is not None, 'BLOCKED_LAYOUT')
                    candidate[p] = source[p]
                else:
                    w.need(source[p] is None, 'BLOCKED_EXISTING_CODEX', 66)
                    candidate[p] = template[p]
            old_engine_profile = self.profile
            self.profile = 'claude'
            old_render = self.render({p: source[p] for p in old_files})
            self.profile = old_engine_profile
            for path in old_targets:
                w.need(target[path] == old_render[path], 'DRIFT', 2)
            for path in set(self.targets) - set(old_targets):
                w.need(target[path] is None, 'BLOCKED_TARGET_COLLISION', 66)
        rendered = self.render(candidate)
        # Strict byte/mode preservation for the existing Claude-only settings.
        w.need(rendered['.claude/settings.json'] == target['.claude/settings.json'], 'BLOCKED_SETTINGS_MODE', 66)
        proposed = {p: candidate.get(p) for p in source_paths}
        self.scan_values(source, 'source')
        self.scan_values(target, 'target')
        self.scan_values(proposed, 'source')
        self.scan(rendered, 'render')
        w.need(self.git_state() == before_git and snap(self.src, source_paths) == source
               and snap(self.dst, self.targets) == target, 'BLOCKED_STALE_PLAN', 68)
        directories = []
        for scope, root, values in [('source', self.src, proposed), ('target', self.dst, rendered)]:
            for p, value in values.items():
                if value is None:
                    continue
                parent = (root / p).parent
                while parent != root and not parent.exists():
                    w.safe(parent)
                    pair = [scope, parent.relative_to(root).as_posix()]
                    if pair not in directories:
                        directories.append(pair)
                    parent = parent.parent
                w.need(parent.is_dir(), 'BLOCKED_PATH_COLLISION', 66)
        doc = dict(schema=1, created=int(time.time()), mode=self.a.mode, profile=self.profile,
                   source=str(self.src), destination=str(self.dst), git=before_git, retired=retired,
                   before=dict(source=refs(source), target=refs(target)),
                   after=dict(source=refs(proposed), target=refs(rendered)),
                   directories=sorted(directories, key=lambda v: (v[1].count('/'), v)),
                   tools={p: w.digest(w.read(HERE / p)[0]) for p in a.SCRIPTS},
                   scanner=w.digest(w.read(self.scanner)[0]))
        # Back up exactly the affected paths, and the original index as evidence.
        w.need(not self.backup.exists() and self.backup.parent.is_dir(), 'INVALID_BACKUP_PATH')
        self.backup.mkdir(mode=0o700)
        try:
            (self.backup / 'blobs').mkdir(mode=0o700)
            for values in (source, target, proposed, rendered):
                for value in values.values():
                    if value is not None:
                        dest = self.backup / 'blobs' / w.digest(value[0])
                        if not dest.exists():
                            w.atomic(dest, (value[0], 0o600))
            w.atomic(self.backup / 'index.before', (w.read(self.gd / 'index')[0], 0o600))
            raw = w.encoded(doc)
            w.atomic(self.backup / 'manifest.json', (raw, 0o600))
        except BaseException:
            shutil.rmtree(self.backup)
            raise
        self.describe(doc)
        print('MIGRATION_ID: ' + w.digest(raw))
        print('OK: baseline backed up; review before applying; no source/index/target mutation')

    def describe(self, doc):
        for scope in ('source', 'target'):
            for p in doc['before'][scope]:
                old, new = doc['before'][scope][p], doc['after'][scope][p]
                if old != new:
                    action = 'create' if old is None else ('remove' if new is None else 'replace')
                    print(scope.upper() + ': ' + p + ' ' + action)
        if doc['retired']:
            print('RETIRED_SYNC_TEXT_SHA256: ' + doc['retired']['content'])
        print('PROFILE: ' + doc['profile'])

    def load(self):
        content, mode = w.read(self.backup / 'manifest.json')
        w.need(mode & 0o077 == 0 and w.digest(content) == self.a.approve, 'BLOCKED_STALE_PLAN', 68)
        doc = a.read_json(self.backup / 'manifest.json')
        w.need(doc['schema'] == 1 and doc['profile'] == self.profile
               and doc['source'] == str(self.src) and doc['destination'] == str(self.dst), 'INVALID_MANIFEST')
        w.need(doc['mode'] in ('legacy', 'enable-codex'), 'INVALID_MANIFEST')
        expected = set(self.files) | (set(a.LEGACY_FILES) if doc['mode'] == 'legacy' else set())
        self.values = {}
        for side in ('before', 'after'):
            self.values[side] = {}
            for scope, paths in [('source', expected), ('target', set(self.targets))]:
                w.need(set(doc[side][scope]) == paths, 'INVALID_MANIFEST')
                self.values[side][scope] = {p: blob(self.backup, e) for p, e in doc[side][scope].items()}
        expected_dirs = set()
        for scope, root in [('source', self.src), ('target', self.dst)]:
            for path, value in self.values['after'][scope].items():
                if value is not None:
                    parent = Path(path).parent
                    while str(parent) != '.':
                        expected_dirs.add((scope, str(parent)))
                        parent = parent.parent
        w.need(type(doc['directories']) is list and all(type(v) is list and len(v) == 2
               and tuple(v) in expected_dirs for v in doc['directories']), 'INVALID_MANIFEST')
        w.need(self.git_state() == doc['git'], 'BLOCKED_STALE_BASELINE', 68)
        w.need(w.digest(w.read(self.backup / 'index.before')[0]) == doc['git']['index']['index'][0],
               'BLOCKED_BACKUP_INTEGRITY', 68)
        self.clean_index()
        return doc

    def current(self):
        return {'source': snap(self.src, self.values['before']['source']),
                'target': snap(self.dst, self.values['before']['target'])}

    def restore(self, doc):
        current = self.current()
        # Validate the ENTIRE rollback before touching any path.
        for scope in current:
            for p, value in current[scope].items():
                w.need(value in (self.values['before'][scope][p], self.values['after'][scope][p]),
                       'RECOVERY_REQUIRED: later edits preserved', 72)
        for scope, root in [('target', self.dst), ('source', self.src)]:
            for p, old in reversed(list(self.values['before'][scope].items())):
                path = root / p
                actual = w.read(path, missing=True)
                if actual == old:
                    continue
                w.need(actual == self.values['after'][scope][p], 'RECOVERY_REQUIRED', 72)
                if old is None:
                    path.unlink()
                else:
                    w.safe(path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    w.atomic(path, old)
        ownership_file = self.backup / 'created-directories.json'
        ownership = a.read_json(ownership_file) if ownership_file.exists() else {}
        for scope, rel in reversed(doc['directories']):
            directory = (self.src if scope == 'source' else self.dst) / rel
            w.safe(directory)
            if directory.is_dir():
                st = directory.stat()
                if ownership.get(scope + '/' + rel) == [st.st_dev, st.st_ino] and not any(directory.iterdir()):
                    directory.rmdir()
        w.need(self.current() == self.values['before'], 'RECOVERY_REQUIRED', 72)

    def apply(self, doc):
        w.need(0 <= time.time() - doc['created'] < 3600, 'BLOCKED_EXPIRED_PLAN', 68)
        w.need(doc['tools'] == {p: w.digest(w.read(HERE / p)[0]) for p in a.SCRIPTS}
               and doc['scanner'] == w.digest(w.read(self.scanner)[0]), 'BLOCKED_STALE_PLAN', 68)
        w.need(self.current() == self.values['before'], 'BLOCKED_STALE_PLAN', 68)
        self.layout(doc['mode'] == 'legacy')
        for side in ('before', 'after'):
            self.scan_values(self.values[side]['source'], 'source')
            self.scan_values(self.values[side]['target'], 'target' if side == 'before' else 'render')
        w.need(self.current() == self.values['before'] and self.git_state() == doc['git'], 'BLOCKED_STALE_PLAN', 68)
        self.journal.mkdir(mode=0o700)
        w.atomic(self.journal / 'manifest.json', (w.encoded({'backup': str(self.backup), 'id': self.a.approve}), 0o600))
        try:
            ownership = {}
            w.atomic(self.backup / 'created-directories.json', (w.encoded(ownership), 0o600))
            for scope, rel in doc['directories']:
                directory = (self.src if scope == 'source' else self.dst) / rel
                w.safe(directory)
                w.need(not directory.exists(), 'BLOCKED_STALE_PLAN', 68)
                directory.mkdir(mode=0o755)
                st = directory.stat()
                ownership[scope + '/' + rel] = [st.st_dev, st.st_ino]
                w.atomic(self.backup / 'created-directories.json', (w.encoded(ownership), 0o600))
            for scope, root in [('source', self.src), ('target', self.dst)]:
                # Remove old plain sources before creating their template counterparts.
                entries = sorted(self.values['after'][scope].items(), key=lambda v: v[1] is not None)
                for p, new in entries:
                    old = self.values['before'][scope][p]
                    if new == old:
                        continue
                    path = root / p
                    w.need(w.read(path, missing=True) == old, 'BLOCKED_STALE_PLAN', 68)
                    if new is None:
                        path.unlink()
                    else:
                        w.atomic(path, new)
            w.need(self.git_state() == doc['git'] and self.current() == self.values['after'], 'RECOVERY_REQUIRED', 72)
        except BaseException:
            self.restore(doc)
            shutil.rmtree(self.journal)
            raise
        shutil.rmtree(self.journal)
        print('OK: conversion applied; HEAD/index unchanged; stop at the requested regression gate')

    def run_saved(self):
        doc = self.load()
        index_lock = self.gd / 'index.lock'
        # Even read-only verification needs only our source lock, not index mutation.
        if self.a.command == 'verify':
            w.need(self.current() == self.values['after'], 'DRIFT', 2)
            print('OK: manifest contents/modes and Git baseline verified; not a product-loading test')
            return
        acquired = False
        try:
            with index_lock.open('xb') as f:
                acquired = True
                f.write(w.read(self.gd / 'index')[0])
            w.need(self.git_state() == doc['git'], 'BLOCKED_STALE_BASELINE', 68)
            if self.a.command == 'apply':
                self.apply(doc)
            else:
                if self.journal.exists():
                    record = a.read_json(self.journal / 'manifest.json')
                    w.need(record == {'backup': str(self.backup), 'id': self.a.approve}, 'RECOVERY_REQUIRED', 72)
                self.restore(doc)
                if self.journal.exists():
                    shutil.rmtree(self.journal)
                print('OK: scoped source/target baseline restored; HEAD/index unchanged')
        finally:
            if acquired:
                index_lock.unlink()


def main():
    os.umask(0o077)
    parser = w.Parser()
    parser.add_argument('command', choices=('plan', 'apply', 'rollback', 'verify'))
    for name in ('source', 'destination', 'backup', 'branch'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--profile', choices=a.PROFILES, required=True)
    parser.add_argument('--mode', choices=('legacy', 'enable-codex'))
    parser.add_argument('--reference')
    parser.add_argument('--rules-map')
    parser.add_argument('--scanner')
    parser.add_argument('--approve')
    args = parser.parse_args()
    for path in (args.source, args.destination, args.backup, args.reference or '/', args.rules_map or '/', args.scanner or '/'):
        w.need(Path(path).is_absolute(), 'USAGE: absolute paths required', 64)
    if args.command == 'plan':
        w.need(args.mode and args.reference and (args.mode != 'legacy' or args.rules_map), 'USAGE: conversion inputs required', 64)
    else:
        w.need(args.approve and re.fullmatch('[0-9a-f]{64}', args.approve), 'USAGE: --approve MIGRATION_ID required', 64)
    with tempfile.TemporaryDirectory(prefix='ai-agent-migration-', dir='/tmp') as tmp:
        with w.lock(Path(args.source).resolve()):
            engine = Migration(args, Path(tmp))
            if args.command == 'plan':
                engine.propose()
            else:
                engine.run_saved()
    return 0


if __name__ == '__main__':
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt()
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    try:
        sys.exit(main())
    except w.Block as error:
        print(error.label)
        sys.exit(error.code)
    except KeyboardInterrupt:
        print('INTERRUPTED: inspect migration journal')
        sys.exit(130)
    except (OSError, ValueError, KeyError, TypeError, RecursionError, a.ScanError):
        print('IO_ERROR: conversion stopped; raw values withheld')
        sys.exit(70)

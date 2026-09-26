#!/usr/bin/env python3
"""Approved fixed-profile sync transactions. No third-party Python dependencies."""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('scanner_api', HERE / 'scan-secrets.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
FILES = api.SOURCE_FILES
TARGETS = api.TARGET_FILES
PREFIX = '.chezmoitemplates/ai/'
SCRIPTS = api.SCRIPTS
LIMIT = api.MAX_BYTES


class Block(Exception):
    def __init__(self, code, label):
        self.code, self.label = code, label


# 封存的 Phase 4 cohort／lease 協定標記。任何一個存在都拒絕操作，留待人工檢視。
COORDINATION_MARKERS = ('ai-agent-cohort.json', 'ai-agent-cohort.lock', 'ai-agent-launch-readers')

# 純文字的共用來源：instructions、六個 skill、兩個 adapter。auto_in 只可自動套用這些檔案的變更。
SHARED_TEXT = frozenset(
    [PREFIX + 'shared/instructions.md']
    + [PREFIX + 'shared/skills/' + s + '/SKILL.md' for s in api.SKILLS]
    + [PREFIX + 'adapters/' + p + '.md' for p in ('claude', 'codex')])


class Diagnostics:
    # 僅保存固定欄位；不保存例外文字、檔案路徑、locals 或子程序輸出。
    OPERATIONS = {
        'validate_plan': 'preflight', 'initialize_engine': 'prepare',
        'build_candidate': 'prepare', 'source_lock': 'coordination',
        'validate_execution': 'preflight', 'write_plan': 'prepare',
        'activate': 'transaction',
        'transfer_objects': 'transfer', 'create_journal': 'transaction',
        'index_lock': 'transaction', 'backup_files': 'transaction',
        'write_manifest': 'transaction', 'apply_files': 'transaction',
        'update_ref': 'transaction', 'restore_files': 'rollback',
        'verify_ref': 'rollback', 'remove_journal': 'cleanup',
        'remove_index_lock': 'cleanup', 'release_lock': 'cleanup',
        'temporary_workspace': 'cleanup', 'atomic_temporary': 'cleanup',
        'object_temporary': 'cleanup', 'close_directory': 'cleanup',
        'unknown': 'unknown',
    }

    def __init__(self):
        self.operation = 'unknown'
        self.first = None
        self.secondary = []
        self.first_error_id = None
        self.transaction_started = 'unknown'
        self.rollback = dict(attempted='unknown', result='unknown')
        self.cleanup = {}

    def mark(self, operation):
        self.operation = operation if operation in self.OPERATIONS else 'unknown'

    def capture(self, error):
        if id(error) == self.first_error_id:
            return
        allowed = (Block, OSError, PermissionError, FileNotFoundError, FileExistsError,
                   IsADirectoryError, NotADirectoryError, TimeoutError, ValueError,
                   UnicodeDecodeError, KeyError, TypeError, RecursionError,
                   subprocess.SubprocessError, subprocess.CalledProcessError,
                   subprocess.TimeoutExpired, KeyboardInterrupt)
        kind = type(error).__name__ if isinstance(error, allowed) else 'unknown'
        location = dict(file='unknown', line=None)
        trace = error.__traceback__
        while trace:
            # 比對完整程式來源，輸出則僅有固定 basename 與行號。
            if trace.tb_frame.f_code.co_filename in (__file__, api.__file__):
                location = dict(file='sync-write.py' if trace.tb_frame.f_code.co_filename == __file__
                                else 'scan-secrets.py', line=trace.tb_lineno)
            trace = trace.tb_next
        record = dict(phase=self.OPERATIONS[self.operation], operation=self.operation,
                      exception_type=kind, location=location)
        if isinstance(error, OSError) and type(error.errno) is int and 0 < error.errno < 4096:
            record['errno'] = error.errno
        if self.first is None:
            self.first_error_id = id(error)
            self.first = record
        elif record != self.first and record not in self.secondary and len(self.secondary) < 8:
            self.secondary.append(record)

    @contextlib.contextmanager
    def cleaning(self, operation):
        previous = self.operation
        self.mark(operation)
        operation = self.operation
        entry = self.cleanup.setdefault(operation, dict(attempted=True, result='unknown'))
        try:
            yield
        except BaseException as error:
            entry['result'] = 'failed'
            self.capture(error)
            raise
        else:
            if entry['result'] != 'failed':
                entry['result'] = 'succeeded'
        finally:
            self.operation = previous

    def emit(self, error):
        if self.first is None:
            self.capture(error)
        record = dict(schema=1, **self.first, transaction_started=self.transaction_started,
                      rollback=self.rollback,
                      cleanup=dict(attempted=True if self.cleanup else 'unknown',
                                   result=('failed' if any(v['result'] == 'failed' for v in self.cleanup.values())
                                           else 'succeeded' if self.cleanup else 'unknown'),
                                   operations=self.cleanup), secondary_errors=self.secondary)
        print('DIAGNOSTIC: ' + json.dumps(record, sort_keys=True), file=sys.stderr)


diagnostics = Diagnostics()


def need(ok, label='INVALID_SOURCE', code=65):
    if not ok:
        raise Block(code, label)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def safe(path):
    for p in (path, *path.parents):
        need(not p.is_symlink(), 'BLOCKED_SYMLINK')


def layout(args, legacy=False):
    try:
        return api.validate_layout(args.source, args.destination,
                                   getattr(args, 'profile', 'claude-codex'), legacy,
                                   getattr(args, 'repository_profile', None))
    except (ValueError, OSError):
        raise Block(65, 'INVALID_LAYOUT') from None


def read(path, missing=False):
    safe(path)
    if missing and not path.exists():
        return None
    m = path.stat()
    need(stat.S_ISREG(m.st_mode) and m.st_mode & 0o444 and m.st_size <= LIMIT)
    with path.open('rb') as f:
        data = f.read(LIMIT + 1)
    need(len(data) <= LIMIT)
    return data, stat.S_IMODE(m.st_mode)


def text_file(data):
    need(len(data) <= LIMIT and b'\x00' not in data, 'UNSUPPORTED_CONTENT')
    data.decode('utf-8')


def snapshot(root, paths):
    return {p: read(root / p) for p in paths}


def summary(snap):
    return {p: [digest(v[0]), v[1]] for p, v in snap.items()}


def normalized(snap):
    return {p: (v[0], 0o755 if v[1] & 0o111 else 0o644) for p, v in snap.items()}


def fsync_dir(path):
    safe(path)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    except BaseException as error:
        diagnostics.capture(error)
        raise
    finally:
        with diagnostics.cleaning('close_directory'):
            os.close(fd)


def atomic(path, value):
    safe(path)
    fd, name = tempfile.mkstemp(prefix='.ai-sync-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(value[0])
            f.flush()
            os.fchmod(f.fileno(), value[1])
            os.fsync(f.fileno())
        os.replace(name, path)
        fsync_dir(path.parent)
    except BaseException as error:
        diagnostics.capture(error)
        raise
    finally:
        with diagnostics.cleaning('atomic_temporary'):
            if os.path.exists(name):
                os.unlink(name)


class Engine:
    def __init__(self, args, tmp):
        diagnostics.mark('initialize_engine')
        self.a, self.tmp = args, tmp
        self.profile = getattr(args, 'profile', 'claude-codex')
        self.files, self.targets = api.mapping(self.profile)
        self.repository_profile = getattr(args, 'repository_profile', None) or self.profile
        need(set(self.files) <= set(api.mapping(self.repository_profile)[0]), 'INVALID_REPOSITORY_PROFILE')
        self.files = api.mapping(self.repository_profile)[0]
        self.offline = getattr(args, 'offline', False)
        self.src, self.dst = layout(args)
        self.gd = self.src / '.git'
        safe(self.gd)
        need(self.gd.is_dir(), 'UNSUPPORTED_WORKTREE')
        homes = [('AI_AGENT_HOME', '.config/ai-agent')]
        if self.profile != 'codex':
            homes.append(('CLAUDE_CONFIG_DIR', '.claude'))
        if self.profile != 'claude':
            homes.append(('CODEX_HOME', '.codex'))
        for key, suffix in homes:
            need(not os.environ.get(key) or os.environ[key] == str(self.dst / suffix), 'UNSUPPORTED_HOME')
        if self.profile != 'claude':
            safe(self.dst / '.codex/AGENTS.override.md')
            need(not (self.dst / '.codex/AGENTS.override.md').exists(), 'BLOCKED_OVERRIDE')
        # Refuse indirection/special repositories before invoking Git against them.
        for name in ('shallow', 'commondir', 'objects/info/alternates', 'info/grafts'):
            need(not (self.gd / name).exists(), 'UNSUPPORTED_REPOSITORY')
        self.env = dict(PATH=os.environ.get('PATH', os.defpath), HOME=str(tmp / 'home'),
                        LC_ALL='C', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
                        GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1',
                        GIT_ALLOW_PROTOCOL='', GIT_PROTOCOL_FROM_USER='0', GIT_TERMINAL_PROMPT='0')
        (tmp / 'home').mkdir()
        self.iso = tmp / 'git'
        self.call(['git', '--no-lazy-fetch', 'init', '--bare', '--template=', str(self.iso)])
        self.git('config', 'core.hooksPath', '/dev/null')
        self.git('config', 'gc.auto', '0')
        self.git('config', 'maintenance.auto', 'false')
        (self.iso / 'objects/info/alternates').write_text(str(self.gd / 'objects') + '\n')
        self.scanner = Path(args.scanner or HERE / 'scan-secrets.py').resolve()
        need(self.scanner.is_file() and os.access(self.scanner, os.X_OK), 'MISSING_DEPENDENCY', 69)
        self.ref = self.source_git('symbolic-ref', '-q', 'HEAD').decode().strip()
        need(self.ref.startswith('refs/heads/'), 'BLOCKED_BRANCH', 66)
        self.git('check-ref-format', 'refs/heads/' + args.branch)
        need(args.branch == self.ref[len('refs/heads/'):], 'BLOCKED_BRANCH', 66)
        self.head = self.source_git('rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
        need(re.fullmatch('[0-9a-f]{40}', self.head), 'UNSUPPORTED_REPOSITORY')
        need(self.source_git('rev-parse', '--show-toplevel').decode().strip() == str(self.src))
        for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply',
                     'BISECT_LOG', 'index.lock', 'ai-agent-sync-transaction', 'ai-agent-migration-transaction'):
            if name == 'ai-agent-migration-transaction' and getattr(args, 'allow_migration_recovery', False):
                continue
            need(not (self.gd / name).exists(), 'BLOCKED_CONFLICT', 66)
        self.remote = '' if self.offline else self.remote_url(args.remote)

    def call(self, cmd, data=None, env=None, code=70, label='GIT_ERROR'):
        try:
            p = subprocess.run(cmd, input=data, env=env or self.env, cwd=self.tmp,
                               capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise Block(71, 'PREPARATION_TIMEOUT') from None
        except FileNotFoundError:
            raise Block(69, 'MISSING_DEPENDENCY') from None
        need(p.returncode == 0, label, code)
        return p.stdout

    def git(self, *args, data=None, network=False):
        env = self.env.copy()
        if network:
            env['GIT_ALLOW_PROTOCOL'] = 'file:https:ssh'
            # SSH agent authentication is permitted only for explicit network operations.
            if os.environ.get('SSH_AUTH_SOCK'):
                env['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']
            # No user SSH config, ProxyCommand, prompts or host-key writes. The agent and
            # the user's default identity files (~/.ssh/id_*) are both accepted; a
            # passphrase-protected file without an agent fails closed under BatchMode.
            known = Path(os.path.expanduser('~/.ssh/known_hosts'))
            import shlex
            env['GIT_SSH_COMMAND'] = ('ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=yes '
                                      '-o UpdateHostKeys=no '
                                      '-o UserKnownHostsFile=' + shlex.quote(str(known)))
        return self.call(['git', '--no-lazy-fetch', '--git-dir=' + str(self.iso), *args], data, env,
                         71 if network else 70, 'NETWORK_ERROR' if network else 'GIT_ERROR')

    def source_git(self, *args, data=None):
        return self.call(['git', '--no-lazy-fetch', '-c', 'core.hooksPath=/dev/null',
                          '-c', 'core.fsmonitor=false', '-C', str(self.src), *args], data)

    def remote_url(self, value):
        need(not any(ord(c) < 32 for c in value), 'INVALID_REMOTE')
        if value.startswith('/'):
            p = Path(value).resolve()
            need(p.is_dir() and p != self.src and self.src not in p.parents and self.dst not in p.parents,
                 'INVALID_REMOTE')
            return str(p)
        need(' ' not in value, 'INVALID_REMOTE')
        # Git 的 scp 型式 user@host:path 視為 ssh://user@host/path；plan 記錄正規化後的 URL。
        scp = re.fullmatch(r'([A-Za-z0-9._-]+)@([A-Za-z0-9.-]+):([^/:][^:]*)', value)
        if scp and '://' not in value:
            value = 'ssh://%s@%s/%s' % scp.groups()
        u = urlsplit(value)
        need(u.scheme in ('https', 'ssh') and u.hostname and u.path.startswith('/')
             and not u.password and not u.query and not u.fragment, 'INVALID_REMOTE')
        need(u.scheme != 'https' or not u.username, 'INVALID_REMOTE')
        return value

    def fetch(self):
        self.git('fetch', '--no-tags', '--no-recurse-submodules', '--no-write-fetch-head',
                 self.remote, 'refs/heads/' + self.a.branch + ':refs/heads/incoming', network=True)
        return self.git('rev-parse', 'refs/heads/incoming^{commit}').decode().strip()

    def ancestor(self, a, b):
        return self.git('merge-base', a, b).decode().strip() == a

    def tree(self, commit):
        entries = {}
        for item in self.git('ls-tree', '-rz', commit).split(b'\x00'):
            if not item:
                continue
            header, path = item.split(b'\t', 1)
            mode, kind, oid = header.decode().split()
            entries[path] = (mode, kind, oid)
        return entries

    def scoped(self, commit):
        entries = self.tree(commit)
        out = {}
        for path in self.files:
            need(path.encode() in entries, 'BLOCKED_LAYOUT')
            mode, kind, oid = entries[path.encode()]
            need(kind == 'blob' and mode in ('100644', '100755'), 'BLOCKED_LAYOUT')
            size = int(self.git('cat-file', '-s', oid))
            need(size <= LIMIT, 'UNSUPPORTED_CONTENT')
            out[path] = (self.git('cat-file', 'blob', oid), int(mode[-3:], 8))
        return out

    def scan(self, snap, scope='source'):
        with tempfile.TemporaryDirectory(dir=self.tmp) as d:
            root = Path(d)
            for p, (content, _) in snap.items():
                text_file(content)
                target = root / 'snapshot' / scope / p
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            report = root / 'report.json'
            try:
                run = subprocess.run([str(self.scanner), str(root / 'snapshot'), str(report)],
                                     cwd=self.tmp, env=self.env, capture_output=True, timeout=120)
                findings = api.validate_report(api.read_json(report), run.returncode)
            except (api.ScanError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                raise Block(70, 'SCANNER_ERROR') from None
            if run.returncode == 10:
                for item in findings:
                    print('FINDING: %s:%d rule=%s' % (item['file'], item['line'], item['rule']))
                raise Block(67, 'BLOCKED_SECRET')
            need(run.returncode == 0, 'MISSING_DEPENDENCY' if run.returncode == 69 else 'SCANNER_ERROR',
                 69 if run.returncode == 69 else 70)

    def render(self, snap):
        for p, (content, _) in snap.items():
            text_file(content)
            if p.endswith('.tmpl'):
                need(content == api.wrapper(p), 'UNSUPPORTED_TEMPLATE')
            elif p.startswith('.chezmoitemplates/'):
                try:
                    api.decode_shared(content)
                except ValueError:
                    raise Block(65, 'UNSUPPORTED_TEMPLATE') from None
        snap = {p: (api.decode_shared(v[0]), v[1]) if p.startswith('.chezmoitemplates/') else v
                for p, v in snap.items()}
        result = {}
        products = ('claude', 'codex') if self.profile == 'claude-codex' else (self.profile,)
        for product in products:
            target = '.' + product + ('/CLAUDE.md' if product == 'claude' else '/AGENTS.md')
            result[target] = (api.BANNER + snap[PREFIX + 'shared/instructions.md'][0] + b'\n'
                              + snap[PREFIX + 'adapters/' + product + '.md'][0], 0o644)
            home = 'claude' if product == 'claude' else 'agents'
            for skill in api.SKILLS:
                result['.' + home + '/skills/' + skill + '/SKILL.md'] = (
                    snap[PREFIX + 'shared/skills/' + skill + '/SKILL.md'][0], 0o644)
        for name in SCRIPTS:
            result['.config/ai-agent/bin/' + name] = (snap[PREFIX + 'shared/scripts/' + name][0],
                                                   0o644 if name.endswith('.json') else 0o755)
        if 'claude' in products:
            result['.claude/settings.json'] = (snap['dot_claude/settings.json'][0], 0o644)
            result['.claude/skills/dotfiles-sync/sync.sh'] = (snap[PREFIX + 'shared/scripts/legacy-sync.sh'][0], 0o755)
        return result

    def migration_baseline(self):
        root = Path(getattr(self.a, 'baseline', '') or '/')
        need(self.offline and getattr(self.a, 'baseline_id', None), 'BLOCKED_MIGRATION_BASELINE', 66)
        raw = read(root / 'manifest.json')[0]
        need(digest(raw) == self.a.baseline_id, 'BLOCKED_STALE_BASELINE', 68)
        doc = api.read_json(root / 'manifest.json')
        need(doc['schema'] == 1, 'INVALID_BASELINE')
        need(doc['source'] == str(self.src) and doc['destination'] == str(self.dst)
             and doc['profile'] == self.profile and doc['git'] == self.git_state(), 'BLOCKED_STALE_BASELINE', 68)
        need(doc['mode'] in ('legacy', 'enable-codex'), 'INVALID_BASELINE')
        expected = set(self.files) | (set(api.LEGACY_FILES) if doc['mode'] == 'legacy' else set())
        need(set(doc['after']['source']) == expected, 'INVALID_BASELINE')
        for p, entry in doc['after']['source'].items():
            if entry is None:
                safe(self.src / p)
                need(not (self.src / p).exists(), 'BLOCKED_INCOMPLETE_MIGRATION', 66)
        result = {}
        for p in self.files:
            entry = doc['after']['source'][p]
            need(type(entry) is list and len(entry) == 2 and type(entry[0]) is str
                 and re.fullmatch('[0-9a-f]{64}', entry[0]) and type(entry[1]) is int
                 and 0 <= entry[1] <= 0o777, 'INVALID_BASELINE')
            content = read(root / 'blobs' / entry[0])[0]
            need(digest(content) == entry[0], 'BLOCKED_STALE_BASELINE', 68)
            result[p] = (content, entry[1])
        return result

    def git_state(self):
        return dict(head=self.source_git('rev-parse', 'HEAD').decode().strip(),
                    ref=self.source_git('symbolic-ref', 'HEAD').decode().strip(),
                    index=summary({'index': read(self.gd / 'index')}),
                    config=summary({'config': read(self.gd / 'config')}))

    def history(self, older, newer):
        need(self.ancestor(older, newer), 'BLOCKED_NON_FAST_FORWARD', 66)
        commits = self.git('rev-list', '--reverse', older + '..' + newer).decode().split()
        need(len(commits) <= 1000, 'BLOCKED_HISTORY_LIMIT', 66)
        for oid in commits:
            raw = self.git('cat-file', 'commit', oid)
            # Commit metadata/messages can contain secrets too. Neutral scanner path.
            self.scan({FILES[0]: (raw, 0o644)})
            parents = [line[7:].decode() for line in raw.split(b'\n\n', 1)[0].splitlines()
                       if line.startswith(b'parent ')]
            need(len(parents) == 1, 'BLOCKED_MERGE_HISTORY', 66)
            before, after = self.tree(parents[0]), self.tree(oid)
            changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
            need(changed and changed <= {p.encode() for p in self.files}, 'BLOCKED_OUT_OF_SCOPE_HISTORY', 66)
            snap = self.scoped(oid)
            self.scan(snap)
            self.scan(self.render(snap), 'render')
        return commits

    def state(self):
        result = dict(head=self.source_git('rev-parse', 'HEAD').decode().strip(),
                    ref=self.source_git('symbolic-ref', 'HEAD').decode().strip(),
                    index=summary({'index': read(self.gd / 'index')}),
                    config=summary({'config': read(self.gd / 'config')}),
                    source=summary(snapshot(self.src, self.files)),
                    target=summary(snapshot(self.dst, self.targets)))
        return result

    def clean_index(self):
        # Clean entire index, including unrelated staged files and special flags.
        index = self.source_git('ls-files', '--stage', '-z')
        entries = {}
        for record in index.split(b'\x00'):
            if record:
                header, path = record.split(b'\t', 1)
                mode, oid, stage = header.decode().split()
                need(stage == '0', 'BLOCKED_CONFLICT', 66)
                entries[path] = (mode, 'blob' if mode != '160000' else 'commit', oid)
        need(entries == self.tree(self.head), 'BLOCKED_STAGED_CHANGES', 66)
        flags = self.source_git('ls-files', '-v', '-z').split(b'\x00')
        need(all(not p or p.startswith(b'H ') for p in flags), 'BLOCKED_INDEX_FLAGS', 66)

    def build(self):
        diagnostics.mark('build_candidate')
        self.before = self.state()
        need(self.before['head'] == self.head and self.before['ref'] == self.ref, 'BLOCKED_STALE_PLAN', 68)
        self.clean_index()
        self.working = snapshot(self.src, self.files)
        self.deployed = snapshot(self.dst, self.targets)  # Missing targets require separate migration.
        baseline = self.migration_baseline() if getattr(self.a, 'baseline', None) else self.scoped(self.head)
        self.scan(baseline)
        self.scan(self.working)
        self.scan(self.deployed, 'target')
        base_render = self.render(baseline)
        self.remote_head = self.head if self.offline else self.fetch()
        if self.a.operation == 'in':
            need(self.ancestor(self.head, self.remote_head), 'BLOCKED_NON_FAST_FORWARD', 66)
            commits = self.history(self.head, self.remote_head)
            if self.remote_head != self.head:
                need(normalized(self.working) == baseline, 'BLOCKED_LOCAL_CHANGES', 66)
                self.candidate = self.scoped(self.remote_head)
            else:
                self.candidate = self.working
        else:
            commits = self.history(self.remote_head, self.head)
            self.candidate = self.working
        rendered = self.render(self.candidate)
        self.scan(rendered, 'render')
        for p in self.targets:
            need(normalized({p: self.deployed[p]})[p] in (base_render[p], rendered[p]), 'DRIFT', 2)
        self.rendered = rendered
        self.git('read-tree', self.head)
        for p, (content, mode) in self.candidate.items():
            oid = self.git('hash-object', '-w', '--stdin', '--no-filters', data=content).decode().strip()
            self.git('update-index', '--add', '--cacheinfo', '100755' if mode & 0o111 else '100644', oid, p)
        self.candidate_tree = self.git('write-tree').decode().strip()
        if self.a.operation == 'in' and self.remote_head != self.head:
            need(self.candidate_tree == self.git('rev-parse', self.remote_head + '^{tree}').decode().strip())
        self.scan({FILES[0]: (self.a.message.encode(), 0o644)})
        need(self.state() == self.before, 'BLOCKED_STALE_PLAN', 68)
        tools = {p: digest(read(HERE / p)[0]) for p in SCRIPTS}
        tools['scanner'] = digest(read(self.scanner)[0])
        return dict(schema=3, profile=self.profile, repository_profile=self.repository_profile, offline=self.offline,
                    baseline_id=getattr(self.a, 'baseline_id', None), operation=self.a.operation, source=str(self.src), destination=str(self.dst),
                    remote=self.remote, branch=self.a.branch, scanner=str(self.scanner),
                    message=self.a.message, identity=[self.a.author_name, self.a.author_email],
                    state=self.before, remote_head=self.remote_head, commits=commits,
                    baseline=summary(baseline), candidate=summary(self.candidate), rendered=summary(rendered),
                    tree=self.candidate_tree, tools=tools)

    def transfer_objects(self):
        diagnostics.mark('transfer_objects')
        for parent, dirs, files in os.walk(self.iso / 'objects'):
            rel = Path(parent).relative_to(self.iso / 'objects')
            if rel.parts and rel.parts[0] == 'info':
                continue
            for name in files:
                source = Path(parent) / name
                dest = self.gd / 'objects' / rel / name
                safe(dest)
                dest.parent.mkdir(exist_ok=True)
                if not dest.exists():
                    # Publish complete immutable Git objects with an atomic rename.
                    fd, temporary = tempfile.mkstemp(dir=dest.parent)
                    try:
                        with os.fdopen(fd, 'wb') as f, source.open('rb') as src:
                            shutil.copyfileobj(src, f)
                            f.flush()
                            os.fsync(f.fileno())
                        os.replace(temporary, dest)
                    except BaseException as error:
                        diagnostics.capture(error)
                        raise
                    finally:
                        with diagnostics.cleaning('object_temporary'):
                            if os.path.exists(temporary):
                                os.unlink(temporary)

    def transact(self, new_head, changes, new_index):
        diagnostics.mark('create_journal')
        need(self.state() == self.before, 'BLOCKED_STALE_PLAN', 68)
        journal = self.gd / 'ai-agent-sync-transaction'
        journal.mkdir(mode=0o700)
        diagnostics.transaction_started = True
        backups, committed, ref_attempted = [], False, False
        index_lock = self.gd / 'index.lock'
        acquired = False
        try:
            diagnostics.mark('index_lock')
            # Git's own index lock prevents cooperating ordinary Git writers too.
            with index_lock.open('xb') as f:
                acquired = True
                f.write(new_index)
                f.flush()
                os.fsync(f.fileno())
            need(self.state() == self.before, 'BLOCKED_STALE_PLAN', 68)
            changes = [(p, v) for p, v in changes if read(p) != v]
            changes.append((self.gd / 'index', (new_index, read(self.gd / 'index')[1])))
            manifest = []
            diagnostics.mark('backup_files')
            for n, (path, value) in enumerate(changes):
                old = read(path)
                atomic(journal / ('old-%d' % n), (old[0], 0o600))
                atomic(journal / ('new-%d' % n), (value[0], 0o600))
                backups.append((path, value, old))
                manifest.append(dict(path=str(path), old_mode=old[1], new_mode=value[1],
                                     old_hash=digest(old[0]), new_hash=digest(value[0])))
            record = dict(ref=self.ref, old_head=self.head, new_head=new_head, files=manifest)
            diagnostics.mark('write_manifest')
            atomic(journal / 'manifest.json', (encoded(record), 0o600))
            diagnostics.mark('apply_files')
            for n, (path, value) in enumerate(changes):
                need(read(path) == ((journal / ('old-%d' % n)).read_bytes(), manifest[n]['old_mode']),
                     'BLOCKED_STALE_PLAN', 68)
                atomic(path, value)
            diagnostics.mark('update_ref')
            need(self.source_git('symbolic-ref', 'HEAD').decode().strip() == self.ref, 'BLOCKED_STALE_PLAN', 68)
            if new_head != self.head:
                ref_attempted = True
                self.source_git('update-ref', self.ref, new_head, self.head)
            else:
                need(self.source_git('rev-parse', self.ref).decode().strip() == self.head,
                     'BLOCKED_STALE_PLAN', 68)
            committed = True
        except BaseException as error:
            diagnostics.capture(error)
            diagnostics.rollback = dict(attempted=True, result='unknown')
            # A killed/timed-out update-ref may already have committed. Preserve
            # the journal instead of rolling files back underneath an advanced ref.
            if ref_attempted:
                try:
                    diagnostics.mark('verify_ref')
                    current = self.source_git('rev-parse', self.ref).decode().strip()
                    need(current == self.head, 'RECOVERY_REQUIRED', 72)
                except BaseException as recovery_error:
                    diagnostics.capture(recovery_error)
                    diagnostics.rollback['result'] = 'failed'
                    raise Block(72, 'RECOVERY_REQUIRED') from None
            # Never overwrite a third-party edit while rolling back.
            recovered = True
            diagnostics.mark('restore_files')
            for path, new, old in reversed(backups):
                try:
                    current = read(path)
                    if current == old:
                        continue
                    need(current == new)
                    atomic(path, old)
                except BaseException as recovery_error:
                    diagnostics.capture(recovery_error)
                    recovered = False
            diagnostics.rollback['result'] = 'succeeded' if recovered else 'failed'
            if recovered:
                with diagnostics.cleaning('remove_journal'):
                    shutil.rmtree(journal)
            else:
                raise Block(72, 'RECOVERY_REQUIRED') from None
            raise
        finally:
            if acquired:
                with diagnostics.cleaning('remove_index_lock'):
                    index_lock.unlink()
        if committed:
            with diagnostics.cleaning('remove_journal'):
                shutil.rmtree(journal)

    def execute(self):
        diagnostics.transaction_started = False
        diagnostics.rollback = dict(attempted=False, result='not_attempted')
        diagnostics.mark('activate')
        if self.a.operation == 'in':
            changes = [(self.dst / p, v) for p, v in self.rendered.items()]
            if self.remote_head != self.head:
                changes += [(self.src / p, v) for p, v in self.candidate.items()]
                new_index = (self.iso / 'index').read_bytes()
            else:
                new_index = read(self.gd / 'index')[0]
            if self.remote_head == self.head and all(read(p) == v for p, v in changes):
                print('NO_CHANGES')
                return
            if self.remote_head != self.head:
                self.transfer_objects()
            self.transact(self.remote_head, changes, new_index)
            print('OK: approved source and generated outputs applied')
            return
        new_head = self.head
        if self.candidate_tree != self.git('rev-parse', self.head + '^{tree}').decode().strip():
            need(self.a.author_name and self.a.author_email, 'USAGE: author identity required', 64)
            env = self.env.copy()
            for role in ('AUTHOR', 'COMMITTER'):
                env['GIT_' + role + '_NAME'] = self.a.author_name
                env['GIT_' + role + '_EMAIL'] = self.a.author_email
            new_head = self.call(['git', '--no-lazy-fetch', '--git-dir=' + str(self.iso), 'commit-tree',
                                  self.candidate_tree, '-p', self.head],
                                 (self.a.message + '\n').encode(), env).decode().strip()
            # Inspect the actual commit and every newly outbound snapshot again.
            self.history(self.remote_head, new_head)
            need(self.git('rev-parse', new_head + '^{tree}').decode().strip() == self.candidate_tree)
            self.transfer_objects()
            self.transact(new_head, [(self.dst / p, v) for p, v in self.rendered.items()],
                          (self.iso / 'index').read_bytes())
        else:
            changes = [(self.dst / p, v) for p, v in self.rendered.items() if read(self.dst / p) != v]
            if changes:
                self.transact(new_head, changes, read(self.gd / 'index')[0])
            else:
                need(self.state() == self.before, 'BLOCKED_STALE_PLAN', 68)
        if new_head == self.remote_head:
            print('NO_CHANGES')
            return
        # Explicit expected-OID lease closes the fetch/push race. Ancestry was
        # independently checked: this can never authorize a non-fast-forward.
        try:
            self.git('push', '--porcelain', '--no-verify', '--no-follow-tags',
                     '--force-with-lease=refs/heads/' + self.a.branch + ':' + self.remote_head,
                     self.remote, new_head + ':refs/heads/' + self.a.branch, network=True)
        except Block:
            raise Block(71, 'NETWORK_ERROR: local commit retained; re-plan before retry') from None
        print('OK: approved commit pushed')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Block(64, 'USAGE: explicit source, destination, remote, branch and plan required')


def external(path, source, destination):
    """Outside the source checkout and outside every deployment namespace."""
    return (not api.overlaps(path, source) and path != destination
            and not any(api.overlaps(path, destination / region) for region in api.TARGET_REGIONS))


def configure(a):
    """Fill options the caller left unset from the reviewed local configuration file."""
    if not a.config:
        return {}
    need(Path(a.config).is_absolute(), 'USAGE: absolute paths required', 64)
    try:
        values = api.load_config(a.config)
    except (ValueError, OSError, api.ScanError):
        raise Block(78, 'INVALID_CONFIG') from None
    for key in ('source', 'destination', 'branch', 'scanner', 'profile', 'repository_profile'):
        if getattr(a, key) is None and key in values:
            setattr(a, key, values[key])
    if a.remote is None and not a.offline and 'remote' in values:
        a.remote = values['remote']
    for key in ('author_name', 'author_email'):
        if not getattr(a, key) and key in values:
            setattr(a, key, values[key])
    return values


def resolve_plan(a, values):
    """Without --plan, a new plan file is created in plan_dir or an approved one is located by ID."""
    if a.plan or 'plan_dir' not in values:
        return
    plan_dir = Path(values['plan_dir'])
    if a.command == 'plan':
        plan_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        a.plan = str(plan_dir / ('sync-plan-%s-%s-%s.json' % (a.operation, stamp, secrets.token_hex(4))))
        return
    need(plan_dir.is_dir(), 'PLAN_NOT_FOUND', 66)
    plan_dir = plan_dir.resolve()
    for candidate in sorted(plan_dir.glob('sync-plan-*.json'))[:1000]:
        if candidate.is_symlink():
            continue
        value = read(candidate, missing=True)
        if value and digest(value[0]) == a.approve:
            a.plan = str(candidate)
            return
    raise Block(66, 'PLAN_NOT_FOUND')


def arguments():
    p = Parser(add_help=True)
    p.add_argument('command', choices=('plan', 'in', 'push', 'check'))
    p.add_argument('--operation', choices=('in', 'push'))
    for arg in ('source', 'destination', 'branch', 'plan', 'remote', 'scanner', 'config'):
        p.add_argument('--' + arg)
    p.add_argument('--profile', choices=api.PROFILES)
    p.add_argument('--repository-profile', choices=api.PROFILES)
    p.add_argument('--agent', choices=('claude', 'codex'))
    p.add_argument('--offline', action='store_true')
    p.add_argument('--force', action='store_true')
    p.add_argument('--baseline')
    p.add_argument('--baseline-id')
    p.add_argument('--approve')
    p.add_argument('--message')
    p.add_argument('--author-name', default='')
    p.add_argument('--author-email', default='')
    a = p.parse_args()
    need(a.command != 'plan' or a.operation, 'USAGE: plan needs --operation in|push', 64)
    need(a.command == 'plan' or not a.operation, 'USAGE: operation is for plan only', 64)
    a.operation = a.operation if a.command == 'plan' else a.command
    values = configure(a)
    a.profile = a.profile or 'claude-codex'
    a.message_given = a.message is not None
    a.message = a.message if a.message is not None else 'chore: sync shared agent configuration'
    need(a.source and a.destination and a.branch, 'USAGE: explicit source, destination and branch required', 64)
    need(not a.offline or (a.operation == 'in' and not a.remote), 'USAGE: offline is local in only', 64)
    need(a.offline or a.remote, 'USAGE: remote required', 64)
    need(not a.baseline or (a.offline and a.baseline_id), 'USAGE: baseline requires offline and ID', 64)
    for value in (a.message, a.author_name, a.author_email):
        need(len(value) <= 4096 and not any(ord(c) < 32 for c in value), 'USAGE: invalid text option', 64)
    # 角色：參數檔的 writer 決定哪個 agent 可以套用與發布；其他 agent 只能記錄、檢查、規劃。
    writer = values.get('writer')
    need(not (a.agent and writer and a.command in ('in', 'push') and a.agent != writer),
         'NOT_WRITER: only the configured writer applies or publishes; report pending instead', 77)
    a.config_values = values
    if a.command == 'check':
        need(not a.approve and not a.plan and not a.offline, 'USAGE: check takes no plan, approval or offline', 64)
        for value in (a.source, a.destination, a.scanner or '/'):
            need(Path(value).is_absolute(), 'USAGE: absolute paths required', 64)
        return a
    # auto_in：只有 in、只有參數檔明確為 true、且必須指明 plan 檔；push 永遠需要 --approve。
    a.auto = (a.command == 'in' and not a.approve and values.get('auto_in') is True and bool(a.plan))
    need(a.command == 'plan' or a.auto or (a.approve and re.fullmatch('[0-9a-f]{64}', a.approve)),
         'USAGE: --approve PLAN_ID required', 64)
    resolve_plan(a, values)
    need(a.plan, 'USAGE: --plan or configured plan_dir required', 64)
    for value in (a.source, a.destination, a.plan, a.scanner or '/', a.baseline or '/'):
        need(Path(value).is_absolute(), 'USAGE: absolute paths required', 64)
    return a


def check(args):
    """Remote freshness only: fetch into quarantine and compare, without scanning or writing a plan."""
    values = args.config_values
    state_file = Path(values['plan_dir']) / 'last-check.json' if 'plan_dir' in values else None
    if state_file is not None and not args.force and state_file.parent.is_dir():
        previous = read(state_file.parent.resolve() / state_file.name, missing=True)
        if previous is not None:
            record = json.loads(previous[0])
            if (type(record) is dict and type(record.get('checked')) is int and type(record.get('result')) is str
                    and time.strftime('%Y-%m-%d', time.localtime(record['checked'])) == time.strftime('%Y-%m-%d')):
                print('CHECKED_TODAY: ' + time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(record['checked'])))
                print('REMOTE: ' + record['result'] + ' (previous result; use --force to refresh)')
                return 0
            if os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1' and type(record.get('checked')) is int and type(record.get('result')) is str:
                # 沙箱內無網路：不嘗試連線，回報上次（非今日）的結果與日期供參考。
                print('CHECK_SKIPPED: sandbox network disabled; remote freshness unknown')
                print('REMOTE: ' + record['result'] + ' (previous result from '
                      + time.strftime('%Y-%m-%d', time.localtime(record['checked'])) + ')')
                return 0
    if os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1':
        print('CHECK_SKIPPED: sandbox network disabled; remote freshness unknown')
        return 0
    temporary = tempfile.TemporaryDirectory(prefix='ai-agent-check-', dir='/tmp')
    try:
        engine = Engine(args, Path(temporary.name))
        remote_head = engine.fetch()
        if remote_head == engine.head:
            result = 'UP_TO_DATE'
        elif engine.ancestor(engine.head, remote_head):
            result = 'BEHIND %d' % len(engine.git('rev-list', engine.head + '..' + remote_head).split())
        elif engine.ancestor(remote_head, engine.head):
            result = 'AHEAD %d' % len(engine.git('rev-list', remote_head + '..' + engine.head).split())
        else:
            result = 'DIVERGED'
    finally:
        with diagnostics.cleaning('temporary_workspace'):
            temporary.cleanup()
    print('HEAD: ' + engine.head)
    print('REMOTE_HEAD: ' + remote_head)
    print('REMOTE: ' + result)
    if state_file is not None:
        state_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = state_file.parent.resolve() / state_file.name
        atomic(target, (encoded(dict(checked=int(time.time()), head=engine.head, remote_head=remote_head,
                                     result=result)), 0o600))
    return 0



@contextlib.contextmanager
def lock(source):
    """One atomic mkdir lock per source; a leftover directory is never removed automatically."""
    diagnostics.mark('source_lock')
    path = source / '.git/ai-agent-sync.lock'
    safe(path)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        raise Block(73, 'BLOCKED_LOCK') from None
    try:
        atomic(path / 'owner.json', (encoded(dict(pid=os.getpid(), started=int(time.time()))), 0o600))
        yield
    except BaseException as error:
        diagnostics.capture(error)
        raise
    finally:
        with diagnostics.cleaning('release_lock'):
            shutil.rmtree(path)


def main():
    global diagnostics
    diagnostics = Diagnostics()
    diagnostics.transaction_started = False
    diagnostics.rollback = dict(attempted=False, result='not_attempted')
    diagnostics.mark('validate_plan')
    os.umask(0o077)
    args = arguments()
    layout(args)  # Reject unsafe paths before even creating a source lock.
    # 封存的 bootstrap／cohort 協定留下的標記一律拒絕並原樣保留；不進入 lock 或任何寫入。
    for name in COORDINATION_MARKERS:
        marker = Path(args.source).resolve() / '.git' / name
        need(not marker.exists() and not marker.is_symlink(), 'BLOCKED_UNSUPPORTED_COORDINATION', 73)
    if args.command == 'check':
        return check(args)
    plan_path = Path(args.plan)
    need(plan_path.parent.is_dir(), 'INVALID_PLAN_PATH')
    # 目錄別名（例如 macOS /tmp）先正規化；plan 本身不得是 symlink，且必須位於
    # source 與所有部署區域之外。destination HOME 下的其他位置是允許的。
    plan_path = plan_path.parent.resolve() / plan_path.name
    need(not plan_path.is_symlink(), 'BLOCKED_SYMLINK')
    need(external(plan_path, Path(args.source).resolve(), Path(args.destination).resolve()), 'INVALID_PLAN_PATH')
    approved = None
    if args.command != 'plan':
        value = read(plan_path)
        need(value[1] & 0o077 == 0, 'INVALID_PLAN_PERMISSIONS')
        approved = value[0]
        if args.auto:
            args.approve = digest(approved)
        need(digest(approved) == args.approve, 'BLOCKED_STALE_PLAN', 68)
        document = json.loads(approved)
        need(type(document) is dict and type(document.get('plan')) is dict, 'INVALID_PLAN')
        # 未明確給定的訊息與作者身分取自已核准的 plan，避免同一 plan 因預設訊息不同而被判過期。
        recorded = document['plan']
        if not args.message_given and type(recorded.get('message')) is str:
            args.message = recorded['message']
        identity = recorded.get('identity')
        if (not args.author_name and not args.author_email and type(identity) is list and len(identity) == 2
                and all(type(v) is str for v in identity)):
            args.author_name, args.author_email = identity
        for value in (args.message, args.author_name, args.author_email):
            need(len(value) <= 4096 and not any(ord(c) < 32 for c in value), 'INVALID_PLAN')
        need(type(document.get('created')) is int and 0 <= time.time() - document['created'] < 3600,
             'BLOCKED_EXPIRED_PLAN', 68)
    temporary = tempfile.TemporaryDirectory(prefix='ai-agent-write-', dir='/tmp')
    try:
        engine = Engine(args, Path(temporary.name))
        result = engine.build()
        with lock(Path(args.source).resolve()):
            diagnostics.mark('validate_execution')
            need(engine.state() == engine.before, 'BLOCKED_STALE_PLAN', 68)
            if args.command == 'plan':
                diagnostics.mark('write_plan')
                document = dict(created=int(time.time()), plan=result)
                blob = encoded(document)
                with plan_path.open('xb') as output:
                    output.write(blob)
                base = result['baseline'] if result['operation'] == 'push' else result['state']['source']
                for p in engine.files:
                    if result['candidate'][p] != base[p]:
                        print('SOURCE: ' + p + ' before=' + base[p][0] +
                              ' after=' + result['candidate'][p][0] +
                              ' mode=' + oct(result['candidate'][p][1]))
                for p in engine.targets:
                    if result['rendered'][p] != result['state']['target'][p]:
                        print('TARGET: ' + p + ' sha256=' + result['rendered'][p][0])
                for oid in result['commits']:
                    print('COMMIT: ' + oid)
                print('COMMITS: ' + str(len(result['commits'])))
                print('REMOTE_ID: ' + digest(result['remote'].encode()))
                print('BRANCH: ' + args.branch)
                print('PLAN_FILE: ' + str(plan_path))
                print('PLAN_ID: ' + digest(blob))
                print('OK: review the private plan; approval expires in one hour')
            else:
                need(document['plan'] == result, 'BLOCKED_STALE_PLAN', 68)
                need(read(plan_path)[0] == approved, 'BLOCKED_STALE_PLAN', 68)
                need(0 <= time.time() - document['created'] < 3600, 'BLOCKED_EXPIRED_PLAN', 68)
                if args.auto:
                    changed = {p for p in engine.files if result['candidate'][p] != result['baseline'][p]}
                    if not changed <= SHARED_TEXT:
                        print('PLAN_ID: ' + args.approve)
                        raise Block(77, 'PENDING_APPROVAL: plan changes files outside shared text; '
                                        'review and rerun with --approve PLAN_ID')
                    print('AUTO_IN: shared text only; applied under the local auto_in policy')
                engine.execute()
    except BaseException as error:
        diagnostics.capture(error)
        raise
    finally:
        with diagnostics.cleaning('temporary_workspace'):
            temporary.cleanup()
    return 0


def cli():
    try:
        return main()
    except Block as error:
        print(error.label)
        diagnostics.emit(error)
        return error.code
    except KeyboardInterrupt as error:
        print('INTERRUPTED: inspect transaction journal before retry')
        diagnostics.emit(error)
        return 130
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, RecursionError,
            subprocess.SubprocessError) as error:
        print('IO_ERROR: operation stopped; no raw tool output exposed')
        diagnostics.emit(error)
        return 70


if __name__ == '__main__':
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    sys.exit(cli())

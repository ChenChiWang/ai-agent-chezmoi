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

# 純文字的共用來源：instructions、兩個 adapter，以及每個 skill 的本體。auto_in 只可自動套用這些檔案的變更。
# skill 集合的增減一定會動到包裝檔，包裝檔不在這裡，所以集合變動永遠需要明確核准。
SHARED_TEXT = frozenset(
    [PREFIX + 'shared/instructions.md']
    + [PREFIX + 'adapters/' + p + '.md' for p in ('claude', 'codex')])


def shared_text(path):
    return path in SHARED_TEXT or bool(api.skill_of(path, api.SKILL_SOURCES[:1]))


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
        need(not api.is_redirected(p), 'BLOCKED_SYMLINK')


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


def snapshot(root, paths, optional=()):
    # optional：正在加入或移除的 skill 的路徑，檔案可以不存在（以 None 表示）
    return {p: read(root / p, missing=p in optional) for p in paths}


def summary(snap):
    return {p: None if v is None else [digest(v[0]), v[1]] for p, v in snap.items()}


def canonical_mode(mode):
    return 0o755 if mode & 0o111 else 0o644


def normalized(snap):
    return {p: None if v is None else (v[0], canonical_mode(v[1])) for p, v in snap.items()}


def effective_mode(current, canonical):
    # 實際要寫入的權限：現有權限與標準相同或更嚴格（例如 600、700）就保留；
    # 比標準寬鬆（例如 664、775、777）就收回標準 644/755。plan 與執行都用這個結果。
    if current is not None and canonical_mode(current) == canonical and current & 0o777 & ~canonical == 0:
        return current
    return canonical


def fsync_dir(path):
    safe(path)
    fd = api.open_directory(path)
    if fd is None:
        return
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
        api.replace(name, path)
        if value[1] & 0o077 == 0:
            api.make_private(path)
        fsync_dir(path.parent)
    except BaseException as error:
        diagnostics.capture(error)
        raise
    finally:
        with diagnostics.cleaning('atomic_temporary'):
            if os.path.exists(name):
                os.unlink(name)


def place(path, value, made):
    """Write, create or remove one file. Directories created here are appended to `made`."""
    if value is None:
        # 只有 skill 自己的檔案會被移除；目錄空了就一併移除，裡面還有別的檔案就保留
        safe(path)
        path.unlink()
        if not any(path.parent.iterdir()):
            path.parent.rmdir()
            fsync_dir(path.parent.parent)
        else:
            fsync_dir(path.parent)
        return
    missing = [p for p in (path.parent, *path.parent.parents) if not p.exists()]
    for directory in reversed(missing):
        safe(directory)
        directory.mkdir()
        directory.chmod(0o755)
        made.append(directory)
    atomic(path, value)


class Engine:
    def __init__(self, args, tmp):
        diagnostics.mark('initialize_engine')
        self.a, self.tmp = args, tmp
        self.profile = getattr(args, 'profile', 'claude-codex')
        self.files, self.targets = api.mapping(self.profile)
        self.repository_profile = getattr(args, 'repository_profile', None) or self.profile
        need(set(self.files) <= set(api.mapping(self.repository_profile)[0]), 'INVALID_REPOSITORY_PROFILE')
        self.files = api.mapping(self.repository_profile)[0]
        # 以上是範本預設的集合；build() 會換成這份 source 自己的 skill 集合
        self.optional = frozenset()
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
        self.env = dict(api.child_environment(tmp / 'home', os.environ.get('PATH', os.defpath)),
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
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

    def scope(self, skills):
        return api.mapping(self.repository_profile, skills)[0], api.mapping(self.profile, skills)[1]

    def skills(self, paths):
        # 每個 snapshot 的 skill 集合由它自己的路徑決定；名稱不合法或包裝檔沒有對應的 skill 就擋下
        try:
            if isinstance(paths, Path):
                return api.source_skills(paths, self.repository_profile)
            return api.skills_in([p.decode('utf-8', 'replace') if type(p) is bytes else p for p in paths],
                                 self.repository_profile)
        except (ValueError, OSError):
            raise Block(65, 'BLOCKED_LAYOUT: invalid skill name, or wrapper without its skill') from None

    def select(self, *sets):
        # 納入所有相關集合的路徑；只屬於部分集合的 skill，它的檔案可以不存在
        union = api.skill_names(set().union(*sets))
        changing = set(union) - set.intersection(*map(set, sets))
        self.files, self.targets = self.scope(union)
        self.optional = frozenset(p for p in self.files + self.targets if api.skill_of(p) in changing)

    def scoped(self, commit):
        entries = self.tree(commit)
        out = {}
        for path in self.scope(self.skills(entries))[0]:
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
                run = subprocess.run(api.scanner_command(self.scanner) + [str(root / 'snapshot'), str(report)],
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
        skills = self.skills(snap)
        products = ('claude', 'codex') if self.profile == 'claude-codex' else (self.profile,)
        for product in products:
            target = '.' + product + ('/CLAUDE.md' if product == 'claude' else '/AGENTS.md')
            result[target] = (api.BANNER + snap[PREFIX + 'shared/instructions.md'][0] + b'\n'
                              + snap[PREFIX + 'adapters/' + product + '.md'][0], 0o644)
            home = 'claude' if product == 'claude' else 'agents'
            for skill in skills:
                result['.' + home + '/skills/' + skill + '/SKILL.md'] = (
                    snap[PREFIX + 'shared/skills/' + skill + '/SKILL.md'][0], 0o644)
        for name in SCRIPTS:
            result['.config/ai-agent/bin/' + name] = (snap[PREFIX + 'shared/scripts/' + name][0],
                                                   0o644 if name.endswith('.json') else 0o755)
        if 'claude' in products:
            result['.claude/settings.json'] = (snap['dot_claude/settings.json'][0], 0o644)
            result['.claude/skills/dotfiles-sync/sync.sh'] = (snap[PREFIX + 'shared/scripts/legacy-sync.sh'][0], 0o755)
        return result

    def baseline_manifest(self):
        root = Path(getattr(self.a, 'baseline', '') or '/')
        need(self.offline and getattr(self.a, 'baseline_id', None), 'BLOCKED_MIGRATION_BASELINE', 66)
        raw = read(root / 'manifest.json')[0]
        need(digest(raw) == self.a.baseline_id, 'BLOCKED_STALE_BASELINE', 68)
        doc = api.read_json(root / 'manifest.json')
        need(type(doc) is dict and doc.get('schema') == 1 and type(doc.get('after')) is dict
             and type(doc['after'].get('source')) is dict, 'INVALID_BASELINE')
        return root, doc

    def migration_baseline(self):
        root, doc = self.baseline_manifest()
        files = self.scope(self.base_skills)[0]
        need(doc['source'] == str(self.src) and doc['destination'] == str(self.dst)
             and doc['profile'] == self.profile and doc['git'] == self.git_state(), 'BLOCKED_STALE_BASELINE', 68)
        need(doc['mode'] in ('legacy', 'enable-codex'), 'INVALID_BASELINE')
        expected = set(files) | (set(api.legacy_files(self.base_skills)) if doc['mode'] == 'legacy' else set())
        need(set(doc['after']['source']) == expected, 'INVALID_BASELINE')
        for p, entry in doc['after']['source'].items():
            if entry is None:
                safe(self.src / p)
                need(not (self.src / p).exists(), 'BLOCKED_INCOMPLETE_MIGRATION', 66)
        result = {}
        for p in files:
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
            # 範圍是這個 commit 前後兩個集合的路徑：新增的 skill 在後者，移除的 skill 在前者
            allowed = self.scope(self.skills(before))[0] + self.scope(self.skills(after))[0]
            need(changed and changed <= {p.encode() for p in allowed}, 'BLOCKED_OUT_OF_SCOPE_HISTORY', 66)
            snap = self.scoped(oid)
            self.scan(snap)
            self.scan(self.render(snap), 'render')
        return commits

    def state(self):
        result = dict(head=self.source_git('rev-parse', 'HEAD').decode().strip(),
                    ref=self.source_git('symbolic-ref', 'HEAD').decode().strip(),
                    index=summary({'index': read(self.gd / 'index')}),
                    config=summary({'config': read(self.gd / 'config')}),
                    source=summary(snapshot(self.src, self.files, self.optional)),
                    target=summary(snapshot(self.dst, self.targets, self.optional)))
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
        local = self.skills(self.src)
        # 轉換後尚未 commit 時，基準是已核准的轉換清單，集合也從它讀出
        self.base_skills = (self.skills(self.baseline_manifest()[1]['after']['source'])
                            if getattr(self.a, 'baseline', None) else self.skills(self.tree(self.head)))
        self.select(self.base_skills, local)
        self.before = self.state()
        need(self.before['head'] == self.head and self.before['ref'] == self.ref, 'BLOCKED_STALE_PLAN', 68)
        self.clean_index()
        need(all((self.src / p).exists() for p in self.scope(local)[0] if p in self.optional),
             'BLOCKED_LAYOUT: skill without its wrappers')
        self.working = snapshot(self.src, self.scope(local)[0])
        # Missing targets require separate migration, except those of a skill being added or removed.
        self.deployed = snapshot(self.dst, self.targets, self.optional)
        baseline = self.migration_baseline() if getattr(self.a, 'baseline', None) else self.scoped(self.head)
        self.scan(baseline)
        self.scan(self.working)
        self.scan({p: v for p, v in self.deployed.items() if v is not None}, 'target')
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
            # 執行位元由 git 決定：commit 用 HEAD 的模式，HEAD 沒有的新檔案一律 644。檔案系統的位元
            # 不可信（Windows 的 stat 對所有檔案回報 666），只在執行時被收回成 git 的值（#31）
            self.candidate = {p: (v[0], baseline[p][1] if p in baseline else 0o644) for p, v in self.working.items()}
        rendered = self.render(self.candidate)
        self.scan(rendered, 'render')
        self.skill_set = self.skills(self.candidate)
        # 遠端新增的 skill：它的路徑到這裡才知道。納入範圍並記錄目前的狀態，之後的過期檢查才涵蓋得到。
        added = [p for p in self.candidate if p not in self.files], [p for p in rendered if p not in self.targets]
        if added[0] or added[1]:
            incoming = snapshot(self.src, added[0], added[0]), snapshot(self.dst, added[1], added[1])
            need(not any(incoming[0].values()), 'BLOCKED_LOCAL_CHANGES', 66)
            existing = {p: v for p, v in incoming[1].items() if v is not None}
            if existing:
                self.scan(existing, 'target')
            self.deployed.update(incoming[1])
            self.files, self.targets = self.files + tuple(added[0]), self.targets + tuple(added[1])
            self.optional = self.optional | frozenset(added[0] + added[1])
            self.before['source'].update(summary(incoming[0]))
            self.before['target'].update(summary(incoming[1]))
        for p in self.targets:
            current, old, new = normalized({p: self.deployed[p]})[p], base_render.get(p), rendered.get(p)
            if new is None:
                # 移除的 skill：目標必須還是上一次產生的內容，或已經不存在；被改過的檔案不刪
                need(current in (None, old), 'DRIFT', 2)
            elif old is None:
                # 新增的 skill：目標不存在就建立，內容相同就收編，內容不同不覆寫
                need(current in (None, new), 'BLOCKED_TARGET_COLLISION: ' + p + ' exists with different content', 66)
            else:
                need(current in (old, new), 'DRIFT', 2)
        self.rendered = {p: None if p not in rendered else
                         (rendered[p][0], effective_mode(self.deployed[p] and self.deployed[p][1], rendered[p][1]))
                         for p in self.targets}
        self.git('read-tree', self.head)
        for p in baseline:
            if p not in self.candidate:
                # 隔離的 Git 目錄沒有工作目錄，--force-remove 不能用；mode 0 的 index-info 會移除該項目
                self.git('update-index', '--index-info', data=('0 ' + '0' * 40 + '\t' + p + '\n').encode())
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
                    baseline=summary(baseline), candidate=summary(self.candidate), rendered=summary(self.rendered),
                    tree=self.candidate_tree, tools=tools)

    def source_modes(self):
        # push 不改 source 的內容，但執行位元以 git 為準：檔案系統不一致時收回成 git 的模式，
        # 規則與 in 寫入 source 時相同（比標準嚴格的現有權限保留）
        changes = []
        for p, (content, mode) in self.candidate.items():
            current = self.working[p][1]
            if canonical_mode(current) != canonical_mode(mode):
                changes.append((self.src / p, (content, effective_mode(current, canonical_mode(mode)))))
        return changes

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
                        api.replace(temporary, dest)
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
        api.make_private(journal)
        diagnostics.transaction_started = True
        backups, committed, ref_attempted, made = [], False, False, []
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
            # 值為 None 代表檔案不存在：舊值 None 是建立，新值 None 是移除。journal 裡對應的欄位是 null。
            changes = [(p, v) for p, v in changes if read(p, missing=True) != v]
            changes.append((self.gd / 'index', (new_index, read(self.gd / 'index')[1])))
            manifest = []
            diagnostics.mark('backup_files')
            for n, (path, value) in enumerate(changes):
                old = read(path, missing=True)
                for label, item in (('old', old), ('new', value)):
                    if item is not None:
                        atomic(journal / ('%s-%d' % (label, n)), (item[0], 0o600))
                backups.append((path, value, old))
                manifest.append(dict(path=str(path), old_mode=old and old[1], new_mode=value and value[1],
                                     old_hash=old and digest(old[0]), new_hash=value and digest(value[0])))
            record = dict(ref=self.ref, old_head=self.head, new_head=new_head, files=manifest)
            diagnostics.mark('write_manifest')
            atomic(journal / 'manifest.json', (encoded(record), 0o600))
            diagnostics.mark('apply_files')
            for n, (path, value) in enumerate(changes):
                recorded = manifest[n]['old_hash'] and ((journal / ('old-%d' % n)).read_bytes(), manifest[n]['old_mode'])
                need(read(path, missing=True) == recorded, 'BLOCKED_STALE_PLAN', 68)
                place(path, value, made)
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
                    current = read(path, missing=True)
                    if current == old:
                        continue
                    need(current == new)
                    place(path, old, [])
                except BaseException as recovery_error:
                    diagnostics.capture(recovery_error)
                    recovered = False
            for directory in reversed(made):
                try:
                    if directory.is_dir() and not any(directory.iterdir()):
                        directory.rmdir()
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
                changes += [(self.src / p, (v[0], effective_mode(self.working[p][1] if p in self.working else None,
                                                                 canonical_mode(v[1]))))
                            for p, v in self.candidate.items()]
                changes += [(self.src / p, None) for p in self.working if p not in self.candidate]
                new_index = (self.iso / 'index').read_bytes()
            else:
                new_index = read(self.gd / 'index')[0]
            if self.remote_head == self.head and all(read(p, missing=True) == v for p, v in changes):
                print('NO_CHANGES')
                return
            if self.remote_head != self.head:
                self.transfer_objects()
            self.transact(self.remote_head, changes, new_index)
            print('OK: approved source and generated outputs applied')
            return
        new_head = self.head
        applied = False
        fixes = self.source_modes()
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
            self.transact(new_head, fixes + [(self.dst / p, v) for p, v in self.rendered.items()],
                          (self.iso / 'index').read_bytes())
        else:
            changes = fixes + [(self.dst / p, v) for p, v in self.rendered.items() if read(self.dst / p, missing=True) != v]
            if changes:
                self.transact(new_head, changes, read(self.gd / 'index')[0])
                applied = True
            else:
                need(self.state() == self.before, 'BLOCKED_STALE_PLAN', 68)
        if new_head == self.remote_head:
            # 沒有可發布的 commit 時，寫入只可能是 plan 列出的權限修正，不能報成 NO_CHANGES
            print('OK: generated outputs applied; nothing to publish' if applied else 'NO_CHANGES')
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
        api.make_private(plan_dir)
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        a.plan = str(plan_dir / ('sync-plan-%s-%s-%s.json' % (a.operation, stamp, secrets.token_hex(4))))
        return
    need(plan_dir.is_dir(), 'PLAN_NOT_FOUND', 66)
    plan_dir = plan_dir.resolve()
    for candidate in sorted(plan_dir.glob('sync-plan-*.json'))[:1000]:
        if api.is_redirected(candidate):
            continue
        value = read(candidate, missing=True)
        if value and digest(value[0]) == a.approve:
            a.plan = str(candidate)
            return
    raise Block(66, 'PLAN_NOT_FOUND')


def arguments():
    p = Parser(add_help=True)
    p.add_argument('command', choices=('plan', 'in', 'push', 'check', 'doctor'))
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
    if a.command == 'doctor':
        a.config_values = values
        return a
    a.message_given = a.message is not None
    a.message = a.message if a.message is not None else 'chore: sync shared agent configuration'
    need(a.source and a.destination and a.branch, 'USAGE: explicit source, destination and branch required', 64)
    need(not a.offline or (a.operation == 'in' and not a.remote), 'USAGE: offline is local in only', 64)
    need(a.offline or a.remote, 'USAGE: remote required', 64)
    need(not a.baseline or (a.offline and a.baseline_id), 'USAGE: baseline requires offline and ID', 64)
    for value in (a.message, a.author_name, a.author_email):
        need(len(value) <= 4096 and not any(ord(c) < 32 for c in value), 'USAGE: invalid text option', 64)
    # 角色：參數檔的 writer 決定哪些 agent 可以套用與發布；其他 agent 只能記錄、檢查、規劃。
    # 沒有 --agent 的人工呼叫不受限制。
    writer = values.get('writer', 'any')
    allowed = set(api.AGENTS) if writer == 'any' else set() if writer == 'none' else {writer} if type(writer) is str else set(writer)
    need(not (a.agent and a.command in ('in', 'push') and a.agent not in allowed),
         'NOT_WRITER: this agent may not apply or publish on this machine; report pending instead', 77)
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


# ---- status（#35）：離線、唯讀的範圍內狀態，從 sync.sh 移植。輸出、exit code、檢查順序逐字沿用
# sh 版（tests/golden/status 把關）；git 的 argv 前綴與第一個 --version 探測也不變，測試的 git shim
# 靠固定的參數位置攔截。
STATUS_OPTIONS = {'--source': 'source', '--destination': 'destination', '--profile': 'profile',
                  '--repository-profile': 'repository_profile', '--scanner': 'scanner', '--config': 'config'}
STATUS_EXECUTABLES = frozenset(['.config/ai-agent/bin/sync.sh', '.config/ai-agent/bin/scan-secrets.py',
                                '.config/ai-agent/bin/sync-write.py', '.config/ai-agent/bin/sync-migrate.py',
                                '.claude/skills/dotfiles-sync/sync.sh'])
STATUS_METADATA = ('.chezmoiignore', '.gitignore', '.gitattributes')


def status_options(argv):
    """sh 版的選項迴圈：每個選項都要有值，不可重複，status 不使用 --agent 的身分。"""
    values = dict(source='', destination='', profile='', repository_profile='', scanner='', config='')
    while argv:
        need(len(argv) >= 2, 'USAGE: missing option value', 64)
        option, value, argv = argv[0], argv[1], argv[2:]
        if option == '--agent':
            continue
        need(option in STATUS_OPTIONS, 'USAGE: unknown option', 64)
        key = STATUS_OPTIONS[option]
        need(not values[key], 'USAGE: duplicate ' + key.replace('_', ' '), 64)
        values[key] = value
    return values


def unlinked(path):
    """路徑與所有上層目錄都不是重導向；sh 版的 safe_path。"""
    return not any(api.is_redirected(p) for p in (path, *path.parents))


def readable_file(path):
    return path.is_file() and os.access(path, os.R_OK)


def store(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class Status:
    def __init__(self, argv):
        options = status_options(argv)
        formatter = HERE / 'scan-secrets.py'
        # 本地參數檔只補足未明確給定的選項；命令列永遠優先
        if options['config']:
            need(api.absolute_path(options['config']), 'USAGE: explicit absolute paths required', 64)
            try:
                values = api.load_config(options['config'])
            except (ValueError, OSError, api.ScanError):
                raise Block(78, 'INVALID_CONFIG: reviewed local configuration required') from None
            for key in ('source', 'destination', 'profile', 'repository_profile', 'scanner'):
                if not options[key] and key in values:
                    options[key] = values[key]
        self.profile = options['profile'] or 'claude-codex'
        scanner = options['scanner'] or str(formatter)
        for value in (options['source'], options['destination'], scanner):
            need(api.absolute_path(value), 'USAGE: explicit absolute paths required', 64)
        for tool in ('git', 'chezmoi'):
            need(shutil.which(tool), 'MISSING_DEPENDENCY: required command unavailable', 69)
        self.scanner = Path(scanner)
        need(self.scanner.is_file() and os.access(self.scanner, os.X_OK),
             'MISSING_DEPENDENCY: reviewed scanner adapter required', 69)
        need(formatter.is_file() and (HERE / 'gitleaks-rules.json').is_file(),
             'MISSING_DEPENDENCY: scanner report validator required', 69)
        src, dst = Path(options['source']), Path(options['destination'])
        need(src.is_dir() and dst.is_dir(), 'INVALID_SOURCE: source and destination must exist', 65)
        self.src, self.dst = src.resolve(), dst.resolve()
        need(self.profile in api.PROFILES, 'USAGE: invalid profile', 64)
        self.repository_profile = options['repository_profile'] or self.profile
        need(self.repository_profile in ('claude-codex', self.profile), 'USAGE: invalid repository profile', 64)
        try:
            api.validate_layout(self.src, self.dst, self.profile, False, self.repository_profile)
        except (ValueError, OSError, api.ScanError):
            raise Block(65, 'INVALID_LAYOUT: roots or managed paths') from None
        git_dir = self.src / '.git'
        need(git_dir.is_dir() and not api.is_redirected(git_dir),
             'INVALID_SOURCE: regular Git checkout required; worktrees unsupported', 65)
        for marker in COORDINATION_MARKERS:
            need(not (git_dir / marker).exists() and not api.is_redirected(git_dir / marker),
                 'BLOCKED_UNSUPPORTED_COORDINATION: archived bootstrap metadata present; inspect manually', 73)
        if self.profile != 'codex':
            self.home('CLAUDE_CONFIG_DIR', '.claude')
        self.home('AI_AGENT_HOME', '.config/ai-agent')
        if self.profile != 'claude':
            self.home('CODEX_HOME', '.codex')
            override = self.dst / '.codex/AGENTS.override.md'
            need(unlinked(override), 'INVALID_SOURCE: symlink in override path', 65)
            need(not override.exists(), 'BLOCKED_OVERRIDE: review AGENTS.override.md before deployment', 65)
        self.tool_path = os.environ.get('PATH', os.defpath)
        self.report = []

    def home(self, key, suffix):
        value = os.environ.get(key, '')
        need(not value or value == str(self.dst / suffix), 'UNSUPPORTED_HOME: custom ' + key, 65)

    def run(self):
        # 所有暫存狀態都在選定的根目錄之外，且只有擁有者可讀；結束時整個移除
        try:
            work = Path(tempfile.mkdtemp(prefix='ai-agent-status.', dir=str(api.temporary_root())))
            api.make_private(work)
        except OSError:
            raise Block(70, 'IO_ERROR: temporary directory') from None
        try:
            return self.inspect(work)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def git(self, *args):
        """只讀 Git 中繼資料與物件：最小環境、關閉 hooks 與 fsmonitor、禁止 lazy fetch。回傳 (exit, stdout)。"""
        command = ['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
                   '-C', str(self.src), '--no-lazy-fetch', *args]
        try:
            run = subprocess.run(command, env=self.git_env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120)
        except (OSError, subprocess.SubprocessError):
            return 1, b''
        return run.returncode, run.stdout

    def skill_paths(self, profile, kind):
        """這份 source 自己的 skill 集合所對應的 source 或 target 路徑；sh 版的 schema --schema。"""
        try:
            return api.mapping(profile, api.source_skills(self.src, profile))[kind == 'target']
        except (ValueError, OSError, api.ScanError):
            raise Block(65, 'INVALID_PROFILE') from None

    def retired(self, head_paths, profile, kind):
        """HEAD 有、工作目錄已經沒有的 skill 的路徑；sh 版的 schema --retired。"""
        try:
            present = api.source_skills(self.src, profile)
            gone = tuple(s for s in api.skills_in(head_paths, profile) if s not in present)
            paths = api.mapping(profile, gone)[kind == 'target']
        except (ValueError, OSError, api.ScanError):
            raise Block(65, 'INVALID_SOURCE: skill set at HEAD') from None
        return tuple(p for p in paths if api.skill_of(p))

    def inspect(self, work):
        for name in ('home', 'source', 'render', 'scan', 'cache'):
            (work / name).mkdir()
        (work / 'config.toml').write_bytes(b'')
        self.git_env = dict(api.child_environment(work / 'home', self.tool_path),
                            GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_OPTIONAL_LOCKS='0',
                            GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1',
                            GIT_ALLOW_PROTOCOL='', GIT_PROTOCOL_FROM_USER='0')
        # 沒有這個旗標的 Git 在讀任何物件之前就拒絕；旗標加環境一起禁止 lazy fetch 與所有傳輸
        need(self.git('--version')[0] == 0, 'MISSING_DEPENDENCY: Git with --no-lazy-fetch support required', 69)
        rc, out = self.git('rev-parse', '--show-toplevel')
        # 以 Path 比較：Git 在 Windows 印出正斜線的路徑；POSIX 上與字串比較等價
        need(rc == 0 and Path(os.fsdecode(out.rstrip(b'\n'))) == self.src, 'INVALID_SOURCE: source must be Git root', 65)
        rc, out = self.git('rev-parse', '--verify', 'HEAD')
        if rc == 0:
            head = os.fsdecode(out.rstrip(b'\n'))
        else:
            # unborn branch：symbolic-ref 必須可讀，而且那個 ref 必須確實不存在
            rc, out = self.git('symbolic-ref', 'HEAD')
            need(rc == 0, 'GIT_ERROR: invalid HEAD', 70)
            need(self.git('show-ref', '--verify', '--quiet', os.fsdecode(out.rstrip(b'\n')))[0] == 1,
                 'GIT_ERROR: unreadable HEAD', 70)
            head = ''
        files = self.skill_paths(self.repository_profile, 'source')
        # HEAD 還有、工作目錄已經沒有的 skill：等待發布的移除
        retired, orphans = (), ()
        if head:
            head_paths = []
            for base in ('.chezmoitemplates/ai/shared/skills', 'dot_claude/skills', 'dot_agents/skills'):
                leaf = 'SKILL.md' if base == '.chezmoitemplates/ai/shared/skills' else 'SKILL.md.tmpl'
                rc, out = self.git('ls-tree', head, '--', base + '/')
                need(rc == 0, 'GIT_ERROR: HEAD tree', 70)
                for line in out.split(b'\n'):
                    if not line:
                        continue
                    candidate = os.fsdecode(line.split(b'\t', 1)[-1]) + '/' + leaf
                    rc, entry = self.git('ls-tree', head, '--', candidate)
                    need(rc == 0, 'GIT_ERROR: HEAD tree', 70)
                    if entry.rstrip(b'\n'):
                        head_paths.append(candidate)
            retired = self.retired(head_paths, self.repository_profile, 'source')
            orphans = self.retired(head_paths, self.profile, 'target')
        changed = False
        for rel in files + retired:
            need(unlinked(self.src / rel), 'INVALID_SOURCE: symlink: ' + rel, 65)
            gone = rel in retired
            out_path = work / 'source' / rel
            if not gone:
                need(readable_file(self.src / rel), 'INVALID_SOURCE: missing or unreadable: ' + rel, 65)
                content = (self.src / rel).read_bytes()
                store(work / 'source', rel, content)
                store(work / 'scan' / 'source', rel, content)
                # 封閉的 schema：包裝檔只能是固定的 template 引用，共用文字只允許字面的開頭分隔符
                if rel.endswith('.tmpl'):
                    try:
                        expected = api.wrapper(rel)
                    except ValueError:
                        raise Block(65, 'UNSUPPORTED_TEMPLATE') from None
                    need(content == expected, 'UNSUPPORTED_TEMPLATE: ' + rel, 65)
                elif rel.startswith('.chezmoitemplates/'):
                    try:
                        api.decode_shared(content)
                    except (ValueError, api.ScanError):
                        raise Block(65, 'UNSUPPORTED_TEMPLATE: delimiter in shared text: ' + rel) from None
            # 只讀 blob 的中繼資料與內容，不經過 diff driver 或 clean filter
            rc, entry = self.git('ls-files', '--stage', '--', rel)
            need(rc == 0, 'GIT_ERROR: index read', 70)
            index_mode = index_oid = ''
            fields = entry.split()
            if fields:
                need(len(fields) == 4 and fields[2] == b'0', 'BLOCKED_CONFLICT: ' + rel, 66)
                index_mode, index_oid = fields[0].decode(), fields[1].decode()
                need(index_mode in ('100644', '100755'), 'INVALID_SOURCE: index type: ' + rel, 65)
                rc, blob = self.git('cat-file', 'blob', index_oid)
                need(rc == 0, 'GIT_ERROR: index blob', 70)
                store(work / 'scan' / 'index', rel, blob)
            base_mode = base_oid = ''
            if head:
                rc, entry = self.git('ls-tree', head, '--', rel)
                need(rc == 0, 'GIT_ERROR: HEAD tree', 70)
                fields = entry.split()
                if fields:
                    need(len(fields) == 4 and fields[1] == b'blob', 'INVALID_SOURCE: HEAD type: ' + rel, 65)
                    base_mode, base_oid = fields[0].decode(), fields[2].decode()
                    need(base_mode in ('100644', '100755'), 'INVALID_SOURCE: HEAD mode: ' + rel, 65)
                    rc, blob = self.git('cat-file', 'blob', base_oid)
                    need(rc == 0, 'GIT_ERROR: HEAD blob', 70)
                    store(work / 'scan' / 'head', rel, blob)
            oid = mode = ''
            if not gone:
                rc, out = self.git('hash-object', '--no-filters', str(out_path))
                need(rc == 0, 'GIT_ERROR: hash', 70)
                oid = out.rstrip(b'\n').decode()
                mode = '100755' if os.access(self.src / rel, os.X_OK) else '100644'
            staged = 'clean' if (base_oid, base_mode) == (index_oid, index_mode) else 'changed'
            working = 'clean' if (oid, mode) == (index_oid, index_mode) else 'changed'
            if gone:
                working = 'removed'
            if (staged, working) != ('clean', 'clean'):
                changed = True
                self.report.append('SOURCE: %s staged=%s working=%s' % (rel, staged, working))
        # 中繼資料檔只掃描與回報，隔離渲染時不解讀
        for rel in STATUS_METADATA:
            (work / 'source' / rel).unlink(missing_ok=True)

        drift = False
        targets = self.skill_paths(self.profile, 'target')
        render_env = dict(api.child_environment(work / 'home', self.tool_path),
                          XDG_CONFIG_HOME=str(work / 'home' / 'config'), XDG_CACHE_HOME=str(work / 'cache'),
                          XDG_DATA_HOME=str(work / 'home' / 'data'))
        for rel in targets:
            need(unlinked(self.dst / rel), 'INVALID_SOURCE: target symlink: ' + rel, 65)
            command = ['chezmoi', '--config', str(work / 'config.toml'), '--source', str(work / 'source'),
                       '--destination', str(work / 'render'), '--cache', str(work / 'cache'),
                       '--persistent-state', str(work / 'state.boltdb'), '--refresh-externals=never', '--no-tty',
                       'cat', str(work / 'render' / rel)]
            try:
                run = subprocess.run(command, env=render_env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120)
            except (OSError, subprocess.SubprocessError):
                raise Block(70, 'RENDER_ERROR: ' + rel) from None
            need(run.returncode == 0, 'RENDER_ERROR: ' + rel, 70)
            rendered = run.stdout
            store(work / 'scan' / 'render', rel, rendered)
            state = 'missing'
            target = self.dst / rel
            if target.exists():
                need(readable_file(target), 'INVALID_SOURCE: target type or access: ' + rel, 65)
                current = target.read_bytes()
                store(work / 'scan' / 'target', rel, current)
                state = 'clean' if current == rendered else 'changed'
                if rel in STATUS_EXECUTABLES and not os.access(target, os.X_OK):
                    state = 'mode'
                # 比標準 644/755 寬鬆（group 或 other 可寫入）也要看得見
                if state == 'clean' and api.foreign_writable(target, target.stat()):
                    state = 'mode'
            if state != 'clean':
                drift = True
                self.report.append('TARGET: %s %s' % (rel, state))
        # 移除的 skill 的輸出會留在部署區，直到核准的 plan 套用移除
        for rel in orphans:
            need(unlinked(self.dst / rel), 'INVALID_SOURCE: target symlink: ' + rel, 65)
            target = self.dst / rel
            if target.exists():
                need(readable_file(target), 'INVALID_SOURCE: target type or access: ' + rel, 65)
                store(work / 'scan' / 'target', rel, target.read_bytes())
                drift = True
                self.report.append('TARGET: %s orphan' % rel)

        # scanner 是受信任的可執行程式，不是沙箱：離線、唯讀、經過審閱；它的輸出永遠不轉發
        report_path = work / 'scanner-report.json'
        try:
            run = subprocess.run(api.scanner_command(self.scanner) + [str(work / 'scan'), str(report_path)],
                                 env=api.child_environment(work / 'home', self.tool_path), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
            scan_rc = run.returncode
        except (OSError, subprocess.SubprocessError):
            scan_rc = 126
        try:
            findings = api.validate_report(api.read_json(report_path), scan_rc)
        except (api.ScanError, OSError, ValueError, KeyError, TypeError):
            raise Block(70, 'SCANNER_ERROR: invalid or missing structured report') from None
        if scan_rc == 10:
            for item in findings:
                print('FINDING: %s:%d rule=%s' % (item['file'], item['line'], item['rule']))
            raise Block(67, 'BLOCKED_SECRET: scoped snapshot; values withheld')
        need(scan_rc != 69, 'MISSING_DEPENDENCY: pinned Gitleaks required on PATH', 69)
        need(scan_rc == 0, 'SCANNER_ERROR: scan failed; no clean result', 70)
        for line in self.report:
            print(line)
        if drift:
            raise Block(2, 'DRIFT: generated files differ; no changes applied')
        print('OK: source changes within v2 scope; not push approval' if changed
              else 'NO_CHANGES: v2 scope only; history and unrelated files not assessed')
        return 0


def status_command(argv):
    os.umask(0o077)
    return Status(argv).run()


def doctor(args):
    """Read-only bring-up checks after deployment. Prints OK/WARN/FAIL lines; exit 1 on any FAIL."""
    counts = dict(OK=0, WARN=0, FAIL=0)

    def report(status, item, detail, fix=''):
        counts[status] += 1
        print('%-4s %s: %s%s' % (status, item, detail, (' -> ' + fix) if fix else ''))

    def run(cmd, timeout=15):
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout)
            return p.returncode, p.stdout.decode(errors='replace'), p.stderr.decode(errors='replace')
        except (OSError, subprocess.SubprocessError):
            return None, '', ''

    rc, out, _ = run(['git', '--version'])
    version = re.search(r'(\d+\.\d+(?:\.\d+)?)', out or '')
    if rc == 0 and version and run(['git', '--no-lazy-fetch', '--version'])[0] == 0:
        report('OK', 'git', version.group(1) + ' with --no-lazy-fetch')
    else:
        report('FAIL', 'git', 'missing or without --no-lazy-fetch', 'install Git 2.45 or newer')
    rc, out, _ = run(['chezmoi', '--version'])
    report('OK', 'chezmoi', out.strip().split(',')[0]) if rc == 0 else report('FAIL', 'chezmoi', 'not found', 'install chezmoi')
    report('OK' if sys.version_info >= (3, 9) else 'FAIL', 'python3', '%d.%d.%d' % sys.version_info[:3], '' if sys.version_info >= (3, 9) else 'install Python 3.9 or newer')
    binary = shutil.which('gitleaks')
    rc, out, _ = run([binary, 'version']) if binary else (None, '', '')
    if rc == 0 and out.strip() == api.VERSION:
        report('OK', 'gitleaks', api.VERSION + ' at ' + binary)
    else:
        report('FAIL', 'gitleaks', ('version ' + out.strip()) if rc == 0 else 'not found', 'run: sh setup/install-gitleaks.sh from the public repo')
    values = args.config_values
    if not args.config:
        report('WARN', 'config', 'no --config given; source, targets, remote and roles not checked', 'rerun with --config ~/.config/ai-agent/sync.local.json')
    else:
        report('OK', 'config', 'valid; writer=%s auto_in=%s profile=%s' % (values.get('writer', 'any'), values.get('auto_in', False), args.profile))
        if 'plan_dir' in values:
            plan_dir = Path(values['plan_dir'])
            if plan_dir.is_dir() and os.access(plan_dir, os.W_OK):
                ok, detail, fix = api.private_directory_report(plan_dir)
                report('OK' if ok else 'WARN', 'plan_dir', str(plan_dir) + detail, fix)
            else:
                report('FAIL', 'plan_dir', str(plan_dir) + ' missing or not writable', 'mkdir -p -m 700 ' + str(plan_dir))
        else:
            report('WARN', 'plan_dir', 'not configured', 'add plan_dir to the parameter file')
    if args.source and args.destination:
        src, dst = Path(args.source), Path(args.destination)
        # skill 集合由 source 的目錄決定；集合本身有問題時，後面的 layout 檢查只會說 invalid，這裡先講清楚
        try:
            skills = api.source_skills(src, args.repository_profile or args.profile)
            added = [s for s in skills if s not in api.SKILLS]
            report('OK', 'skills', '%d in the source%s' % (len(skills), (', beyond the template: ' + ', '.join(added)) if added else ''))
        except (ValueError, OSError):
            report('FAIL', 'skills', 'the skill set of the source is invalid',
                   'under .chezmoitemplates/ai/shared/skills every directory with a SKILL.md needs a name matching '
                   '[a-z0-9][a-z0-9-]*, and every wrapper under dot_claude/skills or dot_agents/skills needs its skill')
        try:
            api.validate_layout(src, dst, args.profile, source_profile=args.repository_profile)
            skills = api.source_skills(src, args.repository_profile or args.profile)
            files = api.mapping(args.repository_profile or args.profile, skills)[0]
            deployed = api.mapping(args.profile, skills)[1]
            missing = [p for p in files if not (src / p).is_file()]
            report('OK' if not missing else 'FAIL', 'source', '%s, %d/%d mapped files present' % (src, len(files) - len(missing), len(files)), '' if not missing else 'the private source is missing mapped files; check its layout')
            missing = [p for p in deployed if not (dst / p).is_file()]
            report('OK' if not missing else 'FAIL', 'targets', '%d/%d deployed under %s' % (len(deployed) - len(missing), len(deployed), dst), '' if not missing else 'chezmoi apply (first deployment) or an approved in')
        except (ValueError, OSError):
            deployed = api.mapping(args.profile)[1]
            report('FAIL', 'layout', 'source/destination layout invalid', 'check absolute paths, symlinks and that the source is a regular Git checkout')
        # chezmoi 沒設定 umask 時，部署權限跟著 shell 的 umask（002 會產生 664）。在 umask 000 下
        # 詢問，才不會把引擎自己的 077 誤判成已設定。
        rc, out, _ = run(['sh', '-c', 'umask 000 && exec chezmoi dump-config --format json'])
        try:
            mask = json.loads(out).get('umask') if rc == 0 else None
        except (ValueError, AttributeError):
            mask = None
        if type(mask) is int and mask & 0o022 == 0o022:
            report('OK', 'chezmoi_umask', '%03o' % mask)
        else:
            report('WARN', 'chezmoi_umask', 'not set; deployed modes follow the shell umask' if mask == 0 else 'unknown or allows group/other write',
                   'add "umask = 0o022" to ~/.config/chezmoi/chezmoi.toml')
        loose = [p for p in deployed
                 if (dst / p).is_file() and not api.is_redirected(dst / p) and api.foreign_writable(dst / p, (dst / p).stat())]
        report('OK' if not loose else 'WARN', 'permissions',
               'no deployed file is group/other writable' if not loose else '%d group/other writable: %s' % (len(loose), ', '.join(loose[:3]) + (' ...' if len(loose) > 3 else '')),
               '' if not loose else 'set the chezmoi umask, then chezmoi apply (or approve the next in/push plan)')
        for name, label in (('ai-agent-sync.lock', 'writer lock'), ('ai-agent-sync-transaction', 'recovery journal'), ('index.lock', 'git index lock')):
            if (src / '.git' / name).exists():
                report('WARN', 'source_state', label + ' present', 'inspect before any write; never delete blindly')
        engine = dst / '.config/ai-agent/bin/sync-write.py'
        if engine.is_file():
            same = digest(engine.read_bytes()) == digest(Path(__file__).read_bytes())
            report('OK' if same else 'WARN', 'engine', 'deployed engine ' + ('matches this build' if same else 'differs from the engine running doctor'), '' if same else 'run doctor through the deployed ~/.config/ai-agent/bin/sync.sh')
        if 'claude' in (('claude', 'codex') if args.profile == 'claude-codex' else (args.profile,)):
            settings = dst / '.claude/settings.json'
            try:
                allow = json.loads(settings.read_text()).get('permissions', {}).get('allow', [])
                # 只預先允許唯讀的子指令；in/push 要經過 Claude Code 的權限確認，不能被 :* 一併放行
                prefix = 'Bash(sh ~/.config/ai-agent/bin/sync.sh'
                broad = [r for r in allow if r in (prefix + ':*)', prefix + ' in:*)', prefix + ' push:*)')]
                missing = [prefix + ' %s:*)' % c for c in ('status', 'check', 'doctor', 'plan') if prefix + ' %s:*)' % c not in allow]
                if broad:
                    report('WARN', 'settings', 'permissions.allow lets ' + ', '.join(broad) + ' run in/push without a prompt',
                           'remove it and pre-allow only: ' + ', '.join(prefix + ' %s:*)' % c for c in ('status', 'check', 'doctor', 'plan')))
                elif missing:
                    report('WARN', 'settings', 'read-only sync commands not pre-allowed: ' + ', '.join(missing), 'add them to permissions.allow to avoid a prompt per session')
                else:
                    report('OK', 'settings', 'read-only sync commands pre-allowed; in/push prompt')
            except (OSError, ValueError, AttributeError):
                report('WARN', 'settings', str(settings) + ' unreadable or not JSON', 'check the deployed Claude settings')
    if args.remote:
        value = args.remote
        if value.startswith('/'):
            report('OK', 'remote', 'local path ' + value)
        else:
            scp = re.fullmatch(r'([A-Za-z0-9._-]+)@([A-Za-z0-9.-]+):([^/:][^:]*)', value)
            u = urlsplit('ssh://%s@%s/%s' % scp.groups() if scp and '://' not in value else value)
            if u.scheme != 'ssh' or not u.hostname:
                report('WARN', 'remote', value + ' is not an ssh remote; ssh checks skipped')
            else:
                known = Path(os.path.expanduser('~/.ssh/known_hosts'))
                rc, _, _ = run(['ssh-keygen', '-F', u.hostname, '-f', str(known)])
                report('OK' if rc == 0 else 'FAIL', 'known_hosts', u.hostname + (' present' if rc == 0 else ' missing'), '' if rc == 0 else 'verify the published host fingerprints, then ssh-keyscan %s >> ~/.ssh/known_hosts' % u.hostname)
                import shlex
                rc, out, err = run(['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=yes',
                                    '-o', 'UpdateHostKeys=no', '-o', 'UserKnownHostsFile=' + str(known), '-T', '%s@%s' % (u.username or 'git', u.hostname)], timeout=20)
                text = (out + err)
                if 'successfully authenticated' in text:
                    report('OK', 'ssh_auth', u.hostname + ' accepts the key')
                elif 'Permission denied' in text:
                    report('FAIL', 'ssh_auth', u.hostname + ': permission denied', 'load the key into ssh-agent or keep it as ~/.ssh/id_*, and register its public key with the account')
                elif rc == 255 or rc is None:
                    report('FAIL', 'ssh_auth', 'connection to %s failed' % u.hostname, 'check network, DNS and known_hosts')
                else:
                    report('OK', 'ssh_auth', '%s reachable (exit %s)' % (u.hostname, rc))
    products = ('claude', 'codex') if args.profile == 'claude-codex' else (args.profile,)
    for product in products:
        path = shutil.which(product)
        report('OK' if path else 'WARN', product, path or 'not on PATH', '' if path else 'install %s on this machine or choose a profile without it' % product)
    print('DOCTOR: %d ok, %d warn, %d fail' % (counts['OK'], counts['WARN'], counts['FAIL']))
    return 1 if counts['FAIL'] else 0


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
    temporary = tempfile.TemporaryDirectory(prefix='ai-agent-check-', dir=str(api.temporary_root()))
    api.make_private(temporary.name)
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
        api.make_private(state_file.parent)
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
    api.make_private(path)
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
    if args.command == 'doctor':
        return doctor(args)
    layout(args)  # Reject unsafe paths before even creating a source lock.
    # 封存的 bootstrap／cohort 協定留下的標記一律拒絕並原樣保留；不進入 lock 或任何寫入。
    for name in COORDINATION_MARKERS:
        marker = Path(args.source).resolve() / '.git' / name
        need(not marker.exists() and not api.is_redirected(marker), 'BLOCKED_UNSUPPORTED_COORDINATION', 73)
    if args.command == 'check':
        return check(args)
    plan_path = Path(args.plan)
    need(plan_path.parent.is_dir(), 'INVALID_PLAN_PATH')
    # 目錄別名（例如 macOS /tmp）先正規化；plan 本身不得是 symlink，且必須位於
    # source 與所有部署區域之外。destination HOME 下的其他位置是允許的。
    plan_path = plan_path.parent.resolve() / plan_path.name
    need(not api.is_redirected(plan_path), 'BLOCKED_SYMLINK')
    need(external(plan_path, Path(args.source).resolve(), Path(args.destination).resolve()), 'INVALID_PLAN_PATH')
    approved = None
    if args.command != 'plan':
        value = read(plan_path)
        need(api.private_mode(plan_path, value[1]), 'INVALID_PLAN_PERMISSIONS')
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
    temporary = tempfile.TemporaryDirectory(prefix='ai-agent-write-', dir=str(api.temporary_root()))
    api.make_private(temporary.name)
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
                api.make_private(plan_path)
                base = result['baseline'] if result['operation'] == 'push' else result['state']['source']
                for label, names in (('SKILL_ADDED: ', set(engine.skill_set) - set(engine.base_skills)),
                                     ('SKILL_REMOVED: ', set(engine.base_skills) - set(engine.skill_set))):
                    for name in sorted(names):
                        print(label + name)
                for p in engine.files:
                    before, after = base.get(p), result['candidate'].get(p)
                    if before is None or after is None:
                        # 集合變動：push 時寫進 commit，in 只在遠端領先時寫入 source
                        if before != after and (result['operation'] == 'push'
                                                or result['remote_head'] != result['state']['head']):
                            print('SOURCE: ' + p + ' before=' + (before[0] if before else 'absent') + ' after='
                                  + (after[0] + ' mode=' + oct(canonical_mode(after[1])) if after else 'absent'))
                        continue
                    if result['operation'] == 'push':
                        # commit 的模式來自 HEAD；檔案系統的執行位元不一致時收回，umask 造成的 664 不算變更
                        mode = canonical_mode(after[1])
                        changed = after[0] != before[0] or canonical_mode(result['state']['source'][p][1]) != mode
                    else:
                        # in 只在遠端領先時寫入 source，實際權限依現有權限決定
                        mode = effective_mode(before[1], canonical_mode(after[1]))
                        changed = (result['remote_head'] != result['state']['head']
                                   and (after[0] != before[0] or mode != before[1]))
                    if changed:
                        print('SOURCE: ' + p + ' before=' + before[0] + ' after=' + after[0] + ' mode=' + oct(mode))
                for p in engine.targets:
                    before, after = result['state']['target'][p], result['rendered'][p]
                    if before is None or after is None:
                        if before != after:
                            print('TARGET: ' + p + (' removed' if after is None else ' sha256=' + after[0] + ' created'))
                        continue
                    if after != before:
                        line = 'TARGET: ' + p + ' sha256=' + after[0]
                        if after[1] != before[1]:
                            line += ' mode=%o->%o' % (before[1], after[1])
                        print(line)
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
                    changed = {p for p in engine.files if result['candidate'].get(p) != result['baseline'].get(p)}
                    if engine.skill_set != engine.base_skills or not all(shared_text(p) for p in changed):
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
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        # status 沿用 sync.sh 的輸出合約：只有報告行、標籤與 exit code，沒有 DIAGNOSTIC 行
        try:
            return status_command(sys.argv[2:])
        except Block as error:
            print(error.label)
            return error.code
        except KeyboardInterrupt:
            return 130
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, RecursionError,
                subprocess.SubprocessError):
            print('IO_ERROR: operation stopped; no raw tool output exposed')
            return 70
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
    # SIGHUP 在部分平台（例如原生 Windows 的 Python）不存在；缺少時只處理 SIGTERM
    for sig in (signal.SIGTERM, getattr(signal, 'SIGHUP', None)):
        if sig is not None:
            signal.signal(sig, interrupted)
    sys.exit(cli())

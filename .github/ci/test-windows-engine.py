#!/usr/bin/env python3
"""原生 Windows 的引擎端對端測試（#15 W6）：source、bare remote、destination 都在 %TEMP% 的暫存目錄，
不碰真實環境。走一輪 doctor、status、check、plan push、push、check、plan in、in、status，
並檢查 HEAD 的執行位元、部署檔內容、參數檔的 ACL 判定與 junction 的拒絕。
CI 先以 install-windows-tools.ps1 安裝固定版的 chezmoi 與 Gitleaks；本機裝好後可直接執行：
    python .github\\ci\\test-windows-engine.py
"""
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / 'examples/chezmoi/.chezmoitemplates/ai/shared/scripts'
SHARED = '.chezmoitemplates/ai/shared/instructions.md'
api = runpy.run_path(str(SCRIPTS / 'scan-secrets.py'))
if not api['WINDOWS']:
    sys.exit('this test runs on native Windows only')
for tool in ('git', 'chezmoi', 'gitleaks'):
    if not shutil.which(tool):
        sys.exit('MISSING_DEPENDENCY: put %s on PATH (install-windows-tools.ps1)' % tool)

root = Path(tempfile.mkdtemp(prefix='engine-test-'))
api['make_private'](root)
src, dst, remote, other = root / 'source', root / 'destination', root / 'remote.git', root / 'other'
env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(root / 'gitconfig'), GIT_TERMINAL_PROMPT='0',
           GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.test',
           GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.test', PYTHONDONTWRITEBYTECODE='1')
(root / 'gitconfig').write_bytes(b'[core]\n\tautocrlf = false\n')
checks = 0


def ok(condition, message):
    global checks
    if not condition:
        sys.exit('ASSERT: ' + message)
    checks += 1


def git(cwd, *args):
    run = subprocess.run(['git', '-C', str(cwd), *args], env=env, capture_output=True, text=True)
    ok(run.returncode == 0, 'git %s: %s' % (' '.join(args), run.stderr.strip()))
    return run.stdout.strip()


def engine(*args, expect=0):
    """以原生 Python 執行引擎（Git Bash 裡的 sh sync.sh 最後也是這條路）；回傳 stdout 的行。"""
    run = subprocess.run([sys.executable, str(SCRIPTS / 'sync-write.py'), *args], env=env,
                         capture_output=True, text=True, timeout=600)
    lines = [line for line in run.stdout.splitlines() if line]
    print('$ %s -> %d | %s' % (' '.join(args[:3]), run.returncode, lines[-1] if lines else ''))
    ok(run.returncode == expect, '%s exited %d, expected %d\n%s\n%s' % (args[:2], run.returncode, expect, run.stdout, run.stderr))
    ok('Traceback' not in run.stderr, 'traceback in stderr: ' + run.stderr)
    return lines


def plan_id(lines):
    return [line.split()[1] for line in lines if line.startswith('PLAN_ID: ')][0]


try:
    # 夾具：範本加測試 skill，一個 commit，bare remote，chezmoi 部署到暫存的 destination
    shutil.copytree(REPO / 'examples/chezmoi', src)
    shutil.copytree(REPO / 'tests/fixtures/skills', src, dirs_exist_ok=True)
    dst.mkdir()
    git(src, 'init', '-q', '-b', 'main')
    git(src, 'add', '.')
    # Windows 的 checkout 沒有執行位元：三個 .py 腳本在 index 標成 100755，與公開範本相同
    for name in ('scan-secrets.py', 'sync-migrate.py', 'sync-write.py'):
        git(src, 'update-index', '--chmod=+x', '.chezmoitemplates/ai/shared/scripts/' + name)
    git(src, 'commit', '-q', '-m', 'fixture baseline')
    git(root, 'init', '-q', '--bare', str(remote))
    git(src, 'push', '-q', str(remote), 'main')
    git(src, 'remote', 'add', 'origin', str(remote))
    run = subprocess.run(['chezmoi', '--source', str(src), '--destination', str(dst), '--cache', str(root / 'cache'),
                          '--persistent-state', str(root / 'state.db'), '--no-tty', 'apply', '--force'],
                         env=env, capture_output=True, text=True)
    ok(run.returncode == 0, 'chezmoi apply: ' + run.stderr)
    ok((dst / '.config/ai-agent/bin/sync-write.py').is_file(), 'engine not deployed by chezmoi')

    # 參數檔：故意讓 Everyone 可讀，引擎必須拒絕並印出 icacls；--make-private 之後才接受
    config = root / 'sync.local.json'
    config.write_text(json.dumps(dict(source=str(src), destination=str(dst), profile='claude-codex', remote=str(remote),
                                      branch='main', plan_dir=str(root / 'plans'), author_name='Fixture',
                                      author_email='fixture@example.test', writer='claude', auto_in=False,
                                      scanner=str(SCRIPTS / 'scan-secrets.py'))))
    subprocess.run(['icacls', str(config), '/grant', '*S-1-1-0:R'], check=True, capture_output=True)
    lines = engine('status', '--config', str(config), '--agent', 'claude', expect=78)
    ok(lines[-1].startswith('INVALID_CONFIG') and 'icacls' in lines[-1], 'open parameter file not refused with a hint')
    run = subprocess.run([sys.executable, str(SCRIPTS / 'scan-secrets.py'), '--make-private', str(config)],
                         env=env, capture_output=True, text=True)
    ok(run.returncode == 0 and run.stdout.startswith('OK: '), '--make-private: ' + run.stdout + run.stderr)
    (root / 'plans').mkdir()
    api['make_private'](root / 'plans')

    # 一輪完整的同步
    lines = engine('doctor', '--config', str(config))
    ok(lines[-1].endswith('0 fail'), 'doctor reported a failure: ' + '\n'.join(lines))
    ok(any(line.startswith('OK   chezmoi_umask: not applicable') for line in lines), 'umask check not marked as not applicable')
    ok(engine('status', '--config', str(config), '--agent', 'claude')[-1].startswith('NO_CHANGES'), 'fresh deployment not NO_CHANGES')
    ok(engine('check', '--config', str(config), '--agent', 'claude')[-1] == 'REMOTE: UP_TO_DATE', 'check not UP_TO_DATE')
    with (src / SHARED).open('a', newline='\n') as f:
        f.write('\nNative Windows engine edit.\n')
    lines = engine('status', '--config', str(config), '--agent', 'claude', expect=2)
    ok('SOURCE: %s staged=clean working=changed' % SHARED in lines, 'edit not reported by status')
    ok('TARGET: .claude/CLAUDE.md changed' in lines, 'drift of CLAUDE.md not reported')
    lines = engine('plan', '--operation', 'push', '--config', str(config), '--agent', 'claude')
    ok(not any(' mode=' in line for line in lines if line.startswith('TARGET: ')), 'a mode line appeared in a Windows plan')
    engine('push', '--config', str(config), '--agent', 'claude', '--approve', plan_id(lines))
    ok(engine('status', '--config', str(config), '--agent', 'claude')[-1].startswith('NO_CHANGES'), 'not NO_CHANGES after push')
    ok(git(remote, 'rev-parse', 'main') == git(src, 'rev-parse', 'HEAD'), 'remote did not receive the commit')
    modes = {line.split('\t')[1]: line.split()[0] for line in git(src, 'ls-tree', '-r', 'HEAD').splitlines()}
    for name in ('scan-secrets.py', 'sync-migrate.py', 'sync-write.py'):
        ok(modes['.chezmoitemplates/ai/shared/scripts/' + name] == '100755', name + ' lost its executable bit')
    ok(modes[SHARED] == '100644', 'instructions.md gained an executable bit')
    ok('Native Windows engine edit.' in (dst / '.claude/CLAUDE.md').read_text(encoding='utf-8'), 'deployed CLAUDE.md without the edit')

    # 另一台機器推了新的 commit：check BEHIND，plan in，in
    git(root, 'clone', '-q', '-b', 'main', str(remote), str(other))
    with (other / SHARED).open('a', newline='\n') as f:
        f.write('\nIncoming from the other machine.\n')
    git(other, 'add', '.')
    git(other, 'commit', '-q', '-m', 'incoming')
    git(other, 'push', '-q', 'origin', 'main')
    ok(engine('check', '--config', str(config), '--agent', 'claude', '--force')[-1] == 'REMOTE: BEHIND 1', 'check not BEHIND 1')
    lines = engine('plan', '--operation', 'in', '--config', str(config), '--agent', 'claude')
    engine('in', '--config', str(config), '--agent', 'claude', '--approve', plan_id(lines))
    ok(engine('status', '--config', str(config), '--agent', 'claude')[-1].startswith('NO_CHANGES'), 'not NO_CHANGES after in')
    ok('Incoming from the other machine.' in (dst / '.claude/CLAUDE.md').read_text(encoding='utf-8'), 'incoming edit not deployed')
    ok(git(src, 'rev-parse', 'HEAD') == git(remote, 'rev-parse', 'main'), 'source HEAD not advanced by in')

    # junction 是重導向：部署區裡出現就拒絕
    skill_dir = dst / '.agents/skills/sample-alpha'
    aside = root / 'aside'
    shutil.move(str(skill_dir), str(aside))
    subprocess.run(['cmd', '/c', 'mklink', '/J', str(skill_dir), str(aside)], check=True, capture_output=True)
    ok(engine('status', '--config', str(config), '--agent', 'claude', expect=65)[-1].startswith('INVALID_LAYOUT'), 'junction not refused')
    os.rmdir(skill_dir)
    shutil.move(str(aside), str(skill_dir))
    ok(engine('status', '--config', str(config), '--agent', 'claude')[-1].startswith('NO_CHANGES'), 'not NO_CHANGES after restoring the junction target')
    print('OK native engine end-to-end checks (%d assertions)' % checks)
finally:
    shutil.rmtree(root, ignore_errors=True)

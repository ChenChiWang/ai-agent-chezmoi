#!/usr/bin/env python3
"""Obtain a pinned repository without init hooks/apply or credential handling."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
import bootstrap as b
w = b.w


def acquire(remote, revision, source, destination, state):
    w.need(source.is_absolute() and destination.is_absolute() and state.is_absolute(), 'ABSOLUTE_PATH_REQUIRED')
    w.safe(destination)
    w.need(not b.a.overlaps(source, destination / '.config/ai-agent') and
           all(not b.a.overlaps(source, destination / p) for p in ('.claude', '.codex', '.agents')), 'INVALID_LAYOUT')
    b.external(state, source, destination)
    b.private(state, True)
    w.safe(source)
    w.need(not source.exists() and source.parent.is_dir(), 'SOURCE_COLLISION')
    w.need(re.fullmatch('[0-9a-f]{40}', revision), 'EXACT_REVISION_REQUIRED')
    # Only the agreed private origin; no URL credentials, helpers, or aliases.
    w.need(remote == 'ssh://git@github.com/OWNER/dotfiles.git', 'INVALID_REMOTE')
    with tempfile.TemporaryDirectory(prefix='acquire-', dir=state) as tmp:
        tmp = Path(tmp)
        (tmp / 'home').mkdir()
        import shlex
        env = dict(PATH=os.environ['PATH'], HOME=str(tmp / 'home'), LC_ALL='C',
                   GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0',
                   GIT_ALLOW_PROTOCOL='ssh', GIT_NO_REPLACE_OBJECTS='1',
                   GIT_SSH_COMMAND='ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=3 '
                   '-o StrictHostKeyChecking=yes -o IdentityFile=none -o UpdateHostKeys=no '
                   '-o UserKnownHostsFile=' + shlex.quote(str(Path.home() / '.ssh/known_hosts')))
        if os.environ.get('SSH_AUTH_SOCK'):
            env['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']
        def git(*args):
            try:
                p = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', *args], env=env, cwd=tmp,
                                   capture_output=True, timeout=60)
            except subprocess.SubprocessError:
                raise w.Block(71, 'REMOTE_UNAVAILABLE') from None
            w.need(p.returncode == 0, 'REMOTE_UNAVAILABLE_OR_AUTH_REQUIRED', 71)
            return p.stdout
        repo = tmp / 'repo'
        git('clone', '--no-checkout', '--no-recurse-submodules', '--template=', '--branch', 'main', remote, str(repo))
        w.need(git('-C', str(repo), 'rev-parse', 'HEAD').decode().strip() == revision, 'REMOTE_REVISION_CHANGED')
        # Inspect names/types from objects before checking out anything.
        allowed = set(b.a.mapping('claude-codex')[0]) | {'README.md'}
        entries = git('-C', str(repo), 'ls-tree', '-rz', 'HEAD').split(b'\0')
        for item in filter(None, entries):
            header, name = item.split(b'\t')
            w.need(name.decode() in allowed and header.split()[0] in (b'100644', b'100755'), 'BLOCKED_SCOPE')
        git('-C', str(repo), '-c', 'core.autocrlf=false', 'checkout', '--force', 'main')
        with b.engine(repo, destination, 'codex') as e:
            b.check_tree(e)
        # Publication to selected source is explicit; copy to same-filesystem
        # sibling first, then rename. Never replace an existing checkout.
        import shutil
        staging = Path(tempfile.mkdtemp(prefix='.ai-bootstrap-clone-', dir=source.parent))
        try:
            shutil.copytree(repo, staging, dirs_exist_ok=True)
            w.need(not source.exists(), 'SOURCE_COLLISION')
            os.rename(staging, source)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    print('SOURCE_READY; no deployment or authentication performed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('remote', 'revision', 'source', 'destination', 'state'):
        p.add_argument('--' + name, required=True)
    o = p.parse_args()
    try:
        acquire(o.remote, o.revision, Path(o.source), Path(o.destination), Path(o.state))
    except (w.Block, OSError, ValueError, KeyError, TypeError) as e:
        print(e.label if isinstance(e, w.Block) else 'ACQUIRE_ERROR', file=sys.stderr)
        sys.exit(e.code if isinstance(e, w.Block) else 70)

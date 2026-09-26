#!/usr/bin/env python3
"""Checksum-locked macOS artifact installation into an explicitly owned prefix.

No vendor installer scripts, package-manager upgrades, or credentials.
Apple CLT/Python is an explicit OS checkpoint; PATH is a separate reviewed step.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
import bootstrap as b
import artifacts
w = b.w
NAMES = {'git', 'python', 'chezmoi', 'gitleaks', 'claude', 'codex', 'node'}
MAX = 256 * 1024 * 1024


def selected(profile):
    return {'git', 'python', 'chezmoi', 'gitleaks'} | (
        {'claude', 'node'} if profile == 'claude' else {'codex'} if profile == 'codex' else {'claude', 'node', 'codex'})


def lockfile(path):
    doc = b.a.read_json(path)
    w.need(doc.get('schema') == 1 and doc.get('platform') in ('darwin-arm64', 'darwin-x86_64'), 'INVALID_TOOL_LOCK')
    w.need(set(doc['tools']) <= NAMES, 'UNKNOWN_TOOL')
    for name, item in doc['tools'].items():
        w.need(item['kind'] in ('archive', 'prerequisite', 'raw', 'tree', 'build-git'), 'INVALID_TOOL_LOCK')
        w.need(re.fullmatch(r'[A-Za-z0-9._+-]+', item['version']), 'INVALID_TOOL_VERSION')
        if item['kind'] != 'prerequisite':
            u = urlsplit(item['url'])
            w.need(u.scheme == 'https' and not u.username and not u.password and not u.query and not u.fragment,
                   'INVALID_ARTIFACT_URL')
            w.need(re.fullmatch('[0-9a-f]{64}', item['sha256']), 'INVALID_ARTIFACT_DIGEST')
            if item['kind'] == 'archive':
                member = PurePosixPath(item['member'])
                w.need(not member.is_absolute() and '..' not in member.parts, 'INVALID_ARCHIVE_MEMBER')
            if item['kind'] in ('tree', 'build-git'):
                w.need(re.fullmatch(r'[A-Za-z0-9._+-]+', item['top']), 'INVALID_ARCHIVE_ROOT')
        if name == 'gitleaks':
            w.need(item['version'] == '8.30.1', 'SCANNER_PIN_REQUIRED')
    return doc


def prepare(lock, prefix, profile):
    w.need(prefix.is_absolute(), 'ABSOLUTE_PREFIX_REQUIRED')
    w.safe(prefix)
    w.need(prefix.is_dir(), 'EXPLICIT_PREFIX_REQUIRED')
    b.private(prefix, True)
    w.need(platform.system() == 'Darwin' and 'darwin-' + platform.machine() == lock['platform'], 'UNSUPPORTED_PLATFORM')
    wanted = selected(profile)
    w.need(wanted <= set(lock['tools']), 'INCOMPLETE_TOOL_LOCK')
    before = {}
    for name in wanted:
        p = prefix / (name + '-' + lock['tools'][name]['version'])
        before[name] = artifacts.fingerprint(p)
    return dict(schema=1, created=int(b.time.time()), lock=lock, prefix=str(prefix), profile=profile, before=before)


def download(item):
    # Exact digest authenticates bytes even across an upstream CDN redirect.
    with urllib.request.urlopen(item['url'], timeout=20) as response:
        w.need(urlsplit(response.url).scheme == 'https', 'INSECURE_REDIRECT')
        data = response.read(MAX + 1)
    w.need(len(data) <= MAX and w.digest(data) == item['sha256'], 'ARTIFACT_INTEGRITY')
    return data


def payload(item, data):
    w.need(w.digest(data) == item['sha256'], 'ARTIFACT_INTEGRITY')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        names = set()
        expanded = 0
        for entry in archive:
            expanded += entry.size
            w.need(len(names) < 4096 and expanded <= MAX, 'ARCHIVE_LIMIT')
            p = PurePosixPath(entry.name)
            w.need(not p.is_absolute() and '..' not in p.parts and entry.name not in names,
                   'UNSAFE_ARCHIVE')
            names.add(entry.name)
            w.need(entry.isdir() or entry.isfile(), 'UNSAFE_ARCHIVE')
            w.need(entry.size <= MAX and not entry.mode & 0o6000, 'UNSAFE_ARCHIVE')
        member = archive.getmember(item['member'])
        w.need(member.isfile(), 'INVALID_EXECUTABLE')
        content = archive.extractfile(member).read(MAX + 1)
        w.need(0 < len(content) <= MAX, 'INVALID_EXECUTABLE')
        return content


def prerequisite(name, item):
    binary = shutil.which('python3' if name == 'python' else name)
    if not binary:
        return 'PREREQUISITE_MISSING'
    command = [binary, '--no-lazy-fetch', '--version'] if name == 'git' else [binary, '--version']
    try:
        result = subprocess.run(command, capture_output=True, timeout=10)
        if result.returncode:
            return 'PREREQUISITE_INCOMPATIBLE'
        text = result.stdout + result.stderr
        found = re.search(rb'(?<![0-9])(\d+)\.(\d+)(?:\.(\d+))?', text)
        if not found:
            return 'PREREQUISITE_INCOMPATIBLE'
        version = tuple(int(x or 0) for x in found.groups())
        if name == 'python':
            ok = version >= (3, 9, 0)
        elif name == 'node':
            ok = version[0] >= 22
        elif name == 'git':
            ok = True  # Capability check above is authoritative.
        else:
            ok = '.'.join(map(str, version)) == item['version']
        return 'PREREQUISITE_READY' if ok else 'PREREQUISITE_INCOMPATIBLE'
    except (OSError, subprocess.SubprocessError):
        return 'PREREQUISITE_UNAVAILABLE'


def install(doc, fetch=download):
    lock, prefix = doc['lock'], Path(doc['prefix'])
    current = prepare(lock, prefix, doc['profile'])
    current['created'] = doc['created']
    w.need(current == doc and 0 <= b.time.time() - doc['created'] < 3600, 'STALE_TOOL_PLAN')
    result = {}
    # Agent branches independent; a failed artifact does not trigger a fallback.
    # Core dependencies still gate subsequent configuration deployment.
    for name in sorted(selected(doc['profile'])):
        item = lock['tools'][name]
        if item['kind'] == 'prerequisite':
            result[name] = prerequisite(name, item)
            continue
        path = prefix / (name + '-' + item['version'])
        receipt = prefix / (path.name + '.json')
        if path.exists():
            try:
                w.need(receipt.exists(), 'UNOWNED_TOOL_COLLISION')
                old = b.load(receipt)
                w.need(old['artifact'] == item['sha256'] and old['binary'] == artifacts.fingerprint(path), 'TOOL_DRIFT')
                result[name] = 'NO_CHANGES'
            except (w.Block, OSError, KeyError, TypeError):
                result[name] = 'BLOCKED_TOOL_COLLISION_OR_DRIFT'
            continue
        try:
            raw = fetch(item)
            w.need(w.digest(raw) == item['sha256'], 'ARTIFACT_INTEGRITY')
            if item['kind'] in ('tree', 'build-git'):
                install_tree(name, item, raw, prefix, path, receipt)
                result[name] = 'INSTALLED'
                continue
            data = raw if item['kind'] == 'raw' else payload(item, raw)
            # Execute only approved artifact bytes, isolated from personal HOME.
            with tempfile.TemporaryDirectory(prefix='ai-tool-health-', dir='/tmp') as tmp:
                binary = Path(tmp).resolve() / name
                w.atomic(binary, (data, 0o755))
                if name == 'claude' and item['kind'] == 'raw':
                    signature = subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(binary)],
                                               capture_output=True, timeout=15)
                    w.need(signature.returncode == 0, 'CLAUDE_SIGNATURE_INVALID')
                run = subprocess.run([str(binary), 'version' if name == 'gitleaks' else '--version'], env={'HOME':tmp, 'PATH':os.defpath, 'LC_ALL':'C'},
                                     cwd=tmp, capture_output=True, timeout=15)
                w.need(run.returncode == 0 and re.search(rb'(?<![0-9.])' + re.escape(item['version'].encode()) + rb'(?![0-9.])', run.stdout), 'TOOL_HEALTH_FAILED')
            w.need(not path.exists(), 'TOOL_COLLISION')
            w.atomic(path, (data, 0o755))
            b.save(receipt, dict(artifact=item['sha256'], binary=artifacts.fingerprint(path), version=item['version']), True)
            result[name] = 'INSTALLED'
        except (w.Block, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError):
            result[name] = 'BLOCKED_ARTIFACT_OR_HEALTH'
    return result



def install_tree(name, item, raw, prefix, path, receipt):
    with tempfile.TemporaryDirectory(prefix='.tool-stage-', dir=prefix) as temporary:
        stage = Path(temporary).resolve()
        extracted = stage / 'tree'
        artifacts.extract(raw, extracted, item['top'])
        home = stage / 'home'; home.mkdir(mode=0o700)
        tree = artifacts.build_git(extracted, stage / 'install', home, path) if item['kind'] == 'build-git' else extracted
        binary = tree / 'bin' / name
        w.need(binary.is_file() and not binary.is_symlink(), 'INVALID_EXECUTABLE')
        env = dict(HOME=str(home), PATH=str(tree / 'bin') + ':' + os.defpath, LC_ALL='C',
                   GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
        args = [str(binary), '--version']
        if name == 'git': args.insert(1, '--no-lazy-fetch')
        run = subprocess.run(args, env=env, cwd=home, capture_output=True, timeout=20)
        w.need(run.returncode == 0 and item['version'].encode() in run.stdout, 'TOOL_HEALTH_FAILED')
        if name == 'git':
            w.need((tree / 'libexec/git-core/git-remote-https').is_file(), 'GIT_HTTPS_UNAVAILABLE')
        if name == 'node':
            for command in ('npm', 'npx'):
                run = subprocess.run([str(tree / 'bin' / command), '--version'],env=env,cwd=home,capture_output=True,timeout=20)
                w.need(run.returncode == 0, 'NPM_HEALTH_FAILED')
        fingerprint = artifacts.fingerprint(tree)
        w.need(not path.exists(), 'TOOL_COLLISION')
        tree.rename(path)
        b.save(receipt, dict(artifact=item['sha256'], binary=fingerprint, version=item['version']), True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('plan', 'install'))
    p.add_argument('--lock', required=True)
    p.add_argument('--prefix', required=True)
    p.add_argument('--profile', choices=b.PROFILES, required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--approve')
    opt = p.parse_args()
    os.umask(0o077)
    doc = prepare(lockfile(Path(opt.lock)), Path(opt.prefix), opt.profile)
    plan = Path(opt.plan)
    if opt.command == 'plan':
        b.save(plan, doc, True)
        print('PLAN_ID: ' + w.digest(w.encoded(doc)))
    else:
        approved = b.load(plan)
        w.need(w.digest(w.encoded(approved)) == opt.approve, 'INVALID_APPROVAL')
        doc['created'] = approved['created']
        w.need(doc == approved, 'STALE_TOOL_PLAN')
        result = install(doc)
        print(json.dumps(result, sort_keys=True))
        if any(v not in ('INSTALLED', 'NO_CHANGES', 'PREREQUISITE_READY') for v in result.values()):
            sys.exit(69)


if __name__ == '__main__':
    try:
        main()
    except (w.Block, OSError, ValueError, KeyError, TypeError) as exc:
        print(exc.label if isinstance(exc, w.Block) else 'TOOL_ERROR', file=sys.stderr)
        sys.exit(exc.code if isinstance(exc, w.Block) else 70)

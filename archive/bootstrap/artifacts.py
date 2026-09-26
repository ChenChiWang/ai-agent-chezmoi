#!/usr/bin/env python3
"""Bounded extraction for pinned tool trees; no vendor installer scripts."""
import io
import os
from pathlib import Path, PurePosixPath
import posixpath
import stat
import subprocess
import tarfile
import bootstrap as b
w = b.w
LIMIT = 512 * 1024 * 1024


def fingerprint(path):
    if not path.exists(): return None
    w.safe(path)
    if path.is_file(): return [w.digest(path.read_bytes()), stat.S_IMODE(path.stat().st_mode)]
    result = {}
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in sorted(dirs + files):
            p = Path(parent) / name
            info = p.lstat()
            rel = p.relative_to(path).as_posix()
            if stat.S_ISLNK(info.st_mode):
                w.need(p.resolve().is_relative_to(path.resolve()), 'TOOL_LINK_ESCAPE')
                result[rel] = ['link', os.readlink(p)]
            elif stat.S_ISDIR(info.st_mode): result[rel] = ['dir', stat.S_IMODE(info.st_mode)]
            else:
                w.need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'UNSAFE_TOOL_TREE')
                result[rel] = [w.digest(p.read_bytes()), stat.S_IMODE(info.st_mode)]
    return w.digest(w.encoded(result))


def extract(data, root, top):
    """Validate every entry before writing; publish symlinks last."""
    w.need(not root.exists(), 'TOOL_COLLISION')
    entries = {}
    expanded = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for entry in archive:
            name = PurePosixPath(entry.name)
            w.need(not name.is_absolute() and '..' not in name.parts and name.parts and name.parts[0] == top,
                   'UNSAFE_ARCHIVE')
            rel = PurePosixPath(*name.parts[1:]).as_posix()
            w.need(rel not in entries and (entry.isdir() or entry.isfile() or entry.issym())
                   and not entry.mode & 0o6000, 'UNSAFE_ARCHIVE')
            expanded += entry.size
            w.need(len(entries) < 20000 and expanded <= LIMIT and entry.size >= 0, 'ARCHIVE_LIMIT')
            entries[rel] = entry
        links = {n for n,e in entries.items() if e.issym()}
        for name,entry in entries.items():
            w.need(not any(str(p) in links for p in PurePosixPath(name).parents), 'ARCHIVE_LINK_PREFIX')
            if entry.issym():
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name),entry.linkname))
                w.need(not entry.linkname.startswith('/') and target != '..' and not target.startswith('../')
                       and target in entries and (entries[target].isfile() or entries[target].isdir()), 'ARCHIVE_LINK_ESCAPE')
        root.mkdir(mode=0o700)
        for name,entry in entries.items():
            path = root / name
            if entry.isdir(): path.mkdir(parents=True,exist_ok=True,mode=0o755)
            elif entry.isfile():
                path.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
                content = archive.extractfile(entry).read(LIMIT + 1)
                w.need(len(content) == entry.size, 'ARCHIVE_SIZE_MISMATCH')
                w.atomic(path, (content, 0o755 if entry.mode & 0o111 else 0o644))
        for name in links:
            path = root / name
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
            path.symlink_to(entries[name].linkname)


def build_git(source, staging, home, final):
    # Apple CLT is an explicit OS prerequisite. No sudo/license acceptance.
    sdk = subprocess.run(['/usr/bin/xcrun','--show-sdk-path'],capture_output=True,timeout=15)
    w.need(sdk.returncode == 0, 'APPLE_CLT_REQUIRED', 69)
    sdk_path = sdk.stdout.decode().strip()
    env = dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',HOME=str(home),LC_ALL='C',
               SDKROOT=sdk_path, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
    flags = ['prefix='+str(final), 'CC=/usr/bin/clang', 'NO_GETTEXT=YesPlease',
             'NO_TCLTK=YesPlease', 'NO_PERL=YesPlease', 'NO_PYTHON=YesPlease',
             'NO_OPENSSL=YesPlease', 'NO_RUST=YesPlease', 'NO_INSTALL_HARDLINKS=YesPlease',
             'CFLAGS=-O2 -isysroot '+sdk_path, 'LDFLAGS=-isysroot '+sdk_path]
    run = subprocess.run(['/usr/bin/make','-j2',*flags,'all'],cwd=source,env=env,
                         capture_output=True,timeout=600)
    w.need(run.returncode == 0, 'GIT_BUILD_FAILED',69)
    run = subprocess.run(['/usr/bin/make',*flags,'DESTDIR='+str(staging),'install'],cwd=source,env=env,
                         capture_output=True,timeout=120)
    w.need(run.returncode == 0, 'GIT_INSTALL_FAILED',69)

    return staging / str(final).lstrip('/')

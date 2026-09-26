#!/usr/bin/env python3
"""Explicit owned PATH integration. Never stores shell rc contents or credentials."""
import argparse
import os
from pathlib import Path
import shlex
import sys
sys.dont_write_bytecode = True
import bootstrap as b
import tools
import artifacts
import launcher
w = b.w


def shell_exec(path):
    return '#!/bin/sh\nexec ' + shlex.quote(str(path)) + ' "$@"\n'


def plan(prefix, home, state, lock, profile, launch_state=None):
    for p in (prefix, home, state):
        w.need(p.is_absolute(), 'ABSOLUTE_PATH_REQUIRED');w.safe(p)
    b.private(prefix, True);b.private(state, True)
    w.need(home.is_dir() and state != home and home not in state.parents, 'EXTERNAL_STATE_REQUIRED')
    w.need(profile in b.PROFILES, 'INVALID_PROFILE')
    w.need(not (state / 'path-journal.json').exists(), 'PATH_RECOVERY_REQUIRED',72)
    owned = b.load(state / 'path-receipt.json') if (state / 'path-receipt.json').exists() else None
    desired = {}
    for name in sorted(tools.selected(profile) - {'python'}):
        item = lock['tools'][name];root = prefix / (name + '-' + item['version'])
        receipt = b.load(prefix / (root.name + '.json'))
        w.need(receipt['artifact'] == item['sha256'] and receipt['binary'] == artifacts.fingerprint(root), 'TOOL_DRIFT')
        path = root / 'bin' / name if root.is_dir() else root
        desired[name] = shell_exec(path)
        if name in ('claude','codex') and launch_state:
            doc = b.receipt(launch_state)
            w.need(doc and doc['binaries'][name]['path'] == str(path.resolve()), 'LAUNCH_BINARY_MISMATCH')
            b.verify_receipt(doc,Path(doc['source']),Path(doc['destination']))
            desired[name] = launcher.render(launch_state,name)
        if name == 'node':
            for command in ('npm','npx'): desired[command] = shell_exec(root / 'bin' / command)
    before = {}
    for name in desired:
        p = prefix / 'bin' / name;w.safe(p)
        before[name] = artifacts.fingerprint(p)
        if p.exists():
            w.need(owned and name in owned['entries'] and before[name] == owned['entries'][name], 'UNOWNED_PATH_COLLISION')
    # Retain previously enrolled inactive commands; their launcher uses receipt
    # profile to pass through. No unrelated command is deleted or overwritten.
    fragment = 'export PATH=' + shlex.quote(str(prefix / 'bin')) + ':"$PATH"\n'
    suffix = '\n# ai-agent bootstrap PATH\n' + fragment + '# end ai-agent bootstrap PATH\n'
    shells = {}
    for name in ('.zprofile','.zshrc'):
        path = home / name;w.safe(path)
        raw = path.read_bytes() if path.exists() else b''
        prior = owned['shells'].get(name) if owned else None
        if prior:
            w.need(raw.endswith(prior['suffix'].encode()) and raw.count(b'# ai-agent bootstrap PATH') == 1,
                   'SHELL_PATH_BLOCK_CHANGED')
            w.need(prior['suffix'] == suffix, 'PATH_PREFIX_CHANGE_REQUIRES_REVIEW')
            append = ''
        else:
            w.need(b'# ai-agent bootstrap PATH' not in raw,'UNOWNED_PATH_BLOCK')
            append = suffix
        shells[name] = dict(before=w.digest(raw), after=w.digest(raw+append.encode()), size=len(raw), append=append,
                            mode=(path.stat().st_mode & 0o777) if path.exists() else 0o600)
    return dict(schema=1,prefix=str(prefix),home=str(home),state=str(state),profile=profile,
                entries=desired,before=before,shells=shells,previous=owned)


def apply(doc, approval, recovery=False):
    w.need(w.digest(w.encoded(doc)) == approval, 'INVALID_APPROVAL')
    prefix,home,state = (Path(doc[k]) for k in ('prefix','home','state'))
    for p in (prefix,home,state):w.safe(p)
    b.private(prefix,True);b.private(state,True)
    w.need(set(doc['entries']) == set(doc['before']) and set(doc['entries']) <= tools.NAMES | {'npm','npx'},'INVALID_PATH_PLAN')
    journal=state/'path-journal.json'
    if recovery:
        w.need(b.load(journal)==doc,'STALE_PATH_PLAN')
    else:
        w.need(not journal.exists(),'PATH_RECOVERY_REQUIRED',72)
    previous=b.load(state / 'path-receipt.json') if (state / 'path-receipt.json').exists() else None
    w.need(previous == doc['previous'],'STALE_PATH_PLAN')
    for name,expected in doc['before'].items():
        w.need(name in tools.NAMES | {'npm','npx'},'INVALID_PATH_PLAN')
        after=[w.digest(doc['entries'][name].encode()),0o755]
        w.need(artifacts.fingerprint(prefix / 'bin' / name) in ([expected,after] if recovery else [expected]),'STALE_PATH_PLAN')
    # Revalidate all rc files before writing; retain only digests in metadata.
    for name,entry in doc['shells'].items():
        w.need(name in ('.zprofile','.zshrc'),'INVALID_PATH_PLAN')
        path=home/name;w.safe(path)
        raw=path.read_bytes() if path.exists() else b''
        w.need(w.digest(raw) in ([entry['before'],entry['after']] if recovery else [entry['before']]),'STALE_PATH_PLAN')
    if not recovery: b.save(journal,doc,True)
    (prefix / 'bin').mkdir(mode=0o700,exist_ok=True)
    entries=dict(previous['entries']) if previous else {}
    for name,script in doc['entries'].items():
        w.atomic(prefix / 'bin' / name,(script.encode(),0o755))
        entries[name]=artifacts.fingerprint(prefix / 'bin' / name)
    shells=dict(previous['shells']) if previous else {}
    for name,entry in doc['shells'].items():
        if entry['append']:
            path=home/name
            raw=path.read_bytes() if path.exists() else b''
            if w.digest(raw) != entry['after']:
                w.need(w.digest(raw)==entry['before'],'STALE_PATH_PLAN')
                w.atomic(path,(raw+entry['append'].encode(),entry['mode']))
            shells[name]=dict(size=entry['size'],before=entry['before'],suffix=entry['append'])
    b.save(state / 'path-receipt.json',dict(schema=1,entries=entries,shells=shells))
    journal.unlink()
    return 'PATH_READY'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('plan','apply','recover'))
    for name in ('prefix','home','state','lock','profile','plan'):p.add_argument('--'+name)
    p.add_argument('--launch-state');p.add_argument('--approve')
    args=p.parse_args();os.umask(0o077)
    if args.command=='recover':
        state=Path(args.state);b.private(state,True)
        doc=b.load(state/'path-journal.json');w.need(doc['state']==str(state),'STATE_ROOT_MISMATCH')
        print(apply(doc,args.approve,recovery=True));return
    doc=plan(Path(args.prefix),Path(args.home),Path(args.state),tools.lockfile(Path(args.lock)),args.profile,
             Path(args.launch_state) if args.launch_state else None)
    if args.command=='plan':
        b.save(Path(args.plan),doc,True);print('PLAN_ID: '+w.digest(w.encoded(doc)))
    else:
        approved=b.load(Path(args.plan));w.need(doc==approved,'STALE_PATH_PLAN')
        print(apply(doc,args.approve))


if __name__=='__main__':
    try:main()
    except (w.Block,OSError,ValueError,KeyError,TypeError) as error:
        print(error.label if isinstance(error,w.Block) else 'PATH_ERROR',file=sys.stderr)
        sys.exit(error.code if isinstance(error,w.Block) else 70)

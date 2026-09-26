#!/usr/bin/env python3
"""Opt-in real pinned tree qualification, exclusively in a disposable /tmp prefix."""
import argparse
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bootstrap'))
import tools
p=argparse.ArgumentParser();p.add_argument('--component',choices=('git','node'),required=True)
p.add_argument('--prefix',type=Path,required=True);args=p.parse_args()
root=args.prefix
assert root.is_absolute() and root.parent==Path('/private/tmp') and root.name.startswith('phase4-tool-qualification-')
tools.b.private(root,True)
item=tools.lockfile(ROOT/'bootstrap/toolchain.arm64.json')['tools'][args.component]
archive=root/(args.component+'-artifact.tar.gz')
if not archive.exists():tools.w.atomic(archive,(tools.download(item),0o600))
data=archive.read_bytes();tools.w.need(tools.w.digest(data)==item['sha256'],'ARTIFACT_INTEGRITY')
path=root/(args.component+'-'+item['version']);receipt=root/(path.name+'.json')
if path.exists():
 saved=tools.b.load(receipt)
 tools.w.need(saved['artifact']==item['sha256'] and saved['binary']==tools.artifacts.fingerprint(path),'TOOL_DRIFT')
 print('NO_CHANGES: '+args.component)
else:
 tools.install_tree(args.component,item,data,root,path,receipt)
 print('ARTIFACT_INSTALL_PASS: '+args.component)

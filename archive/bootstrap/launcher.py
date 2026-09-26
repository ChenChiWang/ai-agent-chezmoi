#!/usr/bin/env python3
"""Emit a thin launcher; never overwrite a production command or modify PATH."""
import argparse
from pathlib import Path
import shlex
import subprocess
import tempfile
import os
import sys
sys.dont_write_bytecode = True
import bootstrap as b



def ensure_bridge(state):
    source=Path(__file__).with_name('exec-bridge.c')
    identity=b.w.digest(source.read_bytes())
    binary=state / ('exec-bridge-'+identity)
    receipt=state / (binary.name+'.json')
    b.w.safe(binary);b.w.safe(receipt)
    if binary.exists():
        b.w.need(receipt.exists() and b.load(receipt)==dict(source=identity,binary=b.w.digest(binary.read_bytes())),
                 'EXEC_BRIDGE_DRIFT')
        return binary
    with tempfile.TemporaryDirectory(prefix='bridge-build-',dir=state) as tmp:
        output=Path(tmp)/'bridge'
        result=subprocess.run(['/usr/bin/clang','-O2','-Wall','-Wextra','-Werror',str(source),'-o',str(output)],
                              env={'PATH':os.defpath,'HOME':tmp},capture_output=True,timeout=30)
        b.w.need(result.returncode==0,'EXEC_BRIDGE_BUILD_FAILED',69)
        b.w.atomic(binary,(output.read_bytes(),0o700))
        b.save(receipt,dict(source=identity,binary=b.w.digest(binary.read_bytes())),True)
    return binary

def render(state, agent):
    b.private(state, True)
    b.w.need(agent in ('claude', 'codex'), 'INVALID_AGENT')
    bridge = ensure_bridge(state)
    args = [str(bridge), str(Path(sys.executable).resolve()), '-B', str(Path(__file__).with_name('launch.py').resolve()),
            '--state', str(state.resolve()), '--agent', agent, '--']
    return '#!/bin/sh\nexec ' + ' '.join(shlex.quote(s) for s in args) + ' "$@"\n'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', required=True)
    p.add_argument('--agent', choices=('claude', 'codex'), required=True)
    args = p.parse_args()
    print(render(Path(args.state), args.agent), end='')

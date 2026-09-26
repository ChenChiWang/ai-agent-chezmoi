#!/usr/bin/env python3
"""Negative loading-hook qualification; explicitly supplied native Claude only.

No model requests, login, production HOME/config, or credential environment.
Passing proves the hook cannot be an unconditional loading-complete signal;
it does NOT qualify the launcher or claim a successful agent runtime session.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def qualify(binary):
    binary = binary.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='phase4-native-loading-', dir='/tmp') as td:
        root = Path(td).resolve()
        home = root / 'home'
        config = home / '.claude'
        config.mkdir(parents=True, mode=0o700)
        env = {
            'HOME': str(home), 'CLAUDE_CONFIG_DIR': str(config),
            'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'LC_ALL': 'C',
            'DISABLE_AUTOUPDATER': '1',
            'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
            'XDG_CONFIG_HOME': str(home / '.config'),
            'XDG_CACHE_HOME': str(home / '.cache'),
        }

        def run(arguments):
            return subprocess.run([str(binary), *arguments], env=env, cwd=home,
                                  stdin=subprocess.DEVNULL, capture_output=True,
                                  timeout=25)

        version = run(['--version'])
        if version.returncode != 0 or version.stdout.strip() != b'2.1.278 (Claude Code)':
            raise RuntimeError('PINNED_NATIVE_VERSION_REQUIRED')
        marker = root / 'started'
        # Constant relative path; hooks run in this disposable cwd. No shell
        # interpolation of a caller-supplied path or consumption of CLI stdin.
        hook = root / 'ready.sh'
        hook.write_text('#!/bin/sh\nprintf ready > ../started\n')
        hook.chmod(0o700)
        settings = config / 'settings.json'
        settings.write_text(json.dumps({'hooks': {'SessionStart': [{
            'hooks': [{'type': 'command', 'command': '../ready.sh'}],
        }]}}))
        settings_before = settings.read_bytes()
        cases = []
        for name, extra, expected in (
            ('ordinary_init', [], True),
            ('hooks_disabled_init', ['--settings', '{"disableAllHooks":true}'], False),
        ):
            if marker.exists():
                marker.unlink()
            result = run(['--init-only', *extra])
            observed = marker.is_file()
            if (result.returncode, observed) != (0, expected):
                raise RuntimeError('NATIVE_OBSERVATION_CHANGED: ' + name)
            if result.stdout or result.stderr or settings.read_bytes() != settings_before:
                raise RuntimeError('UNEXPECTED_NATIVE_SIDE_EFFECT: ' + name)
            cases.append(dict(case=name, exit=0, callback=observed,
                              stdout_bytes=0, stderr_bytes=0))
        return dict(version='2.1.278', binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    cases=cases, unconditional_sessionstart_barrier='NOT_QUALIFIED',
                    model_runtime='NOT_TESTED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude', type=Path, required=True,
                        help='Explicit native 2.1.278 executable (not a launcher)')
    options = parser.parse_args()
    try:
        print(json.dumps(qualify(options.claude), sort_keys=True))
    except (OSError, RuntimeError, subprocess.SubprocessError):
        # Do not print captured native output or environment on failure.
        parser.exit(1, 'Native loading qualification failed; raw output withheld.\n')

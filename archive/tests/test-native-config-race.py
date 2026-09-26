#!/usr/bin/env python3
"""Native configuration readers during a real, paused v2 fixture transaction.

Explicit binary paths; no model requests, login, hooks or production HOME.
Passing reproduces the unsafe unpinned model; it does NOT qualify deployment.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('bootstrap_fixture', Path(__file__).with_name('test-bootstrap.py'))
fmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fmod)
b, w = fmod.b, fmod.w


def probe(claude, codex, cohort=False):
    f = fmod.BootstrapTests(); f.setUp()
    try:
        # Distinct metadata markers make mixed revisions observable without
        # model inference or timing assumptions. All source is public fixture data.
        for name in ('d3-component', 'review'):
            path = f.src / b.a.PREFIX / 'shared/skills' / name / 'SKILL.md'
            path.write_text(re.sub(r'^description:.*$', 'description: LOADING_' + name + '_A',
                                   path.read_text(), flags=re.M))
        f.git('add', '.'); f.git('commit', '-qm', 'native reader fixture A')
        f.git('push', str(f.remote), 'main')
        f.deploy()
        other = f.root / 'other'
        f.run_cmd(['git', 'clone', str(f.remote), str(other)])
        for name in ('d3-component', 'review'):
            path = other / b.a.PREFIX / 'shared/skills' / name / 'SKILL.md'
            path.write_text(path.read_text().replace('LOADING_' + name + '_A', 'LOADING_' + name + '_B'))
        for cmd in (('add', '.'), ('commit', '-qm', 'native reader fixture B'), ('push', 'origin', 'main')):
            f.run_cmd(['git', '-C', str(other), *cmd])
        work = f.root / 'native-work'; work.mkdir()
        config = f.home / '.codex/config.toml'
        # prompt-input renders locally; even unexpected provider contact would
        # target loopback with no authentication requirement or credentials.
        config.write_text('model_provider = "fixture"\nmodel = "gpt-5.3-codex"\n'
                          '[model_providers.fixture]\nname = "fixture"\n'
                          'base_url = "http://127.0.0.1:9/v1"\nwire_api = "responses"\n'
                          'requires_openai_auth = false\n')
        env = dict(HOME=str(f.home), CLAUDE_CONFIG_DIR=str(f.home / '.claude'),
                   CODEX_HOME=str(f.home / '.codex'), PATH='/usr/bin:/bin', LC_ALL='C',
                   TMPDIR=str(f.root), DISABLE_AUTOUPDATER='1',
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                   ANTHROPIC_BASE_URL='http://127.0.0.1:9',
                   GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')
        versions = {}
        for name, binary, expected in [('claude', claude, b'2.1.278 (Claude Code)'),
                                       ('codex', codex, b'codex-cli 0.155.1')]:
            result = subprocess.run([str(binary), '--version'], env=env, cwd=work,
                                    capture_output=True, timeout=15)
            if result.returncode or result.stdout.strip() != expected:
                raise RuntimeError('NATIVE_PIN_MISMATCH')
            versions[name] = expected.decode()
        def native_read(product):
            if product == 'claude':
                argv = [str(claude), '-p', '--input-format', 'stream-json',
                        '--output-format', 'stream-json', '--verbose',
                        '--settings', '{"disableAllHooks":true}']
                # SDK initialization only: EOF without a user/model turn.
                data = b'{"type":"control_request","request_id":"fixture","request":{"subtype":"initialize"}}\n'
            else:
                argv = [str(codex), 'debug', 'prompt-input', '--disable', 'hooks', 'fixture']
                data = b''
            return subprocess.run(argv, input=data, env=env, cwd=work,
                                  capture_output=True, timeout=25)

        if cohort:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from generation_cohort_model import Cohort
            state = f.root / 'cohort-state'; state.mkdir(mode=0o700)
            c = Cohort(state, f.home)
            a = c.stage('claude-codex', w.snapshot(f.home, b.a.mapping('claude-codex')[1]), None)
            c.initialize(a)
            leases = {}
            for product in ('claude', 'codex'):
                identity = dict(boot='fixture', pid=os.getpid(), start=product)
                token, _ = c.admit(product, identity)
                leases[product] = (token, identity)
            # Use real v2 prepare/render, with the explicit fixture scanner.
            # Do not advance canonical source/HEAD while the cohort is active.
            before_head = f.git('rev-parse', 'HEAD')
            with b.engine(f.src, f.home, 'claude-codex', str(f.scanner), str(f.remote)) as e:
                e.build()
                candidate = c.stage('claude-codex', e.rendered, a)
            outcomes = []
            for product in ('claude', 'codex'):
                if c.activate(candidate) != 'DEFERRED_READERS':
                    raise RuntimeError('ACTIVATED_UNDER_READER')
                native = native_read(product)
                if native.returncode or any(('LOADING_' + name + '_A').encode() not in native.stdout
                                            for name in ('d3-component', 'review')):
                    raise RuntimeError('ACTIVE_GENERATION_NOT_PRESERVED')
                outcomes.append(dict(agent=product, generation='A', consistent=True))
                token, identity = leases[product]
                # This harness owns and has waited for each short native child.
                c.complete(token, identity, completion_observed=True)
            if c.activate(candidate) != 'ACTIVATED':
                raise RuntimeError('QUIESCENT_ACTIVATION_FAILED')
            for product in ('claude', 'codex'):
                identity = dict(boot='fixture', pid=os.getpid(), start=product + '-B')
                token, _ = c.admit(product, identity)
                native = native_read(product)
                if native.returncode or any(('LOADING_' + name + '_B').encode() not in native.stdout
                                            for name in ('d3-component', 'review')):
                    raise RuntimeError('NEW_GENERATION_NOT_DISCOVERED')
                outcomes.append(dict(agent=product, generation='B', consistent=True))
                c.complete(token, identity, completion_observed=True)
            if f.git('rev-parse', 'HEAD') != before_head:
                raise RuntimeError('PREPARATION_ADVANCED_SOURCE')
            return dict(versions=versions, fixed_path_cohort=outcomes,
                        model_requests='NOT_RUN', cohort_model_gate='PASS',
                        production_guardian='NOT_EXERCISED_BY_THIS_MODEL_TEST')

        results = {}
        original = w.atomic
        def paused(path, value):
            original(path, value)
            for product, skill_home in [('claude', '.claude'), ('codex', '.agents')]:
                if path != f.home / skill_home / 'skills/d3-component/SKILL.md':
                    continue
                native = native_read(product)
                observed = dict(exit=native.returncode,
                                first_skill_B=b'LOADING_d3-component_B' in native.stdout,
                                second_skill_A=b'LOADING_review_A' in native.stdout)
                if observed != dict(exit=0, first_skill_B=True, second_skill_A=True):
                    raise RuntimeError('NATIVE_RACE_NOT_REPRODUCED: ' + product)
                results[product] = observed
        with patch.object(w, 'atomic', paused), contextlib.redirect_stdout(io.StringIO()):
            fmod.launch.attempt(f.state, scanner=str(f.scanner))
        b.verify_receipt(b.receipt(f.state), f.src, f.home)
        if set(results) != {'claude', 'codex'}:
            raise RuntimeError('MISSING_NATIVE_OBSERVATION')
        # Negative routing control: CODEX_HOME alone does not pin the separate
        # HOME/.agents skill discovery root. These are synthetic files only;
        # never clone or proxy a real config/auth/session directory.
        generation = f.root / 'routing-control'
        snapshot_codex = generation / '.codex'; snapshot_codex.mkdir(parents=True)
        (snapshot_codex / 'config.toml').write_bytes(config.read_bytes())
        (snapshot_codex / 'AGENTS.md').write_text('PINNED_RULE_CONTROL\n')
        snapshot_skill = generation / '.agents/skills/review'
        snapshot_skill.mkdir(parents=True)
        (snapshot_skill / 'SKILL.md').write_text('---\nname: review\ndescription: PINNED_SKILL_CONTROL\n---\nfixture\n')
        routed_env = dict(env, CODEX_HOME=str(snapshot_codex))
        routed = subprocess.run([str(codex), 'debug', 'prompt-input', '--disable', 'hooks', 'fixture'],
                                input=b'', env=routed_env, cwd=work, capture_output=True, timeout=25)
        routing = dict(exit=routed.returncode,
                       pinned_rule=b'PINNED_RULE_CONTROL' in routed.stdout,
                       live_home_skill=b'LOADING_review_B' in routed.stdout,
                       pinned_skill=b'PINNED_SKILL_CONTROL' in routed.stdout)
        if routing != dict(exit=0, pinned_rule=True, live_home_skill=True, pinned_skill=False):
            raise RuntimeError('NATIVE_ROUTING_OBSERVATION_CHANGED')
        return dict(versions=versions, mixed_revision_observations=results,
                    codex_home_only_routing=routing,
                    model_requests='NOT_RUN', unpinned_launch_gate='FAIL')
    finally:
        f.doCleanups()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--claude', required=True, type=Path)
    p.add_argument('--codex', required=True, type=Path)
    p.add_argument('--cohort', action='store_true', help='Validate fixed paths with deferred activation instead')
    args = p.parse_args()
    try:
        print(json.dumps(probe(args.claude.resolve(strict=True), args.codex.resolve(strict=True), args.cohort), sort_keys=True))
    except Exception:
        p.exit(1, 'Native race probe failed; raw native output withheld.\n')

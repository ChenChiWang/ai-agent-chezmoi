#!/usr/bin/env python3
"""Real Gitleaks + isolated engine tests. No network, credentials or commits."""
import hashlib
import json
import os
from pathlib import Path
import random
import runpy
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "examples/chezmoi/.chezmoitemplates/ai/shared/scripts"
ADAPTER = SCRIPTS / "scan-secrets.py"
ENGINE = SCRIPTS / "sync.sh"
API = runpy.run_path(str(ADAPTER))
LOCATION = "source/.chezmoitemplates/ai/shared/instructions.md"
REL = ".chezmoitemplates/ai/adapters/codex.md"
REAL_GITLEAKS = shutil.which("gitleaks")


def synthetic():
    # Deterministic, non-issued detector fixture; never printed or committed.
    rng = random.Random(7391)
    return "gh" + "p_" + "".join(rng.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=36))


def tree(root):
    return sorted((str(p.relative_to(root)), p.stat().st_mode,
                   hashlib.sha256(p.read_bytes()).hexdigest())
                  for p in root.rglob("*") if p.is_file())


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="scanner-test-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.snapshot = self.root / "snapshot 中文 space"
        self.snapshot.mkdir()
        (self.root / "home").mkdir()
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.root / "home"),
                    "LC_ALL": "C", "TMPDIR": str(self.root)}
        self.report = self.root / "safe-report.json"

    def put(self, value, location=LOCATION):
        p = self.snapshot / location
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value if isinstance(value, bytes) else value.encode())
        return p

    def run_scan(self, expected, env=None):
        self.report.unlink(missing_ok=True)
        before = tree(self.snapshot)
        result = subprocess.run([sys.executable, str(ADAPTER), str(self.snapshot), str(self.report)],
                                cwd=self.root, env=env or self.env, capture_output=True)
        self.assertEqual(result.returncode, expected, "adapter exit code")
        self.assertEqual(tree(self.snapshot), before, "scanner mutated input")
        self.assertFalse(synthetic().encode() in result.stdout + result.stderr, "secret escaped logs")
        data = json.loads(self.report.read_text())
        self.assertFalse(synthetic() in self.report.read_text(), "secret escaped report")
        API["validate_report"](data, expected)
        return data

    def test_clean_and_real_rules(self):
        self.put("Ordinary portable instructions\n")
        self.assertEqual(self.run_scan(0)["findings"], [])
        value = synthetic()
        self.put('api_key = "' + value + '" # gitleaks:allow\n')
        findings = self.run_scan(10)["findings"]
        self.assertTrue(any(f["rule"] == "github-pat" and f["file"] == LOCATION and f["line"] == 1 for f in findings))
        rng = random.Random(37)
        generic = "".join(rng.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=40))
        self.put('api_key = "' + generic + '"\n')
        self.assertTrue(any(f["rule"] == "generic-api-key" for f in self.run_scan(10)["findings"]))
        self.put("-----BEGIN RSA PRIVATE KEY-----\n" + "QUJD" * 32 + "\n-----END RSA PRIVATE KEY-----\n")
        self.assertTrue(any(f["rule"] == "private-key" for f in self.run_scan(10)["findings"]))

    def test_no_config_or_ignore_bypass(self):
        self.put(synthetic() + " # gitleaks:allow\n", "head/.gitignore")
        (self.root / ".gitleaksignore").write_text("*\n")
        (self.root / ".gitleaks.toml").write_text("invalid toml")
        env = dict(self.env, GITLEAKS_CONFIG="/does-not-exist", GITLEAKS_CONFIG_TOML="invalid")
        findings = self.run_scan(10, env)["findings"]
        self.assertTrue(any(f["file"] == "head/.gitignore" for f in findings))

    def test_each_snapshot_scope(self):
        for scope in ("source", "index", "head", "render", "target"):
            with self.subTest(scope=scope):
                shutil.rmtree(self.snapshot)
                self.snapshot.mkdir()
                rel = REL if scope in ("source", "index", "head") else ".codex/AGENTS.md"
                location = scope + "/" + rel
                self.put(synthetic(), location)
                self.assertTrue(any(f["file"] == location for f in self.run_scan(10)["findings"]))

    def test_missing_tool(self):
        self.put("clean")
        empty = self.root / "empty-bin"
        empty.mkdir()
        self.run_scan(69, dict(self.env, PATH=str(empty)))

    def fake_binary(self, body):
        bindir = self.root / "bin"
        bindir.mkdir(exist_ok=True)
        p = bindir / "gitleaks"
        p.write_text("#!/bin/sh\n" + body)
        p.chmod(0o755)
        return dict(self.env, PATH=str(bindir) + os.pathsep + self.env["PATH"])

    def test_wrong_version_and_scan_failures(self):
        self.put("clean")
        self.run_scan(70, self.fake_binary("echo 8.29.0\n"))
        for body in ("exit 2", "exit 0", "exit 10", "echo unsafe-output; exit 0"):
            with self.subTest(body=body):
                self.run_scan(70, self.fake_binary('if [ "$1" = version ]; then echo 8.30.1; exit 0; fi\n' + body + "\n"))

    def test_timeout(self):
        self.put("clean")
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gitleaks", 10)):
            with self.assertRaises(subprocess.TimeoutExpired):
                API["scan"](self.snapshot)
        # main maps subprocess errors (including timeout) to a structured failure.
        argv = [str(ADAPTER), str(self.snapshot), str(self.report)]
        with mock.patch.object(sys, "argv", argv), mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gitleaks", 10)):
            self.assertEqual(API["main"](), 70)
        API["validate_report"](json.loads(self.report.read_text()), 70)

    def test_corrupt_gitleaks_reports(self):
        self.put("clean")
        bodies = [
            ("not JSON", 0), ("[]", 10),
            (json.dumps([{"File": "/outside-snapshot", "RuleID": "github-pat", "StartLine": 1}]), 10),
            (json.dumps([{"File": "payload/0000.txt", "RuleID": synthetic(), "StartLine": 1}]), 10),
        ]
        for body, code in bodies:
            program = "import sys,pathlib; args=sys.argv; pathlib.Path(args[args.index('--report-path')+1]).write_text(" + repr(body) + "); sys.exit(" + str(code) + ")"
            shell = 'if [ "$1" = version ]; then echo 8.30.1; exit 0; fi\nexec ' + shlex.quote(sys.executable) + " -c " + shlex.quote(program) + ' "$@"\n'
            self.run_scan(70, self.fake_binary(shell))

    def test_reject_skippable_or_unreadable_inputs(self):
        for content in (b"bad\x00data", b"\xff", b"a" * (API["MAX_BYTES"] + 1)):
            self.put(content)
            self.run_scan(70)
        p = self.put("clean")
        p.chmod(0)
        try:
            # Avoid tree() opening a deliberately unreadable file.
            result = subprocess.run([sys.executable, str(ADAPTER), str(self.snapshot), str(self.report.with_name("unreadable.json"))], env=self.env, capture_output=True)
            self.assertEqual(result.returncode, 70)
        finally:
            p.chmod(0o600)
        p.unlink()
        p.symlink_to(self.root / "nonexistent")
        result = subprocess.run([sys.executable, str(ADAPTER), str(self.snapshot), str(self.root / "symlink-report.json")], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 70)

    def test_strict_report_validation_and_redaction(self):
        good = {"file": LOCATION, "rule": "github-pat", "line": 1}
        invalid = [
            {"schema": 1, "status": "clean", "findings": [good]},
            {"schema": 1, "status": "secret", "findings": []},
            {"schema": 1, "status": "secret", "findings": [good, dict(good, file=synthetic())]},
            {"schema": 1, "status": "secret", "findings": [dict(good, rule=synthetic())]},
            {"schema": 1, "status": "secret", "findings": [dict(good, line=True)]},
            {"schema": 1, "status": "secret", "findings": [dict(good, Secret=synthetic())]},
        ]
        for item in invalid:
            self.report.write_text(json.dumps(item))
            result = subprocess.run([sys.executable, str(ADAPTER), "--display-report", str(self.report), "10"], capture_output=True)
            self.assertEqual(result.returncode, 70)
            self.assertEqual(result.stdout, b"", "partial/unsafe findings escaped")
        for raw in ('{"schema":', '{"schema":1,"schema":1,"status":"clean","findings":[]}', '[' * 2000 + ']' * 2000):
            self.report.write_text(raw)
            result = subprocess.run([sys.executable, str(ADAPTER), "--display-report", str(self.report), "0"], capture_output=True)
            self.assertEqual(result.returncode, 70)
            self.assertEqual(result.stdout, b"")


class EngineTests(ScannerTests):
    # The suite below selects only this integration method from the subclass.
    def test_engine_real_scanner(self):
        src, dst = self.root / "source", self.root / "destination"
        shutil.copytree(REPO / "examples/chezmoi", src)
        dst.mkdir()
        config = self.root / "config.toml"
        config.write_text("")
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0")
        def run(args):
            result = subprocess.run(args, env=self.env, cwd=self.root, capture_output=True)
            self.assertEqual(result.returncode, 0, "fixture setup failed")
            return result.stdout
        run(["git", "-C", str(src), "init", "-q"])
        run(["git", "-C", str(src), "add", "."])
        run(["chezmoi", "--config", str(config), "--source", str(src), "--destination", str(dst),
             "--cache", str(self.root / "cache"), "--persistent-state", str(self.root / "state"),
             "--no-tty", "--refresh-externals=never", "apply", "--force"])
        deployed_engine = dst / ".config/ai-agent/bin/sync.sh"
        def status(expected, location=None):
            before = (tree(src), tree(dst))
            result = subprocess.run(["sh", str(deployed_engine), "status", "--source", str(src),
                                     "--destination", str(dst)], env=self.env, capture_output=True)
            self.assertEqual(result.returncode, expected, "engine result")
            self.assertEqual((tree(src), tree(dst)), before, "engine changed fixture")
            output = result.stdout + result.stderr
            self.assertFalse(synthetic().encode() in output, "engine leaked synthetic secret")
            if location:
                self.assertTrue(location.encode() in output, "missing safe finding location")
                self.assertTrue(b"rule=github-pat" in output)
                self.assertFalse(b"SOURCE:" in output or b"TARGET:" in output, "normal report before block")
            return output
        status(0)
        original = (src / REL).read_bytes()
        (src / REL).write_text(synthetic())
        status(67, "source/" + REL)
        run(["git", "-C", str(src), "add", REL])
        (src / REL).write_bytes(original)
        status(67, "index/" + REL)
        run(["git", "-C", str(src), "add", REL])
        target = dst / ".codex/AGENTS.md"
        target_original = target.read_bytes()
        target.write_text(synthetic())
        status(67, "target/.codex/AGENTS.md")
        target.write_bytes(target_original)

        # Synthetic HEAD tree, real blob stored by git add, no commit creation.
        (src / REL).write_text(synthetic())
        run(["git", "-C", str(src), "add", REL])
        baseline = self.root / "baseline"
        baseline.write_bytes(run(["git", "-C", str(src), "ls-files", "--stage"]))
        (src / REL).write_bytes(original)
        run(["git", "-C", str(src), "add", REL])
        bindir = self.root / "bin"
        bindir.mkdir(exist_ok=True)
        git = bindir / "git"
        git.write_text("#!/bin/sh\n" +
            'if [ "$8" = rev-parse ] && [ "${9:-}" = --verify ]; then echo synthetic-head; exit 0; fi\n' +
            'if [ "$8" = ls-tree ]; then awk -v target="${11}" \'$4 == target {printf "%s blob %s\\t%s\\n", $1, $2, $4}\' ' + shlex.quote(str(baseline)) + '; exit 0; fi\n' +
            'exec ' + shlex.quote(shutil.which("git")) + ' "$@"\n')
        git.chmod(0o755)
        self.env["PATH"] = str(bindir) + os.pathsep + self.env["PATH"]
        status(67, "head/" + REL)
        # Scanner dependency failure is distinct from a clean/secret result.
        self.env["PATH"] = os.defpath + os.pathsep + "/opt/homebrew/bin"
        self.assertTrue(b"MISSING_DEPENDENCY:" in status(69))

        # A custom adapter cannot smuggle raw fields through the renderer.
        self.env["PATH"] = os.environ["PATH"]
        bad = self.root / "bad-adapter"
        bad_report = {"schema": 1, "status": "secret", "findings": [
            {"file": LOCATION, "rule": "github-pat", "line": 1},
            {"file": synthetic(), "rule": "github-pat", "line": 1},
        ]}
        bad.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(json.dumps(bad_report)) + ' > "$2"\nexit 10\n')
        bad.chmod(0o755)
        result = subprocess.run(["sh", str(deployed_engine), "status", "--source", str(src),
                                 "--destination", str(dst), "--scanner", str(bad)], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 70)
        self.assertTrue(b"SCANNER_ERROR:" in result.stdout)
        self.assertFalse(b"FINDING:" in result.stdout or synthetic().encode() in result.stdout + result.stderr)


if __name__ == "__main__":
    if not REAL_GITLEAKS:
        sys.exit("MISSING_DEPENDENCY: put Gitleaks 8.30.1 on PATH; real tests are not skipped")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScannerTests)
    suite.addTest(EngineTests("test_engine_real_scanner"))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

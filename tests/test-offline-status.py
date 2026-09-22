#!/usr/bin/env python3
"""No-lazy-fetch regression using real Git, Trace2 and a non-network SSH stub."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "examples/chezmoi/.chezmoitemplates/ai/shared/scripts/sync.sh"
REL = ".chezmoitemplates/ai/shared/instructions.md"
MISSING = "1" * 40


def snapshot(root):
    return sorted((str(p.relative_to(root)), p.stat().st_mode,
                   hashlib.sha256(p.read_bytes()).hexdigest())
                  for p in root.rglob("*") if p.is_file())


class OfflineStatusTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="offline-status-", dir="/tmp")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.src, self.dst = self.root / "source 中文 space", self.root / "destination"
        shutil.copytree(REPO / "examples/chezmoi", self.src)
        self.dst.mkdir()
        (self.root / "home").mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.real_git = shutil.which("git")
        self.env = dict(PATH=os.environ["PATH"], HOME=str(self.root / "home"), LC_ALL="C",
                        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0")
        self.git("init", "-q")
        self.git("add", ".")
        self.marker, self.trace = self.root / "ssh-attempt", self.root / "trace.jsonl"
        stub = self.root / "fake-ssh"
        stub.write_text("#!/bin/sh\nprintf attempted > " + shlex.quote(str(self.marker)) + "\nexit 1\n")
        self.git("config", "core.sshCommand", "sh " + shlex.quote(str(stub)))
        # Even explicit source-local/inherited transport permission must lose.
        self.git("config", "protocol.ssh.allow", "always")
        self.git("config", "remote.origin.url", "ssh://invalid.example/fixture")
        self.scanner = self.root / "scanner"
        self.scanner.write_text('#!/bin/sh\nprintf \'%s\\n\' \'{"schema":1,"status":"clean","findings":[]}\' > "$2"\n')
        self.scanner.chmod(0o755)
        self.tracer = self.bin / "git"
        self.tracer.write_text("#!/bin/sh\nexport GIT_TRACE2_EVENT=" + shlex.quote(str(self.trace)) +
                               "\nexec " + shlex.quote(self.real_git) + ' "$@"\n')
        self.tracer.chmod(0o755)

    def git(self, *args):
        result = subprocess.run([self.real_git, "-C", str(self.src), *args], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 0, "fixture Git setup failed")
        return result.stdout

    def partial(self):
        self.git("config", "core.repositoryformatversion", "1")
        self.git("config", "extensions.partialClone", "origin")
        self.git("config", "remote.origin.promisor", "true")

    def missing_index(self):
        self.git("update-index", "--cacheinfo", "100644," + MISSING + "," + REL)

    def fetch_attempts(self):
        events = [json.loads(line) for line in self.trace.read_text().splitlines()]
        return [event for event in events if event.get("event") == "child_start"
                and any(arg == "fetch" or arg.endswith("/git-fetch") for arg in event.get("argv", []))]

    def status(self, expected):
        before = snapshot(self.src), snapshot(self.dst)
        env = dict(self.env, PATH=str(self.bin) + os.pathsep + self.env["PATH"],
                   GIT_NO_LAZY_FETCH="0", GIT_ALLOW_PROTOCOL="ssh:file:https", GIT_PROTOCOL_FROM_USER="1")
        result = subprocess.run(["sh", str(ENGINE), "status", "--source", str(self.src),
                                 "--destination", str(self.dst), "--scanner", str(self.scanner)],
                                env=env, capture_output=True)
        self.assertEqual(result.returncode, expected, "unexpected status result")
        self.assertEqual((snapshot(self.src), snapshot(self.dst)), before, "status modified Git/source/destination")
        self.assertFalse(self.marker.exists(), "SSH transport was invoked")
        self.assertEqual(self.fetch_attempts(), [], "Git attempted fetch even though transport may be blocked")
        return result.stdout

    def test_partial_clone_missing_index_blob(self):
        self.partial()
        self.missing_index()
        # Positive control: unprotected real Git MUST trigger the stub and trace.
        control = subprocess.run([str(self.tracer), "-C", str(self.src), "cat-file", "blob", MISSING],
                                 env=self.env, capture_output=True)
        self.assertNotEqual(control.returncode, 0)
        self.assertTrue(self.marker.exists(), "fixture did not reproduce the original bug")
        self.assertTrue(self.fetch_attempts(), "trace did not observe the control fetch")
        self.marker.unlink()
        self.trace.unlink()
        self.assertIn(b"GIT_ERROR: index blob", self.status(70))

    def test_regular_repository_missing_blob(self):
        self.missing_index()
        self.assertIn(b"GIT_ERROR: index blob", self.status(70))

    def test_partial_clone_all_objects_local(self):
        self.partial()
        self.assertIn(b"DRIFT:", self.status(2))  # empty fixture destination

    def test_partial_clone_missing_head_tree(self):
        self.partial()
        # Stub only HEAD resolution. Real ls-tree must refuse to fetch its object.
        original = self.tracer.read_text()
        self.tracer.write_text(original.replace("exec " + shlex.quote(self.real_git),
            'if [ "${8:-}" = rev-parse ] && [ "${9:-}" = --verify ]; then echo ' + MISSING + '; exit 0; fi\nexec ' + shlex.quote(self.real_git)))
        self.assertIn(b"GIT_ERROR: HEAD tree", self.status(70))

    def test_partial_clone_missing_head_blob(self):
        self.partial()
        original = self.tracer.read_text()
        prefix = ('if [ "${8:-}" = rev-parse ] && [ "${9:-}" = --verify ]; then echo synthetic-head; exit 0; fi\n'
                  'if [ "${8:-}" = ls-tree ]; then printf "100644 blob ' + MISSING + '\\t%s\\n" "${11}"; exit 0; fi\n')
        self.tracer.write_text(original.replace("exec " + shlex.quote(self.real_git), prefix + "exec " + shlex.quote(self.real_git)))
        self.assertIn(b"GIT_ERROR: HEAD blob", self.status(70))

    def test_unsupported_git_fails_before_object_reads(self):
        # Simulate an old executable; ensure only the capability probe is called.
        calls = self.root / "calls"
        self.tracer.write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >> ' + shlex.quote(str(calls)) + '\nexit 129\n')
        env = dict(self.env, PATH=str(self.bin) + os.pathsep + self.env["PATH"])
        result = subprocess.run(["sh", str(ENGINE), "status", "--source", str(self.src),
                                 "--destination", str(self.dst), "--scanner", str(self.scanner)], env=env, capture_output=True)
        self.assertEqual(result.returncode, 69)
        self.assertIn(b"MISSING_DEPENDENCY:", result.stdout)
        entries = calls.read_text().splitlines()
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].endswith("--no-lazy-fetch --version"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

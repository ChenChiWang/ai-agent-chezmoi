#!/usr/bin/env python3
"""Offline Gitleaks adapter and strict redacted-report renderer (stdlib only)."""
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

VERSION = "8.30.1"
MAX_BYTES = 8 * 1024 * 1024
SOURCE_FILES = (
    ".chezmoitemplates/ai/shared/instructions.md",
    ".chezmoitemplates/ai/shared/skills/dotfiles-sync/SKILL.md",
    ".chezmoitemplates/ai/shared/scripts/sync.sh",
    ".chezmoitemplates/ai/shared/scripts/scan-secrets.py",
    ".chezmoitemplates/ai/shared/scripts/sync-write.py",
    ".chezmoitemplates/ai/shared/scripts/gitleaks-rules.json",
    ".chezmoitemplates/ai/adapters/claude.md",
    ".chezmoitemplates/ai/adapters/codex.md",
    "dot_claude/CLAUDE.md.tmpl",
    "dot_codex/AGENTS.md.tmpl",
    "dot_claude/skills/dotfiles-sync/SKILL.md.tmpl",
    "dot_agents/skills/dotfiles-sync/SKILL.md.tmpl",
    "dot_config/ai-agent/bin/executable_sync.sh.tmpl",
    "dot_config/ai-agent/bin/executable_scan-secrets.py.tmpl",
    "dot_config/ai-agent/bin/executable_sync-write.py.tmpl",
    "dot_config/ai-agent/bin/gitleaks-rules.json.tmpl",
    ".chezmoiignore", ".gitignore", ".gitattributes",
)
TARGET_FILES = (
    ".claude/CLAUDE.md", ".codex/AGENTS.md",
    ".claude/skills/dotfiles-sync/SKILL.md",
    ".agents/skills/dotfiles-sync/SKILL.md",
    ".config/ai-agent/bin/sync.sh",
    ".config/ai-agent/bin/scan-secrets.py",
    ".config/ai-agent/bin/sync-write.py",
    ".config/ai-agent/bin/gitleaks-rules.json",
)
LOCATIONS = frozenset(
    [scope + "/" + p for scope in ("source", "index", "head") for p in SOURCE_FILES]
    + [scope + "/" + p for scope in ("target", "render") for p in TARGET_FILES]
)


class ScanError(Exception):
    pass


def require(condition):
    if not condition:
        raise ScanError()


def rules():
    data = json.loads(Path(__file__).with_name("gitleaks-rules.json").read_text())
    require(data["version"] == VERSION)
    return frozenset(data["rules"])


def read_json(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_BYTES)
    # Reject duplicate JSON keys as well as malformed/truncated reports.
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def validate_report(report, code):
    require(type(report) is dict and set(report) == {"schema", "status", "findings"})
    require(type(report["schema"]) is int and report["schema"] == 1)
    expected = {0: "clean", 10: "secret", 69: "missing", 70: "error"}
    require(code in expected and report["status"] == expected[code])
    findings = report["findings"]
    require(type(findings) is list and len(findings) <= 10000)
    require(bool(findings) == (code == 10))
    allowed_rules = rules()
    for finding in findings:
        require(type(finding) is dict and set(finding) == {"file", "rule", "line"})
        require(finding["file"] in LOCATIONS and finding["rule"] in allowed_rules)
        require(type(finding["line"]) is int and 0 < finding["line"] <= MAX_BYTES)
    return findings


def write_report(path, status, findings):
    # Caller supplies a fresh report path outside the snapshot. Never overwrite.
    with path.open("x", encoding="utf-8") as output:
        json.dump({"schema": 1, "status": status, "findings": findings}, output)
        output.write("\n")


def scan(snapshot):
    require(snapshot.is_absolute() and snapshot.is_dir() and not snapshot.is_symlink())
    binary = shutil.which("gitleaks")
    if not binary:
        return 69, []
    binary = str(Path(binary).resolve())
    with tempfile.TemporaryDirectory(prefix="ai-agent-gitleaks-", dir="/tmp") as tmp:
        root = Path(tmp)
        (root / "home").mkdir()
        payload = root / "payload"
        payload.mkdir()
        child_env = {"HOME": str(root / "home"), "LC_ALL": "C", "PATH": os.defpath,
                     "XDG_CONFIG_HOME": str(root / "home"), "TMPDIR": tmp}
        version = subprocess.run([binary, "version"], cwd=tmp, env=child_env,
                                 capture_output=True, timeout=10)
        require(version.returncode == 0 and not version.stderr)
        require(version.stdout.strip() == VERSION.encode("ascii"))
        mapping = {}
        for parent, dirs, files in os.walk(snapshot, followlinks=False, onerror=lambda _: require(False)):
            for name in dirs:
                require(not (Path(parent) / name).is_symlink())
            for name in sorted(files):
                original = Path(parent) / name
                location = original.relative_to(snapshot).as_posix()
                require(location in LOCATIONS)
                mode = original.lstat().st_mode
                require(stat.S_ISREG(mode) and mode & 0o444)
                require(original.stat().st_size <= MAX_BYTES)
                with original.open("rb") as input_file:
                    content = input_file.read(MAX_BYTES + 1)
                require(len(content) <= MAX_BYTES and b"\x00" not in content)
                content.decode("utf-8", errors="strict")
                # Neutral filenames avoid Gitleaks' default path allowlists and
                # prevent input-controlled paths/config/ignore files affecting it.
                safe_name = "%04d.txt" % len(mapping)
                (payload / safe_name).write_bytes(content)
                mapping[safe_name] = location
        require(mapping)
        config = root / "gitleaks.toml"
        config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
        ignore = root / "empty.ignore"
        ignore.write_text("", encoding="utf-8")
        raw_report = root / "report.json"
        result = subprocess.run([
            binary, "dir", str(payload), "--config", str(config),
            "--gitleaks-ignore-path", str(ignore), "--ignore-gitleaks-allow",
            "--exit-code", "10", "--redact=100", "--no-banner", "--no-color",
            "--log-level", "error", "--report-format", "json", "--report-path", str(raw_report),
            "--max-target-megabytes", "0", "--max-decode-depth", "5",
            "--max-archive-depth", "0", "--timeout", "90",
        ], cwd=tmp, env=child_env, capture_output=True, timeout=100)
        require(result.returncode in (0, 10) and not result.stdout and not result.stderr)
        raw = read_json(raw_report)
        require(type(raw) is list and bool(raw) == (result.returncode == 10))
        require(len(raw) <= 10000)
        known_rules = rules()
        findings = set()
        for item in raw:
            require(type(item) is dict)
            rule = item["RuleID"]
            require(rule in known_rules)
            file = Path(item["File"])
            if not file.is_absolute():
                file = root / file
            require(file.parent == payload and file.name in mapping)
            line = item["StartLine"]
            require(type(line) is int and 0 < line <= MAX_BYTES)
            # Never copy Match, Secret, Description, Fingerprint, Commit, etc.
            findings.add((mapping[file.name], rule, line))
        return result.returncode, [dict(file=f, rule=r, line=l) for f, r, l in sorted(findings)]


def main():
    os.umask(0o077)
    if len(sys.argv) == 4 and sys.argv[1] == "--display-report":
        # Validate the entire document before emitting even the first finding.
        findings = validate_report(read_json(Path(sys.argv[2])), int(sys.argv[3]))
        for item in findings:
            print("FINDING: %s:%d rule=%s" % (item["file"], item["line"], item["rule"]))
        return 0
    require(len(sys.argv) == 3)
    snapshot, output = map(Path, sys.argv[1:])
    require(output.is_absolute() and not output.exists() and not output.is_symlink())
    require(snapshot.resolve() not in output.resolve().parents)
    try:
        code, findings = scan(snapshot)
    except (OSError, ValueError, KeyError, TypeError, RecursionError, ScanError, subprocess.SubprocessError):
        code, findings = 70, []
    write_report(output, {0: "clean", 10: "secret", 69: "missing", 70: "error"}[code], findings)
    return code


if __name__ == "__main__":
    def interrupted(_signum, _frame):
        # Unwind subprocess.run/TemporaryDirectory on normal termination.
        # SIGKILL cannot be handled; snapshots have owner-only permissions.
        raise KeyboardInterrupt()
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, RecursionError, ScanError, subprocess.SubprocessError, KeyboardInterrupt):
        # Exception messages may contain user bytes: never print them or tracebacks.
        sys.exit(70)

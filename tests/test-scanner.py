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
import stat
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
# 原生 Windows（#15 W6）：夾具經由平台層取得暫存根與子程序環境；sh 腳本的 shim 由 Git Bash 的 sh 執行
WINDOWS = API["WINDOWS"]
SH = shutil.which("sh") or "sh"


def shim(path, body):
    """以 sh 腳本假冒一個指令。Windows 沒有 shebang：寫成 <name>.sh 加 <name>.cmd 包裝；
    shutil.which 會經 PATHEXT 找到 .cmd，直接以絕對路徑執行。回傳要放進 PATH 搜尋的那個檔案。"""
    if WINDOWS:
        script = path.with_name(path.name + ".sh")
        script.write_text("#!/bin/sh\n" + body, newline="\n")
        wrapper = path.with_name(path.name + ".cmd")
        wrapper.write_text('@"%s" "%%~dp0%s" %%*\r\n' % (SH, script.name))
        return wrapper
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return path


def synthetic():
    # Deterministic, non-issued detector fixture; never printed or committed.
    rng = random.Random(7391)
    return "gh" + "p_" + "".join(rng.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=36))


def tree(root):
    return sorted((str(p.relative_to(root)), p.stat().st_mode,
                   hashlib.sha256(p.read_bytes()).hexdigest())
                  for p in root.rglob("*") if p.is_file())


# 夾具的 Git 不做背景維護：commit、fetch、push 之後的自動維護會短暫留下
# .git/objects/maintenance.lock，比對完整狀態的測試會因此時好時壞（#26）
QUIET_GIT = dict(GIT_CONFIG_COUNT="3", GIT_CONFIG_KEY_0="maintenance.auto", GIT_CONFIG_VALUE_0="false",
                 GIT_CONFIG_KEY_1="gc.auto", GIT_CONFIG_VALUE_1="0",
                 GIT_CONFIG_KEY_2="receive.autogc", GIT_CONFIG_VALUE_2="false")

class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="scanner-test-", dir=str(API["temporary_root"]()))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.snapshot = self.root / "snapshot 中文 space"
        self.snapshot.mkdir()
        (self.root / "home").mkdir()
        # POSIX 上與原本的 PATH/HOME/LC_ALL 相同；Windows 多出 git 與 chezmoi 需要的系統變數
        self.env = dict(API["child_environment"](self.root / "home", os.environ["PATH"]), TMPDIR=str(self.root))
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
        shim(bindir / "gitleaks", body)
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
        if WINDOWS:
            # chmod(0) 在 NTFS 只是唯讀，檔案仍可讀；symlink 需要特權。Windows 的重導向由 PlatformTests 以 junction 驗證
            return
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
        # 範本只附帶引擎自己的 skill；其他的是測試專用的夾具
        shutil.copytree(REPO / "tests/fixtures/skills", src, dirs_exist_ok=True)
        dst.mkdir()
        config = self.root / "config.toml"
        config.write_text("umask = 0o022\n")
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0", **QUIET_GIT)
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
            result = subprocess.run([SH, str(deployed_engine), "status", "--source", str(src),
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
        if not WINDOWS:
            # Windows 的 CreateProcess 以 git 這個名字只找 git.exe，攔不到 .cmd shim；synthetic HEAD 的情境只在 POSIX 驗證
            bindir = self.root / "bin"
            bindir.mkdir(exist_ok=True)
            shim(bindir / "git",
                 'if [ "$8" = rev-parse ] && [ "${9:-}" = --verify ]; then echo synthetic-head; exit 0; fi\n' +
                 'if [ "$8" = ls-tree ]; then awk -v target="${11}" \'$4 == target {printf "%s blob %s\\t%s\\n", $1, $2, $4}\' ' + shlex.quote(str(baseline)) + '; exit 0; fi\n' +
                 'exec ' + shlex.quote(shutil.which("git")) + ' "$@"\n')
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
        if WINDOWS:
            # 引擎在 Windows 以 Python 執行 scanner：壞的 adapter 也用 Python 寫
            bad.write_text("import pathlib, sys\npathlib.Path(sys.argv[2]).write_text(" + repr(json.dumps(bad_report)) + ")\nsys.exit(10)\n")
        else:
            bad.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(json.dumps(bad_report)) + ' > "$2"\nexit 10\n')
            bad.chmod(0o755)
        result = subprocess.run([SH, str(deployed_engine), "status", "--source", str(src),
                                 "--destination", str(dst), "--scanner", str(bad)], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 70)
        self.assertTrue(b"SCANNER_ERROR:" in result.stdout)
        self.assertFalse(b"FINDING:" in result.stdout or synthetic().encode() in result.stdout + result.stderr)


class PlatformTests(unittest.TestCase):
    """平台層（#33）：POSIX 分支逐字保留原本的行為；Windows 分支以旗標模擬，不需要 Windows 機器。"""

    def windows(self):
        # runpy 回傳的是模組 globals 的複本；要改到函式真正讀取的那份
        return mock.patch.dict(API["replace"].__globals__, WINDOWS=True)

    @unittest.skipIf(WINDOWS, "POSIX branch of the platform layer")
    def test_posix_behaviour_unchanged(self):
        self.assertFalse(API["WINDOWS"])
        self.assertEqual(API["temporary_root"](), Path("/tmp"))
        self.assertTrue(API["absolute_path"]("/home/user"))
        self.assertFalse(API["absolute_path"]("C:\\Users\\user"))
        self.assertFalse(API["absolute_path"]("relative"))
        self.assertEqual(API["child_environment"](Path("/h"), "/bin"), {"PATH": "/bin", "HOME": "/h", "LC_ALL": "C"})
        self.assertEqual(API["child_environment"](Path("/h"))["PATH"], os.defpath)
        self.assertTrue(API["private_mode"](Path("/x"), 0o600))
        self.assertFalse(API["private_mode"](Path("/x"), 0o640))
        private = Path(self.temp.name) / "private"
        private.write_bytes(b"{}")
        private.chmod(0o600)
        self.assertTrue(API["private_file"](private, private.stat()))
        private.chmod(0o664)
        self.assertFalse(API["private_file"](private, private.stat()))
        self.assertEqual(API["scanner_command"](Path("/s.py")), ["/s.py"])
        link = Path(self.temp.name) / "link"
        link.symlink_to(private)
        self.assertTrue(API["is_redirected"](link))
        self.assertFalse(API["is_redirected"](private))
        self.assertFalse(API["is_redirected"](Path(self.temp.name) / "missing"))
        fd = API["open_directory"](Path(self.temp.name))
        self.assertIsInstance(fd, int)
        os.close(fd)
        # POSIX 的 replace 不重試：第一次失敗就拋出
        with mock.patch("os.replace", side_effect=PermissionError) as replaced:
            with self.assertRaises(PermissionError):
                API["replace"]("a", "b")
        self.assertEqual(replaced.call_count, 1)

    def test_windows_branches(self):
        with self.windows():
            self.assertEqual(API["temporary_root"](), Path(tempfile.gettempdir()))
            self.assertTrue(API["absolute_path"]("C:\\Users\\user"))
            self.assertTrue(API["absolute_path"]("\\\\server\\share\\x"))
            self.assertFalse(API["absolute_path"]("/home/user"))
            self.assertFalse(API["absolute_path"]("\\rooted-without-drive"))
            self.assertFalse(API["absolute_path"]("C:relative"))
            with mock.patch.dict(os.environ, {"SystemRoot": "C:\\Windows", "PATHEXT": ".EXE", "COMSPEC": "cmd.exe",
                                              "SystemDrive": "C:", "TEMP": "C:\\t", "TMP": "C:\\t"}):
                env = API["child_environment"](Path("C:\\h"), "C:\\bin")
            self.assertEqual(env, {"PATH": "C:\\bin", "HOME": "C:\\h", "LC_ALL": "C", "USERPROFILE": "C:\\h",
                                   "SystemRoot": "C:\\Windows", "SystemDrive": "C:", "PATHEXT": ".EXE",
                                   "TEMP": "C:\\t", "TMP": "C:\\t", "COMSPEC": "cmd.exe"})
            # 做不到等價的擁有者與權限檢查：一律不通過，不略過
            # 做不到的判定不會默默通過：Windows 分支要讀 ACL，這裡給它一個開放的描述子
            with mock.patch.dict(API["replace"].__globals__, USER_SID=self.ME, OWNER_SID=self.ME, ELEVATED=False,
                                 security_descriptor=lambda p: API["parse_sddl"](self.INHERITED)):
                self.assertFalse(API["private_mode"](Path(__file__), 0o600))
                self.assertFalse(API["private_file"](Path(__file__), Path(__file__).stat()))
            self.assertIsNone(API["open_directory"](Path(self.temp.name)))
            with mock.patch("os.fchmod", create=True) as fchmod:
                API["set_mode"](3, 0o600)
            fchmod.assert_not_called()
            self.assertEqual(API["scanner_command"](Path("C:\\s.py")), [sys.executable, "C:\\s.py"])
            # replace：暫時被佔用時重試，持續失敗就拋出
            with mock.patch("os.replace", side_effect=[PermissionError(), PermissionError(), None]) as replaced, \
                    mock.patch("time.sleep") as slept:
                API["replace"]("a", "b")
            self.assertEqual((replaced.call_count, slept.call_count), (3, 2))
            with mock.patch("os.replace", side_effect=PermissionError) as replaced, mock.patch("time.sleep"):
                with self.assertRaises(PermissionError):
                    API["replace"]("a", "b")
            self.assertEqual(replaced.call_count, 5)


    # ---- Windows 的 ACL（#38）：SDDL 解析與政策判定是純函式，這裡用實機錄下的字串 ----

    ME = "S-1-5-21-3944484857-1765433118-1380507665-1001"
    OTHER = "S-1-5-21-3944484857-1765433118-1380507665-1004"
    INHERITED = ("O:" + ME + "D:AI(A;ID;0x1200a9;;;" + OTHER + ")(A;ID;FA;;;SY)(A;ID;FA;;;BA)(A;ID;FA;;;" + ME + ")")
    PROTECTED = "O:" + ME + "D:PAI(A;;FA;;;BA)(A;;FA;;;SY)(A;;FA;;;" + ME + ")"
    DIRECTORY = "O:" + ME + "D:PAI(A;OICI;FA;;;" + ME + ")(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)"

    def test_sddl_parsing_and_policy(self):
        owner, aces = API["parse_sddl"](self.INHERITED)
        self.assertEqual(owner, self.ME)
        self.assertEqual(aces[0], ("A", "ID", 0x1200A9, self.OTHER))
        self.assertEqual(aces[1], ("A", "ID", 0x1F01FF, "S-1-5-18"))
        self.assertEqual(aces[2][3], "S-1-5-32-544")
        self.assertEqual(API["parse_sddl"](self.DIRECTORY)[1][3], ("A", "OICI", 0x1F01FF, "S-1-3-4"))
        self.assertEqual(API["parse_sddl"]("O:BAD:(A;;GRGW;;;WD)"), ("S-1-5-32-544", [("A", "", 0xC0000000, "WD")]))
        for bad in ("", "O:" + self.ME, "O:" + self.ME + "D:(A;;ZZ;;;SY)", "O:" + self.ME + "D:(A;;FA)"):
            with self.assertRaises(ValueError):
                API["parse_sddl"](bad)
        private, writable = API["acl_private"], API["acl_foreign_writable"]
        # 繼承的唯讀群組：不算私有，但也沒有寫入權
        self.assertFalse(private(API["parse_sddl"](self.INHERITED), self.ME))
        self.assertFalse(writable(API["parse_sddl"](self.INHERITED), self.ME))
        # 受保護、只有使用者／SYSTEM／Administrators／OWNER RIGHTS：私有
        self.assertTrue(private(API["parse_sddl"](self.PROTECTED), self.ME))
        self.assertTrue(private(API["parse_sddl"](self.DIRECTORY), self.ME))
        # 別人擁有、或別人可寫
        self.assertFalse(private(API["parse_sddl"](self.PROTECTED), self.OTHER))
        # 提升權限的程序建立的檔案由 Administrators 擁有：token owner 是 BA 時算自己的，否則不算
        elevated = API["parse_sddl"]("O:BAD:PAI(A;;FA;;;BA)(A;;FA;;;SY)(A;;FA;;;" + self.ME + ")")
        self.assertTrue(private(elevated, self.ME, "S-1-5-32-544"))
        # LA 是網域相對的本機 Administrator 帳號：使用者就是它（RID 500）時算自己，否則是別人
        admin = "S-1-5-21-1643835476-1616584234-1346609752-500"
        runner = API["parse_sddl"]("O:BAD:PAI(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;FA;;;LA)")
        self.assertTrue(private(runner, admin, "S-1-5-32-544"))
        self.assertFalse(private(runner, self.ME, "S-1-5-32-544"))
        self.assertTrue(writable(runner, self.ME))
        self.assertFalse(writable(runner, admin))
        self.assertFalse(private(elevated, self.ME, self.ME))
        self.assertFalse(private(elevated, self.ME))
        # token 有提升權限：Administrators 擁有的檔案算自己的，即使 token owner 已被 MSYS 改回使用者
        self.assertTrue(private(elevated, self.ME, self.ME, True))
        self.assertFalse(private(API["parse_sddl"]("O:" + self.OTHER + "D:PAI(A;;FA;;;" + self.ME + ")"), self.ME, self.ME, True))
        self.assertTrue(writable(API["parse_sddl"]("O:" + self.ME + "D:(A;;FA;;;SY)(A;;0x120116;;;" + self.OTHER + ")"), self.ME))
        self.assertTrue(writable(API["parse_sddl"]("O:" + self.ME + "D:(A;;SD;;;WD)"), self.ME))
        self.assertTrue(writable(API["parse_sddl"]("O:" + self.ME + "D:(A;;GA;;;AU)"), self.ME))
        # deny ACE 只會限制：不影響私有，也不算可寫
        denied = API["parse_sddl"]("O:" + self.ME + "D:(D;;FA;;;" + self.OTHER + ")(A;;FA;;;" + self.ME + ")")
        self.assertTrue(private(denied, self.ME))
        self.assertFalse(writable(denied, self.ME))

    def test_windows_reparse_points_and_scratch_rule(self):
        # Windows 的重導向是任何 reparse point；暫存根在使用者目錄下，只要不碰 source 與部署區就允許（#39）
        attributes = {"junction": stat.FILE_ATTRIBUTE_REPARSE_POINT | stat.FILE_ATTRIBUTE_DIRECTORY,
                      "plain": stat.FILE_ATTRIBUTE_DIRECTORY}
        def lstat(path):
            if Path(path).name not in attributes:
                raise FileNotFoundError(path)
            return mock.Mock(st_file_attributes=attributes[Path(path).name])
        conflict, home = API["scratch_conflict"], Path("/home/u")
        with self.windows():
            with mock.patch("os.lstat", side_effect=lstat):
                self.assertTrue(API["is_redirected"](Path("/x/junction")))
                self.assertFalse(API["is_redirected"](Path("/x/plain")))
                self.assertFalse(API["is_redirected"](Path("/x/missing")))
            self.assertFalse(conflict(home / ".local/share/chezmoi", home, home / "AppData/Local/Temp"))
            self.assertTrue(conflict(home / ".local/share/chezmoi", home, home / ".claude/tmp"))
            self.assertTrue(conflict(home / ".local/share/chezmoi", home, home / ".claude"))
            self.assertTrue(conflict(home / ".local/share/chezmoi", home, home / ".config/ai-agent/tmp"))
            self.assertTrue(conflict(home / ".local/share/chezmoi", home, home / ".local/share/chezmoi/tmp"))
            # 暫存根底下的 source 或部署目錄本身不算：和 POSIX 允許 /tmp/src 一樣
            self.assertFalse(conflict(home / "AppData/Local/Temp/fixture/src", home / "AppData/Local/Temp/fixture/dst",
                                      home / "AppData/Local/Temp"))
            self.assertFalse(conflict(home / ".local/share/chezmoi", home, home / ".config"))
        if WINDOWS:
            return
        # POSIX 規則不變：root 不得等於或包含暫存根
        self.assertTrue(conflict(Path("/x"), Path("/tmp"), Path("/tmp")))
        self.assertTrue(conflict(Path("/x"), Path("/"), Path("/tmp")))
        self.assertTrue(conflict(Path("/tmp"), Path("/home/u"), Path("/tmp")))
        self.assertFalse(conflict(Path("/home/u/.local/share/chezmoi"), Path("/home/u"), Path("/tmp")))
        self.assertFalse(conflict(Path("/tmp/src"), Path("/home/u"), Path("/tmp")))

    @unittest.skipUnless(WINDOWS, "real ACLs and junctions exist only on Windows")
    def test_windows_real_acl_and_junction(self):
        # 不用 mock：真的檔案、真的 icacls、真的 junction
        root = Path(self.temp.name)
        target = root / "params.json"
        target.write_bytes(b"{}")
        me = API["current_user_sid"]()
        self.assertTrue(me.startswith("S-1-5-21-"))
        # 一般使用者建立的檔案 owner 是自己；提升權限的 Administrator（CI runner）是 Administrators 群組
        self.assertIn(API["security_descriptor"](target)[0],
                      (me, API["token_owner_sid"]()) + (("S-1-5-32-544",) if API["token_elevated"]() else ()))
        subprocess.run(["icacls", str(target), "/grant", "*S-1-1-0:W"], check=True, capture_output=True)
        self.assertFalse(API["private_file"](target, target.stat()))
        self.assertTrue(API["foreign_writable"](target, target.stat()))
        API["make_private"](target)
        self.assertTrue(API["private_file"](target, target.stat()))
        self.assertFalse(API["foreign_writable"](target, target.stat()))
        plans = root / "plans"
        plans.mkdir()
        API["make_private"](plans)
        self.assertEqual(API["private_directory_report"](plans)[:2], (True, " acl private"))
        child = plans / "child.json"
        child.write_bytes(b"{}")
        self.assertTrue(API["private_mode"](child, 0o600), "children inherit the private DACL")
        aside = root / "aside"
        aside.mkdir()
        junction = root / "junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(aside)], check=True, capture_output=True)
        self.assertTrue(API["is_redirected"](junction))
        self.assertFalse(API["is_redirected"](aside))
        os.rmdir(junction)
        temp_root = API["temporary_root"]()
        self.assertFalse(API["scratch_conflict"](root / "src", root / "dst", temp_root))
        self.assertTrue(API["scratch_conflict"](temp_root / "src", root / "dst", temp_root / "src" / "tmp"))

    def test_mode_semantics_without_mode_bits(self):
        # Windows 沒有 mode bits：快照記錄預期模式，執行位元以 index 為準，umask 檢查不適用（#15 W4c）
        private = Path(self.temp.name) / "script"
        private.write_bytes(b"#!/bin/sh\n")
        if not WINDOWS:
            private.chmod(0o755)
            self.assertEqual(API["observed_mode"](private.stat(), 0o644), 0o755)
            self.assertTrue(API["executable_bit"](private, "100644"))
            self.assertTrue(API["target_executable"](private))
            private.chmod(0o644)
            self.assertFalse(API["executable_bit"](private, "100755"))
            self.assertFalse(API["target_executable"](private))
            self.assertTrue(API["umask_applies"]())
            self.assertEqual(API["config_refused"](private, "INVALID_CONFIG"), "INVALID_CONFIG")
        with self.windows(), mock.patch.dict(API["replace"].__globals__, USER_SID=self.ME, OWNER_SID=self.ME, ELEVATED=False):
            self.assertEqual(API["observed_mode"](private.stat(), 0o755), 0o755)
            self.assertTrue(API["executable_bit"](private, "100755"))
            self.assertFalse(API["executable_bit"](private, "100644"))
            self.assertFalse(API["executable_bit"](private, ""))
            self.assertTrue(API["target_executable"](private))
            self.assertFalse(API["umask_applies"]())
            self.assertEqual(API["config_refused"](private, "INVALID_CONFIG"),
                             "INVALID_CONFIG; " + API["private_hint"](private))
        # 標準 target 模式與 mapping 一致：引擎腳本與相容入口 755，其餘 644
        _, targets = API["mapping"]("claude-codex")
        executables = {p for p in targets if API["target_mode"](p) == 0o755}
        self.assertEqual(executables, {".config/ai-agent/bin/sync.sh", ".config/ai-agent/bin/scan-secrets.py",
                                       ".config/ai-agent/bin/sync-write.py", ".config/ai-agent/bin/sync-migrate.py",
                                       ".claude/skills/dotfiles-sync/sync.sh"})
        self.assertEqual(API["target_modes"]([".claude/CLAUDE.md"]), {".claude/CLAUDE.md": 0o644})

    def test_protect_and_make_private_entry(self):
        # 上線用的 --make-private：POSIX 是 chmod 600／700，Windows 交給 make_private（這裡會真的設 ACL）
        target = Path(self.temp.name) / "params.json"
        target.write_bytes(b"{}")
        plans = Path(self.temp.name) / "plans"
        plans.mkdir(mode=0o755)
        if not WINDOWS:
            target.chmod(0o644)
            API["protect"](target)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            API["protect"](plans)
            self.assertEqual(plans.stat().st_mode & 0o777, 0o700)
            target.chmod(0o644)
        run = subprocess.run([sys.executable, str(ADAPTER), "--make-private", str(target)], capture_output=True, text=True)
        self.assertEqual((run.returncode, run.stdout.strip()), (0, "OK: " + str(target) + " is private"))
        if WINDOWS:
            self.assertTrue(API["private_file"](target, target.stat()))
        else:
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        for bad in ("relative", str(Path(self.temp.name) / "missing")):
            self.assertEqual(subprocess.run([sys.executable, str(ADAPTER), "--make-private", bad], capture_output=True).returncode, 70)
        with self.windows(), mock.patch.dict(API["replace"].__globals__, make_private=mock.Mock()) as patched:
            API["protect"](target)
            patched["make_private"].assert_called_once_with(target)

    def test_private_checks_posix_and_windows(self):
        private = Path(self.temp.name) / "private"
        private.write_bytes(b"{}")
        directory = Path(self.temp.name) / "plans"
        directory.mkdir(mode=0o700)
        if not WINDOWS:
            private.chmod(0o600)
            self.assertTrue(API["private_file"](private, private.stat()))
            self.assertTrue(API["private_mode"](private, 0o600))
            self.assertFalse(API["private_mode"](private, 0o640))
            self.assertFalse(API["foreign_writable"](private, private.stat()))
            private.chmod(0o664)
            self.assertFalse(API["private_file"](private, private.stat()))
            self.assertTrue(API["foreign_writable"](private, private.stat()))
            self.assertEqual(API["private_hint"](private), "chmod 600 " + str(private))
            self.assertEqual(API["private_hint"](Path(self.temp.name)), "chmod 700 " + self.temp.name)
            self.assertEqual(API["private_directory_report"](directory), (True, " mode 700", ""))
            directory.chmod(0o750)
            self.assertEqual(API["private_directory_report"](directory), (False, " mode 750", "chmod 700 " + str(directory)))
            # POSIX 的 make_private 不做任何事，也不呼叫 icacls
            with mock.patch("subprocess.run") as run:
                API["make_private"](private)
            run.assert_not_called()
        with self.windows(), mock.patch.dict(API["replace"].__globals__, USER_SID=self.ME, OWNER_SID=self.ME, ELEVATED=False), \
                mock.patch.dict(API["replace"].__globals__, security_descriptor=lambda p: API["parse_sddl"](self.INHERITED)):
            self.assertFalse(API["private_file"](private, private.stat()))
            self.assertFalse(API["private_mode"](private, 0o600))
            self.assertFalse(API["foreign_writable"](private, private.stat()))
            self.assertEqual(API["private_directory_report"](directory),
                             (False, " acl open to other principals", API["private_hint"](directory)))
            self.assertEqual(API["private_hint"](private),
                             'icacls "%s" /inheritance:r /grant:r *%s:F *S-1-5-18:F *S-1-5-32-544:F' % (private, self.ME))
            self.assertTrue(API["private_hint"](directory).endswith("*S-1-5-32-544:(OI)(CI)F"))
        with self.windows(), mock.patch.dict(API["replace"].__globals__, USER_SID=self.ME, OWNER_SID=self.ME, ELEVATED=False), \
                mock.patch.dict(API["replace"].__globals__, security_descriptor=lambda p: API["parse_sddl"](self.PROTECTED)), \
                mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)) as run:
            self.assertTrue(API["private_file"](private, private.stat()))
            API["make_private"](private)
            self.assertEqual(run.call_args[0][0], ["icacls", str(private), "/inheritance:r", "/grant:r",
                                                  "*" + self.ME + ":F", "*S-1-5-18:F", "*S-1-5-32-544:F"])
            API["make_private"](directory)
            self.assertEqual(run.call_args[0][0][4:], ["*" + self.ME + ":(OI)(CI)F", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"])
        # icacls 失敗，或設定後讀回仍不私有：OSError，絕不默默通過
        with self.windows(), mock.patch.dict(API["replace"].__globals__, USER_SID=self.ME, OWNER_SID=self.ME, ELEVATED=False), \
                mock.patch.dict(API["replace"].__globals__, security_descriptor=lambda p: API["parse_sddl"](self.INHERITED)), \
                mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)):
            with self.assertRaises(OSError):
                API["make_private"](private)
        with self.windows(), mock.patch.dict(API["replace"].__globals__, USER_SID=self.ME, OWNER_SID=self.ME, ELEVATED=False), \
                mock.patch("subprocess.run", return_value=mock.Mock(returncode=1)):
            with self.assertRaises(OSError):
                API["make_private"](private)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="platform-test-", dir=str(API["temporary_root"]()))
        self.addCleanup(self.temp.cleanup)


if __name__ == "__main__":
    if not REAL_GITLEAKS:
        sys.exit("MISSING_DEPENDENCY: put Gitleaks 8.30.1 on PATH; real tests are not skipped")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScannerTests)
    suite.addTest(EngineTests("test_engine_real_scanner"))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(PlatformTests))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

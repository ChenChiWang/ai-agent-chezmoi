#!/bin/sh
# preflight 的平台檢查：原生 Windows 要 FAIL，POSIX 平台不得多出任何 platform 行；
# WSL 上解析到 Windows 磁碟的 claude 要 WARN。
# 以 PATH shim 假造 uname、ssh、wslpath 與 claude，不連網、不讀使用者的 HOME。
set -eu
repo=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd -P)
test_root=$(mktemp -d /tmp/ai-agent-test.XXXXXXXX)
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/bin" "$test_root/home" "$test_root/mnt/c/npm" "$test_root/linux-bin"
cat > "$test_root/bin/uname" <<'SHIM'
#!/bin/sh
case "${1:-}" in
  -m) echo x86_64 ;;
  -r) echo "${FAKE_UNAME_R:-6.8.0-generic}" ;;
  *) echo "$FAKE_UNAME_S" ;;
esac
SHIM
cat > "$test_root/bin/ssh" <<'SHIM'
#!/bin/sh
echo 'git@example.invalid: Permission denied (publickey).' >&2
exit 255
SHIM
# 模擬 WSL 的磁碟掛載點：C:\ 對應到 $test_root/mnt/c/
printf '#!/bin/sh\necho "%s/mnt/c/"\n' "$test_root" > "$test_root/bin/wslpath"
printf '#!/bin/sh\n' > "$test_root/mnt/c/npm/claude"
printf '#!/bin/sh\n' > "$test_root/linux-bin/claude"
chmod +x "$test_root/bin/uname" "$test_root/bin/ssh" "$test_root/bin/wslpath" \
  "$test_root/mnt/c/npm/claude" "$test_root/linux-bin/claude"

# 用法：run_preflight UNAME_S [UNAME_R] [額外 PATH]
run_preflight() {
  set +e
  FAKE_UNAME_S=$1 FAKE_UNAME_R=${2:-} HOME="$test_root/home" PATH="$test_root/bin:${3:+$3:}$PATH" \
    sh "$repo/setup/preflight.sh" --host example.invalid > "$test_root/output" 2>&1
  rc=$?
  set -e
}
expect_line() {
  grep -q "$1" "$test_root/output" || { echo "missing: $1 ($2)"; cat "$test_root/output"; exit 1; }
}

for os in MINGW64_NT-10.0-26200 MSYS_NT-10.0-26200 CYGWIN_NT-10.0-26200; do
  run_preflight "$os"
  expect_line "^FAIL platform: native Windows ($os) unsupported -> use WSL" "$os"
  [ "$rc" != 0 ] || { echo "preflight exited 0 on $os"; exit 1; }
done

for os in Darwin Linux; do
  run_preflight "$os"
  if grep -Eq '^(OK|WARN|FAIL) +platform:' "$test_root/output"; then
    echo "unexpected platform check line on $os"; cat "$test_root/output"; exit 1
  fi
  [ "$(grep -c '^platform: ' "$test_root/output")" = 1 ] || {
    echo "platform header changed on $os"; cat "$test_root/output"; exit 1; }
done

wsl_kernel=6.18.33.2-microsoft-standard-WSL2
run_preflight Linux "$wsl_kernel" "$test_root/mnt/c/npm"
expect_line "^WARN claude: Windows binary at $test_root/mnt/c/npm/claude -> install Claude Code inside WSL" 'WSL, Windows claude'
run_preflight Linux "$wsl_kernel" "$test_root/linux-bin:$test_root/mnt/c/npm"
expect_line "^OK   claude: $test_root/linux-bin/claude$" 'WSL, Linux claude first'
run_preflight Linux '' "$test_root/mnt/c/npm"
expect_line "^OK   claude: $test_root/mnt/c/npm/claude$" 'not WSL, same path'

echo 'OK preflight platform checks'

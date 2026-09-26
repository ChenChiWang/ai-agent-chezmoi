#!/bin/sh
# preflight 的平台檢查：原生 Windows 要 FAIL，POSIX 平台不得多出任何 platform 行。
# 以 PATH shim 假造 uname 與 ssh，不連網、不讀使用者的 HOME。
set -eu
repo=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd -P)
test_root=$(mktemp -d /tmp/ai-agent-test.XXXXXXXX)
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/bin" "$test_root/home"
cat > "$test_root/bin/uname" <<'SHIM'
#!/bin/sh
case "${1:-}" in -m) echo x86_64 ;; *) echo "$FAKE_UNAME_S" ;; esac
SHIM
cat > "$test_root/bin/ssh" <<'SHIM'
#!/bin/sh
echo 'git@example.invalid: Permission denied (publickey).' >&2
exit 255
SHIM
chmod +x "$test_root/bin/uname" "$test_root/bin/ssh"

run_preflight() {
  set +e
  FAKE_UNAME_S=$1 HOME="$test_root/home" PATH="$test_root/bin:$PATH" \
    sh "$repo/setup/preflight.sh" --host example.invalid > "$test_root/output" 2>&1
  rc=$?
  set -e
}

for os in MINGW64_NT-10.0-26200 MSYS_NT-10.0-26200 CYGWIN_NT-10.0-26200; do
  run_preflight "$os"
  grep -q "^FAIL platform: native Windows ($os) unsupported -> use WSL" "$test_root/output" || {
    echo "missing platform FAIL for $os"; cat "$test_root/output"; exit 1; }
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

echo 'OK preflight platform checks'

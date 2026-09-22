#!/bin/sh
# Source from test scripts. All mutations remain under a fresh temporary root.
set -eu
repo=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd -P)
test_root=$(mktemp -d /tmp/ai-agent-test.XXXXXXXX)
trap 'rm -rf "$test_root"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
test_path=$PATH
src="$test_root/source 中文 space"
dst="$test_root/destination 中文 space"
mkdir -p "$src" "$dst" "$test_root/home" "$test_root/cache"
cp -R "$repo/examples/chezmoi/." "$src/"
: > "$test_root/config.toml"
isolated() {
  env -i PATH="$test_path" HOME="$test_root/home" LC_ALL=C \
    XDG_CONFIG_HOME="$test_root/home/config" XDG_CACHE_HOME="$test_root/cache" \
    XDG_DATA_HOME="$test_root/home/data" XDG_STATE_HOME="$test_root/home/state" \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
    "$@"
}
cm() {
  isolated chezmoi --config "$test_root/config.toml" --source "$src" \
    --destination "$dst" --cache "$test_root/cache" \
    --persistent-state "$test_root/state.boltdb" --refresh-externals=never --no-tty "$@"
}
engine="$repo/examples/chezmoi/.chezmoitemplates/ai/shared/scripts/sync.sh"
scanner="$test_root/scanner"
cat > "$scanner" <<'SCANNER'
#!/bin/sh
# Synthetic marker detector for contract tests ONLY. Not a production scanner.
echo 'untrusted scanner output must not escape'
echo 'untrusted scanner stderr must not escape' >&2
grep -r -q 'SYNTHETIC_TEST_SECRET' "$1"
rc=$?
case "$rc" in
  0)
    printf '%s\n' '{"schema":1,"status":"secret","findings":[{"file":"source/.chezmoitemplates/ai/shared/instructions.md","rule":"generic-api-key","line":1}]}' > "$2"
    exit 10 ;;
  1) printf '%s\n' '{"schema":1,"status":"clean","findings":[]}' > "$2"; exit 0 ;;
  *) exit 20 ;;
esac
SCANNER
chmod +x "$scanner"
assert_contains() { grep -F -q "$2" "$1" || { echo "FAIL: expected $2"; exit 1; }; }
run_status() {
  rc=0
  isolated sh "$engine" status --source "$src" --destination "$dst" --scanner "$scanner" \
    > "$test_root/output" 2>&1 || rc=$?
  [ "$rc" = "$1" ] || { cat "$test_root/output"; echo "FAIL: exit $rc, expected $1"; exit 1; }
  if grep -q 'untrusted scanner\|SYNTHETIC_TEST_SECRET' "$test_root/output"; then
    echo 'FAIL: leaked scanner output'; exit 1
  fi
}
# Hash paths, bytes and modes, including .git index/HEAD/config and deployed files.
snapshot() {
  isolated python3 - "$src" "$dst" <<'PY'
import hashlib, os, stat, sys
for root in sys.argv[1:]:
    for parent, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(dirs + files):
            p = os.path.join(parent, name)
            mode = os.lstat(p).st_mode
            value = os.readlink(p) if stat.S_ISLNK(mode) else (hashlib.sha256(open(p, 'rb').read()).hexdigest() if stat.S_ISREG(mode) else '')
            print(os.path.relpath(p, root), mode, value)
PY
}

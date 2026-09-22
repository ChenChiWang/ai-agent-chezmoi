#!/bin/sh
. "$(dirname "$0")/helpers.sh"
isolated git -C "$src" init -q
# No commits, remotes or credentials needed: exercise the unborn branch as well.
isolated git -C "$src" add .
cm apply --force
snapshot > "$test_root/before"
run_status 0
assert_contains "$test_root/output" 'OK: source changes'
snapshot > "$test_root/after"
cmp "$test_root/before" "$test_root/after"

# Supply a synthetic HEAD through a Git shim, using the real index's existing
# blobs. This exercises committed-baseline reads without creating any commit.
isolated git -C "$src" ls-files --stage > "$test_root/baseline-index"
mkdir "$test_root/bin"
real_git=$(command -v git)
isolated python3 - "$test_root" "$real_git" <<'PY'
import pathlib, shlex, sys
root, git = sys.argv[1:]
script = '''#!/bin/sh
real_git=GIT_EXEC
baseline=BASELINE
# Engine prefix: git -c ... -c ... -C source --no-lazy-fetch.
case "$8" in
  rev-parse)
    if [ "${9:-}" = --verify ] && [ "${10:-}" = HEAD ]; then
      echo synthetic-head; exit 0
    fi ;;
  ls-tree)
    if [ "${9:-}" = synthetic-head ]; then
      awk -v target="$11" '$4 == target { printf "%s blob %s\\t%s\\n", $1, $2, $4 }' "$baseline"
      exit 0
    fi ;;
esac
exec "$real_git" "$@"
'''.replace('GIT_EXEC', shlex.quote(git)).replace('BASELINE', shlex.quote(root+'/baseline-index')).replace('"$11"', '"${11}"')
p = pathlib.Path(root)/'bin/git'
p.write_text(script)
p.chmod(0o755)
PY
original_test_path=$test_path
test_path="$test_root/bin:$test_path"
run_status 0
assert_contains "$test_root/output" 'NO_CHANGES:'
printf '\nShared working change\n' >> "$src/.chezmoitemplates/ai/shared/instructions.md"
run_status 2
assert_contains "$test_root/output" 'staged=clean working=changed'
assert_contains "$test_root/output" 'TARGET: .codex/AGENTS.md changed'
cp "$repo/examples/chezmoi/.chezmoitemplates/ai/shared/instructions.md" "$src/.chezmoitemplates/ai/shared/instructions.md"
# Even an otherwise clean status must fail when the scanner fails.
cp "$scanner" "$test_root/clean-scanner"
printf '#!/bin/sh\nexit 20\n' > "$scanner"
run_status 70
assert_contains "$test_root/output" 'SCANNER_ERROR:'
cp "$test_root/clean-scanner" "$scanner"
test_path=$original_test_path

printf 'unrelated dotfile\n' > "$src/dot_unrelated"
isolated git -C "$src" add dot_unrelated
printf 'untracked private state\n' > "$src/do-not-read"
printf '\nA local edit\n' >> "$dst/.claude/CLAUDE.md"
snapshot > "$test_root/before"
run_status 2
assert_contains "$test_root/output" 'TARGET: .claude/CLAUDE.md changed'
if grep -q 'unrelated\|do-not-read' "$test_root/output"; then exit 1; fi
snapshot > "$test_root/after"
cmp "$test_root/before" "$test_root/after"

printf '\nSYNTHETIC_TEST_SECRET\n' >> "$dst/.claude/CLAUDE.md"
run_status 67
assert_contains "$test_root/output" 'BLOCKED_SECRET:'
if grep -q 'SOURCE:\|TARGET:' "$test_root/output"; then exit 1; fi
cm apply --force

printf '\nSYNTHETIC_TEST_SECRET\n' >> "$src/.chezmoitemplates/ai/adapters/codex.md"
isolated git -C "$src" add .chezmoitemplates/ai/adapters/codex.md
cp "$repo/examples/chezmoi/.chezmoitemplates/ai/adapters/codex.md" "$src/.chezmoitemplates/ai/adapters/codex.md"
run_status 67
assert_contains "$test_root/output" 'BLOCKED_SECRET:'
isolated git -C "$src" add .chezmoitemplates/ai/adapters/codex.md

printf '\nSYNTHETIC_TEST_SECRET\n' >> "$src/.chezmoitemplates/ai/adapters/claude.md"
run_status 67
assert_contains "$test_root/output" 'BLOCKED_SECRET:'
cp "$repo/examples/chezmoi/.chezmoitemplates/ai/adapters/claude.md" "$src/.chezmoitemplates/ai/adapters/claude.md"

cp "$scanner" "$test_root/scanner-save"
printf '#!/bin/sh\nexit 20\n' > "$scanner"
run_status 70
assert_contains "$test_root/output" 'SCANNER_ERROR:'
chmod -x "$scanner"
run_status 69
cp "$test_root/scanner-save" "$scanner"
chmod +x "$scanner"

# Unknown source scripts/config must never run or be rendered.
printf '#!/bin/sh\nexit 99\n' > "$src/run_before_bad.sh"
printf '{{ output "sh" "-c" "exit 99" }}\n' > "$src/dot_unrelated.tmpl"
printf 'not valid config\n' > "$src/.chezmoi.toml.tmpl"
run_status 0

printf '{{ output "sh" "-c" "exit 99" }}\n' > "$src/dot_codex/AGENTS.md.tmpl"
run_status 65
assert_contains "$test_root/output" 'UNSUPPORTED_TEMPLATE:'
cp "$repo/examples/chezmoi/dot_codex/AGENTS.md.tmpl" "$src/dot_codex/AGENTS.md.tmpl"

printf '\n{{ output "sh" "-c" "exit 99" }}\n' >> "$src/.chezmoitemplates/ai/shared/instructions.md"
run_status 65
assert_contains "$test_root/output" 'delimiter in shared text'
cp "$repo/examples/chezmoi/.chezmoitemplates/ai/shared/instructions.md" "$src/.chezmoitemplates/ai/shared/instructions.md"

chmod -x "$dst/.config/ai-agent/bin/sync.sh"
run_status 2
assert_contains "$test_root/output" 'sync.sh mode'
chmod +x "$dst/.config/ai-agent/bin/sync.sh"
mv "$dst/.agents/skills/dotfiles-sync/SKILL.md" "$test_root/saved-skill"
run_status 2
assert_contains "$test_root/output" 'SKILL.md missing'
mv "$test_root/saved-skill" "$dst/.agents/skills/dotfiles-sync/SKILL.md"

# Unmerged index entries must block without resetting the user's index.
blob=$(isolated git -C "$src" hash-object "$src/.chezmoitemplates/ai/adapters/claude.md")
isolated git -C "$src" update-index --force-remove .chezmoitemplates/ai/adapters/claude.md
printf '100644 %s 1\t.chezmoitemplates/ai/adapters/claude.md\n100644 %s 2\t.chezmoitemplates/ai/adapters/claude.md\n' "$blob" "$blob" \
  | isolated git -C "$src" update-index --index-info
snapshot > "$test_root/before"
run_status 66
assert_contains "$test_root/output" 'BLOCKED_CONFLICT:'
snapshot > "$test_root/after"
cmp "$test_root/before" "$test_root/after"
isolated git -C "$src" add .chezmoitemplates/ai/adapters/claude.md

rc=0
isolated env CODEX_HOME="$test_root/custom-codex" sh "$engine" status \
  --source "$src" --destination "$dst" --scanner "$scanner" > "$test_root/output" 2>&1 || rc=$?
[ "$rc" = 65 ]; assert_contains "$test_root/output" 'UNSUPPORTED_HOME:'

mv "$dst/.claude/CLAUDE.md" "$test_root/saved-instructions"
ln -s "$test_root/saved-instructions" "$dst/.claude/CLAUDE.md"
run_status 65
assert_contains "$test_root/output" 'target symlink'
rm "$dst/.claude/CLAUDE.md"
mv "$test_root/saved-instructions" "$dst/.claude/CLAUDE.md"
printf 'override\n' > "$dst/.codex/AGENTS.override.md"
run_status 65
assert_contains "$test_root/output" 'BLOCKED_OVERRIDE:'

for cmd in in push plan; do
  rc=0
  isolated sh "$engine" "$cmd" > "$test_root/output" 2>&1 || rc=$?
  [ "$rc" = 64 ]; assert_contains "$test_root/output" 'UNSUPPORTED:'
done
echo 'PASS: read-only status, scoped files, drift, staged secret, scanner failures, unsafe templates, symlinks, overrides, unsupported writes'

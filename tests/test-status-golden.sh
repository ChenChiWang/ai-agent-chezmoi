#!/bin/sh
# status 的 golden 特性測試（#35）：對一組情境執行 status，把完整輸出與 exit code 和
# tests/golden/status/<情境>.txt 逐字比對。移植到 Python 時用這些檔案證明輸出不變。
#   sh tests/test-status-golden.sh            比對
#   sh tests/test-status-golden.sh --record   重新產生 golden 檔；只在輸出有意改變時使用，並在 PR 說明
. "$(dirname "$0")/helpers.sh"
record=0
[ "${1:-}" != --record ] || record=1
golden_dir="$repo/tests/golden/status"
mkdir -p "$golden_dir"
shared=.chezmoitemplates/ai/shared/instructions.md
failed=0

commit() {
  isolated env GIT_AUTHOR_NAME=Fixture GIT_AUTHOR_EMAIL=fixture@example.test \
    GIT_COMMITTER_NAME=Fixture GIT_COMMITTER_EMAIL=fixture@example.test \
    git -C "$src" commit -q -m "$1"
}

# 每個情境都從同一個基準開始：範本加夾具 skill、一個 commit、chezmoi 已部署
reset() {
  rm -rf "$src" "$dst" "$test_root/state.boltdb"
  mkdir -p "$src" "$dst"
  cp -R "$repo/examples/chezmoi/." "$src/"
  cp -R "$repo/tests/fixtures/skills/." "$src/"
  isolated git -C "$src" init -q -b main
  isolated git -C "$src" add .
  commit baseline
  cm apply --force
}

# golden_case 名稱 預期exit [status 的參數...]；額外的環境變數經 case_env 傳入
case_env=
golden_case() {
  name=$1
  expected=$2
  shift 2
  rc=0
  # shellcheck disable=SC2086
  isolated env $case_env sh "$engine" status "$@" > "$test_root/raw" 2>&1 || rc=$?
  { sed "s#$test_root#<root>#g" "$test_root/raw"; printf 'exit: %s\n' "$rc"; } > "$test_root/actual"
  if [ "$rc" != "$expected" ]; then
    cat "$test_root/actual"
    echo "FAIL: $name exited $rc, expected $expected"
    exit 1
  fi
  if grep -q 'untrusted scanner\|SYNTHETIC_TEST_SECRET' "$test_root/actual"; then
    echo "FAIL: $name leaked scanner output"
    exit 1
  fi
  if [ "$record" = 1 ]; then
    cp "$test_root/actual" "$golden_dir/$name.txt"
  elif ! diff -u "$golden_dir/$name.txt" "$test_root/actual"; then
    echo "FAIL: $name differs from tests/golden/status/$name.txt"
    failed=1
  fi
}
std() { golden_case "$1" "$2" --source "$src" --destination "$dst" --scanner "$scanner"; }

# ---- 基準與 profile ----
reset
rm -rf "$src/.git"
isolated git -C "$src" init -q -b main
isolated git -C "$src" add .
std unborn-index-only 0
reset
std clean 0
golden_case profile-claude 0 --source "$src" --destination "$dst" --scanner "$scanner" \
  --profile claude --repository-profile claude-codex
golden_case profile-codex 0 --source "$src" --destination "$dst" --scanner "$scanner" \
  --profile codex --repository-profile claude-codex

# ---- source 的變更 ----
printf '\nShared working change\n' >> "$src/$shared"
std working-change 2
isolated git -C "$src" add "$shared"
std staged-change 2
reset
printf '\nSYNTHETIC_TEST_SECRET\n' >> "$src/.chezmoitemplates/ai/adapters/claude.md"
std working-secret 67
isolated git -C "$src" add .chezmoitemplates/ai/adapters/claude.md
cp "$repo/examples/chezmoi/.chezmoitemplates/ai/adapters/claude.md" "$src/.chezmoitemplates/ai/adapters/claude.md"
std index-secret 67
reset
printf '{{ output "sh" "-c" "exit 99" }}\n' > "$src/dot_codex/AGENTS.md.tmpl"
std unsupported-wrapper 65
reset
printf '\n{{ output "sh" "-c" "exit 99" }}\n' >> "$src/$shared"
std shared-text-delimiter 65

# ---- 部署檔的變更 ----
reset
printf '\nA local edit\n' >> "$dst/.claude/CLAUDE.md"
std target-edited 2
printf '\nSYNTHETIC_TEST_SECRET\n' >> "$dst/.claude/CLAUDE.md"
std target-secret 67
reset
chmod -x "$dst/.config/ai-agent/bin/sync.sh"
std target-not-executable 2
reset
chmod g+w "$dst/.claude/CLAUDE.md"
chmod o+w "$dst/.config/ai-agent/bin/sync-write.py"
std target-group-other-writable 2
reset
rm "$dst/.agents/skills/sample-alpha/SKILL.md"
std target-missing 2

# ---- skill 集合 ----
reset
for base in .chezmoitemplates/ai/shared/skills dot_claude/skills dot_agents/skills; do
  rm -rf "$src/$base/sample-beta"
done
std skill-removed-orphan 2
reset
mkdir -p "$src/.chezmoitemplates/ai/shared/skills/sample-new" "$src/dot_claude/skills/sample-new" "$src/dot_agents/skills/sample-new"
printf -- '---\nname: sample-new\ndescription: Fixture skill.\n---\n\nFixture body.\n' > "$src/.chezmoitemplates/ai/shared/skills/sample-new/SKILL.md"
for home in dot_claude dot_agents; do
  printf '{{ template "ai/shared/skills/sample-new/SKILL.md" . -}}\n' > "$src/$home/skills/sample-new/SKILL.md.tmpl"
done
std skill-added 2

# ---- scanner 與 Git 狀態 ----
reset
cp "$scanner" "$test_root/scanner-save"
printf '#!/bin/sh\nexit 20\n' > "$scanner"
std scanner-failure 70
chmod -x "$scanner"
std scanner-not-executable 69
cp "$test_root/scanner-save" "$scanner"
chmod +x "$scanner"
blob=$(isolated git -C "$src" hash-object "$src/.chezmoitemplates/ai/adapters/claude.md")
isolated git -C "$src" update-index --force-remove .chezmoitemplates/ai/adapters/claude.md
printf '100644 %s 1\t.chezmoitemplates/ai/adapters/claude.md\n100644 %s 2\t.chezmoitemplates/ai/adapters/claude.md\n' "$blob" "$blob" \
  | isolated git -C "$src" update-index --index-info
std index-conflict 66

# ---- 環境、symlink 與 override ----
reset
case_env="CODEX_HOME=$test_root/custom-codex"
std custom-codex-home 65
case_env=
mv "$dst/.claude/CLAUDE.md" "$test_root/saved-instructions"
ln -s "$test_root/saved-instructions" "$dst/.claude/CLAUDE.md"
std target-symlink 65
rm "$dst/.claude/CLAUDE.md"
mv "$test_root/saved-instructions" "$dst/.claude/CLAUDE.md"
printf 'override\n' > "$dst/.codex/AGENTS.override.md"
std codex-override 65
rm "$dst/.codex/AGENTS.override.md"

# ---- 參數檔與用法 ----
config="$test_root/sync.local.json"
isolated python3 - "$config" "$src" "$dst" "$scanner" "$test_root/plans" <<'PY'
import json, sys
path, source, destination, scanner, plans = sys.argv[1:]
with open(path, 'w') as f:
    json.dump(dict(source=source, destination=destination, profile='claude-codex', scanner=scanner,
                   remote='ssh://git@example.invalid/fixture.git', branch='main', plan_dir=plans,
                   writer='claude', auto_in=False), f)
PY
chmod 600 "$config"
golden_case config-valid 0 --config "$config"
golden_case config-with-agent 0 --config "$config" --agent claude
chmod 664 "$config"
golden_case config-loose-mode 78 --config "$config"
golden_case config-relative-path 64 --config sync.local.json
golden_case usage-no-arguments 64
golden_case usage-relative-path 64 --source relative --destination "$dst" --scanner "$scanner"
golden_case usage-invalid-profile 64 --source "$src" --destination "$dst" --scanner "$scanner" --profile other
golden_case usage-unknown-option 64 --source "$src" --bogus value

[ "$failed" = 0 ] || exit 1
if [ "$record" = 1 ]; then
  echo "RECORDED: $(ls "$golden_dir" | wc -l | tr -d ' ') golden files under tests/golden/status"
else
  echo 'PASS: status golden output for every recorded case'
fi

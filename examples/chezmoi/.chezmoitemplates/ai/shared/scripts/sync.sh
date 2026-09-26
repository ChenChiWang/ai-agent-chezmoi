#!/bin/sh
# v2: offline status; approved write operations use the sibling helper.
set -eu
umask 077

fail() { printf '%s\n' "$2"; exit "$1"; }
case "${1:-}" in
  status) shift ;;
  migration)
    shift
    engine_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
    exec python3 "$engine_dir/sync-migrate.py" "$@" ;;
  plan|in|push)
    command -v python3 >/dev/null 2>&1 || fail 69 'MISSING_DEPENDENCY: Python required'
    engine_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
    exec python3 "$engine_dir/sync-write.py" "$@" ;;
  *) fail 64 'USAGE: sync.sh status --source ABS_PATH --destination ABS_PATH [--scanner ABS_EXECUTABLE]' ;;
esac
src= dst= scanner= profile=claude-codex repository_profile=
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || fail 64 'USAGE: missing option value'
  case "$1" in
    --source) [ -z "$src" ] || fail 64 'USAGE: duplicate source'; src=$2 ;;
    --destination) [ -z "$dst" ] || fail 64 'USAGE: duplicate destination'; dst=$2 ;;
    --profile) profile=$2 ;;
    --repository-profile) repository_profile=$2 ;;
    --scanner) [ -z "$scanner" ] || fail 64 'USAGE: duplicate scanner'; scanner=$2 ;;
    *) fail 64 'USAGE: unknown option' ;;
  esac
  shift 2
done
engine_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
formatter="$engine_dir/scan-secrets.py"
[ -n "$scanner" ] || scanner=$formatter
for p in "$src" "$dst" "$scanner"; do
  case "$p" in /*) ;; *) fail 64 'USAGE: explicit absolute paths required' ;; esac
done
for dep in git chezmoi mktemp cmp cp mkdir env grep cat rm python3; do
  command -v "$dep" >/dev/null 2>&1 || fail 69 'MISSING_DEPENDENCY: required command unavailable'
done
[ -f "$scanner" ] && [ -x "$scanner" ] || fail 69 'MISSING_DEPENDENCY: reviewed scanner adapter required'
[ -f "$formatter" ] && [ -f "$engine_dir/gitleaks-rules.json" ] || fail 69 'MISSING_DEPENDENCY: scanner report validator required'

# Refuse symlink components, including dangling links. Do not read through them.
safe_path() {
  checked=$1
  while [ "$checked" != / ]; do
    [ ! -L "$checked" ] || return 1
    checked=${checked%/*}
    [ -n "$checked" ] || checked=/
  done
}
# macOS /tmp is a system symlink: canonicalize explicitly selected roots first.
[ -d "$src" ] && [ -d "$dst" ] || fail 65 'INVALID_SOURCE: source and destination must exist'
src=$(cd "$src" && pwd -P)
dst=$(cd "$dst" && pwd -P)
case "$profile" in claude|codex|claude-codex) ;; *) fail 64 'USAGE: invalid profile' ;; esac
[ -n "$repository_profile" ] || repository_profile=$profile
case "$profile:$repository_profile" in claude:claude|codex:codex|*:claude-codex) ;; *) fail 64 'USAGE: invalid repository profile' ;; esac
python3 "$formatter" --validate-layout "$src" "$dst" "$profile" "$repository_profile" 2>/dev/null || fail 65 'INVALID_LAYOUT: roots or managed paths'
[ -d "$src/.git" ] && [ ! -L "$src/.git" ] || fail 65 'INVALID_SOURCE: regular Git checkout required; worktrees unsupported'
if [ "$profile" != codex ]; then
  [ -z "${CLAUDE_CONFIG_DIR:-}" ] || [ "$CLAUDE_CONFIG_DIR" = "$dst/.claude" ] || fail 65 'UNSUPPORTED_HOME: custom CLAUDE_CONFIG_DIR'
fi
[ -z "${AI_AGENT_HOME:-}" ] || [ "$AI_AGENT_HOME" = "$dst/.config/ai-agent" ] || fail 65 'UNSUPPORTED_HOME: custom AI_AGENT_HOME'
if [ "$profile" != claude ]; then
  [ -z "${CODEX_HOME:-}" ] || [ "$CODEX_HOME" = "$dst/.codex" ] || fail 65 'UNSUPPORTED_HOME: custom CODEX_HOME'
  safe_path "$dst/.codex/AGENTS.override.md" || fail 65 'INVALID_SOURCE: symlink in override path'
  [ ! -e "$dst/.codex/AGENTS.override.md" ] || fail 65 'BLOCKED_OVERRIDE: review AGENTS.override.md before deployment'
fi

# All temporary state is private and outside the selected roots. Child tools get
# a minimal environment: no SSH, global Git config, chezmoi config or agent home.
work=$(mktemp -d /tmp/ai-agent-status.XXXXXXXX) || fail 70 'IO_ERROR: temporary directory'
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
mkdir -p "$work/home" "$work/source" "$work/render" "$work/scan" "$work/cache"
: > "$work/config.toml"
: > "$work/report"
tool_path=$PATH
git_read() {
  env -i PATH="$tool_path" HOME="$work/home" LC_ALL=C \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_OPTIONAL_LOCKS=0 \
    GIT_NO_REPLACE_OBJECTS=1 GIT_TERMINAL_PROMPT=0 \
    GIT_NO_LAZY_FETCH=1 GIT_ALLOW_PROTOCOL= GIT_PROTOCOL_FROM_USER=0 \
    git -c core.fsmonitor=false -c core.hooksPath=/dev/null -C "$src" --no-lazy-fetch "$@" 2>/dev/null
}
# Fail closed on Git versions without this flag, before reading any objects.
# The flag + environment prohibit lazy fetch; the empty protocol allowlist also
# denies transports even if source-local protocol settings explicitly allow them.
git_read --version >/dev/null || fail 69 'MISSING_DEPENDENCY: Git with --no-lazy-fetch support required'
[ "$(git_read rev-parse --show-toplevel)" = "$src" ] || fail 65 'INVALID_SOURCE: source must be Git root'
head=$(git_read rev-parse --verify HEAD 2>/dev/null) || {
  branch_ref=$(git_read symbolic-ref HEAD) || fail 70 'GIT_ERROR: invalid HEAD'
  ref_rc=0
  git_read show-ref --verify --quiet "$branch_ref" || ref_rc=$?
  [ "$ref_rc" = 1 ] || fail 70 'GIT_ERROR: unreadable HEAD'
  head=
}

# Closed schema: wrappers name fixed templates; shared text permits only a literal opener escape.
# This prevents status from executing source-provided templates, hooks or externals.
wrappers() {
  env -i PATH="$tool_path" HOME="$work/home" LC_ALL=C python3 "$formatter" --wrapper "$1" 2>/dev/null || fail 65 'UNSUPPORTED_TEMPLATE'
}
files=$(env -i PATH="$tool_path" HOME="$work/home" LC_ALL=C python3 "$formatter" --schema "$repository_profile" source 2>/dev/null) || fail 65 'INVALID_PROFILE'
changed=0
for rel in $files; do
  safe_path "$src/$rel" || fail 65 "INVALID_SOURCE: symlink: $rel"
  [ -f "$src/$rel" ] && [ -r "$src/$rel" ] || fail 65 "INVALID_SOURCE: missing or unreadable: $rel"
  parent=${rel%/*}; [ "$parent" != "$rel" ] || parent=.
  mkdir -p "$work/source/$parent" "$work/scan/source/$parent"
  out="$work/source/$rel"; snap="$work/scan/source/$rel"
  cp "$src/$rel" "$out" || fail 70 "IO_ERROR: snapshot: $rel"
  cp "$out" "$snap"
  case "$rel" in *.tmpl)
    wrappers "$rel" > "$work/expected"
    cmp -s "$out" "$work/expected" || fail 65 "UNSUPPORTED_TEMPLATE: $rel" ;;
    .chezmoitemplates/*)
      env -i PATH="$tool_path" HOME="$work/home" LC_ALL=C python3 "$formatter" --validate-shared "$out" 2>/dev/null || fail 65 "UNSUPPORTED_TEMPLATE: delimiter in shared text: $rel" ;;
  esac

  # Read only blob metadata/content; never run diff drivers or clean filters.
  entry=$(git_read ls-files --stage -- "$rel") || fail 70 'GIT_ERROR: index read'
  index_oid= index_mode=
  if [ -n "$entry" ]; then
    set -- $entry
    [ "$#" = 4 ] && [ "$3" = 0 ] || fail 66 "BLOCKED_CONFLICT: $rel"
    index_mode=$1; index_oid=$2
    case "$index_mode" in 100644|100755) ;; *) fail 65 "INVALID_SOURCE: index type: $rel" ;; esac
    git_read cat-file blob "$index_oid" > "$work/index-blob" || fail 70 'GIT_ERROR: index blob'
    # Preserve each blob for scanning, without exposing arbitrary Git filenames.
    mkdir -p "$work/scan/index/$parent"
    cp "$work/index-blob" "$work/scan/index/$rel"
  fi
  base_oid= base_mode=
  if [ -n "$head" ]; then
    entry=$(git_read ls-tree "$head" -- "$rel") || fail 70 'GIT_ERROR: HEAD tree'
    if [ -n "$entry" ]; then
      set -- $entry
      [ "$#" = 4 ] && [ "$2" = blob ] || fail 65 "INVALID_SOURCE: HEAD type: $rel"
      base_mode=$1; base_oid=$3
      case "$base_mode" in 100644|100755) ;; *) fail 65 "INVALID_SOURCE: HEAD mode: $rel" ;; esac
      mkdir -p "$work/scan/head/$parent"
      blob="$work/scan/head/$rel"
      git_read cat-file blob "$base_oid" > "$blob" || fail 70 'GIT_ERROR: HEAD blob'
    fi
  fi
  oid=$(git_read hash-object --no-filters "$out") || fail 70 'GIT_ERROR: hash'
  mode=100644; [ ! -x "$src/$rel" ] || mode=100755
  staged=clean; local_state=clean
  [ "$base_oid:$base_mode" = "$index_oid:$index_mode" ] || staged=changed
  [ "$oid:$mode" = "$index_oid:$index_mode" ] || local_state=changed
  if [ "$staged:$local_state" != clean:clean ]; then
    changed=1
    printf 'SOURCE: %s staged=%s working=%s\n' "$rel" "$staged" "$local_state" >> "$work/report"
  fi
done
# Metadata is scanned and reported but not interpreted during isolated render.
for rel in .chezmoiignore .gitignore .gitattributes; do rm -f "$work/source/$rel"; done

drift=0
targets=$(env -i PATH="$tool_path" HOME="$work/home" LC_ALL=C python3 "$formatter" --schema "$profile" target 2>/dev/null) || fail 65 'INVALID_PROFILE'
for rel in $targets; do
  safe_path "$dst/$rel" || fail 65 "INVALID_SOURCE: target symlink: $rel"
  env -i PATH="$tool_path" HOME="$work/home" LC_ALL=C \
    XDG_CONFIG_HOME="$work/home/config" XDG_CACHE_HOME="$work/cache" XDG_DATA_HOME="$work/home/data" \
    chezmoi --config "$work/config.toml" --source "$work/source" \
    --destination "$work/render" --cache "$work/cache" --persistent-state "$work/state.boltdb" \
    --refresh-externals=never --no-tty cat "$work/render/$rel" \
    > "$work/rendered" 2>/dev/null || fail 70 "RENDER_ERROR: $rel"
  mkdir -p "$work/scan/render/${rel%/*}" "$work/scan/target/${rel%/*}"
  cp "$work/rendered" "$work/scan/render/$rel"
  state=missing
  if [ -e "$dst/$rel" ]; then
    [ -f "$dst/$rel" ] && [ -r "$dst/$rel" ] || fail 65 "INVALID_SOURCE: target type or access: $rel"
    cp "$dst/$rel" "$work/scan/target/$rel" || fail 70 "IO_ERROR: target snapshot: $rel"
    state=changed
    if cmp -s "$work/rendered" "$work/scan/target/$rel"; then state=clean; fi
    case "$rel" in .config/ai-agent/bin/sync.sh|.config/ai-agent/bin/scan-secrets.py|.config/ai-agent/bin/sync-write.py|.config/ai-agent/bin/sync-migrate.py|.claude/skills/dotfiles-sync/sync.sh)
      [ -x "$dst/$rel" ] || state=mode ;;
    esac
  fi
  if [ "$state" != clean ]; then
    drift=1; printf 'TARGET: %s %s\n' "$rel" "$state" >> "$work/report"
  fi
done

# The adapter is trusted executable code, not a sandbox. It must be offline,
# read-only, and reviewed. Never forward its stdout/stderr, even on failure.
scan_rc=0
env -i PATH="$tool_path" HOME="$work/home" LC_ALL=C \
  "$scanner" "$work/scan" "$work/scanner-report.json" >/dev/null 2>&1 || scan_rc=$?
env -i PATH="$tool_path" HOME="$work/home" LC_ALL=C \
  python3 "$formatter" --display-report "$work/scanner-report.json" "$scan_rc" \
  > "$work/findings" 2>/dev/null || fail 70 'SCANNER_ERROR: invalid or missing structured report'
case "$scan_rc" in
  0) ;;
  10) cat "$work/findings"; fail 67 'BLOCKED_SECRET: scoped snapshot; values withheld' ;;
  69) fail 69 'MISSING_DEPENDENCY: pinned Gitleaks required on PATH' ;;
  *) fail 70 'SCANNER_ERROR: scan failed; no clean result' ;;
esac
cat "$work/report"
if [ "$drift" = 1 ]; then fail 2 'DRIFT: generated files differ; no changes applied'; fi
if [ "$changed" = 1 ]; then fail 0 'OK: source changes within v2 scope; not push approval'; fi
fail 0 'NO_CHANGES: v2 scope only; history and unrelated files not assessed'

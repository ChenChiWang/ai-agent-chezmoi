#!/bin/sh
# v2 薄殼：每個命令都交給 Python 引擎。status 的輸出合約由 tests/golden/status 把關（#35）。
set -eu
umask 077

fail() { printf '%s\n' "$2"; exit "$1"; }
case "${1:-}" in
  migration)
    shift
    engine_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
    exec python3 "$engine_dir/sync-migrate.py" "$@" ;;
  status|plan|in|push|check|doctor)
    command -v python3 >/dev/null 2>&1 || fail 69 'MISSING_DEPENDENCY: Python required'
    engine_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
    exec python3 "$engine_dir/sync-write.py" "$@" ;;
  *) fail 64 'USAGE: sync.sh status [--config ABS_JSON] --source ABS_PATH --destination ABS_PATH [--profile P] [--scanner ABS_EXECUTABLE]' ;;
esac

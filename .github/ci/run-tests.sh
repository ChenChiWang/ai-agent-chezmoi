#!/bin/sh
# CI 用：依序執行 README「Tests」列出的測試。session-acceptance 會呼叫真實模型、有費用，不在 CI 執行。
set -eu
cd "$(dirname "$0")/../.."
for test in "sh tests/test-render.sh" "sh tests/test-status.sh" "sh tests/test-preflight.sh" \
            "python3 tests/test-write.py" "python3 tests/test-layout.py" \
            "python3 tests/test-migration.py" "python3 tests/test-offline-status.py" \
            "python3 tests/test-scanner.py"; do
  echo "::group::$test"
  $test
  echo "::endgroup::"
done

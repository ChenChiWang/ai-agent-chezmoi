#!/bin/sh
# OS prerequisite checkpoint; never trigger an installer or accept a license.
set -eu
if [ "$(uname -s)" != Darwin ]; then
    echo 'MACOS_REQUIRED' >&2
    exit 69
fi
if ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
    echo 'APPLE_CLT_REQUIRED: install Apple Command Line Tools using the OS flow, then rerun. Authentication is separate.' >&2
    exit 69
fi
if ! /usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3,9))' >/dev/null 2>&1; then
    echo 'PYTHON_3_9_REQUIRED' >&2
    exit 69
fi
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec /usr/bin/python3 -B "$script_dir/tools.py" "$@"

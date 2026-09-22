#!/bin/sh
# Compatibility entrypoint. Explicit v2 arguments and approvals are required.
set -eu
engine="${AI_AGENT_HOME:-$HOME/.config/ai-agent}/bin/sync.sh"
[ -f "$engine" ] || { echo 'MISSING_DEPENDENCY: neutral v2 engine'; exit 69; }
exec sh "$engine" "$@"

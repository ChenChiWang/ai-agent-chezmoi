#!/bin/sh
# CI 用：把引擎要求的 chezmoi 與 Gitleaks 裝到 ~/.local/bin，並確認 git、python3 符合需求。
# 不用 sudo；兩個安裝都會核對官方 SHA-256。
set -eu
CHEZMOI_VERSION=v2.71.1
repo=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd -P)
bindir=$HOME/.local/bin
mkdir -p "$bindir"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

curl -fsSL --proto '=https' --max-time 120 -o "$tmp/install-chezmoi.sh" https://get.chezmoi.io
sh "$tmp/install-chezmoi.sh" -b "$bindir" -t "$CHEZMOI_VERSION"
sh "$repo/setup/install-gitleaks.sh"

PATH="$bindir:$PATH"
git --no-lazy-fetch --version >/dev/null 2>&1 || { echo "FAIL git $(git --version) lacks --no-lazy-fetch (need 2.45+)"; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo "FAIL python3 older than 3.9"; exit 1; }
echo "git:      $(command -v git) $(git --version)"
echo "python3:  $(command -v python3) $(python3 --version)"
echo "chezmoi:  $(chezmoi --version)"
echo "gitleaks: $(gitleaks version)"

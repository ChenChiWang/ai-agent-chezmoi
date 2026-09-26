#!/bin/sh
# 安裝引擎要求的固定版本 Gitleaks 到使用者目錄（預設 ~/.local/bin），不用 sudo、不碰系統目錄。
# 下載後以官方 release 的 SHA-256 核對，再確認二進位回報的版本，最後原子性放到目的地。
set -eu
VERSION=8.30.1
prefix=${GITLEAKS_PREFIX:-$HOME/.local/bin}
force=0; [ "${1:-}" = --force ] && force=1
fail() { printf 'FAIL %s\n' "$1" >&2; exit "${2:-1}"; }
case "$(uname -s)/$(uname -m)" in
  Darwin/arm64)  asset=darwin_arm64; sum=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
  Darwin/x86_64) asset=darwin_x64;   sum=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
  Linux/x86_64)  asset=linux_x64;    sum=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
  Linux/aarch64|Linux/arm64) asset=linux_arm64; sum=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
  *) fail "unsupported platform $(uname -s)/$(uname -m); install gitleaks $VERSION manually" 69 ;;
esac
if [ -x "$prefix/gitleaks" ]; then
  current=$("$prefix/gitleaks" version 2>/dev/null || true)
  if [ "$current" = "$VERSION" ]; then echo "OK gitleaks $VERSION already installed at $prefix/gitleaks"; exit 0; fi
  [ "$force" = 1 ] || fail "$prefix/gitleaks exists with version '${current:-unknown}'; rerun with --force to replace it" 73
fi
command -v curl >/dev/null || fail 'curl required' 69
command -v tar >/dev/null || fail 'tar required' 69
if command -v shasum >/dev/null; then digest() { shasum -a 256 "$1" | cut -d' ' -f1; }
elif command -v sha256sum >/dev/null; then digest() { sha256sum "$1" | cut -d' ' -f1; }
else fail 'shasum or sha256sum required' 69; fi
tmp=$(mktemp -d "${TMPDIR:-/tmp}/gitleaks-install.XXXXXXXX"); trap 'rm -rf "$tmp"' EXIT
url="https://github.com/gitleaks/gitleaks/releases/download/v$VERSION/gitleaks_${VERSION}_$asset.tar.gz"
curl -fsSL --proto '=https' --max-time 120 -o "$tmp/archive.tgz" "$url" || fail "download failed: $url" 71
actual=$(digest "$tmp/archive.tgz")
[ "$actual" = "$sum" ] || fail "checksum mismatch for $asset: expected $sum got $actual; archive discarded" 65
tar -xzf "$tmp/archive.tgz" -C "$tmp" gitleaks || fail 'archive does not contain the gitleaks binary' 65
chmod 755 "$tmp/gitleaks"
reported=$("$tmp/gitleaks" version 2>/dev/null || true)
[ "$reported" = "$VERSION" ] || fail "downloaded binary reports '${reported:-nothing}', expected $VERSION" 65
mkdir -p "$prefix"
mv -f "$tmp/gitleaks" "$prefix/gitleaks"
echo "INSTALLED gitleaks $VERSION at $prefix/gitleaks (sha256 verified)"
case ":$PATH:" in *":$prefix:"*) ;; *) echo "NOTE add $prefix to PATH (e.g. export PATH=\"$prefix:\$PATH\" in your shell rc)" ;; esac

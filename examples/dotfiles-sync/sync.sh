#!/bin/sh
# dotfiles-sync skill 引擎 - 同步 ~/.claude 設定(chezmoi + git)。
# 由 Claude 依 SKILL.md 呼叫,子命令:
#   in            開場:git pull 並套用最新設定到 ~/.claude
#   status        把本機變更抓回 source、顯示 diff 與 secret 掃描(不 commit)
#   push [訊息]   commit 並 push(由 Claude 在使用者確認 diff 後才呼叫)
#
# 設計:跨平台(Windows 走 Git Bash);任何非預期錯誤都不阻斷,回報後結束。
set -u

# --- 確保找得到 chezmoi(繼承的 PATH 可能不完整)---
if ! command -v chezmoi >/dev/null 2>&1; then
  for d in "$HOME/.local/bin" "$HOME/bin" \
           "$HOME/AppData/Local/Microsoft/WinGet/Links" \
           "$HOME/AppData/Local/Microsoft/WinGet/Packages/twpayne.chezmoi_Microsoft.Winget.Source_8wekyb3d8bbwe"; do
    if [ -x "$d/chezmoi" ] || [ -x "$d/chezmoi.exe" ]; then
      PATH="$d:$PATH"; export PATH
    fi
  done
fi
command -v chezmoi >/dev/null 2>&1 || { echo "[sync] 找不到 chezmoi,略過"; exit 0; }

SRC=$(chezmoi source-path 2>/dev/null) || { echo "[sync] 取不到 chezmoi source-path"; exit 0; }

# 高信號 secret 掃描(只抓真實金鑰格式,避免 CLAUDE.md 裡的 "token/password" 等字詞誤判)
scan_secret() {
  grep -rIlE --exclude-dir=.git \
    -e 'ghp_[A-Za-z0-9]{20,}' \
    -e 'github_pat_[A-Za-z0-9_]{20,}' \
    -e 'gho_[A-Za-z0-9]{20,}' \
    -e 'sk-[A-Za-z0-9]{20,}' \
    -e 'xox[baprs]-[A-Za-z0-9-]{10,}' \
    -e 'AKIA[0-9A-Z]{16}' \
    -e '-----BEGIN [A-Z ]*PRIVATE KEY-----' \
    "$SRC" 2>/dev/null
}

case "${1:-}" in
  in)
    chezmoi update >/dev/null 2>&1 \
      && echo "[sync] 已拉取並套用最新 ~/.claude 設定" \
      || echo "[sync] chezmoi update 失敗(可能離線或有衝突),略過"
    ;;

  status)
    chezmoi re-add >/dev/null 2>&1 || true
    git -C "$SRC" add -A 2>/dev/null || true
    if git -C "$SRC" diff --cached --quiet 2>/dev/null; then
      echo "NO_CHANGES:沒有待同步的變更"
      exit 0
    fi
    echo "===== 變更檔案 ====="
    git -C "$SRC" diff --cached --stat
    echo ""
    echo "===== diff ====="
    git -C "$SRC" --no-pager diff --cached
    hits=$(scan_secret)
    if [ -n "$hits" ]; then
      echo ""
      echo "SECRET_WARNING:⚠️ 下列檔案疑似含 secret,請人工確認後再決定是否 push:"
      echo "$hits"
    fi
    ;;

  push)
    msg=${2:-"chore: sync Claude Code config"}
    git -C "$SRC" add -A 2>/dev/null || true
    if git -C "$SRC" diff --cached --quiet 2>/dev/null; then
      echo "NO_CHANGES:沒有待 commit 的變更"
      exit 0
    fi
    git -C "$SRC" commit -m "$msg" || { echo "[sync] commit 失敗"; exit 0; }
    git -C "$SRC" push && echo "[sync] 已推送到遠端" || echo "[sync] push 失敗(請檢查網路/認證)"
    ;;

  *)
    echo "用法:$0 in|status|push [訊息]"
    ;;
esac

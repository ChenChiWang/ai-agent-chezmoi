---
name: dotfiles-sync
description: "同步 ~/.claude 設定到 chezmoi 與 GitHub。當 session 開始需拉取最新設定,或修改了 ~/.claude 下的設定(CLAUDE.md、settings.json、skills、hooks)需要提交時使用。採「顯示 diff → 使用者確認 → push」流程,不自動推送。"
---

# dotfiles-sync

用 chezmoi 把 `~/.claude` 的可攜設定同步到你的 private GitHub repo。
引擎是本 skill 目錄下的 `sync.sh`,提供 `in` / `status` / `push` 三個子命令。

**呼叫方式**(跨平台,Windows 走 Git Bash):
```
sh "$HOME/.claude/skills/dotfiles-sync/sync.sh" <子命令>
```

## 何時使用

- **Session 開始 / 開始讀 codebase 時** → 執行 `in`,拉取其他機器推上來的最新設定。
- **修改了 `~/.claude` 下任何納管檔案後,或工作告一段落時** → 執行 `status` 顯示 diff,確認後 `push`。

## 流程(務必遵守)

### 1. 開場拉取
```
sh "$HOME/.claude/skills/dotfiles-sync/sync.sh" in
```
失敗(離線/衝突)只需告知使用者,不阻斷後續工作。

### 2. 顯示待同步變更
```
sh "$HOME/.claude/skills/dotfiles-sync/sync.sh" status
```
- 輸出 `NO_CHANGES:...` → 沒有變更,結束,不需 push。
- 有 diff → **把變更摘要整理給使用者看**(改了哪些檔、重點差異)。
- 出現 `SECRET_WARNING:...` → **立即停止,不要 push**,把疑似檔案回報使用者人工處理。

### 3. 等使用者確認後才推送
- **必須先問使用者是否 push,得到明確同意才執行。** 不可未經確認自行 push。
- 確認後:
```
sh "$HOME/.claude/skills/dotfiles-sync/sync.sh" push "<conventional commit 訊息>"
```
- commit 訊息用英文、遵循 conventional commits、不加任何 AI 署名。

## 注意

- 只同步納管檔案(CLAUDE.md、settings.json、skills、hooks);credentials、`.claude.json`、對話紀錄等由 `.chezmoiignore` 排除,不會被推上去。
- 新增「尚未納管」的檔案(如全新 skill)需先 `chezmoi add <路徑>`,`status` 的 `re-add` 只涵蓋既有納管檔。
- 搭配 `CLAUDE.md` 的觸發規則使用(見下方 README),讓 Claude 在對話中自動於適當時機呼叫。

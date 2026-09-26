[English](./README.md) | **繁體中文**

# Claude Code 設定跨平台同步(chezmoi)

用 [chezmoi](https://www.chezmoi.io/) 把 `~/.claude/` 的**可攜設定**跨 **Windows / macOS / Linux** 同步的完整指南與範本。

設計目標是只同步可攜的設定與能力。Ignore 是多層防護之一，不能保證 secret 永不進 Git，也不會清除已追蹤內容。

## 實驗性 Claude Code + Codex 共用範本（v2）

[`examples/chezmoi/`](./examples/chezmoi/) 使用單一 shared source 產生兩邊 instructions、skills 與中立引擎。
v2 已支援 **離線 `status`、核准計畫、安全 `in` 與限定範圍的 `push`**。
私人 migration 與 legacy 入口切換維持暫停；請先閱讀
[同步契約、核准與復原指南](./docs/sync-v2.md)。
必須指定 source、destination；預設使用內附 scanner adapter，需要 PATH 上的 **Gitleaks 8.30.1** 與 Python 3.9+。
掃描結果只顯示已驗證的路徑、規則 ID 與行號，詳見[scanner 契約與測試](./docs/secret-scanner.md)。

v2 現在有 `claude`／`codex`／`claude-codex` 三種 profile、機器本地參數檔 `sync.local.json`（`--config`）、
遠端新鮮度 `check`、指定 writer 的 agent 角色，以及只限共用文字的 `auto_in`。詳見
[同步契約](./docs/sync-v2.md)；已完成的遷移程序封存在 [`docs/history/`](./docs/history/migration-v2.md)。
不可對本公開 repo 執行 `chezmoi init --apply`，也不可整包覆蓋現有 agent 設定。
測試：`sh tests/test-render.sh`、`sh tests/test-status.sh`；正式 scanner 測試：`python3 tests/test-scanner.py`。
需要 Git、chezmoi、POSIX sh、Python 3.9+；正式 scanner 測試另需固定版本 Gitleaks。
Git 必須支援 `--no-lazy-fetch`；離線回歸測試：`python3 tests/test-offline-status.py`，以及寫入／歷史測試
`python3 tests/test-write.py`；migration fixture：`python3 tests/test-migration.py`。
Commit／push 僅在臨時本機 fixture 執行。

Phase 2.6 新增分階段 profile、完整六個 shared skills，以及保留 rollback 的離線 legacy
conversion；紀錄見 [docs/history](./docs/history/migration-readiness.md)。

### 設定注意事項（啟用 agent 主動同步前先讀）

第二台機器上線、端到端驗收與結果對照表見 [`docs/new-machine.md`](./docs/new-machine.md)。要讓 agent 代勞，
指給它 [`setup/AGENT-SETUP.md`](./setup/AGENT-SETUP.md)；它會用 `setup/preflight.sh`、`setup/install-gitleaks.sh`
與引擎的 `doctor`。

每台機器要有一份你自己寫的參數檔 `~/.config/ai-agent/sync.local.json`（agent 被要求絕不自行建立），
它不會被同步。欄位範例見英文 README。

- **`writer` 是唯一表達使用習慣的設定。** 填 `"claude"` 或 `"codex"`：只有那個 agent 套用與發布，另一個
  只把記憶寫進 source 並回報待發布。填 `["claude", "codex"]`：兩邊都可發布（一邊剛推完、另一邊的 plan 會
  過期重建）。填 `"any"` 或省略：不檢查角色。填 `"none"`：agent 一律不發布，由你不帶 `--agent` 自己跑 `push`。
  不確定就先用單一 writer。
- **`auto_in` 會不經詢問套用共用文字的 incoming 變更**（只限 instructions、skills、adapters；腳本、settings、
  metadata 仍要 `--approve`）。只有你是私有 repo 唯一推送者時才開：能推到那個 repo 的人，就能改所有機器上
  agent 的指令而不經審閱。
- **`plan_dir`** 必須在 source 之外，也不能在 `.claude`、`.codex`、`.agents`、`.config/ai-agent` 之下；建議
  `~/.local/state/ai-agent/plans`。引擎會自己建（0700），`check` 的每日快取也放這裡。
- **Remote 與 SSH。** 用 `ssh://` 或 `git@host:path`，不支援帶憑證的 HTTPS。引擎不讀 `~/.ssh/config`、不會
  提示：金鑰要在 ssh-agent 裡或是預設檔名（`~/.ssh/id_*`），host 要已在 `known_hosts`。
- **Codex 預設在 sandbox 內**，沒有網路也不能寫 HOME。在那裡 `check` 會回 `CHECK_SKIPPED`，寫記憶到 source
  需要核准一次工作區外的寫入。不要為了同步放寬 sandbox；讓 Claude 當 writer，或自己跑 `push`。
- **Plan 綁定 source 的 index。** `plan` 與 `in`／`push` 之間不要對 source 跑 `git status` 之類的命令，
  `--message` 也要相同，否則會 `BLOCKED_STALE_PLAN` 要重建。
- **權限提示。** 互動模式的 Claude Code 執行 `sync.sh` 前會先問，除非 `settings.json` 的 `permissions.allow`
  含 `Bash(sh ~/.config/ai-agent/bin/sync.sh:*)`；範例 settings 已包含這條。

Phase 2.7 支援 source 位於 destination HOME 下（例如 `$HOME/.local/share/chezmoi`），
並保留明確 managed paths 與部署區域隔離。詳見
[production layout 安全邊界](./docs/production-layout.md)。

以下章節描述 **legacy v1**：它的 `status` 會改 source/index、先輸出 diff 才掃描，`push` 不強制掃描。
舊引擎保留相容性，新增 v2 不代表已修復 v1 的安全缺口。


## 這是什麼

- 📄 [`chezmoi-claude-setup.md`](./chezmoi-claude-setup.md) — **完整設定指南**,可直接交給 Claude Code 逐步執行(內含安全規則、跨平台防護、secret 掃描)
- 📁 [`examples/`](./examples/) — 可直接參考/複製的範本(排除規則、換行設定、CLAUDE.md、settings.json)

## 同步了哪些內容

| 項目 | 說明 |
|------|------|
| `~/.claude/CLAUDE.md` | 全域指示(語言、程式風格、git 規範) |
| `~/.claude/settings.json` | statusLine / TUI 等設定 |
| `~/.claude/skills/` | 自訂 skills |
| `~/.claude/commands/` `agents/` `hooks/` | 若有則一併納管 |

## 預計排除

- `~/.claude.json`、`~/.claude/.credentials.json`(含 MCP token、OAuth 憑證)
- `~/.claude/settings.local.json`（機器本地設定）
- `projects/`、`sessions/`、`shell-snapshots/`、`file-history/`、`history.jsonl`
- `cache/`、`plugins/` 等機器本地快取

憑證與 MCP server token **每台機器各自設定**,不同步。範例見 [`examples/.chezmoiignore`](./examples/.chezmoiignore)。

## 快速上手

### 主機器(第一台)

把 [`chezmoi-claude-setup.md`](./chezmoi-claude-setup.md) 交給 Claude Code,依指南跑完階段 0～6,即可把設定推上你自己的 GitHub private repo。核心指令:

```bash
chezmoi init
chezmoi add ~/.claude/CLAUDE.md ~/.claude/settings.json
chezmoi add -r ~/.claude/skills
# 加上 .gitattributes / .chezmoiignore(見 examples/)後 commit、push
```

### 其他機器接入

```bash
# macOS: brew install chezmoi   /   Linux: apt 或 snap install chezmoi
chezmoi init --apply git@github.com:YOUR_NAME/dotfiles.git
```

## 日常同步

```bash
chezmoi update        # 拉最新(git pull + 套用到 ~/.claude,一步到位)

chezmoi re-add        # 把 ~/.claude 的本機修改抓回 source
chezmoi cd && git add -A && git commit -m "update" && git push && exit   # 推出去
```

> chezmoi 不是即時同步工具,是「按需 pull / push」。多機使用請遵守**開工前先 `chezmoi update`、收工後 push**,即可避免分岔。

## 自動同步(dotfiles-sync skill)

可以讓 Claude Code **在對話中**自動完成同步,不必手動打指令。做法是一個內建 skill([`examples/dotfiles-sync/`](./examples/dotfiles-sync/)):

- **Session 開始 / Claude 開始讀 codebase 時** → 執行 `in`(`chezmoi update`)拉最新。
- **改完 `~/.claude` 設定 / 工作告一段落時** → 執行 `status`(顯示 diff + secret 掃描),**經你確認後**才 `push`。

skill 放在 `~/.claude/skills/`,所以會被 chezmoi 同步、每台機器行為一致。在你的 `CLAUDE.md` 加一段觸發規則,讓 Claude 在對的時機呼叫,例如:

```markdown
# Claude Code 設定同步
- session 開始時,用 dotfiles-sync skill 的 `in` 拉取最新設定。
- 改完 ~/.claude 設定後,用 dotfiles-sync:先 `status` 顯示 diff,經我確認後才 `push`。未確認前不得 push。
```

### 運作機制

skill 內附一支小引擎腳本 [`examples/dotfiles-sync/sync.sh`](./examples/dotfiles-sync/sync.sh),有三個子命令。`SKILL.md` 告訴 Claude 這樣呼叫它:

```
sh "$HOME/.claude/skills/dotfiles-sync/sync.sh" <子命令>
```

| 子命令 | 動作 |
|--------|------|
| `in` | `chezmoi update` — 拉最新並套用到 `~/.claude` |
| `status` | `chezmoi re-add` + 顯示暫存的 diff + 掃描金鑰格式字串(不 commit) |
| `push "<訊息>"` | commit 並 push — Claude **只在你確認後**才執行 |

完整流程:

1. 你改了設定,或 session 開始。
2. Claude 依 `CLAUDE.md` 的觸發規則,決定使用 `dotfiles-sync` skill。
3. `SKILL.md` 載入 context,裡面寫著要 Claude 執行 `sh …/sync.sh <子命令>`。
4. Claude 透過 shell 執行(Windows 走 Git Bash、macOS/Linux 走 `sh`),`$HOME` 在各平台被解析成正確路徑。

skill 不會自己執行腳本 —— 是 Claude 讀了 `SKILL.md` 後去跑那行指令。因為 skill 和腳本都放在 `~/.claude/skills/` 下、會被 chezmoi 同步,所以每台機器都有完全一樣的自動化。

設計說明:同步**不是**在「關掉程式」的瞬間自動發生(那時已沒有 Claude 的回合)。而是在有意義的回合(session 開始、改完設定)執行,且每次 push 前都有人工確認。

## 安全提醒

- **任何 token / API key / credentials 都不得進 repo**,commit 前務必掃描
- 你自己的同步 repo 請開 **private**;本專案是公開的「範本 / 指南」,不含任何個人機密

## License

[MIT](./LICENSE)

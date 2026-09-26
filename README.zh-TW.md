[English](./README.md) | **繁體中文**

# Claude Code + Codex 設定同步（chezmoi）

把 Claude Code 與 Codex 的**可攜設定**（全域指示、skills、settings）放進一份 chezmoi source，
同步到 macOS / Linux / Windows 的每一台機器，並讓 agent 自己在**開工與收工時安全地同步**：
開工先拉最新、收工經你核准後才發布。

## 讓 agent 幫你上線（推薦）

前提：你已經有一個私有 dotfiles repo（v2 佈局）。在新機器上開 Claude Code 或 Codex，只要說一句：

> Clone `https://github.com/ChenChiWang/ai-agent-chezmoi`，然後照 `setup/AGENT-SETUP.md` 把這台機器上線。

**agent 會自己做**：唯讀自檢（`setup/preflight.sh`）、提出缺少工具的安裝命令並在你確認後執行、
釘版本安裝 Gitleaks 並核對官方 SHA-256、核對 GitHub 主機指紋、`chezmoi init` 與 diff 摘要、
推導參數檔內容、部署後自檢（`doctor`）、第一次 `status` 與 `check`。

**只有這幾件事需要你**：把 SSH 公鑰貼到 GitHub、決定是否覆寫既有設定、決定 `writer` 與
`auto_in`（見下方參數檔）、核准每一次 push。agent 不會用 sudo、不會放寬 sandbox、不會替你核准。

還沒有私有 repo？見[第一台機器](#第一台機器還沒有私有-repo)。人工流程與結果對照表見
[`docs/new-machine.md`](./docs/new-machine.md)。

## 它做什麼

一份 source 產生兩個 agent 的設定：

| source（`.chezmoitemplates/ai/`） | 產生到 |
|---|---|
| `shared/instructions.md` + `adapters/claude.md` | `~/.claude/CLAUDE.md` |
| `shared/instructions.md` + `adapters/codex.md` | `~/.codex/AGENTS.md` |
| `shared/skills/<name>/SKILL.md` | `~/.claude/skills/<name>/` 與 `~/.agents/skills/<name>/` |
| `shared/scripts/`（同步引擎、secret scanner） | `~/.config/ai-agent/bin/` |
| `dot_claude/settings.json` | `~/.claude/settings.json` |

**不同步**：`~/.claude.json`、`.credentials.json`、`settings.local.json`、`~/.codex/auth.json`、
sessions／history／cache／plugins，以及任何 `*.key`、`*.pem`、`*.token`。完整清單見
[`examples/chezmoi/.chezmoiignore`](./examples/chezmoi/.chezmoiignore)。憑證與 MCP token 每台機器各自設定。

**agent 的三個 checkpoint**（寫在共用指示裡，兩個 agent 都遵守）：

1. **開工**：每個 session 第一回合先跑 `status` 與 `check`，落後就建 plan 套用（每天只真的探測遠端一次）。
2. **記錄**：確認為長期有效的偏好或規則，寫進 source，回報「本機已記錄」。
3. **收工**：source 有修改時建 push plan，**你核准後**才 commit 與 push。

**安全機制**：每次寫入前用 Gitleaks 掃描；`in`／`push` 都經過可審閱的 plan；`writer` 決定哪個 agent
可以發布；plan 綁定 source 狀態，狀態變了就作廢重建；引擎不碰 stash、reset、rebase 或 force push。

## 需求

| 工具 | 要求 |
|---|---|
| Git | 2.45 以上（需支援 `--no-lazy-fetch`） |
| chezmoi | 2.71 系列已測 |
| Python | 3.9 以上，只用標準函式庫 |
| Gitleaks | **必須是 8.30.1**（`setup/install-gitleaks.sh` 會釘版本安裝到 `~/.local/bin`） |
| SSH | 金鑰能存取私有 repo，主機已在 `known_hosts`；不支援帶憑證的 HTTPS |

## 參數檔 `~/.config/ai-agent/sync.local.json`

每台機器一份，不同步，權限 600。平常 agent 不會替你建立；只有在上線流程中、值經你確認後才會寫。

```json
{
  "source": "/Users/you/.local/share/chezmoi",
  "destination": "/Users/you",
  "profile": "claude-codex",
  "remote": "ssh://git@github.com/OWNER/dotfiles.git",
  "branch": "main",
  "plan_dir": "/Users/you/.local/state/ai-agent/plans",
  "author_name": "you",
  "author_email": "you@example.com",
  "writer": "claude",
  "auto_in": false
}
```

**`writer`：哪個 agent 可以套用與發布**

| 值 | 意義 | 適合 |
|---|---|---|
| `"claude"` 或 `"codex"` | 只有它可以 `in`／`push`，另一個只記錄並回報待發布 | 一主一輔（建議起點） |
| `["claude", "codex"]` | 兩邊都可以；一邊剛推完，另一邊的 plan 會過期重建 | 兩邊平等使用 |
| `"any"` 或省略 | 不檢查角色 | 只用一個 agent 的機器 |
| `"none"` | agent 一律不發布，由你不帶 `--agent` 自己跑 `push` | 發布永遠由人做 |

**`auto_in`：不經詢問套用 incoming 的共用文字**（只限 instructions、skills、adapters；腳本、settings、
metadata 仍要人工核准）。只有你是私有 repo 唯一推送者時才開：能推到那個 repo 的人，就能改所有機器上
agent 的指令。

其他欄位：`profile` 填 `claude`、`codex` 或 `claude-codex`；`plan_dir` 必須在 source 之外，也不能在
`.claude`、`.codex`、`.agents`、`.config/ai-agent` 之下；`remote` 用 `ssh://` 或 `git@host:path`。
Codex 預設 sandbox 沒有網路也不能寫 HOME，所以 `check` 會回 `CHECK_SKIPPED`，讓 Claude 當 writer 即可，
不要為了同步放寬 sandbox。

## 日常使用

正常情況下你不必打命令，agent 會在開工與收工時自己跑。需要手動時：

```sh
# 離線：source 與 HOME 有沒有變更或 drift
sh ~/.config/ai-agent/bin/sync.sh status --config ~/.config/ai-agent/sync.local.json
# 遠端是否有新 commit（每天快取一次，--force 重探）
sh ~/.config/ai-agent/bin/sync.sh check  --config ~/.config/ai-agent/sync.local.json --agent claude
# 部署後唯讀自檢，14 項 OK/WARN/FAIL
sh ~/.config/ai-agent/bin/sync.sh doctor --config ~/.config/ai-agent/sync.local.json
# 拉最新：建 incoming plan（印出 PLAN_ID），審閱後套用
sh ~/.config/ai-agent/bin/sync.sh plan --operation in --config ~/.config/ai-agent/sync.local.json --agent claude
sh ~/.config/ai-agent/bin/sync.sh in --config ~/.config/ai-agent/sync.local.json --agent claude --approve PLAN_ID
# 發布：建 push plan，審閱後推送
sh ~/.config/ai-agent/bin/sync.sh plan --operation push --config ~/.config/ai-agent/sync.local.json --agent claude --message "docs: ..."
sh ~/.config/ai-agent/bin/sync.sh push --config ~/.config/ai-agent/sync.local.json --agent claude --approve PLAN_ID
```

注意：`plan` 與 `in`／`push` 之間不要對 source 跑 `git status`，否則 plan 會 `BLOCKED_STALE_PLAN`
要重建。每個結果碼的意思與處理見 [`docs/new-machine.md` 第 7 節](./docs/new-machine.md)。

互動模式的 Claude Code 每次執行 `sync.sh` 都會先問，除非 `settings.json` 的 `permissions.allow` 含
`Bash(sh ~/.config/ai-agent/bin/sync.sh:*)`；[範例 settings](./examples/chezmoi/dot_claude/settings.json) 已包含。

## 第一台機器（還沒有私有 repo）

`setup/AGENT-SETUP.md` 假設私有 repo 已存在。第一次建立時：

1. 以 [`examples/chezmoi/`](./examples/chezmoi/) 為範本建立你自己的**私有** dotfiles repo。它是完整的
   chezmoi source（`.chezmoiignore`、`dot_claude/`、`dot_codex/`、`dot_agents/`、`dot_config/`、
   `.chezmoitemplates/ai/`），把 `shared/instructions.md` 與 `dot_claude/settings.json` 換成你的內容。
2. 若你已有一套舊版 `~/.claude` 設定要帶進來，引擎的 `migration` 子命令可做離線轉換並保留 rollback，
   流程見 [migration readiness](./docs/history/migration-readiness.md)。
3. 之後每台機器都走上面的 agent 上線流程。

**不可**對本公開 repo 執行 `chezmoi init --apply`，也不可整包覆蓋現有 agent 設定。

## 文件地圖

| 文件 | 內容 |
|---|---|
| [`setup/AGENT-SETUP.md`](./setup/AGENT-SETUP.md) | 給 agent 的上線手冊，每步標明「agent 做」或「問使用者」 |
| [`docs/new-machine.md`](./docs/new-machine.md) | 給人的上線與驗收指南、結果碼對照表、跨機器端到端測試 |
| [`docs/sync-v2.md`](./docs/sync-v2.md) | 引擎契約：profile、參數檔、角色、plan、lock、復原 |
| [`docs/secret-scanner.md`](./docs/secret-scanner.md) | scanner 契約與測試 |
| [`docs/production-layout.md`](./docs/production-layout.md) | source 位於 HOME 之下時的安全邊界 |
| [`docs/architecture-adjustment-plan.md`](./docs/architecture-adjustment-plan.md) | 2026-09-26 架構調整計畫與執行紀錄 |
| [`docs/implementation-status.md`](./docs/implementation-status.md) | 目前狀態與未完成項目 |
| [`docs/history/`](./docs/history/) | 已完成的遷移程序與 phase 紀錄 |
| [`archive/`](./archive/README.md) | 已停止維護的 bootstrap／launcher／guardian，**不得安裝** |

## 測試

```sh
sh tests/test-render.sh && sh tests/test-status.sh
python3 tests/test-write.py && python3 tests/test-layout.py
python3 tests/test-migration.py && python3 tests/test-offline-status.py
python3 tests/test-scanner.py                    # 需要真實 Gitleaks 8.30.1
sh tests/session-acceptance.sh claude|codex      # 呼叫真實模型驗收開工檢查，有費用，手動執行
```

Commit／push 只在臨時本機 fixture 執行，測試不會碰你的私有 repo。

## Legacy v1

[`chezmoi-claude-setup.md`](./chezmoi-claude-setup.md) 與 [`examples/dotfiles-sync/`](./examples/dotfiles-sync/)
是只同步 `~/.claude` 的第一版：`in`／`status`／`push` 直接包 `chezmoi update`、`re-add` 與 git push。
保留給既有使用者，但它的 `status` 會改 source 與 index、先輸出 diff 才掃描、`push` 不強制掃描。
新使用者請直接用 v2。

## 安全提醒

- 任何 token、API key、credentials 都不得進 repo；v2 每次寫入前都會掃描，但 ignore 與掃描是多層防護，不是保證。
- 你自己的同步 repo 請開 **private**。本專案是公開的範本與引擎，不含任何個人機密。

## License

[MIT](./LICENSE)

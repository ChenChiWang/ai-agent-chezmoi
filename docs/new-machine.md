# 新機器上線與驗收（Claude Code + Codex 共用設定）

> 對象：要在第二台電腦啟用 v2 同步的人，以及被指派協助上線的 agent。
> 假設私有 dotfiles repo 已完成 Phase 3 遷移，且第一台機器已在使用 v2。
> 還沒有私有 repo：`setup/AGENT-SETUP.md` 的 4B 路徑會從 `examples/chezmoi/` 建立它。

> 想讓 agent 代勞：告訴它「clone 公開 repo，照 `setup/AGENT-SETUP.md` 上線」。那份手冊把每一步
> 分成「agent 做」與「問使用者」，只有把公鑰貼到 GitHub、決定覆寫既有設定、決定 `writer` 與
> `auto_in`、核准 push 這幾件事需要人。

## 1. 前置工具

先跑唯讀自檢，它會逐項標 OK／WARN／FAIL 並附下一步：

```sh
sh setup/preflight.sh
```

| 工具 | 要求 | 補救 |
| --- | --- | --- |
| Git | 2.45 以上，支援 `--no-lazy-fetch` | 套件管理員安裝 |
| chezmoi | 2.71 系列已測 | 套件管理員安裝 |
| Python | 3.9 以上 | 套件管理員安裝 |
| Gitleaks | **必須是 8.30.1** | `sh setup/install-gitleaks.sh`（釘版本、核對官方 SHA-256、裝到 `~/.local/bin`） |
| SSH | 金鑰能存取私有 repo，host 已在 known_hosts | 手冊第 3 步 |

## 2. 首次部署用 chezmoi，不用引擎

引擎的 `in` 要求 target 檔案已存在，所以第一次要由 chezmoi 建立：

```sh
chezmoi init git@github.com:OWNER/dotfiles.git
chezmoi diff        # 先看會覆寫什麼，特別是既有的 ~/.claude/settings.json
chezmoi apply
```

## 3. 參數檔與部署後自檢

寫 `~/.config/ai-agent/sync.local.json`（權限 600，欄位見 README「設定注意事項」），建
`~/.local/state/ai-agent/plans`（700）。然後：

```sh
sh ~/.config/ai-agent/bin/sync.sh doctor --config ~/.config/ai-agent/sync.local.json
```

`doctor` 是唯讀的：檢查工具版本、參數檔、plan_dir、source 的 39 個 mapped 檔、21 個 target、
known_hosts 與 SSH 連線、agent 二進位、settings 的允許規則、部署引擎是否與執行中的相同。
沒有 FAIL 再進下一節。

## 4. 引擎自檢

```sh
sh ~/.config/ai-agent/bin/sync.sh status --config ~/.config/ai-agent/sync.local.json --agent claude
sh ~/.config/ai-agent/bin/sync.sh check  --config ~/.config/ai-agent/sync.local.json --agent claude
```

預期 `NO_CHANGES` 與 `UP_TO_DATE`。其他結果見第 7 節。

## 5. 開工檢查驗收

從公開 repo 的 clone 執行 `sh tests/session-acceptance.sh claude` 與
`sh tests/session-acceptance.sh codex`（會呼叫真實模型、有費用），或直接開互動
session 觀察第一個工具呼叫。預期：先 `status` 與 `check`，再讀專案檔。Codex 在
sandbox 內會看到 `CHECK_SKIPPED`；同一天已有人檢查過則兩邊都看到 `CHECKED_TODAY`。

## 6. 端到端：跨機器記憶回合

這是最值得做的一次驗收，A 為既有機器、B 為新機器：

1. 在 B 用 Codex 說「把 X 記進共用規則」。預期它請求一次工作區外寫入，修改
   source 的 `.chezmoitemplates/ai/shared/instructions.md`，回報「本機已記錄、待發布」。
2. 在 B 開 Claude。預期 `status` 看到 `SOURCE ... working=changed`，建 push plan
   請你核准；push 後 B 的 `~/.claude/CLAUDE.md` 與 `~/.codex/AGENTS.md` 都有 X。
3. 回到 A 開 Claude。預期 `check` 回 `BEHIND 1`，建 in plan；`auto_in` 開著就直接
   套用並重讀，CLAUDE.md 出現 X。
4. 在 A 開 Codex，確認 AGENTS.md 也有 X。

## 7. 常見結果對照

| 輸出 | 意思 | 處理 |
| --- | --- | --- |
| `MISSING_DEPENDENCY`（69） | 缺工具或 Gitleaks 版本不對 | 依第 1 節安裝正確版本 |
| `INVALID_CONFIG`（78） | 參數檔欄位、路徑或權限不合 | 檢查 README 的欄位說明；權限 600 |
| `INVALID_LAYOUT`（65） | source／destination 路徑或 managed 檔案缺失 | 確認 `chezmoi apply` 已完成、路徑是絕對路徑 |
| `BLOCKED_OVERRIDE`（65） | `~/.codex/AGENTS.override.md` 存在 | 人工檢視後移除或改名 |
| `DRIFT`（2） | 部署檔與 source 渲染不一致（有人手動改了 target） | 把意圖改回 source，或 `chezmoi apply` 還原 |
| `NETWORK_ERROR`（71） | 連不到 remote | 檢查 SSH 金鑰、known_hosts、網路 |
| `CHECK_SKIPPED`（0） | sandbox 內無網路（Codex） | 正常；由 writer 端探測 |
| `BLOCKED_STALE_PLAN`（68） | plan 建立後狀態變了（含 `--message` 不同、對 source 跑過 `git status`） | 重建 plan |
| `NOT_WRITER`（77） | 這個 agent 不在該機器的 `writer` 集合 | 回報待發布，由 writer 端執行 |
| `PENDING_APPROVAL`（77） | `auto_in` 下 plan 含非文字變更 | 人工檢視後 `--approve PLAN_ID` |
| `BLOCKED_LOCK`（73） | 上一次寫入未正常結束 | 檢視 `.git/ai-agent-sync.lock`，確認無其他程序後人工移除 |
| `BLOCKED_UNSUPPORTED_COORDINATION`（73） | 封存的 bootstrap 標記存在 | 人工檢視 `.git/ai-agent-cohort*` 與 `ai-agent-launch-readers` |

## 8. 給 agent 的自主流程

完整流程在 `setup/AGENT-SETUP.md`。agent 自己做：preflight、依 FAIL 項提出安裝命令並在
確認後執行、Gitleaks 釘版本安裝、known_hosts 指紋核對、`chezmoi init`／`diff` 與 diff 摘要、
參數檔內容推導、`doctor`、`status`／`check`、驗收。

需要人：把公鑰貼到 Git 託管帳號、決定是否覆寫既有設定、決定 `writer` 與 `auto_in`、核准
任何 push。agent 不得用 sudo、不得放寬 sandbox、不得清除 lock。

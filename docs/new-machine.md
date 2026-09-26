# 新機器上線與驗收（Claude Code + Codex 共用設定）

> 對象：要在第二台電腦啟用 v2 同步的人，以及被指派協助上線的 agent。
> 假設私有 dotfiles repo 已完成 Phase 3 遷移，且第一台機器已在使用 v2。

## 1. 前置工具（引擎會逐項檢查，版本不對會直接拒絕）

| 工具 | 要求 | 引擎回報 |
| --- | --- | --- |
| Git | 2.45 以上，支援 `--no-lazy-fetch` | `MISSING_DEPENDENCY`（69） |
| chezmoi | 2.71 系列已測 | 首次部署用；引擎 `status` 也會呼叫 |
| Python | 3.9 以上 | `MISSING_DEPENDENCY`（69） |
| Gitleaks | **必須是 8.30.1**，其他版本一律拒絕 | `MISSING_DEPENDENCY`（69） |
| SSH | 金鑰能存取私有 repo，`github.com` 已在 `~/.ssh/known_hosts` | `NETWORK_ERROR`（71） |
| Claude Code／Codex | 已安裝並登入 | 不在引擎檢查範圍 |

Gitleaks 請從官方 GitHub release 取 8.30.1（套件管理員常給新版）。SSH 請先手動
`ssh -T git@github.com` 一次，讓 known_hosts 有紀錄；引擎不讀 `~/.ssh/config`、
不會互動提示，金鑰要在 ssh-agent 或是預設檔名 `~/.ssh/id_*`。

## 2. 首次部署用 chezmoi，不用引擎

引擎的 `in` 要求 target 檔案已存在，所以第一次要由 chezmoi 建立：

```sh
chezmoi init git@github.com:OWNER/dotfiles.git
chezmoi diff        # 先看會覆寫什麼，特別是既有的 ~/.claude/settings.json
chezmoi apply
```

那台機器若已有自己的 Claude 設定，先決定要保留還是接受 source 版本；若有
`~/.codex/AGENTS.override.md`，先處理掉，否則引擎會回 `BLOCKED_OVERRIDE`。

## 3. 建立本機參數檔

```sh
mkdir -p -m 700 ~/.local/state/ai-agent/plans
```

寫 `~/.config/ai-agent/sync.local.json`（權限 600），欄位與範例見 README 的
「設定注意事項」。`source`／`destination` 用那台的實際絕對路徑；`writer` 與
`auto_in` 依那台的習慣決定；沒裝 Claude 的機器用 `"profile": "codex"` 與
`"writer": "codex"`。這個檔案不會被同步，agent 也不得代建。

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

agent 可以自己做的：第 1 節的版本檢查（讀取版本輸出）、第 4 節的引擎自檢、
第 5 節的觀察、第 7 節的對照與回報。

必須由人做或決定的：安裝或更換系統工具、放置 SSH 金鑰與首次 `ssh -T`、
`chezmoi apply` 前對既有設定的取捨、參數檔的內容（尤其 `writer` 與 `auto_in`）、
任何 `push` 的核准。agent 遇到這些應明確列出缺項並停下，不得自行補建參數檔、
放寬 sandbox 或清除 lock。

### 規劃中：`sync.sh doctor`

目前第 1、3、4 節要人或 agent 分別跑多個命令比對。規劃一個唯讀的 `doctor`
子命令，一次輸出檢查清單（工具版本、參數檔、plan_dir、source 佈局、target 存在、
SSH 與 known_hosts、agent 二進位、settings 允許規則），每項標 OK／FAIL 與下一步。
agent 在新機器上只需跑 `doctor`，照輸出逐項回報缺什麼；全部 OK 後再跑第 4 節。

# Claude Code + Codex 共用設定架構：實作交接文件

> 交接日期：2026-09-22  
> 對象：在 VS Code 中接手此專案的 Codex，也適用於 Claude Code  
> 專案：`ChenChiWang/claude-code-chezmoi-sync`  
> 狀態：**架構與實作任務交接，尚未修改 repo、部署設定或完成產品端測試。**  
> 建議存放：`docs/AGENT_SHARED_CONFIG_HANDOFF.md`

## 0. 接手後先讀這一節

使用者已有 Claude Code + chezmoi 的設定同步設計，正在設定 VS Code Codex。目標不是淘汰 Claude，而是讓兩個 agent 共用開發規則、可攜 skills 與同步引擎，同時保留各自的設定格式及安全權限。

**本次第一個工作單位：先盤點，再於公開範本 repo 內實作最小共用版本與隔離測試。不得順手套用到使用者的真實家目錄、私人 dotfiles repo 或 GitHub 遠端。**

不要把這份文件當成已完成的實作；文中的新增檔案、v2 子命令與測試都是待實作規格。先確認目前工作樹，若已有人完成部分工作，以實際程式碼及測試為準，保留既有修改。

### 已確認與尚待確認

| 類別 | 內容 |
| --- | --- |
| 使用者目標 | Claude Code 與 Codex 共存、共用同一套核心邏輯；延續 chezmoi 跨機器同步。 |
| 已查閱 | 公開 repo 首頁與 README 所呈現內容、`chezmoi-claude-setup.md`、`examples/dotfiles-sync/SKILL.md`、`examples/dotfiles-sync/sync.sh`、`examples/.chezmoiignore`，以及第 13 節官方文件。 |
| 未查閱 | 使用者私人 dotfiles、實際 `~/.claude` / `~/.codex`、憑證、全部本機 skills 與 MCP 設定。 |
| 版本基線限制 | 公開 `main` 的上述檔案經網頁讀取；本次未取得可鎖定的 commit SHA，也未完成本地 clone。接手時記錄 `git rev-parse HEAD`，不能把本文件當作特定 commit 的完整審計。 |
| 執行環境 | 使用者目前的 agent 執行主機、CLI/extension 版本、Windows 原生或 WSL/SSH/container 環境尚未確認。不得沿用舊指南「目前這台是 Windows」的假設。 |

公開 repo 是「指南與範本」，使用者真正的同步來源另為私人 dotfiles repo。兩者不可混用，尤其不能將公開 repo 設成私人設定的推送目的地。[R1]

## 1. 目標與不做的事

### 核心目標

```text
一份可編輯的 shared source
        ├── 共通 instructions
        ├── 共通 SKILL.md
        └── 一份同步引擎
                 │
        agent adapter + chezmoi
          ┌──────┴──────┐
       Claude Code     Codex
```

共用的是「規則、工作流程與可執行邏輯」，不是兩個產品的所有設定、聊天紀錄或自主行為。相同規則也不代表兩個模型會給出完全相同的結果。

**MVP 的成功定義：**改一次共通規則，兩邊產生的入口都更新；改一次同步引擎，兩邊都呼叫該引擎；既有 Claude 功能不被破壞；同步失敗或發現 secret 時不會繼續提交或推送。

第一版不改 repo 名稱、不要求換作業系統、不建立泛用 agent 框架，也不一次搬完 MCP、hooks、subagents。登入、憑證、session、cache、機器信任及權限設定不在共用範圍。產品的自動記憶先維持本機，不進行跨 agent 搬移。

## 2. 現況核對與優先修正

### 2.1 現有檔案的角色

| 已確認的檔案 | 現有角色 | v2 處理方向 |
| --- | --- | --- |
| `README.md` / `README.zh-TW.md` | 英文／繁體中文入口；本次主要核對首頁呈現的英文 README | 同步補充雙 agent 使用方式，保留原有連結。 |
| `chezmoi-claude-setup.md` | 分階段建置與其他機器接入指南 | 保留舊入口；新增 v2 遷移指南，不假設接手主機是 Windows。 |
| `examples/dotfiles-sync/SKILL.md` | 綁定 Claude 路徑的呼叫規則 | 提煉 agent-neutral 的 skill；舊入口需有相容安排。 |
| `examples/dotfiles-sync/sync.sh` | `in` / `status` / `push` 同步流程 | 作為現況基線，抽出共用核心並補安全測試。 |
| `examples/.chezmoiignore` | 排除部分 Claude 機密與本機狀態 | 補齊明確排除，與 Git 層、白名單和 scanner 一起使用。 |

其餘 `examples/` 子目錄的完整結構、測試及 CI 是否存在，接手後以本地列檔確認；不要從本文件推定不存在。[R1–R5]

### 2.2 從實際腳本辨識出的風險

以下是原始碼檢視，不是已成功重現的執行測試。[R2]

| 觀察 | 影響 | 必須補上的行為 |
| --- | --- | --- |
| `status` 先 `chezmoi re-add`，再 `git add -A` | 名為查詢，實際會修改 source 與 index；可能帶入其他 dotfiles。 | v2 `status` 不修改 source/index，不自動收集全部檔案。 |
| `status` 先輸出完整 diff，之後才掃描 | 敏感值可能已出現在 agent 對話或日誌。 | 先掃描；命中時只回報位置與規則，不輸出原值。 |
| `push` 再次 `git add -A`，未重新掃描 | 推送內容可能不同於使用者剛確認的 diff。 | 綁定核准快照；提交前再次驗證實際候選內容。 |
| 多處錯誤被忽略，或以成功狀態結束 | 呼叫端難以分辨成功、離線、衝突與部分失敗。 | 結構化結果與非零錯誤碼；寫入／提交流程失敗即停止。 |
| `in` 直接 `chezmoi update` | 啟動 session 即可能拉取並套用設定；雙 agent 並用增加互相干擾。 | 不再於 session 開場無條件套用；先檢查來源與本機差異。 |
| 沒有跨呼叫鎖定 | 兩個 agent 可能同時操作同一份 source/index。 | 對同一個 source 使用同一把本機鎖。 |

另外，README 宣告排除 `~/.claude.json`，但目前查閱的 `examples/.chezmoiignore` 未見該明確條目；原建置指南還把 `settings.local.json` 列入納管。v2 應明確排除機器本地設定，避免文件與規則不一致。[R1][R4][R5]

不能只在 `SKILL.md` 寫「發現 secret 就停止」。會改檔、commit、push 的程式本身必須拒絕不安全操作；Markdown 不是強制安全邊界。

## 3. 共用邊界與相容性

| 項目 | 共用方式 | 不可直接假設 |
| --- | --- | --- |
| 開發規則 | 一份 shared instructions，分別產生全域入口。 | 不假設兩邊解析、優先順序完全相同。 |
| Skills | 先共用基本 `name`、`description` 與純 Markdown 工作流程。 | Claude 專用 frontmatter、工具名稱、參數替換、動態 shell 注入不一定適用 Codex。 |
| Shell／其他腳本 | agent-neutral 路徑與 CLI 契約。 | 不把 Claude 專有環境變數放進共用核心。 |
| 設定檔 | 分開管理 Claude JSON 與 Codex TOML。 | 不做 JSON → TOML 的逐欄位機械轉換。 |
| MCP | 後續共用非機密 server 定義，adapter 負責產品格式。 | 認證、OAuth 狀態、token 與權限不共用。 |
| Hooks／subagents | 保留 agent-specific 實作，必要時共用底層腳本。 | 不宣稱生命週期事件或 agent 配置一對一對應。 |

官方目前記載 Codex 使用 `~/.agents/skills` 作為使用者 skill 位置，repo skills 為 `.agents/skills`；Claude Code 使用 `~/.claude/skills` 與 `.claude/skills`。兩邊均記載可讀取 symlink 指向的 skill 目錄。[O1][A1]

Codex 全域 instructions 位於 `CODEX_HOME`，預設為 `~/.codex`，且 `AGENTS.override.md` 可能優先於 `AGENTS.md`。因此部署前必須確認實際 home 及 override，不能只寫入預設檔名就宣稱生效。[O2]

### 3.1 修正前次架構討論中的兩個過度簡化

**不是「產生兩份檔案」就等於維護兩套邏輯。**本案採用「一份權威來源、可重建的輸出」。MVP 允許 chezmoi 從同一模板產生兩份入口；禁止的是手動維護兩份不同內容。Symlink 是後續可選部署模式，不是第一版的必要條件。

**`CLAUDE.md` fallback 不是完整遷移機制。**Codex 的 `project_doc_fallback_filenames` 用於 project instructions；同一目錄存在較優先的 `AGENTS.md`／override 時，不會再合併 fallback。它也不能保證理解 Claude 專用語法。因此不把它作為本案的全域共享主方案。[O2]

Claude 官方目前另記載特定版本／條件下可直接讀取 project `AGENTS.md`，但存在版本、其他 instructions 與設定限制。為相容既有環境，本案不依賴此新行為；必要時可用 Claude 支援的 `@AGENTS.md` import 作薄入口，並先檢查是否已自動載入，避免重複。[A2]

## 4. 建議採用的 MVP 架構

以下是本交接文件提出的工程決策，不代表 repo 已存在這些檔案。接手 agent 可因實際相容性問題調整，但須記錄理由，不能無聲改成兩套核心。

### 4.1 公開範本 repo 佈局

```text
claude-code-chezmoi-sync/
├── README.md
├── README.zh-TW.md
├── chezmoi-claude-setup.md                 # 保留原入口
├── docs/
│   ├── AGENT_SHARED_CONFIG_HANDOFF.md
│   └── migration-v2.md                    # 新增：遷移、備份、回滾
├── examples/
│   ├── dotfiles-sync/                     # 既有入口：按遷移策略處理
│   └── chezmoi/                           # 新增：可複製的 v2 source 範本
│       ├── .chezmoiignore
│       ├── .chezmoitemplates/
│       │   └── ai/
│       │       ├── shared/
│       │       │   ├── instructions.md
│       │       │   ├── skills/dotfiles-sync/SKILL.md
│       │       │   └── scripts/sync.sh
│       │       └── adapters/
│       │           ├── claude.md
│       │           └── codex.md
│       ├── dot_config/ai-agent/bin/executable_sync.sh.tmpl
│       ├── dot_claude/
│       │   ├── CLAUDE.md.tmpl
│       │   └── skills/dotfiles-sync/SKILL.md.tmpl
│       ├── dot_codex/AGENTS.md.tmpl
│       └── dot_agents/skills/dotfiles-sync/SKILL.md.tmpl
└── tests/                                # 若已有測試結構則沿用
```

此處 `.chezmoitemplates/ai/shared/` 是 v2 範本的權威編輯來源。`examples/chezmoi` 是供使用者選擇性合併進私人 chezmoi source 的範本，**不是要求直接對公開 repo 執行 `chezmoi init --apply`**。

第一版不自動接管完整 `settings.json` 或 `config.toml`。先讓 Codex 用自己的本機登入與設定正常工作；只增加已審閱的 instructions、skills 入口與共用引擎。之後需要納管部分產品設定時，再設計保留未知欄位的合併流程。

### 4.2 部署到本機後的預期結果

```text
~/.config/ai-agent/bin/sync.sh              # 唯一執行中的共用同步引擎
~/.claude/CLAUDE.md                        # shared 規則 + Claude adapter
~/.claude/skills/dotfiles-sync/SKILL.md     # 從同一個 shared skill 產生
~/.codex/AGENTS.md                         # shared 規則 + Codex adapter
~/.agents/skills/dotfiles-sync/SKILL.md     # 從同一個 shared skill 產生
```

這些是**預設路徑示例**。部署工具須使用已確認的 agent home；若 Claude／Codex 使用非預設目錄，不得另建一套「看似成功但不會被載入」的設定。MVP 可明確拒絕未支援的自訂路徑並回報，不必立刻實作所有變體。

共用引擎使用本案定義的可選環境變數 `AI_AGENT_HOME`，未設定時使用 `$HOME/.config/ai-agent`。這是**本專案的介面**，不是宣稱兩個產品有此內建設定。

共用 skill 中的呼叫範式：

```sh
sh "${AI_AGENT_HOME:-$HOME/.config/ai-agent}/bin/sync.sh" status
```

注意：此處的 `status` 指**完成安全重構後的 v2 契約**，不可把現有 v1 `status` 當作只讀指令。

### 4.3 ChezMoi 模板範例

`dot_claude/CLAUDE.md.tmpl`：

```gotemplate
<!-- Generated by chezmoi. Edit .chezmoitemplates/ai/, not this file. -->
{{ template "ai/shared/instructions.md" . }}

{{ template "ai/adapters/claude.md" . }}
```

`dot_codex/AGENTS.md.tmpl`：

```gotemplate
<!-- Generated by chezmoi. Edit .chezmoitemplates/ai/, not this file. -->
{{ template "ai/shared/instructions.md" . }}

{{ template "ai/adapters/codex.md" . }}
```

兩個 `SKILL.md.tmpl` 的內容相同，frontmatter 必須保持在產物最前面：

```gotemplate
{{ template "ai/shared/skills/dotfiles-sync/SKILL.md" . }}
```

`dot_config/ai-agent/bin/executable_sync.sh.tmpl`：

```gotemplate
{{ template "ai/shared/scripts/sync.sh" . }}
```

ChezMoi 官方定義 `.chezmoitemplates` 的模板引用，以及 `dot_`、`executable_`、`.tmpl` 等來源屬性。上述組合仍須在測試 fixture 實際 render，驗證內容、換行與檔案權限；未 render 前不得聲稱可直接部署。[C1][C2]

共用腳本作為模板時若出現字面 `{{`／`}}`，需正確跳脫或改用已驗證的原文 include 方案，避免把腳本內容誤解析為 Go template。

### 4.4 權威來源與回寫規則

**編輯 shared source → 預覽 render/diff → 核准 → apply → 驗證。**不要反過來把生成的 `CLAUDE.md`、`AGENTS.md` 或 skill 產物當成來源。

ChezMoi `re-add` 不會覆寫模板，且未指定目標時會收集所有適用的修改檔案。[C3] 因此 v2 不能再依賴「改產物後跑全域 `re-add`」；偵測到生成檔被手改時，須顯示 drift 並協助將意圖移回 shared source，禁止靜默丟棄本機修改。

遷移後，同名 skill 只能有一個有效來源。舊 `~/.claude/skills/dotfiles-sync/sync.sh` 可在**新引擎完成部署與備份後**改成薄 wrapper；新引擎不存在就明確失敗，不能偷偷回退到另一套舊同步邏輯。公開舊範例需要清楚版本標示或生成策略，不能讓 README 指向失效路徑。

## 5. 同步引擎 v2 契約

以下是**待實作 API**，不是現有 repo 支援的指令清單。第一個 PR 只需完成安全的 `status` 與必要 preflight；其餘未完成時必須明確拒絕，不能留下假成功實作。

| 操作 | 契約 |
| --- | --- |
| `status` | 預設不連網、不執行 `re-add`／stage／apply。分開呈現 source 相對 Git 的改動，以及部署產物相對 render 的 drift；輸出前先安全掃描。 |
| `plan` | 產生待同步的明確檔案清單、差異、目的 repo／branch 與候選內容識別碼。可寫入排除同步的暫存資料，但不得修改正式 index 或部署目錄。 |
| `in` | 保留拉取語意，但不再無條件 `chezmoi update`。有未處理修改、未核准套用或衝突時停止；只接受已核對的來源、fast-forward 與明確範圍。 |
| `push` | 使用者確認具體 plan 後才執行；再次掃描、驗證候選內容未變，提交後確認實際 commit 符合核准範圍，再推送到已確認遠端。 |

### 必要防護

**範圍固定。**透過已確認的 chezmoi source 找到私人 Git repo，不使用當前業務專案的 repo 作替代。對目標檔案與 source 檔案建立白名單映射。禁止以 `git add -A` 或遞迴納管整個 home 作為同步捷徑。

**核准的是內容，不只是命令。**Plan 應綁定來源 repo、branch、基準 commit、候選檔案內容摘要、遠端與目的 branch。核准後任一項變動就要求重新檢視。命令列的 `--confirmed` 旗標不構成人類真的同意的證明；agent 仍需取得對話中的明確授權。

**實際推送範圍必須檢查。**Git push 可能包含此前尚未推送的 commit，不能只掃描最新工作目錄或 HEAD 的 diff。檢查所有 outbound commits；發現既有未知、無關或含 secret 的提交就停止，不能替使用者自動改寫歷史。

**共享鎖。**`in`／plan 的可變操作／`push` 以 source 的正規化路徑作鎖定識別，不因 caller 是 Claude 或 Codex 而分開。不能只依賴 Linux `flock`；以具跨平台測試的方式實作。鎖只防止遵守協定的呼叫端，不防其他手動 Git 程序，所以提交前仍須檢查候選 snapshot。

**保留既有 index。**遇到使用者已 stage 的無關內容時停止，或使用經過測試的隔離 index；不得 reset、unstage、stash 或混入使用者的變更。任何 commit 必須能證明其 tree 對應核准內容。

**Fail closed。**Scanner 未安裝、無法讀取檔案或執行失敗，不能視為「未發現 secret」。出錯時保留可診斷的錯誤訊息，但不輸出敏感資料。網路失敗與衝突不得被描述為同步成功。

建議結果分類為 `OK`、`NO_CHANGES`、`DRIFT`、`BLOCKED_SECRET`、`BLOCKED_CONFLICT`、`BLOCKED_STALE_PLAN`、`BLOCKED_LOCK`、`MISSING_DEPENDENCY`、`NETWORK_ERROR`。退出碼與分類需文件化；沒有變更是正常結果，不應假造一筆 commit。

## 6. Secrets 與本機狀態

採「白名單納管 + ignore + 候選內容掃描」，而不是依賴黑名單猜完所有未來的檔名。

MVP 僅開放新增的 shared source、adapter、已核對的模板與本案產物。下列內容預設拒絕納管：登入憑證、API keys、OAuth 狀態、token、私鑰、session/history、cache、SQLite 等執行期資料庫、local settings、機器專屬路徑及完整環境變數輸出。

需明確覆蓋的例子包括 `~/.claude.json`、`~/.claude/.credentials.json`、Claude 的 `settings.local.json`，以及 Codex 常見的 `auth.json` 等認證檔。這不是完整的產品狀態檔清單；未知檔案仍預設不納管。不得透過 `cat` 認證檔或 `printenv` 來做盤點。

`.chezmoiignore` 比對的是 **target path**，不是 `dot_` 編碼後的 source path。[C4] Git 的忽略規則則須針對實際 source 路徑；不能把兩者直接複製當作同一套。Ignore 也不會替你清除已追蹤的內容或 Git 歷史中的 secret。

若發現真實憑證已進入歷史，停止推送、只回報受影響位置，請使用者撤銷／輪換。清理歷史需要獨立核准，不納入一般同步或遷移的自動流程。

Secret scanner 應支援比原有少量 regex 更完整的規則與 redaction。實際工具與版本由接手者核對並固定；測試使用臨時合成字串，不把可用的真實憑證放入 fixture，也不為了讓 CI 通過而關掉掃描。

## 7. 產品差異與執行環境

### Codex 設定

官方記載 Codex CLI 與 IDE extension 共用設定層，使用者設定通常在 `~/.codex/config.toml`，project 設定另有信任條件。[O3] 本案先保留使用者現有設定，不完整覆寫它，也不假設存在會自動載入的 `config.local.toml`。

登入由使用者完成。是否有可用的 Codex CLI 與是否已安裝 VS Code extension 是兩項盤點資料；沒有 CLI 不應直接判定 IDE 無法使用。VS Code readiness 以能開啟 Codex、完成登入並針對目前 workspace 回答只讀問題為準。[O5]

不要為了讓引擎能寫家目錄而預設開啟 full access。Repo 內開發、隔離測試與真實部署必須分開；實際需要操作 workspace 外部時，使用已安裝版本支援的最小權限與核准方式。

### 跨平台範圍

先保留原 repo 的 POSIX `sh` 路線；Windows 的 Git Bash、WSL 與原生 PowerShell 是不同環境，必須分別確認實際 shell、`HOME`、工具路徑與 agent 所在主機。VS Code 連到 WSL／SSH／container 時，也不能把桌面主機的家目錄當作 agent 執行端。

MVP 不為了抽象化就重寫成 Node/Python。若現有 shell 無法可靠完成計畫快照或跨平台鎖，提出小範圍替代及依賴成本。Windows 原生環境沒有所需 shell 時應清楚回報，而非自動改系統設定。

### MCP、hooks 與 subagents 後續安排

先保持原有配置可用，建立待遷移清單，不納入第一個小 PR。MCP 共用 registry 僅保存非機密的 server 定義、啟動參數、URL 及環境變數「名稱」，並固定可固定的依賴版本。不得寫入 bearer token、Authorization 值或從機器匯出的完整認證配置。

Codex 官方提供 MCP 設定及環境變數形式的認證參照，但不同產品格式仍需各自 adapter。[O4] 不假設 VS Code 從 GUI 啟動時一定繼承終端機中的 secret 環境變數；在本機配置並驗證，不能因缺變數就把 token 寫入 Git。

## 8. 分階段執行計畫

### Phase 0：Repo 盤點與基線

只讀取目前工作區及非敏感的環境資訊。確認工作樹、branch、commit SHA、現有檔案與測試工具；讀取本 repo 的 instructions，但不因舊同步觸發規則而自動操作私人 dotfiles。

可用的只讀命令示例：

```sh
git status --short
git rev-parse --show-toplevel
git rev-parse HEAD
git --version
chezmoi --version
sh -n examples/dotfiles-sync/sync.sh
```

未安裝工具就記錄缺口，不自動安裝或修改全域 Git 設定。辨識 remote 時不輸出可能嵌有認證字串的完整 URL。Agent 版本存在則記錄；extension 版本從 VS Code 可見資訊確認，不猜測。

**產出：**已確認／未確認清單、實際基線 SHA、保留的既有修改、Phase 1 的具體修改檔案。資訊可由盤點取得時自行核對，不反覆向使用者詢問。

### Phase 1：最小共享版本，只改範本 repo

新增第 4 節的共用規則、兩個 adapter、兩邊 skill 入口與中立引擎路徑。先實作只讀 `status`、來源驗證、錯誤處理和必要 scanner 接口；尚未安全實作的 `in`／`push` 明確回報不支援。

只用隔離 fixture 驗證模板輸出及引擎行為。不要啟用使用者現有 session-start 自動同步，不替換目前的 `~/.claude`，不取得私人設定，不推送。

維護 README 英文／繁體中文入口；新增 `docs/migration-v2.md` 說明「一份來源，多個產物」、依賴、舊路徑相容與未完成項目。新規則要簡短，交接文件及長流程放 docs／skill，不整份塞進全域 instructions。

**驗收：**兩邊的共通規則一致，skill 均指向同一引擎，render 可重現；`status` 不改 Git/chezmoi 狀態；既有使用方式有清楚保留或遷移安排。

### Phase 2：安全同步與遷移工具

在測試環境補完 plan、lock、受控拉取套用、核准快照與安全 push，並驗證 outbound history。之後產出一次性遷移計画、備份 manifest、精確覆蓋清單與回滾步驟。

**此階段完成仍不等於獲得真實部署授權。**要覆寫本機設定、操作私人 dotfiles、commit 或 push 時，分別取得明確確認；不得把「同意實作程式」視為「同意推送我的設定」。

### Phase 3：使用者核准後的本機試點

先暫停會改動設定的自動同步觸發，做本機備份與 diff，確認重名 skill、既有 instructions、override 和非預設 home。必要時先用不同的測試 skill 名稱避免影響正式流程。

逐項部署，不能整包覆蓋 `~/.claude` 或 `~/.codex`。開啟新的 Claude／Codex session 檢查實際載入與只讀工作流程；人工確認結果後才啟用正式同名入口。多機同步最後再接入第二台，不能只憑第一台通過就宣稱跨平台完成。

### Phase 4：可選擴充

逐個 skill 遷移、MCP registry、hooks/subagents adapter，以及 symlink 模式。每項都以已驗證的產品能力為準，不建立未使用的抽象層。

## 9. 測試與驗收矩陣

測試不得使用真實登入、SSH agent 或外部 GitHub 遠端。以 fake `git`／`chezmoi` 記錄呼叫做單元測試，必要時使用本地 bare Git repo 做整合測試。

實際 chezmoi 測試需明確隔離 source、destination、config 與 cache；僅改 `HOME` 不代表所有繼承環境都已隔離。檢查 XDG 路徑、agent home override 與 SSH 環境，不允許測試回落至使用者真實設定。

| 編號 | 情境 | 預期結果 |
| --- | --- | --- |
| T01 | 只改 shared instructions | 兩邊輸出都包含同一份共通規則；產品尾段維持分離。 |
| T02 | Skill 模板 render | YAML frontmatter 在最前面；兩邊指向同一引擎；不帶 Claude 專有注入語法。 |
| T03 | 重複 render／apply fixture | 產物一致；第二次無非預期差異；確認腳本 LF 與適用的權限。 |
| T04 | 執行 v2 `status` | source、index、HEAD、部署檔內容不變；不 fetch、不 stage、不 re-add。 |
| T05 | 修改不在白名單的其他 dotfiles | 不混入候選內容；不得自動納管。 |
| T06 | Secret 出現在候選檔案 | 在輸出原始 diff 前停止；日誌不含該值；無 commit/push。 |
| T07 | Scanner 缺失／掃描失敗 | 明確阻擋寫入與提交，不回報掃描通過。 |
| T08 | Plan 核准後檔案或 branch 改變 | Plan 失效，要求重新檢視。 |
| T09 | 已有無關 staged 檔案 | 保留使用者 index；停止或安全隔離，不混入 commit。 |
| T10 | 兩個 agent 同時同步 | 同一 source 共用鎖；不產生交錯的 stage/commit/apply。 |
| T11 | Offline／non-fast-forward／衝突 | 非零結果與可理解訊息；不 force-push、不自動 rebase/reset。 |
| T12 | 生成的入口被手動修改 | 呈現 drift；不自動用 render 覆蓋，也不錯誤回寫模板。 |
| T13 | 歷史已有未推送的敏感／未知 commit | 推送被阻擋，不只掃描本次差異。 |
| T14 | 路徑含空白、中文、Git Bash／WSL | 正確引用或明確標示不支援，不能靜默指向另一個 home。 |
| T15 | 真實產品 smoke test | Claude 與 VS Code Codex 均辨識規則與 skill；只做安全的 `status`。 |
| T16 | 回滾 | 還原核准前的本機入口與舊 Claude 使用方式，保留原有非本案檔案。 |

單元測試、chezmoi render、CLI／IDE 實機載入是不同層級。只跑單元測試就只能回報該層通過；macOS、Windows、Linux 未實測的項目分開列為待驗證。

## 10. 部署與回滾要求

部署前記錄每個會改動的檔案是否原本存在、內容 hash、檔案種類與可用的權限資料。備份放在使用者本機、Git 及同步白名單以外，不上傳備份，不收集無關憑證。

回滾根據 manifest 只還原本次改動的檔案；新建的產物也只能在確認未被後續修改後移除。不得以刪除整個 `.claude`、`.codex` 或 `.agents` 作為回滾方式。

MVP 不在 agent 主目錄上使用 chezmoi `exact_`，以免把未納管的登入與執行期資料視為應刪除項；該屬性具有清除未納管內容的語意。[C2]

Git 版本控制不是家目錄的完整備份。公開 repo 的回退、私人 source 的回退，以及已部署檔案的回退是三件不同的事，遷移文件必須分開說明。

## 11. 建議的第一輪 Codex 指令

將本文件放進 repo 後，使用以下指令。此指令授權的是 repo 內開發與隔離測試，不是本機部署或遠端推送。

```text
請先完整閱讀 docs/AGENT_SHARED_CONFIG_HANDOFF.md，再檢查目前 repository。

目標：把 claude-code-chezmoi-sync 漸進擴充為 Claude Code + Codex
共用核心的設定架構，而不是維護兩套同步邏輯。

請完成 Phase 0，然後實作 Phase 1 的最小可驗證版本：
- 一份 shared instructions、兩個薄 adapter。
- 一份 shared skill，兩邊入口呼叫同一個中立同步引擎。
- 安全、只讀的 v2 status；未完成的寫入／推送操作明確拒絕。
- 使用隔離 fixture 的模板與安全測試，保留既有 Claude 使用方式。

本輪只修改這個 repo 及隔離測試目錄。
不要讀取或輸出登入憑證；不要改動我的真實 ~/.claude、~/.codex、
~/.agents、chezmoi source 或私人 dotfiles。
不要執行真實 chezmoi apply/update、git commit、git push、force-push，
不要改全域 Git 設定或自動安裝依賴，也不要因舊 skill 的觸發規則執行同步。
測試環境內的操作必須明確隔離，不能回落到我的真實 home 或遠端。

先辨識現有修改並保留。若缺少依賴，回報缺口並完成能做的靜態檢查，
不要把尚未跑過的測試標成通過。

最後回報：基線 commit、修改檔案、實際完成的測試、未驗證項目、
與 Phase 2 的下一個最小工作單位。用繁體中文說明。
```

## 12. 每輪結束時更新的接續狀態

接手 agent 應在 repo 內維護簡短的進度紀錄，例如 `docs/implementation-status.md`。內容保留決策與證據，不複製聊天紀錄或 secrets。

```markdown
# Implementation status

## Baseline
- Commit:
- Working tree changes preserved:
- Environment / tool versions:

## Completed
- Files changed:
- Behaviors implemented:

## Verification
- Commands actually run:
- Passed:
- Failed:
- Not tested / missing dependencies:

## Decisions
- Decision and reason:
- Difference from the handoff, if any:

## Safety boundary
- Real home modified: no / explicitly authorized scope
- Private dotfiles modified: no / explicitly authorized scope
- Commit or push performed: no / explicitly authorized scope

## Next smallest task
- Task:
- Acceptance criteria:
```

**下一位 agent 必須讀進度紀錄並核對實際工作樹，不能因看到本交接文件就從頭重做。**

## 13. 查核來源

以下連結於 2026-09-22 查閱。Repo 連結指向可變動的 `main`；產品文件也可能更新。接手時核對已安裝版本；若行為與文件不同，記錄差異並以實測和官方版本說明為準。

### 專案來源

- [R1] 公開 repo／README：<https://github.com/ChenChiWang/claude-code-chezmoi-sync>
- [R2] 現有同步引擎：<https://github.com/ChenChiWang/claude-code-chezmoi-sync/blob/main/examples/dotfiles-sync/sync.sh>
- [R3] 現有 skill：<https://github.com/ChenChiWang/claude-code-chezmoi-sync/blob/main/examples/dotfiles-sync/SKILL.md>
- [R4] 原始建置指南：<https://github.com/ChenChiWang/claude-code-chezmoi-sync/blob/main/chezmoi-claude-setup.md>
- [R5] ChezMoi ignore 範例：<https://github.com/ChenChiWang/claude-code-chezmoi-sync/blob/main/examples/.chezmoiignore>

### OpenAI 官方文件

原 `developers.openai.com/codex/...` 文件於本次查閱導向下列官方文件位置。

- [O1] Skills 格式、搜尋路徑與 symlink：<https://learn.chatgpt.com/docs/build-skills>
- [O2] AGENTS.md 與 fallback：<https://learn.chatgpt.com/docs/agent-configuration/agents-md>
- [O3] Codex 設定與層級：<https://learn.chatgpt.com/docs/config-file/config-basic>
- [O4] MCP：<https://learn.chatgpt.com/docs/extend/mcp?surface=cli>
- [O5] Codex IDE extension：<https://learn.chatgpt.com/docs/codex/ide>

### Claude Code 官方文件

- [A1] Skills、載入位置與 symlink：<https://code.claude.com/docs/en/skills>
- [A2] CLAUDE.md、imports、AGENTS.md 與載入條件：<https://code.claude.com/docs/en/memory>

### ChezMoi 官方文件

- [C1] 共用模板目錄：<https://www.chezmoi.io/reference/special-directories/chezmoitemplates/>
- [C2] Source state attributes：<https://www.chezmoi.io/reference/source-state-attributes/>
- [C3] `re-add`：<https://www.chezmoi.io/reference/commands/re-add/>
- [C4] `.chezmoiignore`：<https://www.chezmoi.io/reference/special-files/chezmoiignore/>

---

交接終點：**先完成公開範本內、可隔離測試的 shared-core MVP，再經使用者核准遷移真實設定；不要把架構開發與個人環境部署綁成同一個不可回頭的操作。**

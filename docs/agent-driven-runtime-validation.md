# Agent-driven runtime — PARTIAL

## 固定補驗範圍（2026-09-25）

沿用先前隔離登入與 native agent 版本。保留已通過的專案記錄／收工結果，
本輪只補開工遠端檢查、實際 incoming 與重讀、shared scope outgoing。
不改 engine、launcher、guardian，不增加測試框架、不安裝工具。

共同 instructions 與 skill 的最小文字調整明確要求：本機 status 不能證明
遠端最新；開工使用既有 v2 incoming plan；缺少網路／檢查授權須主動請求，
尚未檢查時回報 freshness unknown；檢查授權不等於 apply 授權。

## Fixture 準備與核准邊界

原隔離根目錄為 `/private/tmp/agent-memory-smoke-zvbvglbl`。兩個 agent 各自使用
`<agent>/fixed-gap/` 下獨立 source、project、plans、evidence，以及
bare `remote.git`／publisher。登入與 runtime HOME 保持原 `<agent>/home`；
沒有讀取、複製或連結 credential 內容。舊 source、remote、project 與證據保留。

- 完整準備清單：該隔離根目錄的 `fixed-gap-preparation.json`，包含每個
  baseline source 檔案的 SHA-256、路徑、候選變更、固定 prompts 與擬執行操作。
- 已複製目前 public example 的 39 個來源檔案到每份 fixture。使用者另行
  明確核准此測試資料建置後，已完成 fixture baseline／本地 seed commit／push；
  已將 baseline 渲染至原隔離 runtime HOME，未改登入或正式設定。
- Incoming 候選只在 `.chezmoitemplates/ai/shared/instructions.md` 增加：
  範例時間應附明確單位，例如 `250 ms`；記憶識別為
  `fixture-units-20260925-v1`。兩份候選內容相同，SHA-256 為
  `43baf3a074418f2884f876e49f5ad75fef8928df9f639b03f6f9cb7ac9db567b`。
  每份 `review/incoming.diff` 與 `review/incoming-instructions.md` 可獨立審閱。
- 已核准並完成的資料建置：每個 fixture 建立 baseline commit／推送至其本地 bare
  remote；publisher 在 baseline 上只增加上述記憶，建立第二個 commit／推送。
  測試 source 保持 baseline，將 baseline 渲染到原隔離 HOME；新專案建立
  baseline commit。提交身分僅使用 `Fixture <fixture@example.test>`。
- 上述資料建置核准**不涵蓋 agent 的 in／push**。每個實際 v2 plan 仍須呈現
  來源、部署根、remote／branch、變更與 PLAN_ID，等待本人確認後才執行。
  不從 PLAN_ID 推導同意，也不以 setup 操作充當 agent 行為測試結果。

| Fixture | 被測 source baseline | 本地 remote 新版本 |
| --- | --- | --- |
| Claude | `89abb6d74a0c47af8104da7c7da8bcd00703c991` | `83bebc8e4fa72c8ecabd1ed3a625510b4044ca81` |
| Codex | `bcc943fbf16f79bf25e4b40c0b479442441a603b` | `6620e3f36481ebdc2ded9f3429c29b1bf7b7c89a` |

每個 remote 恰好多一個 commit，僅變更 shared instructions；source worktree
乾淨，source 與部署 instructions 都沒有新 marker。兩份 baseline／incoming
candidate 經原有 Gitleaks adapter 掃描為 clean；部署後 status 均 NO_CHANGES。
證據位於各 fixture 的 `evidence/seed-result.json` 與 `seed-scan-*.json`。
這也直接展示本機 NO_CHANGES 不能代表 remote 沒有更新。

## 固定情境與驗收

開工 prompt 只要求檢查 README.md／calc.py、說明專案與下一個測試，不提同步。
專案 metadata 提供路徑與權限，不額外加入觸發提示。每個 agent 只測一次；
漏觸發時保留失敗證據，人工提醒後的結果另列，不反覆改提示或重試到通過。

Outgoing 使用已確認、限隔離測試環境的共同規則：「範例檔案大小須註明 bytes
單位」。授權記錄到既有 Shared Core 來源，發布另等實際 plan 核准。
專案 integer-cents 決策留在 docs/decisions.md，不搬到全域。

| 驗收 | Claude | Codex |
| --- | --- | --- |
| 專案讀取前主動觸發 incoming 檢查 | PASS（嘗試；執行受阻） | PASS |
| 主動發現新版本／提出具體套用核准 | FAIL（未產生 plan） | PASS |
| 核准後 agent 執行 v2 in | PASS | BLOCKED：exit 70 IO_ERROR |
| 部署檔案／權限驗證 | PASS（操作端完整驗證） | 未部署；操作端確認完整舊狀態不變 |
| Agent 實際重讀更新的 source／instructions outputs | PASS | NOT RUN |
| 內容使用 | PARTIAL：單位格式正確，但虛稱時長為實測 | NOT RUN |
| Shared 規則記錄與主動提出發布核准 | NOT RUN | NOT RUN |
| 核准後 v2 push 實際成功 | NOT RUN | NOT RUN |
| 另一隔離 clone 取得相同 outgoing 內容 | NOT RUN | NOT RUN |

腳本 exit、Git HEAD／remote、來源與部署檔案 hash／內容、native tool read
events 分開蒐證；模型口頭宣稱不算部署或重讀證據。Native config reload
不在本輪保證範圍。兩個固定開工與核准後續接已完成；沒有 outgoing／push。

## 固定開工結果與待核准 plans

Claude Code 2.1.278／claude-sonnet-5 與 Codex CLI 0.155.1／gpt-6-astra
各一個全新 native session，使用同一份事先固定的一般專案 prompt，未加同步提醒。
Session IDs 與選取的工具呼叫／回答位於各 fixture 的
`evidence/start-summary.json`；原始 native events 保留在 `start.jsonl`。

- Claude：Skill → status → incoming plan 嘗試都發生在專案檔案 Read 之前。
  第一個命令自行使用 `/tmp/...$(date +%s).json`，被 native 權限規則拒絕；
  接著自行改為 `/tmp/dotfiles-sync-incoming-plan.json`，engine 回傳
  `BLOCKED_SYMLINK`（本機 `/tmp` 為 symlink）。未採用 metadata 已提供的
  `/private/tmp/.../fixed-gap/plans`，因此沒有發現更新或提出具體套用核准。
  正確報告 freshness unknown，沒有宣稱本機 NO_CHANGES 代表遠端最新。
  沒有重新修改提示、共同規則或重跑開工測試。
- Codex：read skill → status → incoming plan → read plan，主動確認 remote
  新記憶並提出套用核准。第一次從 source `git show` 候選失敗，因 plan fetch
  在隔離區、不將候選物件寫進 source；隨後自行從本地 bare remote 讀取實際
  commit diff 成功。未執行 in／push，沒有僅靠 hash 宣稱完成 review。
- 操作端為 Claude 在已指定的 private plan directory 建立一次
  `operator-in.json`，只做既有 plan 操作。這是**人工補備**，不能算 Claude
  主動發現／提出具體核准 PASS；證據為 `evidence/operator-plan.json`。
- `fixed-gap-before-approval.json` 證實兩邊全部 deployed files 的內容與 mode
  仍符合 plan 的原狀態；兩個 project worktree 乾淨，沒有 agent commit／push。

完整審閱摘要在隔離根目錄的 `fixed-gap-incoming-review.json`，包含實際 commit
diff、source／destination／remote／branch、每項 target content/mode 差異。
兩份 operation 都是 `in`，profile 為 `claude-codex`，branch 為 `main`，
remote 僅各自 fixture 內的 `remote.git`，candidate 為前表的新版本。

| Agent／plan | PLAN_ID | 到期時間（UTC） |
| --- | --- | --- |
| Claude `plans/operator-in.json`（人工補備） | `08277441f890416b1f16bba8a187052cf9276f3a1fceb7a2d7e4b30e8cced10f` | 2026-09-25 06:23:44 |
| Codex `plans/session-in.json`（主動產生） | `ad47650da6e9db239a8cb5c322bdd754c23b161a774d45686e8c4fe5dd3029ca` | 2026-09-25 06:23:12 |

變更範圍：source 僅新增上述 duration-unit 共同記憶，部署內容變更限
`.claude/CLAUDE.md` 與 `.codex/AGENTS.md`。因測試建置採 owner-private umask，
既有 engine plan 另列全部 21 個 mapped target 的 mode 正規化：16 個一般
檔案 `0600 → 0644`、5 個執行檔 `0700 → 0755`；其餘 19 個 target 內容不變。
這些都是測試部署檔，不含 auth/runtime，未修改 engine 或人工跳過 mode 差異。
使用者已分別明確核准上述兩個 PLAN_ID，只涵蓋列明 incoming 與 mode 正規化，
不涵蓋 outgoing。2026-09-25 05:31:49 UTC 操作端重新核對兩份 plan 的完整期限、
SHA-256、來源 HEAD、remote candidate、branch、所有 source／target 內容與 mode、
engine／scanner hashes，結果均一致；21 個 target 範圍與兩份 instructions 內容
變更亦符合核准。證據為 `fixed-gap-approved-in-preflight.json`。

使用者另行明確允許本次原生 session 必要紀錄更新，仍禁止同步腳本管理
auth／session／runtime。操作端於 2026-09-25 05:46:42 UTC 再次確認兩份原
plan 雜湊與完整期限，均有效，才將各自核准與限制傳入原 native session。
未重新產生或修改 plan，未延長期限，操作端沒有代跑 in。

## 核准後 incoming 結果（本輪已停下）

| Agent | 原 session | 續接時間（UTC） |
| --- | --- | --- |
| Claude | `8c77f064-2819-403d-bf31-54c99d3cf84d` | 2026-09-25 05:47:08–05:49:46 |
| Codex | `01a0d704-2241-72a1-a39f-06e53e34bd63` | 2026-09-25 05:49:46–05:50:52 |

Claude 實際 Bash 呼叫原 engine `in`，攜帶核准的完整 plan 路徑、PLAN_ID 與
原 roots／remote／branch／profile，回傳 `OK: approved source and generated
outputs applied`。既有 scanner、drift、lock、plan 重驗均由原 engine 保留。
來源 HEAD 現為 `83bebc8e4fa72c8ecabd1ed3a625510b4044ca81`，與原 remote 相同。
操作端逐一比對全部 39 個 source、21 個 target 的內容 hash 與 mode，全部符合
plan candidate／rendered；除兩份 instructions，其他 target 內容不變。

Claude 的 post-in Read 工具結果依序包含 shared source、`.claude/CLAUDE.md`、
`.codex/AGENTS.md`，三份回傳都有 `fixture-units-20260925-v1` 與 `250 ms`。
這是實際重讀證據，不是僅引用模型回答。Agent 自行執行 status 得 NO_CHANGES，
抽查部分 target mode 正確；直接 stat instructions 受到 native 權限範圍限制，
完整 21 檔驗證由操作端完成，**不冒列為 agent 自主完整驗證**。
它明確跳過未變更 skill 的重讀，故不宣稱完整 skill-source/output 重讀 PASS。

Claude 內容使用只列 PARTIAL：回答確實使用 `900 ms`／`150 ms`，符合單位規則，
但稱為本次 in／status 的「實測」時長。其實際工具呼叫沒有量測指令，對應結果
亦未提供這兩個時間，因此不能當成有根據的實測資料。不追加提示修正到通過。
先前開工選錯 `/tmp` 路徑、未自主發現更新的 FAIL 完整保留。

Codex 在原 session 驗證 UTC 效期、plan SHA-256、當前 source／21 targets 與
remote candidate hashes，之後確實呼叫原 engine `in --approve`。工具退出碼
為 **70**，輸出 `IO_ERROR: operation stopped; no raw tool output exposed`。
Agent 立即停止，沒有重試、另建 plan、繞過保護或發布。

操作端獨立核對 Codex 所有 source／target hash 與 mode **完全等於執行前狀態**；
來源仍為 `bcc943fbf16f79bf25e4b40c0b479442441a603b`，remote 保持
`6620e3f36481ebdc2ded9f3429c29b1bf7b7c89a`。`ai-agent-sync.lock`、
`ai-agent-sync-transaction`、`ai-agent-migration-transaction`、`index.lock`
皆不存在；沒有清除任何 lock／journal。IO_ERROR 的具體原因本輪未確立，
不能推斷為 engine、scanner 或 sandbox 的已證實故障；按停止條件不再診斷重試。
候選未部署，所以同步後重讀與內容使用均 NOT RUN；開工主動發現 PASS 保留。

兩份 plan 檔案雜湊均未改；remote 未新增 commit，專案 worktree 乾淨。
Claude source 只有原 baseline＋seed 共兩個既有 commits，Codex source 仍只有
baseline；本次 agent／操作端均未建立 commit 或 push，也未建立 outgoing plan。
前後僅以 metadata 比較 auth/config 保護檔，size、mtime、ctime、inode、mode
均相同；不讀 credential 內容。未執行 Keychain 操作，不將 native session
紀錄納入 source／targets／Git；必要 session 寫入僅由原生 agent 自身完成。

證據（均在既有 owner-private 隔離根目錄，不封存含 auth 的整個 HOME）：

- `fixed-gap-incoming-result.json`：分項結論與 post-in Read marker 證據。
- `fixed-gap-incoming-verification.json`：source／21 targets 全檔 hash、mode、Git
  identities 與保護檔 metadata 檢查；此為操作端驗證。
- 各 fixture `evidence/incoming.jsonl`、`incoming-tools.json`、`incoming-run.json`：
  原始 native events、工具輸入／結果、原 session 與時間／exit。
- Codex `evidence/incoming-failure-state.json`：完整舊狀態與 lock／journal 檢查。

本輪停止於此，整體仍為 **agent-driven runtime PARTIAL**。沒有 outgoing 授權，
不追加模型回合、改提示、改架構或代跑失敗步驟。

既有 `sh tests/test-render.sh` 與 `git diff --check` 通過。Seed、planning 與
開工觸發結果不代表 incoming／outgoing runtime 驗收完成。正式／private 設定不變；
不對 public/private repo commit／push、不執行 bootstrap／4H。


## 去敏診斷補強與新 Codex plan（2026-09-25）

本輪為操作端程式補強與隔離 fixture planning，**不是 agent incoming 重試**。
整體仍為 agent-driven runtime PARTIAL。沿用 dotfiles-sync v2；沒有同步行為、
scanner、drift、鎖或 approval 契約變更，沒有新 launcher／guardian／測試框架。

`sync-write.py` 在錯誤 stderr 增加 `DIAGNOSTIC:` JSON，成功 stdout／exit code
保持原契約。欄位限定 phase、operation、exception_type、可用的 errno、
本專案 basename／line、transaction_started、rollback、cleanup 與至多八個
secondary_errors。未知狀態使用 unknown；不輸出 exception 原文、locals、環境、
原始 subprocess stderr 或完整路徑。交易、atomic、鎖與暫存目錄的清理邊界先保存
原錯誤；後續恢復失敗另列，保留既有 IO_ERROR／RECOVERY_REQUIRED 返回行為。

沿用 `tests/test-write.py`，31 項全部 PASS；最後錯誤去重調整後，四項新增案例
再次全部 PASS：

| 注入 | 診斷與實際狀態 |
| --- | --- |
| source lock mkdir 前失敗 | source_lock／EPERM；transaction=false，無 rollback；全檔案／Git 狀態不變 |
| 部署中 EIO | apply_files／EIO；transaction=true；rollback 成功，HEAD/index/原檔案恢復，無 journal/index lock |
| rollback 再 EACCES | 第一個 EIO 保留，secondary 列 EACCES；exit 72，未恢復的 target 與 journal 保留，HEAD/index 未變 |
| journal cleanup 再 EACCES | 第一個 EIO 保留，cleanup failed；exit 70；原檔案／Git 恢復但 journal 保留 |

四案均斷言假敏感 exception 文字與完整 fixture 路徑未輸出；不將失敗時新增的
不可變 Git objects 誤報為已刪除。測試內暫存 fixture 由原 unittest teardown
回收，沒有清除原 runtime fixture 的鎖或交易資料。

原始 Codex 呼叫只留下泛用 IO_ERROR；原始 errno、traceback、精確 phase/operation
仍未知。後續獨立權限 probe 在原 sandbox 的 source .git lock mkdir 觀察到
EPERM；該證據不能回填成原呼叫的已證實根因，也不能區分原呼叫是否曾 rollback。
舊 plan 已過期；之前準備的重試在啟動 native session 前即因效期檢查停止，未執行 in。

Claude 的同步／檔案核對／實際重讀證據保持原樣。開工選錯 plan 路徑仍未解決；
900 ms／150 ms 沒有量測證據，只能視為示例，回答品質 PARTIAL 與同步驗收分開。

### 新 incoming plan：待使用者重新核准

- PLAN_ID：`8848cc87e13d93a812a10460ab3ef1e814abf65869a5c629a99bdd88513af9bb`
- 建立：`2026-09-25T13:13:55+00:00`；到期：`2026-09-25T14:13:55+00:00`（UTC；Berlin 為 16:13:55 CEST）。
- Source HEAD：`bcc943fbf16f79bf25e4b40c0b479442441a603b`。
- Local remote main 候選：`6620e3f36481ebdc2ded9f3429c29b1bf7b7c89a`。
- 使用既有 `codex/fixed-gap/source`、`codex/home`、`codex/fixed-gap/remote.git`；profile=claude-codex。
- 新工具 bundle 在 `codex/fixed-gap/review/diagnostic-engine`，僅供隔離測試呼叫。
  它不是部署 target；候選內的 engine 內容仍為原版。這次 plan 驗證的是由診斷版
  engine 執行原本 memory incoming，不是將診斷版 engine 部署至 HOME。
- 相對舊 plan，除了 created，plan 本體只有 tools 中 sync-write.py hash 與 scanner
  路徑改變；scanner bytes／hash 不變，source/state/candidate/rendered/remote 均相同。
- 仍只變更 shared instructions，部署內容僅兩份 instructions：
  「範例時間須附單位，例如 250 ms」；原列明 21 個 managed targets 權限正規化
  600→644、700→755。無 auth/session/runtime targets。
- Planning 前後 source、managed targets、HEAD/index、remote、lock/journal 與保護檔
  metadata 相同。成功 stderr 為空。沒有 native session 呼叫、in、outgoing 或 commit/push。
- 新 PLAN_ID 尚未核准；原核准不轉移。後續執行前仍须驗證效期、ID、完整當前狀態與權限。

| 工具 | 新 SHA-256 |
| --- | --- |
| `gitleaks-rules.json` | `6f9f7cef3084edd7a1967b9ad92e24319ab1dbc87ecf163fe6d2aa8e490fad39` |
| `scan-secrets.py` | `53f1b6fa4b47dec81d4d1fb324736d1932b749705fddd1dbe08fd53289652293` |
| `scanner` | `53f1b6fa4b47dec81d4d1fb324736d1932b749705fddd1dbe08fd53289652293` |
| `sync-migrate.py` | `064dc323912446040566b781ca540776163a8cae5a0c04473f8f1a5058879648` |
| `sync-write.py` | `307ec33f3f72d1417a341e931f041430570688ed25861d3db9e910db1a0fe4bc` |
| `sync.sh` | `a99564f0d9848db58cfeeab3f77f25edc50e817fc9ce6608f2ac3e1a4bb68874` |

原 sync-write.py SHA-256：`70ce2d670b4df37d0b90404e4805445980323cf1c0c86a9372db8f95a2eeeca1`。

完整 plan：隔離根目錄的 `codex/fixed-gap/plans/diagnostic-in.json`。
核准摘要與 hash 差異：`codex/fixed-gap/evidence/diagnostic-plan-review.json`。
本輪程式最小差異：`diagnostic-change.patch`（相對本輪開始的快照，排除既有未提交工作）。
檢查摘要：`diagnostic-checks.json`。原 native 證據未覆寫。


## 已核准診斷版 Codex incoming：PASS（2026-09-25）

本節追加本次結果，不回溯修改原始 exit 70 或開工觸發紀錄。整體維持
**agent-driven runtime PARTIAL**；本次為使用者明確核准後的原 session 續接。

核准 plan `8848cc87e13d93a812a10460ab3ef1e814abf65869a5c629a99bdd88513af9bb`，
效期至 **2026-09-25 14:13:55 UTC／16:13:55 CEST**。操作端與 agent 分別核對
plan ID、全部工具 SHA-256、候選與範圍；agent 工具記錄 UTC 為 13:37:38，仍有效。
診斷 engine SHA-256 為 `307ec33f3f72d1417a341e931f041430570688ed25861d3db9e910db1a0fe4bc`。

首次原生啟動於 13:32:47–13:32:54 UTC，被外層 sandbox 阻止初始化；stderr 記錄
sandbox_apply Operation not permitted，JSONL 為空，未有 in 呼叫。外層執行獲核准後，
於 13:37:19–13:38:45 UTC 續接原 session `01a0d704-2241-72a1-a39f-06e53e34bd63`，
沿用先前驗證的 fixed_gap_in profile（網路禁用、原有保護路徑保留）。這是原生啟動
限制的處理，不是失敗 in 後反覆重試；不將外層啟動失敗冒列 engine IO_ERROR。

| 驗收 | 結果與證據 |
| --- | --- |
| Agent incoming 執行 | PASS；item_3 唯一一次指定 in，exit 0，`OK: approved source and generated outputs applied`；操作端未代跑 |
| Agent 檔案核對 | PASS；item_4 逐檔計算 21 targets SHA-256/mode，符合 plan rendered |
| 操作端獨立核對 | PASS；全部 source/21 targets、HEAD/index 與候選相符，source worktree clean |
| Agent 實際重讀 | PASS；in 後 item_4 讀 shared instructions source、Codex/Claude deployed instructions，三者均有 fixture-units-20260925-v1；另讀 dotfiles-sync source 與兩個 deployed skill 副本 |
| 新規則使用 | PASS；item_6 明確寫「示例：250 ms（示例，非實測）」 |
| 收工檢查 | item_5 status 為 NO_CHANGES；專案 decisions 與 worktree 無待提交變更 |
| 本輪主動開工觸發 | NOT RUN；本次有明確執行與重讀指示，不新增 proactive PASS |

HEAD 已快轉至原候選 `6620e3f36481ebdc2ded9f3429c29b1bf7b7c89a`，local remote main
保持該值，沒有新 commit/push。僅 source shared instructions 與兩份 deployed instructions
內容更新；21 targets 權限符合核准的 600→644／700→755。部署 engine 內容仍是原 SHA
`70ce2d670b4df37d0b90404e4805445980323cf1c0c86a9372db8f95a2eeeca1`，診斷 engine 未部署。
未殘留 ai-agent-sync.lock、ai-agent-sync-transaction、ai-agent-migration-transaction、
index.lock；沒有操作端清鎖。成功流程沒有 DIAGNOSTIC 錯誤摘要，不從缺少錯誤輸出
推造 rollback/cleanup 的量測紀錄。

保護檔只比較 metadata，不讀憑證內容；auth/config 的 size/mtime/ctime/inode/mode
前後相同。必要原生 session 紀錄由 Codex 更新；同步 allowlist 未含 auth/session/runtime。
未操作 Keychain、正式/private 設定、outgoing、安裝或 bootstrap／4H。

證據位於原隔離 Codex `fixed-gap/evidence/`：

- `diagnostic-incoming.jsonl`（空）、`.stderr`、`-run.json`：首次初始化受阻。
- `diagnostic-incoming-resumed.jsonl`、`.stderr`、`-run.json`：原 native session 完整工具事件。
- `diagnostic-incoming-resumed-before.json`、`diagnostic-incoming-after.json`：操作端前後狀態。
- `diagnostic-incoming-tools.json`：實際工具呼叫；item_4 才是同步後重讀，item_2 的候選檢查不冒算重讀。
- `diagnostic-incoming-verification.json`、`diagnostic-incoming-result.json`：操作端驗證與分項結論。

Claude 既有同步／檔案核對／重讀證據、開工路徑 FAIL 與回答品質 PARTIAL 均保留。
原始 Codex IO_ERROR 仍缺少當時底層例外，不以本次成功反推原始根因。完成後停止。

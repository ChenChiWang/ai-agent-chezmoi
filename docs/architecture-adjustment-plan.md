# 架構調整計畫（2026-09-26）

> 依據 2026-09-26 對未提交工作樹的複查整理。本文件是計畫，不是授權；
> 每一項仍依既有 v2 核准與安全規則執行。沒有 production 部署、commit/push 或 4H。

## 1. 複查結論

| 層級 | 狀態 | 依據 |
| --- | --- | --- |
| v2 引擎（`sync.sh` status／plan／in／push、scanner、migration） | 可運行 | 本機 31/24/65/10/6 測試全過；Phase 3H 已在私有 source 發布並部署 |
| 三 profile 擴充與 DIAGNOSTIC 輸出（工作樹） | 可運行，尚未部署 | `tests/test-write.py` 31 PASS；HOME 已部署版本仍為 Phase 3 |
| Claude 與 Codex 共用同一份設定 | 可運行 | 兩端 instructions／六 skill 同源渲染；Phase 3 有實際 discovery 紀錄 |
| Agent-driven memory checkpoints | 未達可靠運行 | 三次 Claude 開工測試兩次 FAIL、一次 PARTIAL；參數無來源；plan 路徑在 macOS 踩到 symlink |
| 兩 agent 同時運行並各自同步 | 有條件 | Codex sandbox 擋住 source `.git`、HOME target 與網路；reader race 仍 BLOCKED |
| `bootstrap/` 與 guardian／launcher | BLOCKED，且與現行需求方向衝突 | 現行需求明示不需 launcher／guardian；子模組另有多項 HIGH 問題 |

## 2. 範圍

- 在範圍：工作樹收斂、skill 參數與授權模型、引擎小幅修正、雙 agent 分工、觸發頻率、文件收斂、部署順序。
- 不在範圍：family retirement、loading gate、bootstrap 工具鏈修復、真實第二台機器部署。這些維持 BLOCKED，不在本計畫內恢復。

## 3. 調整項目

每項列出問題、調整、涉及檔案與驗收條件。編號即建議執行順序。

### A. 工作樹與 commit 切分

**問題**：36 個未提交檔案混合了現行引擎變更與已停止方向的 bootstrap 程式碼（約 1,300 行實作、1,800 行測試）。

**調整**：
1. 引擎、scanner、shell、shared instructions／skill、對應測試與 docs 為一個 commit。
2. `bootstrap/` 與 `tests/test-bootstrap*.py`、`test-enrollment.py`、`test-cohort-integration.py`、`test-generation-cohort.py`、`test-guardian.py`、`test-native-*.py`、`test-loading-races.py`、`generation_cohort_model.py`、`loading_snapshot_model.py`、`qualify-macos-artifact.py` 另開分支或移至 `archive/`，README 標示「已停止維護、不得安裝」。
3. `docs/phase-4*.md`、`docs/agent-driven-runtime-validation.md` 中屬於 bootstrap／loading 的段落一併移入 `docs/history/`。

**驗收**：main 上 `tests/` 只剩會在無真實二進位環境下執行的測試；README 不再連結 bootstrap 為可用元件。

### B. Skill 參數來源

**問題**：SKILL.md 要求 agent 自行確立 source、destination、profile、remote、branch、plan 目錄，又禁止 standing policy，結果每個 session 都要問一次或由 agent 猜。

**調整**：
1. 新增機器本地參數檔 `~/.config/ai-agent/sync.local.json`，欄位：`source`、`destination`、`profile`、`repository_profile`、`remote`、`branch`、`plan_dir`、`author_name`、`author_email`。
2. 該檔不進 chezmoi 對應、不進 Git；`.chezmoiignore` 加入 `.config/ai-agent/sync.local.json`。
3. SKILL.md 改為：先讀參數檔；缺檔或缺欄位才問使用者；讀到的值仍要在 plan 輸出中列出供核對。
4. 文件明確區分「參數從哪來」與「是否授權寫入」；前者可以固定，後者見 C。

**涉及**：`shared/skills/dotfiles-sync/SKILL.md`、`examples/chezmoi/.chezmoiignore`、`docs/sync-v2.md`。

**驗收**：新 session 在參數檔齊全時不需任何提問即可跑 `status` 與 `check`；參數檔缺欄位時提問內容只針對缺項。

### C. 授權分方向

**問題**：`in` 與 `push` 目前共用同一套「逐 plan 核准」語意，開工檢查因此每次都需人工確認，模型也因此傾向跳過。

**調整**：
1. `in`：fast-forward、全掃描、限定範圍，允許在參數檔以 `auto_in: true` 由使用者簽一次「本機允許自動套用 incoming」。引擎仍要求 `--approve PLAN_ID`，由 skill 在 `auto_in` 為真且 plan 只含 shared 文字變更時自行帶入；含 scripts、settings、wrappers 變更時仍停在 pending approval。
2. `push`：維持每個 plan 逐次核准，不提供自動選項。
3. SKILL.md 與 `sync-v2.md` 的「no standing policy」改寫為「push 無 standing policy；in 的 standing policy 只能來自本機參數檔且限 shared 文字」。

**驗收**：`tests/test-write.py` 新增案例：`auto_in` 下含 script 變更的 plan 不被自動套用；純文字變更被套用且輸出列出 plan 內容。

### D. 引擎小幅修正

| 項目 | 問題 | 調整 | 涉及 |
| --- | --- | --- | --- |
| D1 `check` 子命令 | 開工檢查要建完整 plan，每個 commit 跑三次 gitleaks | 新增 `check`：fetch 後比對 remote head 與 HEAD，輸出 `UP_TO_DATE` 或 `BEHIND: n`，不掃描、不寫 plan | `sync.sh`、`sync-write.py` |
| D2 plan 路徑 | 必須在 destination（即 HOME）之外，且拒絕 symlink 元件，`/tmp` 在 macOS 直接失敗 | 對 plan 路徑父目錄做與 roots 相同的 `resolve()` 正規化；「不得在 destination 之下」改為「不得在四個 target 區域之下」 | `sync-write.py` main、`scan-secrets.py` TARGET_REGIONS |
| D3 例外白名單 | `cli()` 漏 AttributeError／IndexError，壞 JSON 會洩露 traceback | 補進 `cli()` 與 `Diagnostics.capture`；分類改用 `isinstance` | `sync-write.py` |
| D4 option 重複檢查 | `--profile`、`--repository-profile` 允許重複給值 | 比照 `--source` 加重複檢查 | `sync.sh` |

**驗收**：D1 有 no-change 與 behind 兩個測試；D2 有 `/tmp` 路徑 plan 成功與 target 區域內 plan 被拒兩個測試；D3 有壞 JSON plan 回傳 `IO_ERROR` 且 stderr 只含 DIAGNOSTIC 的測試。

### E. 雙 agent 分工

**問題**：Codex 預設 sandbox 不開 HOME 寫入與網路，引擎的每次 plan／in／push 都要跳出 sandbox；reader race 未解；兩 agent 各自寫入會提高殘留 lock 的人工處理頻率。

**調整**：
1. Claude 為唯一 writer（`in`、`push`）。Codex 只跑 `status`（sandbox 內可行）與 `check`／`plan`（需一次網路核准），發現更新時回報並提示到 Claude 端套用。
2. `adapters/codex.md` 加入這個角色說明與 sandbox 限制；`adapters/claude.md` 加入「settings.json 變更需重啟」提醒。
3. 參數檔加 `writer: claude|codex`，skill 依此決定是否允許執行寫入。
4. SKILL.md「已知並行使用要延後」改為可操作的規則：`in` 只在開工檢查時做；非 writer 端永不執行 `in`／`push`。

**驗收**：`tests/test-render.sh` 涵蓋兩個 adapter 的新文字；以 `writer: claude` 的參數檔在 Codex 角色下請求 `in` 時，skill 回報 pending 而不執行。

### F. 觸發頻率

**問題**：全域 instructions 要求每個 session、包含唯讀任務都先同步，成本高且模型觸發不穩。

**調整**：
1. 開工檢查改為「每台機器每天一次」，在 `~/.config/ai-agent/state/last-check` 記時間戳；同日已檢查則跳過並在回覆中註明。
2. 收工檢查只在 source 有修改或 `check` 顯示有未推 commit 時執行。
3. `instructions.md` 的 Required memory checkpoints 縮短為三句，細節移到 SKILL.md。

**驗收**：同一天第二個 session 不觸發 fetch；`test-status.sh` 不受影響。

### G. 文件收斂

**調整**：
1. 現行契約只保留 `docs/sync-v2.md`、`docs/secret-scanner.md`、`docs/production-layout.md` 與 SKILL.md。
2. `implementation-status.md` 改為只記錄最近一次狀態，歷史流水帳移入 `docs/history/`。
3. `bootstrap/README.md` 與 phase-4 文件中與程式碼相反的敘述（supervisor vs execv；鎖檔只含三個工具）在移入 history 前加上「已知不符」註記，避免日後誤引。
4. 版本釘住更新：Codex 本機已為 0.157.0，重新確認 `~/.agents/skills` 與 `AGENTS.md` 讀取行為後更新文件。

### H. 部署順序

1. 完成 A 之後才做後續變更，避免再混入 bootstrap。
2. B、D2、D3 一起部署到私有 source（一次 reviewed push），因為 SKILL.md 的新文字依賴 D2 才不會再踩 `/tmp`。
3. D1、C、E 第二批；此時才把 `auto_in` 寫進參數檔。
4. F 與 instructions 縮短最後部署；部署前在隔離 fixture 各跑一次 Claude 與 Codex 的三段 checkpoint。
5. 每批部署後執行 `status` 與 `test-render.sh`，並確認 HOME 的引擎 SHA-256 與 source 一致。

## 4. 不做的事

- 不恢復 family retirement、guardian、launcher 或 hooks 方向。
- 不為了讓 Codex 成為 writer 而放寬其 sandbox 或 approval 設定。
- 不把 `push` 納入任何自動化。
- 不在本計畫完成前把新的 Required memory checkpoints 部署到全域 CLAUDE.md。

## 5. 執行紀錄（2026-09-26）

全部 A–H 已在公開工作樹完成並分批 commit 到 main（未 push、未部署到私有 source）。

| 項目 | 結果 | 與計畫的差異 |
| --- | --- | --- |
| A | 引擎／政策／文件三個快照 commit；`bootstrap/` 與 13 個測試移至 `archive/`，phase-4 文件移至 `docs/history/`，封存測試從新位置全數通過 | 無 |
| B | `--config` 讀取 `sync.local.json`，closed key set，命令列優先；`plan_dir` 自動產生 plan 檔並以 `PLAN_ID` 尋回；`.chezmoiignore` 排除 | 無 |
| C | `auto_in` 只在 `in`、只限共用文字來源；否則 `PENDING_APPROVAL` 77；`push` 無自動模式 | 無 |
| D1 | `check`：`UP_TO_DATE`／`BEHIND n`／`AHEAD n`／`DIVERGED`，不掃描不寫 plan；有 `plan_dir` 時記錄 `last-check.json` | `AHEAD`／`DIVERGED` 為新增結果 |
| D2 | plan 路徑經目錄別名正規化；只拒絕 source 與四個部署區域 | 原測試 `test_plan_file_cannot_be_written_inside_home` 改為新規則 |
| D3 | `cli()` 補 AttributeError／IndexError；分類改 `isinstance`；`INVALID_PLAN`、cohort metadata 型別檢查 | 無 |
| D4 | `--profile`、`--repository-profile`、`--config` 重複給值回 64 | 無 |
| E | `writer` 與 `--agent`：非 writer 的 `in`／`push` 回 `NOT_WRITER` 77；兩個 adapter 補角色與 sandbox 說明 | 無 |
| F | `check` 每日一次（`CHECKED_TODAY`），`--force` 重探；instructions 縮為三句 | 每日狀態放在 `plan_dir/last-check.json`，未另設 state 目錄 |
| G | 現行契約只留 sync-v2、secret-scanner、production-layout、本計畫與精簡後的 implementation-status；其餘移入 `docs/history/`；Codex 0.157.0 以二進位字串確認 skill 路徑 | 未做真實 Codex runtime 重驗 |
| H | B/D2/D3 與 C/D1/E 因同時完成而合併為引擎、skill 兩個 commit | 批次數少於計畫 |

**部署（2026-09-26，本機）**：私有 source 的 8 個對應檔案更新並以 reviewed push 發布（私有 commit
`026e9848`），HOME 21 個 target 與 plan 一致，部署引擎等於公開 `25c0792`。`sync.local.json` 已建
（writer=claude，auto_in=false）。過程中發現並修正兩個引擎阻礙：scp 型式 remote 未被接受、SSH 只信任
agent 而 agent 無金鑰（改為允許預設金鑰檔）。另一個 agent 陷阱：`push` 未重複帶 `--message` 會被判過期，
已改為從 plan 取用（此修正尚未部署到 HOME）。私有 repo 留有一個 stash（9/25 驗證殘留）待處理。
公開 repo 的 `docs/history/` 與 `archive/` 含本機路徑與私有 repo 名稱，公開 push 前應清理。

**公開 repo 收尾（2026-09-26）**：本地 10 個 commit 以 filter-branch 清除本機路徑與私有 repo 名稱
（LICENSE 署名與公開 repo URL 保留）；遠端另有一個早期快照 commit `eb5ba06`（診斷引擎變體、
checkpoint 草稿），以「以本地為準」的 merge 收入，其 `agent-driven-memory.md` 移入 history，其
`test_existing_coordination_metadata_refused` 採納：引擎與 shell status 對封存的 cohort／lease 標記一律
回 `BLOCKED_UNSUPPORTED_COORDINATION`（73）。引擎內剩餘的 cohort 程式碼已不可達，建議下一輪移除。

**cohort 移除（2026-09-26）**：引擎移除全部 cohort／lease／DEFERRED_READERS 與 launcher 專用 timeout 後門，`lock()` 回到單一 mkdir 鎖；最後含 hooks 的版本以 tag `engine-with-cohort-hooks` 標記供封存測試使用。

**真實 session 驗收（2026-09-26，Claude Code 非互動模式，普通唯讀任務）**：第一次 FAIL（模型判定一句
README 摘要非「實質工作」而跳過）；指示改為無條件、列出兩條命令並註明「不是判斷題」後重測 PASS：
先 `status` 再 `check`（真實 fetch，UP_TO_DATE，寫入當日快取），再讀專案檔，7 turns。發現指示中的
`${AI_AGENT_HOME:-…}` 寫法會被權限分類器擋下，已改為字面 `~/` 路徑。Codex session 未測。

**Codex 真實 session 驗收（2026-09-26，`codex exec`，預設 workspace-write sandbox，同一普通任務）**：
無快取時先 `check`（sandbox 無網路，`NETWORK_ERROR` 71）再 `status`（NO_CHANGES），明確回報「更新檢查失敗、
用現有設定繼續」後才讀專案檔，PASS；有當日快取時 `check` 回 `CHECKED_TODAY`，不碰網路，PASS。兩次都未嘗試
跳出 sandbox。注意 `codex exec` 在非 TTY 下會等 stdin，測試需 `< /dev/null`。

**Sandbox 內的 check（2026-09-26）**：Codex sandbox 匯出 `CODEX_SANDBOX_NETWORK_DISABLED=1`（已實測），
`check` 據此不嘗試連線，回 `CHECK_SKIPPED`（exit 0）並附上舊快取結果與日期；不寫快取。維持「Codex 不請求跳出
sandbox」。新增 `tests/session-acceptance.sh`（呼叫真實模型、有費用、不在預設測試集）固化開工檢查驗收流程。

尚未執行：互動模式下建議在 settings.json 加 `Bash(sh ~/.config/ai-agent/bin/sync.sh:*)` 允許清單以免每次提示。

## 6. 多 writer 與使用者習慣（2026-09-26 已實作）

`writer` 由本機參數檔決定，是每台機器的偏好設定，不是架構限制。不同習慣的使用者用同一個參數檔表達，
不改程式碼。README 的「設定注意事項」是使用者面向的說明：

| `writer` 值 | 意義 | 適合的習慣 |
| --- | --- | --- |
| `"claude"` 或 `"codex"` | 只有該 agent 可 `in`／`push`，其他 agent 記錄與回報 | 一主一輔（目前預設） |
| `["claude", "codex"]` | 清單內任一 agent 皆可套用與發布；lock 序列化，plan 過期時重建 | 兩邊平等使用 |
| `"any"` 或省略 | 不做角色檢查 | 單一 agent 的機器、或信任所有 agent |
| `"none"` | 任何帶 `--agent` 的 `in`／`push` 都拒絕，只有人工（不帶 `--agent`）可發布 | 希望 agent 只記錄、發布永遠由人做 |

已實作：`load_config` 接受字串或字串清單；`NOT_WRITER` 判斷為「`--agent` 不在允許集合」。多 writer 的
代價是 BLOCKED_STALE_PLAN 變多（A 建 plan 後 B 先 push），引擎已安全處理，只需重建 plan。`auto_in` 與角色獨立。
Codex 當 writer 時仍受其 sandbox 限制，每次寫入與 push 需核准跳出。

## 7. 附錄：本次複查的程式碼問題


引擎（需修，對應 D）：
- `sync-write.py:1022`：例外白名單漏 AttributeError／IndexError。
- `sync-write.py:76`：例外分類用精確型別比對，子類別歸為 unknown。
- `sync-write.py:439-456`：history 每 commit 三次掃描，遠端領先時開工成本過高。
- `sync-write.py:951-953`：plan 路徑不做 symlink 正規化。

bootstrap（隨 A 封存，不修）：
- `tools.py:173-175, 206-207` binary 先於 receipt 寫入；`tools.py:177, 238` HTTPException 未攔截。
- `bootstrap.py:286-288` journal 先 unlink 再 verify，失敗後無法 recover；同區塊覆寫所有錯誤標籤。
- `launch.py:109` 遞迴檢查不涵蓋 shim；`launch.py:64-78` DEFERRED 時 state 目錄無上限成長。
- `guardian.py:61-77` 30 秒放棄後 lease 卡在 ARMED。
- `path-integration.py:58` owned block 必須是 rc 檔結尾。
- `acquire.py:57` 硬編 codex profile、scanner 取自呼叫端 PATH。
- `README.md:127-131, 136-144` 與程式碼相反。

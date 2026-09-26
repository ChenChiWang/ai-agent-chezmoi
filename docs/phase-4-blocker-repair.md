# Phase 4 — enrollment 與 reader evidence 最小修復

> Current requirement (2026-09-25): [agent-driven memory checkpoints](sync-v2.md#agent-driven-memory-checkpoints-2026-09-25)
> replace the goal of pre-CLI automatic family tracking. Bootstrap is separate from
> daily sync. The material below is retained historical research/status, not current
> authorization to continue guardian/retirement work. Existing barriers/tests remain;
> the historical loading gate is still BLOCKED. No production deployment or 4H.


最新狀態（2026-09-25）：本次只做 family retirement 程式稽核、既有隔離測試與文件更新。
下方原修復紀錄保留；本次提案見第 4 節。**沒有新增 family tracking 實作，loading gate 仍 BLOCKED。**

本輪沿用已接受的 generation cohort／barrier，僅處理兩個已重現 blocker 及相關
regression／入口稽核。**Enrollment 一致性已修復；forked-family retirement 仍 BLOCKED，
loading gate 不宣告 PASS。** 不移除 cohort、不使用短期 lease、hooks、hot reload、
自訂 snapshot discovery 或另一套 loading 模型。

沒有修改 production/private dotfiles，沒有 public/private commit/push，沒有執行 4H。
測試中的 Git commits/pushes、metadata 損壞與程序終止均限於 disposable fixtures。

## 1. Enrollment 中斷一致性：根因與修復

修復前，`bootstrap.apply` 依序寫入 receipt、移除 journal，才呼叫 `enroll_cohort`。
在最後一步中斷會留下「receipt 存在，但沒有有效 barrier」；`verify_receipt` 只驗證
mapped files，重跑也可能直接回傳 `NO_CHANGES`。先前隔離 probe 已重現此狀態。

現在採取同一協定內的以下修正：

1. 先建立並持久化既有 bootstrap journal，再建立 barrier，之後才寫入 targets 與 receipt。
2. 初次 handoff 同時持有 legacy mkdir barrier 與新 kernel flock，直到 receipt／journal
   完成；已存在的 mutex inode 不會被替換。Marker 發布後，新 controller 也不能搶先進入。
3. Barrier 的 mutex、owner、marker 與目錄以 `fsync` 持久化。File replacement 與新增
   journal 也 flush parent directory。既有 enrollment、rollback 及 `NO_CHANGES` 重跑
   會重新驗證／flush barrier；不能把上次失敗的 fsync 當成成功。
4. Receipt 驗證同時檢查 marker、legacy owner、mutex、external state binding、目前
   receipt 與 journal。任何缺失／損壞／pending journal 都不能用既有 receipt 取得 readiness。
5. 正常 v2 write／activation 必須通過同一 readiness gate。Bootstrap 的 pending-state
   權限僅用於受控初次部署／規劃／rollback，仍需 common lock、零 readers、原有 plan
   approval、source/index/target/backup 驗證。
6. Handoff 已發布 owner、但尚未寫 marker 時中斷，approved rollback 可在取得相同
   kernel lock 後，僅以 journal 綁定的 roots 補上 marker。普通啟動／重跑不能擅自補造。
   初次部署 rollback 後保留 barrier、撤回 receipt；下一次 approved bootstrap 才建立設定。

| 中斷／故障位置 | 修復後證據 |
| --- | --- |
| cohort owner 已寫、marker 尚未寫 | 無成功 receipt；一般操作拒絕；approved recovery 後重新 plan/apply 成功 |
| marker 已寫 | journal 仍在，不能啟動／activation；recovery + rerun 成功 |
| barrier directory fsync 已完成 | 同上；尚未發布 receipt |
| 第一個 managed target 已寫 | partial deployment 被 journal 擋住；rollback + rerun 成功 |
| receipt 已寫 | barrier 先成立；pending journal 仍阻止 admission／activation |
| committed journal 已寫 | 未移除 journal 前仍 fail closed；rollback + rerun 成功 |
| journal 已移除 | 完整配置與 barrier 可驗證；重跑重新驗證後 `NO_CHANGES` |
| barrier fsync 回傳失敗 | 不發布 receipt、不略過 journal；recovery／rerun 再次 flush barrier |
| 舊缺口／marker、mutex、owner 被刪除 | receipt 驗證、重跑、行政指令啟動均拒絕，不能誤報 `NO_CHANGES` |

七個 hard-crash 子案例用 `os._exit(91)`，不依賴 exception/finally 清理；kernel lock
由 OS 在程序死亡後釋放，durable journal／legacy barrier 留下。Rollback 仍須原 plan
hash，且拒絕 active reader 與後續 edit。備份保留；已使用的 plan 不覆寫原 backup，
回報 `PLAN_ALREADY_USED_REPLAN`，需重新計畫。

範圍限制：這是已列出的 handoff／deployment 邊界與 fsync failure 驗證，不是實體斷電
實驗。若程序在 cohort handoff 證據建立前死亡，仍可能留下舊 mkdir writer lock；缺乏
安全 ownership/handoff 證據時不自動清除。不能把這類未完成狀態當成成功 enrollment。
既有損壞 receipt／barrier 且無可信 journal 的狀態同樣保持阻擋，不採用 force repair。

## 2. UNCERTAIN_FAMILY：已定位的證據缺口

真實 Claude 2.1.278 與 Codex 0.155.1 再次透過現有 neutral launcher／exec bridge／
guardian，在隔離 HOME 執行最小本機 discovery：兩者 exit 0、六個 skills 可見、managed
files 無 drift。Claude 僅 SDK initialization + EOF，Codex 僅本機 prompt-input；無登入
或成功模型請求。兩個 reader 都觀察到下列實際 kernel evidence：

```text
agent: claude / codex
observer_scope: root-process
fork_event_observed: true
root_exit_observed: true
exit_status_available: true
state: UNCERTAIN_FAMILY
missing:
  - descendant_identities
  - continuous_descendant_lineage
  - descendant_exit_observations
```

確切阻塞者是每個 agent reader 所監看的 root process 發出的 fork event，以及**缺失的
完整 descendants 證據**。目前沒有可靠的 child PID／start identity，不能命名真正阻塞的
子程序，也不能判斷它已退出或仍存活。診斷只保存 agent 名稱與 evidence 狀態；不蒐集
argv、prompt、environment、authentication 或 session payload。

安裝於本機的 macOS SDK `sys/event.h` 在 EVFILT_PROC 定義前明載：kernel fork hint
內有 child PID，但該 PID 不會傳入實際 kevent；同檔亦標註 NOTE_TRACK／NOTE_CHILD
自 macOS 10.5 起不受支援。可檢查
[SDK event.h](/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/sys/event.h:246)。
本 guardian 註冊的是 root process 的 NOTE_FORK／NOTE_EXIT，沒有完整 family observer。

對照測試將兩種真實 ground truth 分開：

| 受控 fixture | Harness 知道的事實 | Guardian 取得的證據與結果 |
| --- | --- | --- |
| 無 fork 的 leaf 正常退出 | 同一 exec PID 完整結束 | 連續 root watch、無 fork、kernel exit；可退休自己的 lease |
| fork 後父程序 `waitpid` 回收 child，再正常退出 | Child 確實 exit 0 且已被 reap | root fork + root exit；仍缺 descendants 證據，保留 UNCERTAIN_FAMILY |
| fork 後 root 正常退出，延遲 child 仍存活 | Harness 確認其受控 child 仍存活 | 相同類型缺失證據，保留 UNCERTAIN_FAMILY；writer／same-boot recovery 被拒絕 |
| observer 被終止，reader 仍存活／之後退出 | 連續觀察已中斷 | 保留 lease，不以 PID 消失或 lease 年齡清除 |

已回收 child 與仍存活 child 對目前 guardian 都只提供 root-level evidence。Harness 的
`waitpid` 結果不會注入 production recovery API，也不會拿來宣稱一般 native family 已
結束。此差異驗證了安全阻擋的必要性；不把 `UNCERTAIN_FAMILY` 當成已證實的誤報。

本輪的最小改動是加入可稽核的 missing-evidence 診斷與上述正反測試，**沒有新增不可靠
的退休判定**。既有機制無法證明 forked family 全部退出，故 blocker 2 尚未解除。
同一次開機仍不允許這些 records 授權 activation；實際新 boot 的既有 reviewed recovery
邊界保留，但本輪沒有 reboot，也不將其冒充普通 session recovery PASS。

## 3. 同一 barrier 的入口與覆蓋範圍

| 入口 | 覆蓋／限制 |
| --- | --- |
| Claude／Codex thin shim → `launch.py` | 同一 source/destination cohort；完整 receipt + barrier + journal 檢查，reserve／arm 成功後才 exec；兩個 agent 可並行讀 A |
| 行政指令、未啟用 agent 的已註冊 shim | 可省略 refresh，但不省略上述保護；保持 native argv、streams、TTY、signals、exit code，不加入 agent flags |
| offline、remote/scanner/dependency failure | 僅在完整 A 可驗證且能建立讀取保護時使用 A；guard failure 不啟動 native，保留不確定 reservation |
| v2 `sync.sh`／`sync-write.py` plan/in/push，以及轉發至 v2 的 dotfiles-sync | 同一 mutex／readers；可 prepare，reader 存在時 in/push 回傳 75、applied=false；pending enrollment 不能 activation |
| bootstrap apply／profile switch／re-enable／receipt update | 同一 barrier，零 readers 才能寫入；initial handoff 同時持有兩個 lock 協定 |
| bootstrap rollback/recover | 同一 mutex，允許檢查 pending journal，不允許繞過 readers；valid recovery plan 下 reader 阻擋測試通過 |
| `sync-migrate.py` apply／rollback | CLI 在讀取／執行 migration 前進入同一 `w.lock`；reader 存在時皆被阻擋 |
| Guardian retirement／reviewed recovery | 同一短 mutex，只處理 lease metadata，不 activate／push；不完整 deployment 不能解除保護 |
| 使用原 `.git/ai-agent-sync.lock` 的舊 v2 writer | 完成 handoff 後保留的 mkdir barrier 阻擋其進入 |
| `status` 等唯讀觀察 | 不取得 agent session 保護、不授權後續 activation；寫入仍須自己的 fresh validation／barrier |
| IDE 實際啟動上述 shim | 才能取得相同保護；GUI PATH 是否指向 shim 不可假定，kernel identity 無權限則 fail closed |
| IDE 內建／absolute vendor binary、直接執行原生 CLI | 不經 shim，**不受此協定保護**；本輪 native negative race 仍可重現 mixed revision |
| 手動 `chezmoi apply/update`、editor/cp、原始 v1 dotfiles-sync、直接改 Git／managed files | 不會自動參與此協定；不能據此宣稱安全或與 managed sessions 並行部署 |

因此，protected configuration loading 的保證只涵蓋 cooperating entrypoints；初次
production enrollment／profile activation 不能假定已有 raw CLI／IDE sessions 都已加入
cohort。Existing unmanaged readers 的 quiescence 仍是 production 前置條件。本輪不掃描
整個 HOME、不改寫 vendor commands、不新增 OS-wide interception，也不以這份覆蓋表
宣稱 production 可部署。Tool/PATH/statusLine 等其它 Phase 4 工作沒有在本輪擴張。

## 最小實作 diff 與測試證據

本輪程式修改限於四檔，沒有更換 loading 模型：

- [bootstrap.py](../bootstrap/bootstrap.py)：journal/barrier/receipt 排序，readiness binding，
  recovery handoff、重新 flush、已使用 plan 的備份保護。
- [sync-write.py](../examples/chezmoi/.chezmoitemplates/ai/shared/scripts/sync-write.py)：
  physical barrier validation、durable file/directory flush、handoff 鎖持有、pending-state
  readiness gate；正常 activation 不能略過 receipt 檢查。
- [launch.py](../bootstrap/launch.py)：所有已註冊 shim invocation 的 admission，行政／
  inactive 僅略過 refresh，並將 agent 名稱記入 reader 診斷。
- [guardian.py](../bootstrap/guardian.py)：明列 root-only 證據與 missing descendants evidence；
  不改變 forked-family 的 fail-closed retirement 規則。

| 測試 | 結果 |
| --- | --- |
| `tests/test-enrollment.py` | 8 PASS，含 7 個 hard-crash 子案例、fsync failure、corrupt barrier、valid rollback + reader、guard failure |
| `tests/test-guardian.py` | 6 PASS，含真正 reaped child 與延遲存活 child；不確定狀態保持阻擋 |
| `tests/test-cohort-integration.py` | 6 PASS，含 shell in、直接 v2 in/push、migration apply/rollback、profile barrier |
| `tests/test-bootstrap.py` | 24 PASS；行政／inactive／並行 reader 另有 3 項 targeted recheck PASS |
| `tests/test-layout.py` | 61 PASS，保留 nested HOME source、migration/write/rollback/scanner/scope regression |
| `tests/test-loading-races.py` | 5 PASS；未保護 reader 的 real engine mixed revision 仍可重現 |
| `tests/test-generation-cohort.py` | 11 PASS；仍是 protocol model，不替代 guardian evidence |
| `tests/test-native-guardian.py` | 兩 agent discovery／六 skills PASS、無 managed drift；兩者 family retirement BLOCKED |
| `tests/test-native-config-race.py` | 原生 unprotected negative control 仍讀到 B/A；cohort model control 讀到 A/A、B/B |
| Gitleaks 8.30.1 | 本輪四個 implementation files，neutral staged filenames，exit 0／零 findings |
| Python syntax／diff whitespace | PASS |

Mixed-revision assertions 沒有被刪除或弱化；僅移除 test harness 的重複 outer lock，
因 `launch.attempt` 現已自行持有 coordination lock。Native model 測試明確標示其未驗證
production guardian，避免把 model completion proof 當成 native family retirement。

以上 tests 合計 121 個 suite cases，不重複計算 targeted rerun；native probes 另列。
成功模型請求、authentication、實體斷電與實際新 boot recovery 均非本輪 PASS 項目。
**完成本輪修復／診斷與 review 後停下；loading gate 維持 BLOCKED。**


## 4. Family retirement 可行性 review（2026-09-25；尚未批准實作）

### 實際程式與證據缺口

本次逐一核對實作，沒有以文件中的模型測試替代 production guardian：

| 程式位置 | 實際行為／缺口 |
| --- | --- |
| `bootstrap/guardian.py:45` `identity` | root／observer 有 boot UUID、PID、start time；沒有 descendants 的穩定身分表。PID 單值不足以抵抗 reuse。 |
| `guardian.py:80–100` `observe` | 只為 root 建立一個 PROC filter，fork 只累積成 boolean；沒有 parent→child 邊、grandchild／double-fork／reparent／exec 延續紀錄。 |
| `guardian.py:102–121` | root EXIT 後，forked 一律保存 UNCERTAIN_FAMILY，再 return／close queue。沒有等待或監看 descendants EXIT；root exit status 不是 family completion。 |
| `guardian.py:124–146` `arm` | ready ACK 證明 root watcher 已 armed；helper.wait 只回收啟動 observer 的中介 helper，沒有等待 native children。 |
| `guardian.py:149–172` `recover` | 同 boot 只接受 EXITED_LEAF + fork_seen=false，或 OS 證實不同 boot。missing 清單是診斷，不是可提交的 family certificate。 |
| `bootstrap/launch.py:165–180` | 同 mutex 下驗證配置、保存 RESERVED、arm、保存 ARMED，再 exec；不是完整 family observation handshake。 |
| `sync-write.py:652,770` | 任何 reader record（含 RESERVED／不確定／損壞）皆阻擋 writer；沒有依年齡或 PID 消失自動退休。 |

缺少的證據是：(1) 每個 descendant 的不可混淆 incarnation 身分；(2) 從受保護 root 到
全部 descendants 的連續建立與 exec lineage，包含父程序先退出或脫離 process group；
(3) 每一成員的 kernel EXIT 與 family closure；(4) 觀察 epoch、事件完整性／缺口與可驗證的
最終完成紀錄。現有 observer crash 會留下 record，但其 stderr 被導向 DEVNULL，record
可能停在 ARMED；不能宣稱目前已有完整的 crash 原因診斷或重啟後補回事件能力。

正常退出仍 UNCERTAIN 的直接原因不是已確認的活 child，而是 root 曾 fork、guardian
無法區分 descendants 已退出與仍活著。當前無可靠 child identity，不能憑空命名阻塞的
程序。Root-only watch 在 root exit 後停止，更不可能靠等候取得晚到 child exit 證據。

### 最小方案的可行性與漏接空窗

**結論：在現有無特權 Python/libproc/kqueue observer、不改 native 行為的條件下，尚未找到
能可靠退休一般 forked family 的小範圍修法。保留安全阻擋，不宣告 loading PASS。**
這是對已檢查機制的結論，並非宣稱所有 macOS 技術都不可能。

本機 macOS 26.6.2／SDK 26.5：`sys/event.h:246–254` 明示 fork child PID 不傳入實際
kevent；`:356–362` 明示 NOTE_TRACK/TRACKERR/CHILD 不受支援。
因此「收到 root fork 後用 libproc/ps 找 child，再掛 child kqueue」無法封閉
fork→grandchild→parent exit/reparent→attach 的空窗；重複快照或縮短 polling interval
也不產生缺失的事件。Guardian 不是那些 descendants 的父程序，現有 helper.wait 亦
無法取得它們的 waitpid 證據。Process-group 空集合、繼承 pipe EOF／FD lock 都沒有原生
程序必須保持群組或 FD 的保證，不能用來取代 lineage，更不能改動 TTY／signals 取得 PASS。

若另行批准擴大「證據來源」，可評估保留 cohort/admission/writer 模型、僅更換 observer
backend；**這是有條件候選，不是已驗證可直接實作的修補**：

- 本機 SDK 的 Endpoint Security `es_new_client` 可訂閱 FORK／EXEC／EXIT。
  `ESMessage.h:441–446` 的 fork.child 提供 child process，message.process 提供事件發起者；
  exec 的 process/target 必須連接起來，不能把更新後的 pidversion 當成無關程序
  （同檔 `:232–243`）。用 kernel audit identity + boot、parent→child 邊與 EXIT 建立 ledger，
  不能只保存 PID／argv 或相信外部 harness 的完成宣告。
- 必須先完成訂閱、根身分綁定與 ready ACK，才允許 native exec；observer 必須繼續存在
  至整個 family 結束。當前 detached guardian 不是 agent 的祖先，不能假定只監看 observer
  自己 descendants 的 API 能套用現有 topology。
- `seq_num`／`global_seq_num` 可偵測 drop，但連續序號不等於已收到全部最後事件。
  尚須證明 fork/exec/exit 的處理次序與 terminal fence：不得在 child birth 尚未處理時因
  已知 live set 暫時為空而退休。SDK 只明示 handler 按 delivery order 串行；本次沒有
  證明它足以構成 family closure。Mute/filter 規則、事件版本、posix_spawn、reparent
  同樣須驗證。任何空窗／drop／無法證明 closure 都保留 lease。
- 取得完整證據後，才在既有 mutex 下核對 token、root incarnation、generation、observer
  epoch 及完整 terminal ledger，持久化完成紀錄，再退休。Crash 若發生在完成紀錄之前，
  同 boot 不自動 recovery；只有可信 durable completion 才能重跑退休。重新 snapshot
  不補足 observer 死亡期間的歷史。這允許 crash 後保持 BLOCKED，不承諾透明自癒。

新增需求必須先批准：本機可用的 system-wide `es_new_client` 需要 Apple 授予的
`com.apple.developer.endpoint-security.client` entitlement、相應簽章／provisioning、root
執行及使用者 TCC Full Disk Access。需要新的 native observer helper 與其受驗證 IPC／封裝，
不是 pip 安裝即可解決。若希望 observer 中斷後仍連續追蹤，需要另評估持續存活的 collector；
那將明顯擴大架構，本提案不要求或部署 daemon。沒有申請 entitlement、提升服務權限、安裝
套件或變更 TCC／SIP。

Apple 亦列出 `es_new_descendants_client`，其文件索引明示仍需同一 entitlement、但不需
root。**不把 system-wide client 的權限要求泛化成所有 ES API。** 本機 SDK 沒有此宣告，
本輪未確認它在本環境可用，也未驗證它的 subtree coverage／observer topology 是否能保持
目前 native exec 與 TTY 語意；不能當成現有小修補或偷偷切換 supervision 架構。

官方參照（權限與事件能力，不代表本專案 qualification）：
[ES client](https://developer.apple.com/documentation/endpointsecurity/client)、
[entitlement](https://developer.apple.com/documentation/BundleResources/Entitlements/com.apple.developer.endpoint-security.client)、
[Apple ES 說明：Full Disk Access](https://developer.apple.com/videos/play/wwdc2020/10159/)、
[事件遺失計數](https://developer.apple.com/documentation/endpointsecurity/es_message_t/seq_num)、
[descendants client](https://developer.apple.com/documentation/endpointsecurity/es_new_descendants_client(_:_:))。

### 若另獲批准，最小修改範圍

- `bootstrap/guardian.py`：證據 backend、family ledger、完成紀錄、缺失原因、retirement/recovery
  validation；root-only leaf 路徑與不確定阻擋保留。
- `bootstrap/launch.py`：ready ACK 綁定 family observer epoch／root／generation；不改 native
  argv／stdio／PID／TTY／signals 或 CLI discovery。`launcher.py`／bootstrap 工具封裝只在
  新 helper 需要版本與 hash binding 時修改；新增 native helper 尚未批准。
- `sync-write.py` 的 writer/readers barrier、bootstrap enrollment 修復保持原樣；若 evidence
  finalization 需要耐久寫入，沿用既有 atomic/fsync helper，不能新增繞過 readers 的入口。
- `tests/test-guardian.py`／`test-native-guardian.py` 擴充實際 evidence backend 的驗收；保留
  enrollment、cohort integration、mixed-revision、crash 與 native compatibility tests。
  本次只提出範圍，沒有新增或改寫測試／implementation。

### 最小驗收矩陣（待實作；不是本次 PASS）

| 情境 | 必須觀察的證據與結果 |
| --- | --- |
| root、child、grandchild 都退出；包含先 reap child 及父先退出 | backend 自己收到完整 lineage、incarnation、每個 EXIT、無缺口 closure；才可退休。Harness waitpid 只作 oracle，不作 recovery 輸入。 |
| root 退出，延遲 child／double-fork detached grandchild 仍活 | record 保留；v2 in/push、bootstrap/profile switch/rollback、migration apply/rollback 都不得 activate；最後 descendant 確實退出且 closure 完成後才退休。 |
| 快速 spawn/exec/exit、parent reparent、PID reuse、事件排隊／drop | 不能認錯 incarnation 或在暫時空集合時退休；可證明則正常完成，缺證據則明確 BLOCKED。 |
| watcher/guardian 在 ready 前後、root EXIT 前後、完成紀錄前後中斷 | 留下 RESERVED/ARMED/uncertain protection；回報 observer identity/epoch、最後證據及缺失原因，不收集 argv/env/credentials；重啟不得靠 PID 不存在或時間清除。僅 durable 完整 certificate 可安全重跑退休。 |
| 兩 agent 同時持有 A，其中一個退出，另一個仍活 | 可並行使用 A／prepare B，但不得 activate；最後一個 family 被可靠退休後 fresh validation 才 activate B。 |
| enrollment 7 crash points、fsync failure、receipt/barrier 損壞 | 維持原 fail-closed／approved rollback + rerun 行為；無 receipt-only shortcut。 |
| 原生 CLI compatibility 與 mixed-revision | 原 argv、空參數、stdin/out/err、PID、exit code、TTY、signal/job control 保持；既有負面 race 仍有效，受保護 readers 不讀 mixed generation。 |

入口邊界不變：只涵蓋經已註冊 launcher 成功 admission 的 CLI 與遵守同一 barrier 的 writers。
直接 native absolute path／未經 launcher 的 CLI **未涵蓋**；VS Code extension **未 qualification**，
不能因 PATH 裡有 shim 就假定涵蓋。即使 extension 確實呼叫 shim，也只涵蓋該 admitted
process family，不包括 extension host 自行讀取設定或其他既有程序。透過 IPC 委託既有
service／launchd 的工作不是必然的 descendant，亦不在 lineage 保證內。手動 chezmoi、
editor 或直接 Git write 不受 barrier 約束。未管理 readers 的初始 quiescence 未自動解決。

### 本次重跑證據

本次既有隔離測試：guardian 6 PASS（14.900s）、enrollment 8 PASS（43.010s）、
loading-races 5 PASS（4.641s）。Guardian 明確重現：leaf 可退休；已回收 child 與仍活 child
都 UNCERTAIN；observer death 不清除 lease。這些 PASS 證明現行保護與已知限制，**不代表
一般 family retirement PASS**。本次沒有重跑模型請求或 native agent discovery；前節
121 cases/native probes 是上一輪歷史結果。另重跑 cohort-integration 6 PASS（25.938s），
覆蓋 v2 in/push、shell in、migration apply/rollback 與 profile barrier。本次共 25 個既有
suite cases PASS，沒有新增測試或弱化原 assertions。

本次停止於 design review；不安裝依賴、不實作 tracking、不新增 Phase、不部署 production、
不修改 private dotfiles、不 commit/push、不執行 4H。Enrollment 修復與既有測試保留。

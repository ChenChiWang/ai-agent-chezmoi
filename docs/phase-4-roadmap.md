# Phase 4 — Bootstrap & Multi-machine roadmap

> Current requirement (2026-09-25): [agent-driven memory checkpoints](sync-v2.md#agent-driven-memory-checkpoints-2026-09-25)
> replace the goal of pre-CLI automatic family tracking. Bootstrap is separate from
> daily sync. The material below is retained historical research/status, not current
> authorization to continue guardian/retirement work. Existing barriers/tests remain;
> the historical loading gate is still BLOCKED. No production deployment or 4H.


**最新本輪 scope：沿用 cohort/barrier，只修復 enrollment 一致性、定位 reader evidence
缺口並驗證原有 races／write entrypoints；不擴張 loading 架構。**

Enrollment ordering／durability／rerun 已修復並通過中斷驗證。真實 Claude/Codex 的
root-only guardian 仍缺完整 descendants evidence，故 family retirement 與
**loading gate 仍 BLOCKED**；不宣告 Phase 4B–4G PASS。已完成本輪 review 後停下。
目前證據與覆蓋範圍見 [兩個 blocker 的最小修復](phase-4-blocker-repair.md)。

較早連續 4B–4G 授權仍保留為歷史；本輪依最新窄化範圍，不繼續工具、PATH、statusLine
或其他階段。沒有 production/private 修改、public/private commit/push 或 4H。

| Phase | 建議範圍 | Gate / status |
| --- | --- | --- |
| 4A | 三 profile bootstrap、安全邊界、獨立 authentication、rerun/upgrade、切換、re-enable 與兩 agent launch-sync 設計 | Accepted |
| 4B | public toolchain lock／probe／plan、first-deploy transaction、三 profile/repository scope、獨立 agent gates、switch/re-enable、launch-sync/standing policy/reader barrier | 已授權；隔離實作/測試完成一輪，**NOT PASS / review blockers** |
| 4C | 假 private repo、新機／重跑／launch-sync／離線／競爭／故障／credential sentinels fixtures | 已授權隔離驗證；完整 gate 待執行 |
| 4D | public security/recovery/idempotence review、對照 4A matrix | 已授權；目前 safety finding 未解決 |
| 4E | 隔離 macOS fresh-machine tool/deployment validation | 已授權隔離範圍；不修改 production；登入保持外部流程 |
| 4F | 隔離 native launch-triggered in、statusLine/runtime、rerun/adoption | 真實 guardian 下兩 agent discovery／六 skills PASS；family retirement BLOCKED，statusLine 未 qualification |
| 4G | 三 profile 雙向切換／重新啟用、隔離 mixed-profile refresh／sync、upgrade/recovery、overall review | 目前 worktree overall review 已完成，結論 BLOCKED；完整 4B–4G acceptance 未完成 |
| 4H | 真實第二台電腦部署 | 未授權；本輪不得執行；commit/push 亦未獲授權 |

[4A 完整設計](phase-4-bootstrap-design.md) 是已接受的前置契約。
其中 first deployment、full-repo history vs profile targets、tool lock 及 statusLine portability
均為實作 prerequisites；既有 Phase 3 PASS 不代表上述新機流程已測試。

歷史 4A 唯讀 launch audit：Claude/Codex 都未具備 launch-sync；因此 4B 為兩邊共用
controller，而不是只補 Codex。所選 agent 的安裝/auth/subscription/model 與另一邊獨立。
本輪 bootstrap/tool installation 僅於 disposable fixture 執行；private network acquisition
採 fake transport 驗證，沒有取得或修改 production private repo。
目前停在已記錄的 native guardian 的 descendants evidence 缺口；4B–4G 的授權仍有效，尚未宣告完成。

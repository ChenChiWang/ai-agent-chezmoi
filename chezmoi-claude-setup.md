# 任務:用 chezmoi 建立 Claude Code 設定的跨平台同步(Mac / Windows / Linux)

> 本文件交給 Claude Code 執行。請逐步進行,每個階段完成後回報結果再繼續。
> 目前這台機器是 **Windows**(第一台/主機器),之後 Mac 和 Linux 會用
> 本文件最後的「其他機器接入」章節加入。

## 目標

把 `~/.claude/` 中**可攜的設定**納入 chezmoi 管理,推送到使用者的
GitHub private repo,並預先處理好跨平台(換行符、路徑、hooks 指令)問題,
讓 Mac / Linux 之後能一行指令接入。

## 絕對規則(不可違反)

1. **任何 token、API key、credentials 檔案都不得進入 git repo。**
   commit 前必須檢查暫存內容,發現疑似 secret 立即停止並回報使用者。
2. **不納管以下項目**:`~/.claude.json`(含絕對路徑與可能的 token)、
   `~/.claude/projects/`、`cache/`、`history.jsonl`、`sessions/`、
   `file-history/`、`shell-snapshots/`、任何 `credentials*`、`*.key`、
   `*.pem`、`*.token`、`*.log`。
3. **不執行 `git push --force`**,不刪除使用者既有檔案。
   需要覆蓋或修改既有檔案時,先備份並告知使用者。
4. 需要使用者提供資訊時(GitHub repo URL、確認 secrets 處理方式),
   **暫停並詢問**,不要猜測或自行建立 repo。

---

## 階段 0:環境檢查

依序確認並回報:

```powershell
chezmoi --version    # 未安裝則:winget install twpayne.chezmoi
git --version        # 未安裝則:winget install Git.Git
ssh -T git@github.com   # 確認 SSH 可連 GitHub(回應含使用者名稱即成功)
```

- 若 chezmoi 或 git 剛安裝,提醒使用者可能需重開終端機讓 PATH 生效。
- 若 SSH 未設定,引導使用者建立 key 並加到 GitHub,**等待完成後再繼續**:
  ```powershell
  ssh-keygen -t ed25519 -C "使用者email"
  Get-Content ~\.ssh\id_ed25519.pub | Set-Clipboard
  ```
- **向使用者詢問**:GitHub private repo 的 SSH URL
  (格式 `git@github.com:USER/dotfiles.git`)。若尚未建立,請使用者先到
  GitHub 建一個空的 **private** repo。

## 階段 1:盤點現有設定

列出 `~\.claude\` 下實際存在的項目,分類回報:

- 預計納管:`CLAUDE.md`、`settings.json`、`settings.local.json`、
  `commands/`、`agents/`、`skills/`、`hooks/`
- 預計排除:規則 2 的清單
- 其他未預期的檔案/目錄:列出並詢問使用者是否納管

同時**讀取 `settings.json`**(若存在),檢查:

- [ ] 是否有 hooks / statusLine 等執行外部指令的欄位 → 記下,階段 4 要轉模板
- [ ] 是否有寫死的絕對路徑(`C:\Users\...`)→ 記下,階段 4 要參數化
- [ ] 是否有任何疑似 token 的字串 → 立即回報使用者,討論改用環境變數

## 階段 2:初始化 chezmoi 並納管

```powershell
chezmoi init

chezmoi add ~\.claude\CLAUDE.md
chezmoi add ~\.claude\settings.json
chezmoi add ~\.claude\settings.local.json
chezmoi add -r ~\.claude\commands
chezmoi add -r ~\.claude\agents
chezmoi add -r ~\.claude\skills
chezmoi add -r ~\.claude\hooks
```

不存在的項目跳過即可,回報實際納管清單。

## 階段 3:跨平台防護(在第一次 commit 前完成,順序不可調換)

在 chezmoi source 目錄(`chezmoi source-path` 取得路徑)中:

1. 建立 `.gitattributes`,內容:
   ```
   * text=auto eol=lf
   ```
2. 設定 git(詢問使用者是否接受全域設定;若不接受,改為只設在此 repo):
   ```powershell
   git config --global core.autocrlf input
   ```
3. 建立 `.chezmoiignore`,防止意外納入排除項:
   ```
   .claude/projects
   .claude/cache
   .claude/history.jsonl
   .claude/sessions
   .claude/file-history
   .claude/shell-snapshots
   **/credentials*
   **/*.key
   **/*.pem
   **/*.token
   **/*.log
   ```

## 階段 4:平台差異轉模板

根據階段 1 盤點結果:

- 對含有外部指令或絕對路徑的檔案執行
  `chezmoi chattr +template <檔案>`,然後編輯,分流格式:
  ```
  {{ if eq .chezmoi.os "windows" }}Windows 版內容{{ else }}Unix 版內容{{ end }}
  ```
- 路徑一律改用 `{{ .chezmoi.homeDir }}/...`,分隔符統一用 `/`。
- hook 腳本若可行,建議改寫為 `node` 或 `python` 執行的跨平台腳本,
  減少模板分流(先詢問使用者是否要這樣重構)。
- 完成後執行 `chezmoi diff` 確認模板展開結果正確,
  再 `chezmoi apply --dry-run` 驗證無誤。

## 階段 5:Secret 掃描與首次推送

1. 在 source 目錄執行 secret 掃描:逐檔檢查是否有
   `sk-`、`ghp_`、`github_pat_`、`token`、`api_key`、`password` 等
   pattern 的可疑值。發現任何一項 → **停止並回報**,不得 commit。
2. 掃描通過後:
   ```powershell
   chezmoi cd
   git add -A
   git status          # 向使用者展示將 commit 的完整檔案清單,等待確認
   git commit -m "Initial Claude Code config (Windows)"
   git branch -M main
   git remote add origin <使用者提供的 SSH URL>
   git push -u origin main
   exit
   ```

## 階段 6:驗證與交付報告

1. `chezmoi verify` 確認狀態一致。
2. 向使用者回報:納管了哪些檔案、轉了哪些模板、排除了哪些項目、
   repo URL、以及下方接入指令。

---

## 其他機器接入(Mac / Linux — 屆時把本章節連同 repo URL 交給該機器的 Claude Code)

```bash
# 安裝:brew install chezmoi(Mac)/ apt 或 snap install chezmoi(Linux)
# 確認 GitHub SSH key 已設定,然後:
chezmoi init --apply git@github.com:USER/dotfiles.git
```

接入後驗證清單:

- [ ] 安裝 Claude Code 並執行 `claude` 登入(憑證不同步,每台各自登入)
- [ ] `/permissions` 顯示正常
- [ ] 自訂 slash commands 出現在 `/` 清單且可執行
- [ ] `/agents` 顯示自訂 agents
- [ ] 若有 hooks:觸發一次確認無平台錯誤(若報錯,檢查模板分流)
- [ ] 設定該機器的環境變數(MCP token 等,不在 repo 內)

## 日常同步(所有機器通用)

```
拉最新:chezmoi update
推修改:chezmoi re-add && chezmoi cd && git add -A && git commit -m "update" && git push && exit
```

穩定使用一段時間後,可再請 Claude Code 加上自動 pull/push 的
shell 包裝函式(開 claude 前自動拉、結束後自動推)。

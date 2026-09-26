# 在 Windows 上透過 WSL 上線

> 對象：Windows 使用者，以及被指派協助上線的 agent。
> 原生 Windows（Git Bash、MSYS2、Cygwin）無法執行引擎，preflight 會回報 `FAIL platform`。
> 在 Windows 上唯一的做法是 WSL2：引擎、Claude Code 與 Codex 全部在 WSL 內執行。

WSL 內的上線流程跟 Linux 相同（`setup/AGENT-SETUP.md` 的 Step 1～7）。這份文件只記錄 WSL
特有、而且實際上線時會踩到的地方。

## 1. 準備 WSL

**用一般使用者，不要用 root。** 有些 WSL 安裝的預設使用者是 root。請在 WSL 內以 root 身分建立
使用者，並設成預設：

```sh
adduser NAME
usermod -aG sudo NAME
printf '\n[user]\ndefault=NAME\n' >> /etc/wsl.conf
```

然後在 PowerShell 執行 `wsl --terminate <distro>` 重新啟動。這會結束該 distro 內所有正在
執行的程式。

**所有東西都放在 Linux 檔案系統上。** 公開 repo 的 clone、chezmoi source、HOME、參數檔和
plan_dir 都要在 WSL 的 ext4 上（例如 `~/src`、`~/.local/share/chezmoi`），不能放在
`/mnt/c`。`/mnt/c` 是 Windows 磁碟，`chmod 600` 在上面會變成 `777`，參數檔和 plan_dir
的權限要求因此無法成立。

## 2. 工具

| 工具 | WSL 上的做法 |
| --- | --- |
| Git 2.45+ | Ubuntu 24.04 內建 2.43，版本不夠。由使用者用 sudo 加入官方 PPA：`add-apt-repository -y ppa:git-core/ppa && apt update && apt install -y git`。agent 不執行 sudo |
| chezmoi 2.71 | preflight 提示的 `brew install` 不適用。改用官方安裝腳本並指定已測版本，裝到 `~/.local/bin`（會核對官方 SHA-256）：先把 `https://get.chezmoi.io` 下載成檔案，再執行 `sh install.sh -b ~/.local/bin -t v2.71.1` |
| Python 3.9+ | Ubuntu 內建即可 |
| Gitleaks 8.30.1 | `sh setup/install-gitleaks.sh`，與 Linux 相同 |

Ubuntu 的 `~/.profile` 在 `~/.local/bin` 存在時才會把它加進 PATH，而且只有 login shell 會讀
`~/.profile`。所以裝完要開新的終端機；從外部呼叫時要用 `bash -l`。

## 3. Claude Code 與 Codex 要裝在 WSL 內

WSL 預設會把 Windows 的 PATH 附加進來，所以 WSL 內的 `claude` 可能解析到 Windows 版，例如
`/mnt/c/Users/<user>/AppData/Roaming/npm/claude`。Windows 版管理的是 Windows 端的
`~/.claude`，不是 WSL 的 HOME。preflight 在這種情況會回報：

```
WARN claude: Windows binary at /mnt/c/... -> install Claude Code inside WSL (docs/wsl.md)
```

在 WSL 內用官方 native installer 安裝 Claude Code（裝到 `~/.local/bin/claude`，不需要 sudo），
然後確認 WSL 版排在前面：

```sh
which -a claude     # 第一行應為 ~/.local/bin/claude
```

WSL 版要另外登入：在 WSL 終端機執行一次 `claude`。Codex 同理要裝在 WSL 內，但目前尚未在 WSL
上驗證。

## 4. SSH

WSL 的 `~/.ssh` 跟 Windows 的是分開的。建議在 WSL 產生一把新的 key，不要複製 Windows 的私鑰：
同一把私鑰存在兩處，出事時也沒辦法分開撤銷。

- known_hosts：照 `setup/AGENT-SETUP.md` Step 3，先比對 GitHub 官方公布的指紋，再寫入。
- key：`ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519`。引擎以 `BatchMode` 連線，所以 key
  如果有 passphrase，就必須事先載入 ssh-agent。
- 公鑰要由使用者自己登錄到 GitHub。

## 5. 上線

接著照 `setup/AGENT-SETUP.md` 走 4A（或第一台機器走 4B），然後 Step 5～7。預期結果跟其他平台
相同：`doctor` 沒有 FAIL、`status` 回傳 `NO_CHANGES`、`check` 回傳 `UP_TO_DATE`。

## 6. 已知限制

- **兩套 Claude 設定。** Windows 端的 `~/.claude` 不受 v2 管理。同一台機器上如果 Windows 和
  WSL 都在用 Claude Code，只有 WSL 那套會同步。
- **statusLine 需要 Node。** 如果 synced 的 `settings.json` 用 `npx` 啟動 statusLine，
  WSL 內也要有 Node；Claude Code 本身（native 版）不需要 Node。
- **從 Windows 端的 agent 驅動 WSL。** PowerShell 傳給 `wsl -- bash -c '...'` 的引號會被
  改寫，指令常常只執行一半。請把步驟寫成腳本檔，再用 `wsl -d <distro> -- bash -l /mnt/c/.../script.sh`
  執行；`-l` 會讀 `~/.profile`，`~/.local/bin` 才會在 PATH 上。

## 驗證紀錄

| 日期 | 環境 | 結果 |
| --- | --- | --- |
| 2026-09-26 | Windows 11 Pro 10.0.26200、WSL2 Ubuntu 24.04.1（kernel 6.18.33.2-microsoft-standard-WSL2）；git 2.55.0（PPA）、chezmoi 2.71.1、Python 3.12.3、Gitleaks 8.30.1、Claude Code 2.1.283；profile `claude`，repository profile `claude-codex`，路徑 4A | preflight 0 fail；`doctor` 13 ok／0 warn／0 fail；`status` `NO_CHANGES`；`check` `UP_TO_DATE`。Codex 與 `tests/session-acceptance.sh` 未驗證 |

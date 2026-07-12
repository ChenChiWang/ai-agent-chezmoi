[English](./README.md) | **繁體中文**

# Claude Code 設定跨平台同步(chezmoi)

用 [chezmoi](https://www.chezmoi.io/) 把 `~/.claude/` 的**可攜設定**跨 **Windows / macOS / Linux** 同步的完整指南與範本。

只同步「設定與能力」;所有含 token、絕對路徑、對話紀錄與快取的「狀態」一律排除,不進 git。

## 這是什麼

- 📄 [`chezmoi-claude-setup.md`](./chezmoi-claude-setup.md) — **完整設定指南**,可直接交給 Claude Code 逐步執行(內含安全規則、跨平台防護、secret 掃描)
- 📁 [`examples/`](./examples/) — 可直接參考/複製的範本(排除規則、換行設定、CLAUDE.md、settings.json)

## 同步了哪些內容

| 項目 | 說明 |
|------|------|
| `~/.claude/CLAUDE.md` | 全域指示(語言、程式風格、git 規範) |
| `~/.claude/settings.json` | statusLine / TUI 等設定 |
| `~/.claude/skills/` | 自訂 skills |
| `~/.claude/commands/` `agents/` `hooks/` | 若有則一併納管 |

## 明確排除(不進 repo)

- `~/.claude.json`、`~/.claude/.credentials.json`(含 MCP token、OAuth 憑證)
- `projects/`、`sessions/`、`shell-snapshots/`、`file-history/`、`history.jsonl`
- `cache/`、`plugins/` 等機器本地快取

憑證與 MCP server token **每台機器各自設定**,不同步。範例見 [`examples/.chezmoiignore`](./examples/.chezmoiignore)。

## 快速上手

### 主機器(第一台)

把 [`chezmoi-claude-setup.md`](./chezmoi-claude-setup.md) 交給 Claude Code,依指南跑完階段 0～6,即可把設定推上你自己的 GitHub private repo。核心指令:

```bash
chezmoi init
chezmoi add ~/.claude/CLAUDE.md ~/.claude/settings.json
chezmoi add -r ~/.claude/skills
# 加上 .gitattributes / .chezmoiignore(見 examples/)後 commit、push
```

### 其他機器接入

```bash
# macOS: brew install chezmoi   /   Linux: apt 或 snap install chezmoi
chezmoi init --apply git@github.com:YOUR_NAME/dotfiles.git
```

## 日常同步

```bash
chezmoi update        # 拉最新(git pull + 套用到 ~/.claude,一步到位)

chezmoi re-add        # 把 ~/.claude 的本機修改抓回 source
chezmoi cd && git add -A && git commit -m "update" && git push && exit   # 推出去
```

> chezmoi 不是即時同步工具,是「按需 pull / push」。多機使用請遵守**開工前先 `chezmoi update`、收工後 push**,即可避免分岔。

## 自動同步(dotfiles-sync skill)

可以讓 Claude Code **在對話中**自動完成同步,不必手動打指令。做法是一個內建 skill([`examples/dotfiles-sync/`](./examples/dotfiles-sync/)):

- **Session 開始 / Claude 開始讀 codebase 時** → 執行 `in`(`chezmoi update`)拉最新。
- **改完 `~/.claude` 設定 / 工作告一段落時** → 執行 `status`(顯示 diff + secret 掃描),**經你確認後**才 `push`。

skill 放在 `~/.claude/skills/`,所以會被 chezmoi 同步、每台機器行為一致。在你的 `CLAUDE.md` 加一段觸發規則,讓 Claude 在對的時機呼叫,例如:

```markdown
# Claude Code 設定同步
- session 開始時,用 dotfiles-sync skill 的 `in` 拉取最新設定。
- 改完 ~/.claude 設定後,用 dotfiles-sync:先 `status` 顯示 diff,經我確認後才 `push`。未確認前不得 push。
```

設計說明:同步**不是**在「關掉程式」的瞬間自動發生(那時已沒有 Claude 的回合)。而是在有意義的回合(session 開始、改完設定)執行,且每次 push 前都有人工確認。

## 安全提醒

- **任何 token / API key / credentials 都不得進 repo**,commit 前務必掃描
- 你自己的同步 repo 請開 **private**;本專案是公開的「範本 / 指南」,不含任何個人機密

## License

[MIT](./LICENSE)

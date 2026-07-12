**English** | [繁體中文](./README.zh-TW.md)

# Sync Claude Code settings across platforms (chezmoi)

A guide and templates for syncing the **portable parts** of `~/.claude/` across **Windows / macOS / Linux** with [chezmoi](https://www.chezmoi.io/).

Only your "settings and capabilities" are synced. Everything that holds tokens, absolute paths, chat history, or caches — the machine-local "state" — is excluded and never enters git.

## What's inside

- 📄 [`chezmoi-claude-setup.md`](./chezmoi-claude-setup.md) — a **complete setup guide** you can hand to Claude Code to run step by step (safety rules, cross-platform hardening, secret scanning included). *Written in Traditional Chinese.*
- 📁 [`examples/`](./examples/) — ready-to-copy templates (ignore rules, line-ending config, CLAUDE.md, settings.json)

## What gets synced

| Item | Description |
|------|-------------|
| `~/.claude/CLAUDE.md` | Global instructions (language, code style, git conventions) |
| `~/.claude/settings.json` | statusLine / TUI and other settings |
| `~/.claude/skills/` | Custom skills |
| `~/.claude/commands/` `agents/` `hooks/` | Managed too, if present |

## Explicitly excluded (never committed)

- `~/.claude.json`, `~/.claude/.credentials.json` (MCP tokens, OAuth credentials)
- `projects/`, `sessions/`, `shell-snapshots/`, `file-history/`, `history.jsonl`
- `cache/`, `plugins/` and other machine-local caches

Credentials and MCP server tokens are **configured per machine** and not synced. See [`examples/.chezmoiignore`](./examples/.chezmoiignore).

## Quick start

### First machine

Hand [`chezmoi-claude-setup.md`](./chezmoi-claude-setup.md) to Claude Code and follow stages 0–6 to push your settings to your own **private** GitHub repo. Core commands:

```bash
chezmoi init
chezmoi add ~/.claude/CLAUDE.md ~/.claude/settings.json
chezmoi add -r ~/.claude/skills
# add .gitattributes / .chezmoiignore (see examples/), then commit & push
```

### Onboard another machine

```bash
# macOS: brew install chezmoi   /   Linux: apt or snap install chezmoi
chezmoi init --apply git@github.com:YOUR_NAME/dotfiles.git
```

## Daily sync

```bash
chezmoi update        # pull latest (git pull + apply to ~/.claude, in one step)

chezmoi re-add        # pull local edits from ~/.claude back into the source
chezmoi cd && git add -A && git commit -m "update" && git push && exit
```

> chezmoi is not a real-time sync tool — it's pull/push on demand. For multiple machines, follow the rule: **`chezmoi update` before you start, push when you're done**, and you'll avoid divergence.

## Automated sync (dotfiles-sync skill)

You can let Claude Code handle the sync **in-conversation** instead of typing commands, via a bundled skill ([`examples/dotfiles-sync/`](./examples/dotfiles-sync/)):

- **On session start / when Claude reads the codebase** → it runs `in` (`chezmoi update`) to pull the latest.
- **After editing `~/.claude` settings / at a milestone** → it runs `status` (shows the diff + scans for secrets), asks you to confirm, and only then runs `push`.

The skill itself lives under `~/.claude/skills/`, so it is synced by chezmoi and works the same on every machine. Add a trigger to your `CLAUDE.md` so Claude invokes it at the right moments — for example:

```markdown
# Claude Code config sync
- On session start, use the dotfiles-sync skill's `in` to pull latest settings.
- After editing ~/.claude settings, use dotfiles-sync: `status` to show the diff,
  then `push` only after I confirm. Never push without confirmation.
```

Design note: sync is **not** automatic on process exit — there is no Claude turn at exit. Instead it runs at meaningful turns (session start, after config edits), with a human confirmation before every push.

## Security notes

- **No token / API key / credentials may ever enter the repo** — scan before every commit.
- Keep your own sync repo **private**. This project is a public *template / guide* and contains no personal secrets.

## License

[MIT](./LICENSE)

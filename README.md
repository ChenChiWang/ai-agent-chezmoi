**English** | [繁體中文](./README.zh-TW.md)

# Sync Claude Code settings across platforms (chezmoi)

A guide and templates for syncing the **portable parts** of `~/.claude/` across **Windows / macOS / Linux** with [chezmoi](https://www.chezmoi.io/).

The intended scope is portable settings and capabilities. Ignore rules are defense in depth: they do not guarantee that secrets cannot enter Git or remove already tracked data.

## Experimental Claude Code + Codex shared templates (v2)

[`examples/chezmoi/`](./examples/chezmoi/) adds one shared source for instructions,
skills and a neutral engine. v2 supports **offline `status`, approval plans, safe
`in`, and scoped `push`**. It requires explicit source/destination paths
and uses the bundled scanner adapter with **Gitleaks 8.30.1** on PATH and Python 3.9+.
Findings report only validated paths, rule IDs and line numbers. See the
[scanner contract and tests](./docs/secret-scanner.md).

Read [`docs/migration-v2.md`](./docs/migration-v2.md) before using it. This is an
development template; private migration and legacy caller cutover remain paused.
Read the [sync contract, approval and recovery guide](./docs/sync-v2.md).
Do not run `chezmoi init --apply` against this public repository or copy it over
your current agent configuration. Tests: `sh tests/test-render.sh` and
`sh tests/test-status.sh`; real scanner tests: `python3 tests/test-scanner.py`
and offline regression: `python3 tests/test-offline-status.py`; write/history tests:
`python3 tests/test-write.py` (real commits/pushes only in temporary local fixtures)
(Git with `--no-lazy-fetch` support, chezmoi, POSIX sh, Python 3.9+ and pinned Gitleaks required).

The remaining instructions describe **legacy v1**. Its `status` changes source
and index, prints diff before scanning, and its `push` does not enforce scanning.
The v1 script is preserved for compatibility; v2 does not repair its safety gaps.

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

## Intended exclusions

- `~/.claude.json`, `~/.claude/.credentials.json` (MCP tokens, OAuth credentials)
- `~/.claude/settings.local.json` (machine-local settings)
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

### How it works

The skill bundles a small engine script, [`examples/dotfiles-sync/sync.sh`](./examples/dotfiles-sync/sync.sh), with three subcommands. `SKILL.md` tells Claude to invoke it like this:

```
sh "$HOME/.claude/skills/dotfiles-sync/sync.sh" <subcommand>
```

| Subcommand | What it does |
|-----------|--------------|
| `in` | `chezmoi update` — pull the latest and apply to `~/.claude` |
| `status` | `chezmoi re-add` + show the staged diff + scan for secret-shaped strings (no commit) |
| `push "<msg>"` | commit and push — Claude runs this **only after you confirm** |

End to end:

1. You edit settings, or a session starts.
2. Claude follows the trigger in `CLAUDE.md` and decides to use the `dotfiles-sync` skill.
3. `SKILL.md` loads into context; it instructs Claude to run `sh …/sync.sh <cmd>`.
4. Claude runs that through its shell (Git Bash on Windows, `sh` on macOS/Linux), where `$HOME` resolves to the correct path on each OS.

The skill doesn't run the script by itself — Claude reads `SKILL.md` and executes the command. Because both the skill and the script live under `~/.claude/skills/`, they're synced by chezmoi, so the exact same automation is available on every machine.

Design note: sync is **not** automatic on process exit — there is no Claude turn at exit. Instead it runs at meaningful turns (session start, after config edits), with a human confirmation before every push.

## Security notes

- **No token / API key / credentials may ever enter the repo** — scan before every commit.
- Keep your own sync repo **private**. This project is a public *template / guide* and contains no personal secrets.

## License

[MIT](./LICENSE)

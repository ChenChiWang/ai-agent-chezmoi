**English** | [繁體中文](./README.zh-TW.md)

# Claude Code + Codex configuration sync (chezmoi)

Keep the **portable parts** of your Claude Code and Codex configuration (global
instructions, skills, settings) in one chezmoi source, sync it to every machine on
macOS / Linux / Windows, and let the agents themselves **sync safely at the start and
end of work**: pull before starting, publish only after you approve.

## Let an agent bring a machine up (recommended)

Prerequisite: you already have a private dotfiles repository in the v2 layout. On the
new machine, open Claude Code or Codex and say one sentence:

> Clone `https://github.com/ChenChiWang/ai-agent-chezmoi`, then follow `setup/AGENT-SETUP.md` to bring this machine up.

**The agent does**: the read-only preflight (`setup/preflight.sh`), proposes install
commands for missing tools and runs them after your confirmation, installs the pinned
Gitleaks and verifies the official SHA-256, verifies the GitHub host fingerprint, runs
`chezmoi init` and summarizes the diff, derives the parameter file, runs the
post-deployment `doctor`, and the first `status` and `check`.

**Only you**: paste the SSH public key into GitHub, decide whether existing settings
may be overwritten, choose `writer` and `auto_in` (see the parameter file below), and
approve every push. The agent never uses sudo, never widens its sandbox and never
approves on your behalf.

No private repository yet? See [First machine](#first-machine-no-private-repository-yet).
The manual procedure and the result table are in [`docs/new-machine.md`](./docs/new-machine.md)
(Traditional Chinese).

## What it does

One source renders the configuration of both agents:

| Source (`.chezmoitemplates/ai/`) | Rendered to |
|---|---|
| `shared/instructions.md` + `adapters/claude.md` | `~/.claude/CLAUDE.md` |
| `shared/instructions.md` + `adapters/codex.md` | `~/.codex/AGENTS.md` |
| `shared/skills/<name>/SKILL.md` | `~/.claude/skills/<name>/` and `~/.agents/skills/<name>/` |
| `shared/scripts/` (sync engine, secret scanner) | `~/.config/ai-agent/bin/` |
| `dot_claude/settings.json` | `~/.claude/settings.json` |

**Never synced**: `~/.claude.json`, `.credentials.json`, `settings.local.json`,
`~/.codex/auth.json`, sessions / history / cache / plugins, and any `*.key`, `*.pem`,
`*.token`. Full list in [`examples/chezmoi/.chezmoiignore`](./examples/chezmoi/.chezmoiignore).
Credentials and MCP tokens are configured per machine.

**Three agent checkpoints** (written into the shared instructions, followed by both agents):

1. **Start of work**: in the first turn of every session run `status` and `check`;
   if behind, build a plan and apply it (the remote is really probed once per day).
2. **Recording**: a preference or rule confirmed as durable is written into the source
   and reported as "recorded locally".
3. **End of work**: if the source changed, build a push plan; commit and push **only
   after you approve**.

**Safety**: Gitleaks scan before every write; `in` and `push` go through a reviewable
plan; `writer` decides which agent may publish; a plan is bound to the source state
and is rebuilt when that changes; the engine never runs stash, reset, rebase or a
force push.

## Requirements

| Tool | Requirement |
|---|---|
| Git | 2.45 or newer (`--no-lazy-fetch` support) |
| chezmoi | 2.71 series tested |
| Python | 3.9 or newer, standard library only |
| Gitleaks | **exactly 8.30.1** (`setup/install-gitleaks.sh` installs the pinned build into `~/.local/bin`) |
| SSH | a key that can reach the private repository, host already in `known_hosts`; HTTPS with credentials is not supported |

## Parameter file `~/.config/ai-agent/sync.local.json`

One per machine, never synced, mode 600. Agents do not create it on their own; only
during the bring-up, with values you confirmed.

```json
{
  "source": "/Users/you/.local/share/chezmoi",
  "destination": "/Users/you",
  "profile": "claude-codex",
  "remote": "ssh://git@github.com/OWNER/dotfiles.git",
  "branch": "main",
  "plan_dir": "/Users/you/.local/state/ai-agent/plans",
  "author_name": "you",
  "author_email": "you@example.com",
  "writer": "claude",
  "auto_in": false
}
```

**`writer`: which agent may apply and publish**

| Value | Meaning | Fits |
|---|---|---|
| `"claude"` or `"codex"` | only that agent runs `in` / `push`; the other records and reports what is pending | one primary agent (recommended start) |
| `["claude", "codex"]` | both may; a plan built after the other agent pushed is simply rebuilt | both agents used equally |
| `"any"` or omitted | no role check | a machine with a single agent |
| `"none"` | agents never publish; you run `push` yourself without `--agent` | publishing always done by a human |

**`auto_in`: apply incoming shared text without asking** (instructions, skills and
adapters only; scripts, settings and metadata still need manual approval). Turn it on
only if you are the sole pusher to your private remote: anyone who can push there
could otherwise change your agents' instructions on every machine.

Other fields: `profile` is `claude`, `codex` or `claude-codex`; `plan_dir` must be
outside the source and outside `.claude`, `.codex`, `.agents` and `.config/ai-agent`;
`remote` is `ssh://` or `git@host:path`. Codex runs in a sandbox without network or
HOME writes by default, so its `check` returns `CHECK_SKIPPED`; make Claude the writer
instead of widening the sandbox.

## Day to day

Normally you type nothing: the agents run the checkpoints at the start and end of
work. When you need the commands yourself:

```sh
# offline: changes or drift between source and HOME
sh ~/.config/ai-agent/bin/sync.sh status --config ~/.config/ai-agent/sync.local.json
# new commits on the remote? (cached once a day, --force re-probes)
sh ~/.config/ai-agent/bin/sync.sh check  --config ~/.config/ai-agent/sync.local.json --agent claude
# read-only post-deployment self-check, 14 OK/WARN/FAIL lines
sh ~/.config/ai-agent/bin/sync.sh doctor --config ~/.config/ai-agent/sync.local.json
# pull: build an incoming plan (prints PLAN_ID), review, apply
sh ~/.config/ai-agent/bin/sync.sh plan --operation in --config ~/.config/ai-agent/sync.local.json --agent claude
sh ~/.config/ai-agent/bin/sync.sh in --config ~/.config/ai-agent/sync.local.json --agent claude --approve PLAN_ID
# publish: build a push plan, review, push
sh ~/.config/ai-agent/bin/sync.sh plan --operation push --config ~/.config/ai-agent/sync.local.json --agent claude --message "docs: ..."
sh ~/.config/ai-agent/bin/sync.sh push --config ~/.config/ai-agent/sync.local.json --agent claude --approve PLAN_ID
```

Do not run `git status` on the source between `plan` and `in` / `push`; the plan
would return `BLOCKED_STALE_PLAN` and need rebuilding. Every result code and what to
do about it is in [`docs/new-machine.md`, section 7](./docs/new-machine.md).

Interactive Claude Code asks before each `sync.sh` run unless `permissions.allow` in
`settings.json` contains `Bash(sh ~/.config/ai-agent/bin/sync.sh:*)`; the
[example settings](./examples/chezmoi/dot_claude/settings.json) include it.

## First machine (no private repository yet)

`setup/AGENT-SETUP.md` assumes the private repository exists. To create it:

1. Start your own **private** dotfiles repository from [`examples/chezmoi/`](./examples/chezmoi/).
   It is a complete chezmoi source (`.chezmoiignore`, `dot_claude/`, `dot_codex/`,
   `dot_agents/`, `dot_config/`, `.chezmoitemplates/ai/`); replace
   `shared/instructions.md` and `dot_claude/settings.json` with your own content.
2. If you have an existing legacy `~/.claude` setup to bring along, the engine's
   `migration` subcommand converts it offline with a rollback; see
   [migration readiness](./docs/history/migration-readiness.md).
3. Every machine after that uses the agent bring-up above.

**Never** run `chezmoi init --apply` against this public repository, and never copy
it over an existing agent configuration.

## Documentation map

| Document | Content |
|---|---|
| [`setup/AGENT-SETUP.md`](./setup/AGENT-SETUP.md) | bring-up manual for an agent; each step marked "you do" or "ask the user" |
| [`docs/new-machine.md`](./docs/new-machine.md) | bring-up and acceptance guide for humans, result-code table, cross-machine end-to-end test (zh-TW) |
| [`docs/sync-v2.md`](./docs/sync-v2.md) | engine contract: profiles, parameter file, roles, plans, locks, recovery |
| [`docs/secret-scanner.md`](./docs/secret-scanner.md) | scanner contract and tests |
| [`docs/production-layout.md`](./docs/production-layout.md) | safety boundaries when the source lives under HOME |
| [`docs/architecture-adjustment-plan.md`](./docs/architecture-adjustment-plan.md) | 2026-09-26 architecture adjustment plan and execution record (zh-TW) |
| [`docs/implementation-status.md`](./docs/implementation-status.md) | current state and open items |
| [`docs/history/`](./docs/history/) | completed migration procedure and phase records |
| [`archive/`](./archive/README.md) | unmaintained bootstrap / launcher / guardian research; **do not install** |

## Tests

```sh
sh tests/test-render.sh && sh tests/test-status.sh
python3 tests/test-write.py && python3 tests/test-layout.py
python3 tests/test-migration.py && python3 tests/test-offline-status.py
python3 tests/test-scanner.py                    # needs the real Gitleaks 8.30.1
sh tests/session-acceptance.sh claude|codex      # fresh-session acceptance against a real model; billed, manual
```

Commits and pushes happen only in temporary local fixtures; the tests never touch
your private repository.

## Legacy v1

[`chezmoi-claude-setup.md`](./chezmoi-claude-setup.md) (Traditional Chinese) and
[`examples/dotfiles-sync/`](./examples/dotfiles-sync/) are the first version, which
synced `~/.claude` only: `in` / `status` / `push` wrap `chezmoi update`, `re-add` and
git push directly. They stay for existing users, but v1 `status` modifies the source
and index, prints the diff before scanning, and its `push` does not enforce a scan.
New users should start with v2.

## Security notes

- No token, API key or credential may ever enter the repository. v2 scans before
  every write, but ignore rules and scanning are defense in depth, not a guarantee.
- Keep your own sync repository **private**. This project is a public template and
  engine and contains no personal secrets.

## License

[MIT](./LICENSE)

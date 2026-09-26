# Agent-driven bring-up of a new machine

This file is written for an agent (Claude Code or Codex) that has been asked to
bring a machine onto the shared v2 configuration. A human only has to say:

> Clone `https://github.com/OWNER/ai-agent-chezmoi`, then follow `setup/AGENT-SETUP.md`.

Every step below is either **you do it** or **ASK THE USER**. Rules that never change:

- No `sudo`, no writes outside the user's home, no changes to sandbox or approval
  settings. Each install or file change is proposed first and run only after the
  user's confirmation prompt.
- Never guess `writer` or `auto_in`; ask. Never approve a `push` on the user's behalf.
- Report with the exact `OK` / `WARN` / `FAIL` lines the scripts print, plus what you
  did about each `FAIL`. Do not summarize a failure away.

## Step 1: preflight (read-only)

```sh
sh setup/preflight.sh                      # GitHub remote
sh setup/preflight.sh --host git.example   # other SSH host
```

Report the lines. Continue with the `FAIL` items only.

## Step 2: tools

| FAIL line | You do |
| --- | --- |
| `git` | propose `brew install git` (macOS) or the distribution package; run after confirmation |
| `chezmoi` | propose `brew install chezmoi` or the official install script into `~/.local/bin`; run after confirmation |
| `python3` | propose the platform's Python 3.9+ package; run after confirmation |
| `gitleaks` | propose `sh setup/install-gitleaks.sh`; it downloads 8.30.1, verifies the official SHA-256 and installs to `~/.local/bin` without sudo; run after confirmation |

Re-run preflight after each install.

## Step 3: SSH

- `known_hosts` FAIL: fetch the host's published fingerprints (for GitHub:
  `curl -s https://api.github.com/meta`, key `ssh_key_fingerprints`), run
  `ssh-keyscan HOST`, compare the fingerprints, and only then append the line to
  `~/.ssh/known_hosts`. Show the user the fingerprint you verified.
- `ssh_identity` WARN: propose `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519`; after
  confirmation, print `~/.ssh/id_ed25519.pub` and **ASK THE USER** to add it to the
  Git hosting account. You cannot do that step.
- `ssh_auth` FAIL after the key is registered: the key is neither in `ssh-agent` nor
  a default `~/.ssh/id_*` file. Propose `ssh-add` of the user's key file.

## Step 4: first deployment with chezmoi

```sh
chezmoi init ssh://git@github.com/OWNER/dotfiles.git    # ASK THE USER for the real remote
chezmoi diff
```

Summarize the diff as a list of files that would be created or overwritten. Point out
any existing `~/.claude/settings.json`, `~/.codex/AGENTS.md` or
`~/.codex/AGENTS.override.md`. **ASK THE USER** whether to apply. Then:

```sh
chezmoi apply
```

## Step 5: parameter file

Derive the values you can:

- `source`: `chezmoi source-path`
- `destination`: `$HOME`
- `remote` and `branch`: `git -C "$(chezmoi source-path)" remote get-url origin` and the checked-out branch
- `plan_dir`: `$HOME/.local/state/ai-agent/plans`
- `author_name` / `author_email`: the source repository's `git config user.name` / `user.email`
- `profile`: `claude-codex` if both CLIs are on PATH, otherwise `claude` or `codex`
- `scanner`: omit (the deployed adapter is used)

**ASK THE USER** for two values, showing the table from README "Setup notes":
`writer` (which agents may publish on this machine) and `auto_in` (apply shared-text
incoming changes without asking; only for a sole pusher). Then write
`~/.config/ai-agent/sync.local.json` with mode 600 and create `plan_dir` with mode 700.
This is the one situation in which an agent may write that file.

## Step 6: doctor (read-only, through the deployed engine)

```sh
sh ~/.config/ai-agent/bin/sync.sh doctor --config ~/.config/ai-agent/sync.local.json
```

Repeat until there is no `FAIL`. `WARN settings` means Claude Code will prompt for
the sync command each session; offer to add
`Bash(sh ~/.config/ai-agent/bin/sync.sh:*)` to `permissions.allow` in the **source**
`dot_claude/settings.json` (it is a synced file, so it goes through a reviewed push).

## Step 7: first sync checks

```sh
sh ~/.config/ai-agent/bin/sync.sh status --config ~/.config/ai-agent/sync.local.json --agent <claude|codex>
sh ~/.config/ai-agent/bin/sync.sh check  --config ~/.config/ai-agent/sync.local.json --agent <claude|codex>
```

Expected: `NO_CHANGES` and `UP_TO_DATE`. Anything else: see the result table in
`docs/new-machine.md`.

## Step 8: acceptance (optional, billed)

From this public repository, `sh tests/session-acceptance.sh claude` and
`sh tests/session-acceptance.sh codex` open a fresh session each and verify that the
start checkpoint runs before any project read. The cross-machine round trip in
`docs/new-machine.md` section 6 is the full end-to-end test.

## Final report

List every step with its outcome, the exact lines from preflight and doctor, the
values written to the parameter file, and what remains for the user (for example a
public key not yet registered).

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

## Which path

- The user already has a private dotfiles repository in the v2 layout (a second or
  later machine): Steps 1 to 3, then **4A**, then 5 to 8.
- The user has no private repository yet (the very first machine): Steps 1 to 3, then
  **4B**, then 5 to 8. Ask which one applies if the request does not say.

## Step 1: preflight (read-only)

```sh
sh setup/preflight.sh                      # GitHub remote
sh setup/preflight.sh --host git.example   # other SSH host
```

Report the lines. Continue with the `FAIL` items only.

## Step 2: tools

| FAIL line | You do |
| --- | --- |
| `platform` | stop the bring-up and install nothing: native Windows (Git Bash, MSYS2, Cygwin) cannot run the engine. Tell the user it has to be done inside WSL, with Claude Code and Codex installed there, and ask whether to continue that way; the WSL specifics are in `docs/wsl.md` |
| `git` | propose `brew install git` (macOS) or the distribution package; run after confirmation. If the distribution ships an older Git (Ubuntu 24.04 has 2.43), the user adds `ppa:git-core/ppa` with sudo; you do not run sudo |
| `chezmoi` | propose `brew install chezmoi` or the official install script into `~/.local/bin`; run after confirmation |
| `python3` | propose the platform's Python 3.9+ package; run after confirmation |
| `gitleaks` | propose `sh setup/install-gitleaks.sh`; it downloads 8.30.1, verifies the official SHA-256 and installs to `~/.local/bin` without sudo; run after confirmation |

Re-run preflight after each install.

On WSL, `WARN claude: Windows binary at ...` (or `codex`) means PATH resolves to the
Windows-side CLI, which manages the Windows `~/.claude`, not this HOME. Propose installing
the agent inside WSL (see `docs/wsl.md`), run it after confirmation, and ask the user to
log in to it there.

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

## Step 4A: join an existing private repository

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

## Step 4B: create the private repository from this template

Use this only when no private v2 repository exists yet. `examples/chezmoi/` in the
public clone is a complete chezmoi source; the test suite deploys it unchanged.
Everything below runs inside HOME, and the only network action is the final push.

### 4B.1 the empty remote (ASK THE USER)

Ask for the SSH URL of a new, **empty, private** repository (no README, no
`.gitignore`, no license; those would make the first push non-fast-forward). If `gh`
is installed and `gh auth status` succeeds, you may propose
`gh repo create dotfiles --private` and run it after confirmation.

### 4B.2 the source checkout

```sh
SRC="$HOME/.local/share/chezmoi"        # chezmoi's default source path
[ -e "$SRC" ] && echo "EXISTS"           # if it exists: ASK THE USER; never overwrite it
git init -b main "$SRC"
cp -R PUBLIC_CLONE/examples/chezmoi/. "$SRC/"
git -C "$SRC" config user.name  "NAME"   # ASK THE USER, or propose the global git identity
git -C "$SRC" config user.email "EMAIL"
```

Do not add files beyond the template to the source during bring-up; the engine's
mapping is closed (39 source files, 21 targets for `claude-codex`).

### 4B.3 bring the user's existing configuration in

Each item: show the current content, propose the exact edit, run it after
confirmation. Everything you write here becomes synced text; leave out anything
machine-specific or secret.

| Existing file | You do |
| --- | --- |
| `~/.claude/CLAUDE.md` | Merge its rules into `SRC/.chezmoitemplates/ai/shared/instructions.md` under "Development rules". Keep the "Required memory checkpoints" section unchanged: it is what makes the agents sync. Rules that apply to one agent only go to `adapters/claude.md` or `adapters/codex.md`. |
| `~/.codex/AGENTS.md` | Same treatment; rules shared by both agents go to the shared file once. |
| `~/.claude/settings.json` | Propose copying it to `SRC/dot_claude/settings.json` and adding `Bash(sh ~/.config/ai-agent/bin/sync.sh:*)` to `permissions.allow`. Say explicitly that it becomes a synced, scanned file; env values that look like tokens must stay out (they belong in `settings.local.json`, which is never synced). |
| `~/.claude/skills/<name>/` | The v2 skill set is fixed to the six names under `SRC/.chezmoitemplates/ai/shared/skills/`. A user skill with one of those names: propose replacing that `SKILL.md` with the user's version. Any other skill stays where it is and is not managed by v2; report that as a known limit, and never rename, add or delete skill directories. |

Shared text is literal except for `{{`: a literal `{{` must be written as
`{{ "{{" }}`, and any other Go template opener is rejected at render time.
`chezmoi diff` in the next step shows a render failure if something slipped through.

### 4B.4 preview, apply, first scan

```sh
chezmoi diff
```

Summarize the diff as a list of files that would be created or overwritten.
`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` and `~/.claude/settings.json` are replaced
by the rendered versions of what you merged in 4B.3, so the summary must show that
nothing from them was lost. **ASK THE USER** whether to apply. Then:

```sh
chezmoi apply
gitleaks dir --no-banner --exit-code 10 "$SRC"
```

A `gitleaks` exit code of 10 means a finding: show the file and rule, remove the
secret from the source, and scan again. Do not continue with a finding.

### 4B.5 the baseline commit and first push

```sh
git -C "$SRC" add -A
git -C "$SRC" commit -m "chore: initial v2 source from ai-agent-chezmoi examples"
git -C "$SRC" remote add origin ssh://git@github.com/OWNER/dotfiles.git   # the URL from 4B.1
```

The first push is the one publication the engine cannot do (it requires an existing
remote branch). Show the commit's file list and **ASK THE USER** before running:

```sh
git -C "$SRC" push -u origin main
```

Continue with Step 5. Every later machine of this user takes path 4A.

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
values written to the parameter file, on path 4B the baseline commit and what was
merged from existing files, and what remains for the user (for example a public key
not yet registered or a skill that stays unmanaged).

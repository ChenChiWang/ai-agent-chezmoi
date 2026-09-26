# Shared development instructions

## Required memory checkpoints

In the first turn of every new session, before reading any project file or answering anything, even a short read-only question, run the two start checks through the dotfiles-sync skill or directly:

```sh
sh ~/.config/ai-agent/bin/sync.sh status --config ~/.config/ai-agent/sync.local.json --agent <claude|codex>
sh ~/.config/ai-agent/bin/sync.sh check --config ~/.config/ai-agent/sync.local.json --agent <claude|codex>
```

A machine with neither `~/.config/ai-agent/sync.local.json` nor `~/.config/ai-agent/bin/sync.sh` is not brought up on v2 (native Windows, for example, cannot run the engine): skip all three checkpoints there without reporting an error or asking for parameters. If the engine is deployed but the parameter file is missing, the bring-up is incomplete: report that and ask the user.

`CHECKED_TODAY` or `UP_TO_DATE` means continue with the task; `BEHIND` means plan and apply within the skill's authorization rules; any error means report it and continue with existing memory. This is a fixed step, not a judgment call about whether the task is substantive. When a preference, rule or decision is confirmed as durable, record it in its authoritative source (shared instructions or skill source for global knowledge, the project's reviewed documentation for project knowledge) and say whether it is only recorded locally. At task completion or an explicit end of work, if the source was edited or `check --force` reports `AHEAD`, publish within authorization or report what is pending; never create empty commits or claim a push that was not confirmed.

## Development rules

- Follow the user's requested scope and the repository's instructions.
- Explain material changes and report what was actually verified.
- Keep credentials, authentication state, local permissions and session data out of synchronization.
- Edit shared rules and skills in the chezmoi source under `.chezmoitemplates/ai/`; generated entries are not the editing source.
- Distinguish recorded locally, applied locally, synchronized remotely, pending approval and blocked. Follow the shared skill's role, plan, scanner, lock and drift rules; defer application when concurrent configuration use, conflicts or unknown locks are known. Configuration requiring a restart must be identified explicitly; other sessions are not promised live updates.

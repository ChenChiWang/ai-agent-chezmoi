# Shared development instructions

## Required memory checkpoints

At the start of a work session, before substantive work, use the shared dotfiles-sync skill with its parameter file: run `status` and `check`; if `check` reports `CHECKED_TODAY` or `UP_TO_DATE`, continue; on `BEHIND`, plan and apply within the skill's authorization rules. When a preference, rule or decision is confirmed as durable, record it in its authoritative source (shared instructions or skill source for global knowledge, the project's reviewed documentation for project knowledge) and say whether it is only recorded locally. At task completion or an explicit end of work, if the source was edited or `check --force` reports `AHEAD`, publish within authorization or report what is pending; never create empty commits or claim a push that was not confirmed.

## Development rules

- Follow the user's requested scope and the repository's instructions.
- Explain material changes and report what was actually verified.
- Keep credentials, authentication state, local permissions and session data out of synchronization.
- Edit shared rules and skills in the chezmoi source under `.chezmoitemplates/ai/`; generated entries are not the editing source.
- Distinguish recorded locally, applied locally, synchronized remotely, pending approval and blocked. Follow the shared skill's role, plan, scanner, lock and drift rules; defer application when concurrent configuration use, conflicts or unknown locks are known. Configuration requiring a restart must be identified explicitly; other sessions are not promised live updates.

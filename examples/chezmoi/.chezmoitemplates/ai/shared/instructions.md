# Shared development instructions

## Required memory checkpoints

Before the first project read or task action in a new session, invoke/read the shared dotfiles-sync skill and perform its permitted sync checks. This applies even to a short read-only task; do not postpone the check until after answering. If checking is blocked, report the actual blocker and continue unrelated work using existing memory. This requirement is not authorization to apply or publish.

Local status cannot establish remote freshness: use the existing v2 incoming plan to check for updates at session start. If network access or operation authorization is missing, proactively request the specific approval needed and report freshness as unknown until the remote check succeeds; never infer approval to apply from permission to inspect.

Before the final response at task completion or when the user ends work, perform the skill's permitted local status check and inspect pending project-memory edits. Report recorded/applied/published/pending states from actual tool results; a conversational summary alone is not a check. Reuse a check already performed after the last change in the same turn.

## Development rules

- Follow the user's requested scope and the repository's instructions.
- Explain material changes and report what was actually verified.
- Keep credentials, authentication state, local permissions and session data out of synchronization.
- Edit shared rules and skills in the chezmoi source under `.chezmoitemplates/ai/`; generated entries are not the editing source.
- At the first turn of a new work session, before substantive work, proactively use the shared dotfiles-sync skill to check for shared-memory updates. Follow its authorization and safety gates; after a successful sync, re-read the updated instructions and relevant skills before continuing. Do not require a user reminder.
- During work, preserve confirmed, durable preferences, rules and decisions in their appropriate authoritative source when authorized. Global shared rules belong in the Shared Core; project-specific knowledge belongs in that project's reviewed documentation. Do not archive conversations, duplicate sources, or store credentials/runtime state.
- At task completion or an explicit end of work, use dotfiles-sync to check for unsynchronized memory. Synchronize within existing authorization or report what is pending; do not create empty commits. No forced-process-exit callback is promised.
- Distinguish recorded locally, applied locally, synchronized remotely, pending approval and blocked. Follow the shared skill's plan/scanner/lock/drift checks; defer application when concurrent configuration use, conflicts or unknown locks are known. Bootstrap is separate from daily memory sync. Configuration requiring a restart must be identified explicitly; other sessions are not promised live updates.

# Agent-driven shared memory

This workflow uses the existing shared instructions, common dotfiles-sync skill,
and v2 engine. It adds no launcher, daemon, callback, guardian or new memory store.
The supported profiles remain `claude` and `claude-codex`.

| Checkpoint | Required behavior |
| --- | --- |
| Start, before the first project read | Read/invoke the common skill, establish reviewed roots/profile, run local status and a permitted incoming plan. Request missing inspection permission; unknown remote freshness stays unknown. |
| Confirmed important memory | Read the authority first, deduplicate, then edit the authorized shared source for global rules or project documentation for project-specific decisions. Never edit generated entries as authority. |
| Finish | Inspect local changes and pending outbound commits, prepare a concrete push plan when permitted, and publish only within explicit authorization. Do not create empty commits. |
| After successful synchronization | Re-read changed sources and generated outputs, verify status and distinguish file availability from native reload. |

Recorded locally is not synchronized. Applied locally means generated deployment
has been verified. Synchronized remotely requires confirmed publication; receiver
receipt is a separate claim requiring evidence. Pending approval and blocked/deferred
must be reported explicitly. An uncertain push outcome is not success.

The task/plan contract remains unchanged: exact roots, profile, remote, branch,
identity, candidate, outbound history and tool hashes are reviewed; plans expire
in one hour. No standing authorization is created. Missing scanner, drift, conflicts,
staged work, locks, journals or known concurrent use cannot be bypassed. Unsupported
experimental coordination markers are rejected, preserved and left for separately
reviewed recovery. No automatic active-session detection or safe hot reload is claimed.

## Accepted evidence and limits

Historical isolated Codex agent-driven incoming/outgoing tests passed. The agent
published the reviewed candidate; an independent receiver operated by the test
operator cloned the same local remote and verified source/generated-file consistency.
The receiver did not run a native agent. These results cover Codex and tested engine
paths, not Claude autonomous publication, every model or all concurrency conditions.

Claude's earlier incoming, deployed-file checks and reread remain successful evidence.
Its startup plan-path problem, unsupported measurement claims and unverified outgoing
remain limitations; no additional Claude test or login is part of this release.
The original IO_ERROR was not reproduced and its root cause is unknown. Overall
runtime acceptance remains PARTIAL. Historical loading safety and production
multi-machine deployment remain unqualified.

The release candidate extracts diagnostics onto the published v2 baseline, retaining
its lock-before-prepare order, mapping, scanner, plan schema and recovery semantics.
Its regression results must be identified separately from historical native-session
acceptance. Required checks are the existing write, offline-status, render and layout
suites, diagnostic fault injection, and rejection/preservation of existing unsupported
coordination metadata. No native incoming/outgoing acceptance session is replayed.

## Private adoption and recovery

Merge checkpoint policy into the existing private shared authority, preserving
personal rules; do not replace it with the public example. Only the shared rule
source, common skill and diagnostic engine are intended to change. Generated
instructions, both skill copies and the engine follow from those sources. Native
agent settings, auth, sessions and runtime state are outside the adoption scope.

Before an approved write, retain an owner-private external backup of the current
mapped source/target bytes and modes, Git HEAD/ref/index/config and trusted engine,
with a SHA-256 manifest. Bind it to the actual reviewed revision; old migration
backups bound to a pre-publication HEAD/index are not drop-in rollback commands.
Validate the backup and scoped restoration in isolation. Unknown barriers or leases
remain intact and block deployment until separately resolved.

Normal exceptions retain existing guarded rollback behavior. Interrupted or ambiguous
transactions require review of the retained journal and current file/ref identities;
never overwrite later edits, expire locks, reset published history or force-push.
Once publication is confirmed, a reversal is a separately reviewed forward commit
and deployment plan, not replay of a historical migration rollback. A source-only
backup is not a promise to restore native configuration/runtime outside the mapping.

---
name: dotfiles-sync
description: Inspect, plan, and safely synchronize a migrated shared Claude Code and Codex chezmoi profile through the v2 engine. Use proactively before substantive work in a new session, when recording confirmed durable memory, and at task completion or an explicit end of work; also use for requested configuration status, incoming sync, or publication.
---

# Shared configuration sync (v2)

Use the single engine at `${AI_AGENT_HOME:-$HOME/.config/ai-agent}/bin/sync.sh`.
Select the source/destination from the task or reviewed configuration. Never infer
that the current project is the dotfiles repository. This is an agent-driven workflow
using Shared Core instructions and this common skill, not a CLI launch callback.
Do not create launchers, guardians, background services or lifecycle hooks for it.
The engine requires an already migrated v2 profile; installation and private
migration are separate tasks. Choose `--profile claude` for Claude-only deployment,
`--profile codex` for Codex-only deployment, or `--profile claude-codex` for both.
All profiles use the same shared skill sources. For a full dual repository deployed
to a single-agent machine, also specify `--repository-profile claude-codex`; this
scans the entire source/history without reading or deploying inactive targets. Never create Codex files to satisfy a Claude-only
status check. The compatibility default is dual, so always supply the chosen profile.
Any existing reader lease, unresolved barrier, writer lock or recovery journal remains
binding. Never remove protection to make this workflow run. Known concurrent
configuration use requires deferring application even if no reader lease exists;
this skill does not detect all native/IDE sessions or fix the historical loading gate.

## Three memory checkpoints

**Start:** On the first turn of a new work session, before substantive work, invoke
this skill without waiting for a reminder. Establish the reviewed source, destination,
profile, remote/branch and authorization scope; ask for missing essentials rather
than guessing roots or silently treating the project as the source. Run local
`status`. It is offline and only describes scoped local state: `NO_CHANGES` does not
mean the remote is current. Create an incoming plan to check the remote when inspection
is permitted; otherwise proactively request the specific missing network/inspection
approval and report remote freshness as unknown. Review its actual content and identities. If the candidate
and deployment are unchanged, begin work without a write or empty commit. Otherwise
execute approved `in` only within existing explicit authorization; if it is missing,
present the concrete plan and request approval to apply it. Do not block unrelated work waiting
for optional sync; state that existing memory is being used and freshness is unknown.

**During work:** Record only confirmed, durable preferences/rules/decisions within
editing authorization. Use `.chezmoitemplates/ai/shared/instructions.md` for portable
global rules, the existing shared skill source for workflow knowledge, or the relevant
project's authoritative documentation for project-specific knowledge. Do not create
an extra global memory database, save all chat, or treat an inference as a confirmed
preference. Read the current source and reconcile with it before editing; never edit
generated CLAUDE.md/AGENTS.md or generated skill copies as the source. Project memory
outside the v2 mapping uses that project's separately authorized workflow, not v2
publication. Writing a source file is recorded locally, not synced. Apply/publish
only under the same reviewed-plan contract below; do not infer push authorization
from permission to remember something. Do not overwrite another session's edits.

**Finish:** At task completion or when the user ends work, check scoped local state,
source edits and any previously known pending publication. If necessary and permitted,
use a push plan to identify outbound commits/remote divergence; a clean worktree or
local status cannot prove all commits were published. Review all outbound content,
not only this task's memory edits. If there is nothing to publish, do not execute an
empty publication or create an empty commit. If authorized, execute the reviewed push;
otherwise report recorded changes/pending approval or the blocker. Checkpoint retries
must re-read actual state; do not repeat a successful write because of a chat summary.
No cleanup on forced termination is promised.

After successful in or push, re-read the changed shared instructions and relevant
skill sources AND their deployed outputs, then run local status. Report what is now
available in this session; text re-reading does not guarantee native configuration
reload. Settings, hooks, plugins or startup-only behavior requiring native reload
must be marked as requiring restart/new session (or unverified if uncertain). Do not
restart an agent automatically or promise other sessions received the update.

Report these states precisely: **recorded locally** (authoritative source edited),
**applied locally** (generated deployment verified), **synchronized remotely** (push
confirmed), **pending approval**, or **blocked/deferred**. Incoming refresh is not
publication. On uncertain push completion, report publication unconfirmed and re-plan;
never claim synchronized merely because a local commit exists.

Offline/GitHub unreachable: keep existing memory and report remote freshness unknown;
no fallback installer, authentication change or successful-sync claim. Missing pinned
scanner/dependency: block sync, report the requirement, never install or bypass it.
Dirty/conflicting source, generated drift, known concurrent configuration use, unknown
lock or journal: defer writes, preserve state and explain the blocker. Read-only
inspection is not permission to resolve conflicts, clear barriers or reset work.
Do not use migration-only offline baseline mode to bypass an unavailable remote.

## Existing v2 plan contract

```sh
sh "$engine" status --source "$sync_source" --destination "$sync_destination" --profile "$sync_profile"
sh "$engine" plan --operation in \
  --source "$sync_source" --destination "$sync_destination" --profile "$sync_profile" \
  --remote "$approved_remote_url" --branch "$sync_branch" --plan "$plan_file"
```

For publication, choose `plan --operation push`. Supply explicit `--author-name`,
`--author-email` and optionally `--message` for a new commit. Plans are private new
JSON files outside both roots and expire after one hour. The output identifies
changed paths/hashes, generated outputs, outbound commits, branch, remote identifier
and `PLAN_ID`; inspect the JSON for the exact remote and candidate identities.
Review the actual edits at those hashes and every listed outbound commit. Hashes
alone do not explain the change.

Use existing explicit task authorization or obtain approval for the concrete plan
before executing `in` or `push`, with the same options and `--approve PLAN_ID`.
The flag is not evidence of human consent. Proactive checkpoints authorize neither
arbitrary writes nor publication: existing explicit authorization must cover the
operation, roots, profile, remote/branch and actual changes/outbound commits. Record
which user instruction supplies that authorization; do not invent a standing policy
or reuse an earlier one-time migration approval. A changed plan needs fresh review;
ask again only when existing authorization does not cover it. Execution rechecks/re-scans the plan;
changed content, branch, remote or index requires a new review. `push` also applies
the approved generated outputs before publication, keeping deployment and its local
commit consistent. A status result is not push approval.

Preserve manual generated-file edits and move their intent into shared source via
a separate reviewed edit. Do not re-add templates, reset/stash staged work, resolve
conflicts automatically, or fall back to v1 after a refusal. The engine blocks
staged changes, drift, unknown/out-of-scope history, merges and non-fast-forwards.

Gitleaks 8.30.1 and Python 3.9+ are required. Missing tools and invalid scan reports
block sync; never substitute a passing scanner. `--scanner` is a trusted executable
extension for reviewed adapters/tests. Findings are redacted; do not expose raw
secret values, scanner logs or credential URLs.

A push failure retains the approved local commit and outputs. Report the failure
and re-plan before retry; the remote may have accepted before a disconnect. A lock
or recovery journal requires inspection, not automatic removal. Deployment of this
skill does not authorize changes outside the v2 allowlist or legacy caller cutover.

During an unpublished migration, a reviewed `migration plan` creates a private
baseline/rollback package; `migration apply` requires its `MIGRATION_ID`. A rules
map must preserve every original instruction segment except explicitly reviewed
legacy sync triggers. Existing portable skills and Claude settings are preserved.
Use the public migration-readiness procedure to prepare this map; do not infer
that installing the skill authorizes conversion.

With the legacy HEAD still in place, local regression may use `plan --operation in
--offline --baseline ABS_BACKUP --baseline-id MIGRATION_ID`, then approved `in`
with the same options. Supply no remote for this mode. It cannot commit, fetch or
push. Normal publication remains blocked until the separately authorized final
migration commit/publication; never use bootstrap as a history-scan bypass.
Stop at the requested phase gate. A successful fixture regression does not approve
private migration, Codex deployment, product loading or final publication.

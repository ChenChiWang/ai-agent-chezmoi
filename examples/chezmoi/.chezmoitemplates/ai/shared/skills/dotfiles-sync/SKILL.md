---
name: dotfiles-sync
description: Inspect, plan, and safely synchronize a migrated shared Claude Code and Codex chezmoi profile through the v2 engine. Use proactively before substantive work in a new session, when recording confirmed durable memory, and at task completion or an explicit end of work; also use for requested configuration status, incoming sync, or publication.
---

# Shared configuration sync (v2)

Use the single engine at `${AI_AGENT_HOME:-$HOME/.config/ai-agent}/bin/sync.sh`.

## Parameters

Read the machine-local parameter file `${AI_AGENT_HOME:-$HOME/.config/ai-agent}/sync.local.json`
and pass it with `--config`. It supplies `source`, `destination`, `profile`,
`repository_profile`, `remote`, `branch`, `plan_dir`, `scanner`, `author_name`,
`author_email`, `writer` and `auto_in`. Explicit options override it. If the file is
missing or lacks an essential value, ask the user for exactly that value; never guess
roots, never treat the current project as the dotfiles repository, and never create
the file yourself. The file is machine-local, outside synchronization, and provides
identity only: it is not authorization to apply or publish. `plan_dir` must be outside
the source checkout and outside `.claude`, `.codex`, `.agents` and `.config/ai-agent`;
`$HOME/.local/state/ai-agent/plans` is a suitable location. With `plan_dir`, `plan`
creates a new file there and prints `PLAN_FILE` and `PLAN_ID`; `in`/`push` then need
only `--config` and `--approve PLAN_ID`.

## Roles

Pass `--agent claude` or `--agent codex` as the adapter for this product instructs.
The parameter file's `writer` names the one agent that applies (`in`) and publishes
(`push`). Any other agent receives `NOT_WRITER` (exit 77) for those commands and must
report the pending work instead. Non-writers still record memory in the source, run
`status`, `check` and `plan`, and review results.

When the file sets `auto_in` to true, an `in` executed with `--plan PLAN_FILE` and
no `--approve` is applied automatically **only** if the plan changes nothing but the
shared text sources (instructions, the six skills, the two adapters). Any change to
scripts, wrappers, settings or metadata returns `PENDING_APPROVAL` (exit 77) and needs
an explicit `--approve PLAN_ID` after review. `push` never has an automatic mode.

## Scope and safety

This is an agent-driven workflow
using Shared Core instructions and this common skill, not a CLI launch callback.
Do not create launchers, guardians, background services or lifecycle hooks for it.
The engine requires an already migrated v2 profile; installation and private
migration are separate tasks. Choose `--profile claude` for Claude-only deployment,
`--profile codex` for Codex-only deployment, or `--profile claude-codex` for both.
All profiles use the same shared skill sources. For a full dual repository deployed
to a single-agent machine, also specify `--repository-profile claude-codex`; this
scans the entire source/history without reading or deploying inactive targets. Never create Codex files to satisfy a Claude-only
status check. The compatibility default is dual, so always supply the chosen profile.
Any existing writer lock, recovery journal or archived coordination marker
(`BLOCKED_UNSUPPORTED_COORDINATION`) remains binding. Never remove protection to make
this workflow run. Known concurrent configuration use requires deferring application;
this skill does not detect all native/IDE sessions.

## Three memory checkpoints

**Start:** On the first turn of a new work session, before substantive work, invoke
this skill without waiting for a reminder. Short read-only tasks are not exempt, but
the daily `CHECKED_TODAY` result keeps the cost to one offline `status`. Read the parameter file; ask only for
missing essentials rather than guessing roots or silently treating the project as
the source. Run local
`status`. It is offline and only describes scoped local state: `NO_CHANGES` does not
mean the remote is current. Then run `check`: it fetches into quarantine and reports
`UP_TO_DATE`, `BEHIND n`, `AHEAD n` or `DIVERGED` without scanning or writing a plan.
The remote is probed once per local day per machine: `CHECKED_TODAY` repeats the
earlier result and needs no further action at start; use `--force` only when the
user asks for a fresh probe or at the finish checkpoint.
`CHECK_SKIPPED` means the sandbox has no network: report remote freshness as
unknown and continue; do not request sandbox escalation for it. If inspection
permission itself is missing, request exactly that. On `UP_TO_DATE`, begin work without any write or empty
commit. On `BEHIND`, create an incoming plan, review its actual content and
identities, then execute `in` under `auto_in` or existing explicit authorization;
otherwise present the concrete plan and request approval. `AHEAD` means unpublished
local commits: report them for the finish checkpoint. `DIVERGED` requires the user.
Do not block unrelated work waiting for optional sync; state that existing memory is
being used and freshness is unknown.

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

**Finish:** At task completion or when the user ends work, run `status` for scoped
local state and source edits, and `check --force` for unpublished commits (`AHEAD`);
a clean worktree or local status cannot prove all commits were published. If there
are source edits or outbound commits and this agent is the writer, use a push plan.
Review all outbound content,
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
config="${AI_AGENT_HOME:-$HOME/.config/ai-agent}/sync.local.json"
sh "$engine" status --config "$config" --agent "$this_agent"
sh "$engine" check --config "$config" --agent "$this_agent"
sh "$engine" plan --operation in --config "$config" --agent "$this_agent"
sh "$engine" in --config "$config" --agent "$this_agent" --plan "$plan_file"   # auto_in, shared text only
sh "$engine" in --config "$config" --agent "$this_agent" --approve "$reviewed_plan_id"
```

Every option can still be given explicitly instead of, or in addition to, the file:
`--source`, `--destination`, `--profile`, `--repository-profile`, `--remote`,
`--branch`, `--plan`, `--scanner`, `--author-name`, `--author-email`.

For publication, choose `plan --operation push`. Supply explicit `--author-name`,
`--author-email` and optionally `--message` for a new commit. Plans are private new
JSON files outside both roots and expire after one hour. The output identifies
changed paths/hashes, generated outputs, outbound commits, branch, remote identifier
and `PLAN_ID`; inspect the JSON for the exact remote and candidate identities.
Review the actual edits at those hashes and every listed outbound commit. Hashes
alone do not explain the change.

Use existing explicit task authorization or obtain approval for the concrete plan
before executing `in` or `push`, with the same roots/profile/remote/branch options
and `--approve PLAN_ID`. The commit message and author identity are taken from the
approved plan when not repeated; giving a different message is a different plan.
Do not run `git status` or other index-refreshing commands against the source
between `plan` and `in`/`push`: the plan binds the index hash.
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
Use the archived migration-readiness procedure (docs/history) to prepare this map; do not infer
that installing the skill authorizes conversion.

With the legacy HEAD still in place, local regression may use `plan --operation in
--offline --baseline ABS_BACKUP --baseline-id MIGRATION_ID`, then approved `in`
with the same options. Supply no remote for this mode. It cannot commit, fetch or
push. Normal publication remains blocked until the separately authorized final
migration commit/publication; never use bootstrap as a history-scan bypass.
Stop at the requested phase gate. A successful fixture regression does not approve
private migration, Codex deployment, product loading or final publication.

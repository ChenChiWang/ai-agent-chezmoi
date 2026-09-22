---
name: dotfiles-sync
description: Inspect, plan, and safely synchronize a migrated shared Claude Code and Codex chezmoi profile through the v2 engine. Use when the user requests configuration status, incoming sync, or publication of shared configuration edits.
---

# Shared configuration sync (v2)

Use the single engine at `${AI_AGENT_HOME:-$HOME/.config/ai-agent}/bin/sync.sh`.
Select the source/destination from the task or reviewed configuration. Never infer
that the current project is the dotfiles repository or trigger writes on session
start. The engine requires an already migrated v2 profile; installation and private
migration are separate tasks. Choose `--profile claude` for Claude-only deployment,
or `--profile claude-codex` after the separate Codex deployment gate. Both profiles
use the same shared skill sources. Never create Codex files to satisfy a Claude-only
status check. The compatibility default is dual, so always supply the chosen profile.

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
The flag is not evidence of human consent. Execution rechecks/re-scans the plan;
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

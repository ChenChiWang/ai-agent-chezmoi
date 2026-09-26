# Phase 3D validation matrix

**Result: PASS for the Claude-only migration gate. Stop before 3E–3H.**

This records the completed 3D gate. The user's subsequent 3E–3G authorization,
deployment and current stop are tracked in the separate
[3E–3G validation matrix](phase-3efg-validation.md); this 3D result is retained.

Reference: accepted public `15f17ca3ed349a48142f8ada8b62ca8568c1426d`.
Production remains migrated, uncommitted and unpushed. The user explicitly
authorized a session-only alternate Claude model after confirming the original
credits/limit blocker was external. No permanent model/settings change was made.

| Check | Evidence type | Result | Evidence |
| --- | --- | --- | --- |
| Baseline / rollback | Integrity + isolated actual-content execution | PASS | External owner-private package; conversion/rollback restores files, modes and Git state |
| Actual deployed files | Production hash/mode verification | PASS | All 14 targets and managed sources equal approved migration manifest |
| Settings / model preference | Exact baseline comparison | PASS | Full settings bytes/mode unchanged; alternate model supplied only as CLI argument |
| Five portable skills | Exact baseline comparison | PASS | Generated skill payloads preserved verbatim |
| Shared Core render | Actual production chezmoi | PASS | All 14 renders equal deployed bytes; normal-shell scoped apply/diff is idempotent; final diff empty |
| Skill discovery / configuration | Actual Claude initialization | PASS | All six skills discovered from deployed user configuration; actual skill origins under `~/.claude/skills` |
| Skill invocation | Actual successful Claude/Sonnet session | PASS | Six Skill tool calls, six non-error results, six individual content summaries; no other tool calls |
| Shared rule runtime | Actual successful Claude/Sonnet response | PASS | Language, comments, conventional commits/signatures, uncertainty, destructive-action precautions and no automatic session-start writes correctly recognized; Claude-only profile and neutral engine path identified |
| StatusLine runtime | Actual configured command and widget config | PASS | Existing `npx -y ccstatusline@latest` executed with startup and active-context stdin; exit 0, nonempty output, model/branch visible, context changes reflected, no stderr; settings unchanged |
| Scanner / status | Actual production engine | PASS | Pinned Gitleaks 8.30.1 and scoped status pass, including final verification |
| Offline plan/in / old entrypoint | Actual production engine | PASS | Approved bootstrap offline plan/in with unchanged legacy HEAD; old path forwards to v2; final manifest consistent |
| Changed rules/skills and sync guards | Deployed engine on isolated actual-content copy | PASS | Rules plus six skills propagate; stale approval rejected (68), offline push rejected (64), divergent reverse edit rejected (2); scoped restore and rollback verified |
| Final non-regression invariants | Production hash/Git verification | PASS | Source/target approved state, HEAD/index/config and original settings unchanged by regression; no Codex adapter deployed |

## Runtime evidence and scope

The original preferred-model attempt exited before Skill invocation and was never
counted as a runtime PASS. The subsequent session used `--model sonnet`, normal
user settings/instruction discovery, `--tools Skill`, and an explicit Skill
allowlist. It exited successfully with `is_error=false`. The session loaded
dotfiles-sync, d3-component, deploy, excel-import, review and supabase-migrate, and
returned their distinct content summaries. Static file checks are separate rows;
they are not substitutes for this runtime evidence.

StatusLine was run as the command configured by the user, with the user's existing
widget configuration and representative Claude JSON input. This proves command
execution, configuration loading and output behavior independently of model
availability. It is not a pixel/font/layout inspection of every terminal. Its
unchanged `@latest` dependency remains externally mutable.

No deployment, destructive database action or project workflow inside the skills
was executed. This gate verifies discovery, invocation/loading, retained content
and shared-rule recognition, not arbitrary future task correctness. MCP and other
execution tools were disabled for the regression session; this is not a separate
MCP/plugin integration certification.

The original preferred model's credits/limit remains an external service condition,
not a migration defect repaired here. Its availability is still unverified; the
authorized alternative completed all required model-dependent gate checks.

## Guard behavior and harness corrections

The unpublished bootstrap uses the original approved migration snapshot. After an
isolated successful edited `in`, reversing source to that original snapshot while
leaving edited outputs correctly fails with DRIFT: the engine does not silently
treat an intermediate deployment as a new approved baseline. The isolated copy
was reconciled through reviewed scoped chezmoi apply, then verified and rolled
back, matching the accepted fixture procedure. Production was not edited for
these tests. Do not bypass this guard for future uncommitted changes.

Two harness issues were corrected without changing production: process-wide
umask077 initially created a permission-only chezmoi diff, so log files now receive
explicit 0600 permissions while the normal shell umask is retained; statusLine
uses NBSP, so semantic text checks normalize whitespace. Both corrected checks
passed using unchanged production settings and outputs.

## Evidence retention and stop

Owner-private evidence is outside HOME at
`/Users/Shared/ai-agent-migration-<user>/phase3-20260922-221058/`:
`review/phase3-validation-matrix.json`, `review/claude-sonnet.stdout`,
`review/statusline-results.json`, `review/local3d-results.json`, final status/diff
logs, and `ROLLBACK.md`. Do not publish raw transcripts, settings or baseline blobs.

No production rollback, Codex deployment, Phase 3E–3H work, or private commit/push
was performed. Retain deployment and rollback evidence; wait for explicit approval.

# v2 approved synchronization

The public template now implements `status`, `plan`, `in`, and `push`. Migration
is paused: none of these changes installs or changes a private source, agent home,
legacy script, or session-start trigger. This engine replaces the legacy sync
operations **for an already migrated v2 profile**; it does not automatically ingest
arbitrary legacy settings, hooks, skills, or other dotfiles.

## Profiles

The engine supports `claude` (31 sources / 14 targets), `codex` (28 / 12) and
`claude-codex` (39 / 21), plus `--repository-profile claude-codex` for full-repo
history/source scans with a single-agent target profile. The Phase 4 cohort/lease
protocol (`DEFERRED_READERS`, receipts, kernel mutex) was removed from the engine on
2026-09-26; its markers are refused (see below) and its records live in
[history](history/phase-4-blocker-repair.md).

## Design and scope

The POSIX `sync.sh` entrypoint retains the offline status implementation and
routes mutations to the sibling `sync-write.py`. Python 3.9+ standard-library
facilities provide structured snapshots, shared locks, isolated Git indexes,
atomic file replacement and recovery records. There is one shared engine for
both agents, and no new runtime Python package dependency.

Profiles select a closed mapping: `claude` has 31 source files / 14 targets;
`claude-codex` has 39 / 21. Always pass `--profile claude` for a Claude-only stage;
the compatibility default is dual. Both include all six shared skills and
Claude-only settings. The scanner owns the mapping and wrapper schema consumed by
shell/Python engines. Normal sync still rejects missing output files or source
layout changes; the separate approved converter handles first deployment and staged
expansion. See [Phase 2.6 migration readiness](history/migration-readiness.md) for offline
baseline, conversion, local regression, rollback and later Codex expansion.

Git and target selection are explicit; the engine never calls `chezmoi source-path`.
For normal network sync, use a regular SHA-1 Git checkout with a committed v2 baseline, an existing remote
branch, and the same local/remote branch name. Linked worktrees, shallow clones,
object alternates, grafts and nonstandard repositories are rejected. Git must
support `--no-lazy-fetch` (tested with 2.55.0). Partial clones work only when needed
local objects are present; they are never repaired by lazy fetch.

`plan`, `in`, and `push` use one atomic mkdir lock at
`SOURCE/.git/ai-agent-sync.lock`, regardless of caller or path alias. Any staged
changes, unresolved Git operation, special index flags, or previous incomplete
transaction block the operation. Unrelated unstaged/untracked files are untouched.
No stash/reset/rebase, global `add`, clean/smudge filter, diff driver, source hook,
arbitrary source template execution, or unrestricted chezmoi apply occurs.

## Local configuration file

Since 2026-09-26 the engine accepts `--config ABS_JSON`, a machine-local parameter
file (conventionally `$HOME/.config/ai-agent/sync.local.json`, excluded from
synchronization by `.chezmoiignore`). It is owner-controlled, must not be group or
world writable, and has a closed key set: `source`, `destination`, `profile`,
`repository_profile`, `remote`, `branch`, `plan_dir`, `scanner`, `author_name`,
`author_email`, `writer` (`claude` or `codex`) and `auto_in` (boolean). Unknown keys,
relative paths or invalid values return `INVALID_CONFIG` (exit 78). Explicit options
always override the file. The file resolves *where* to sync; it never proves human
authorization for a write or publication.

With `plan_dir`, `plan` creates a fresh owner-only file
`plan_dir/sync-plan-<op>-<utc>-<random>.json` and prints `PLAN_FILE` and `PLAN_ID`;
`in` and `push` locate the approved file by `--approve PLAN_ID` when `--plan` is
omitted (`PLAN_NOT_FOUND`, exit 66, otherwise). Plan files are resolved through
directory aliases such as macOS `/tmp`; the file itself must not be a symlink. A
plan must be outside the source checkout and outside the `.claude`, `.codex`,
`.agents` and `.config/ai-agent` regions of the destination; other locations under
HOME are allowed.

Malformed plan documents return `INVALID_PLAN` (exit 65) with a redacted
`DIAGNOSTIC` record instead of a traceback. On `in`/`push`, an omitted `--message`
or author identity is taken from the approved plan, so the same plan can be executed
without repeating them; a different explicit message is a different plan
(`BLOCKED_STALE_PLAN`). The plan also binds the source index hash: an intervening
`git status` on the source refreshes the index and invalidates the plan.

### Archived coordination metadata

Any `ai-agent-cohort.json`, `ai-agent-cohort.lock` or `ai-agent-launch-readers`
entry under the source `.git` belongs to the archived Phase 4 bootstrap protocol.
Every command, including `status` and `check`, refuses with
`BLOCKED_UNSUPPORTED_COORDINATION` (exit 73) before taking any lock and leaves the
entry untouched for manual inspection. The engine contains no cohort/lease code any
more; the last revision with those hooks is tagged `engine-with-cohort-hooks`.

### Roles and automatic incoming

`writer` names the agent allowed to run `in` and `push`. Commands carrying
`--agent NAME` with a different name return `NOT_WRITER` (exit 77) before any lock
or plan lookup; `status`, `check` and `plan` are open to every agent. Without
`--agent` (a human at a shell) no role check applies.

`auto_in: true` lets `in --plan PLAN_FILE` run without `--approve`. The engine
derives the approval from the plan bytes and, after the usual re-fetch, re-scan and
plan comparison, applies it only when every changed source file is shared text
(`shared/instructions.md`, `shared/skills/*/SKILL.md`, `adapters/*.md`). Any other
change returns `PENDING_APPROVAL` (exit 77) and prints the `PLAN_ID` to approve
explicitly. `push` has no automatic mode. Every other safety gate (scanner, drift,
locks, journals, staged changes, history scope) is unchanged.

### Codex skill discovery (0.157.0)

The deployed Codex targets are `.codex/AGENTS.md` and `.agents/skills/<name>/SKILL.md`.
Runtime discovery of all six skills was recorded with Codex 0.155.1 (Phase 3). The
installed 0.157.0 binary still references both `.agents/skills` and
`$CODEX_HOME/skills` as skill locations (binary string inspection on 2026-09-26, not
a runtime session); the mapping is therefore unchanged, and a fresh runtime
confirmation remains a manual acceptance step.

### check

`check` fetches the branch into quarantine and prints `HEAD`, `REMOTE_HEAD` and
`REMOTE: UP_TO_DATE | BEHIND n | AHEAD n | DIVERGED`. It scans nothing, writes no
plan and takes no source lock; network failures return `NETWORK_ERROR` (exit 71).
With `plan_dir`, a successful check records `plan_dir/last-check.json`; a later
`check` on the same local calendar day prints `CHECKED_TODAY` with the previous
result instead of fetching, unless `--force` is given. This is the intended
start-of-work freshness probe; a full incoming plan is only needed on `BEHIND`.

## Commands and approval

For an **authorized, already migrated source/destination**, use absolute paths or
`--config`:

```sh
engine="$sync_destination/.config/ai-agent/bin/sync.sh"
plan_file="$private_plan_directory/sync-plan.json"

sh "$engine" plan --operation in \
  --source "$sync_source" --destination "$sync_destination" --profile "$sync_profile" \
  --remote "$approved_remote_url" --branch main --plan "$plan_file"

# After reviewing the plan and obtaining authorization for its concrete effects:
sh "$engine" in \
  --source "$sync_source" --destination "$sync_destination" --profile "$sync_profile" \
  --remote "$approved_remote_url" --branch main --plan "$plan_file" \
  --approve "$reviewed_plan_id"
```

For push, use `plan --operation push`, followed by `push`, with the same options.
Supply `--author-name`, `--author-email` and optionally `--message` to **both**
commands when a commit is needed. Identity is explicit: no global Git identity is
read. The default message is `chore: sync shared agent configuration`.

A plan is a new owner-only JSON file outside the source checkout and outside the
deployment regions (`.claude`, `.codex`, `.agents`, `.config/ai-agent`) of the
destination. Nested source under HOME is supported under the
[Phase 2.7 layout boundary](production-layout.md); backups and local bare remotes
still may not live inside destination HOME. The plan's parent directory
must already exist (or come from a configured `plan_dir`). Existing plan files are not overwritten. It records:

- Canonical roots, exact remote URL, branch and base/remote commit IDs.
- Full index and repository-config hashes; source/target bytes and permission hashes.
- Candidate tree, before/after scoped content hashes, generated outputs and outbound
  commit IDs; commit message and author identity.
- Trusted engine, scanner adapter and rule-registry hashes.

The SHA-256 of the entire plan is `PLAN_ID`. Plans expire after one hour. The
console prints changed known paths, before/after hashes, affected output hashes,
commit IDs, branch and a remote identifier; URLs and raw content stay out of logs.
The private JSON contains the exact URL for local review. Review the actual source
edits at these hashes and the listed existing commits before approving; a hash is
an identity check, **not a substitute for reviewing content**. No raw textual diff
is emitted by the engine. It also binds metadata-only permission changes.

`--approve` proves only that the caller supplied the reviewed identifier, not that
a person actually authorized the action. Agents must use existing task authorization
or obtain approval of the concrete plan before writes/network publication. A new
or changed plan requires a new review. A clean `status` is never push approval.

Execution re-fetches into quarantine, rebuilds/scans the full candidate, and compares
it with the approved plan. Content, branch, index, config, tool or remote-tip changes
invalidate approval (some fail earlier as conflict/drift). The plan is also checked
again immediately before execution. Reusing an unchanged no-op plan is harmless;
state changes naturally invalidate plans that performed writes.

## Incoming and outgoing behavior

`in` accepts only a remote descendant of local HEAD. Every intervening commit must
be a nonempty, single-parent change entirely within the allowlist. A remote advance
requires clean scoped source content. If remote equals HEAD, an approved `in` can
render local source edits without committing or staging them. Each existing target
must match either the HEAD render or the proposed render; manual drift blocks it.
Only the mapped source/target files are replaced; metadata ignore files are never
executed. Scoped rendering is a fixed profile, not arbitrary chezmoi configuration.

`push` requires the remote tip to be an ancestor of local HEAD. It checks **every**
outbound commit, not just HEAD: all changed paths, modes, complete scoped snapshots,
and raw commit metadata/messages. Merges, empty/unknown commits, unrelated paths,
missing required files and over 1,000 commits block publication. A secret added and
removed in earlier commits still blocks it. The remote's already-published baseline
is the trust boundary; unrelated unchanged baseline files are neither re-approved
nor scanned as new outbound content. Initial publication to an empty remote is not
supported.

A private isolated index builds the approved tree from raw bytes, without Git
filters. A new commit is created only if the tree changes, then its actual tree and
outbound history are verified again. **The push plan includes deployment of its
rendered outputs**: local commit/index and generated files become consistent before
publication. This prevents a retained local commit from turning its own old output
into unresolvable drift on retry. Existing targets still need to match a validated
baseline or candidate; this is not a drift override. No-change pushes create no
empty commit. Existing approved outbound commits can be pushed without a new commit.

Only one explicit branch refspec is pushed from quarantine. Git push uses an exact
expected-remote-OID lease to close the fetch/push race; the engine separately proves
fast-forward ancestry, so the lease cannot permit a history rewrite. It never uses
bare `--force`, a `+` refspec, tags, configured push refspecs or mirror mode. See
[Git push's expected-OID lease](https://git-scm.com/docs/git-push).

## Git/network isolation and scanner

Reads and object construction use a temporary Git repository with the source object
database as a read-only alternate, a fresh index, empty HOME/global config and
transport denial. Source Git calls are limited to metadata/index reads and a CAS
ref update, with hooks/fsmonitor disabled and lazy fetch prohibited. No configured
remote, credential helper, URL rewrite, receive-pack or remote helper is inherited.
Fetch writes neither source refs nor FETCH_HEAD. Immutable objects are transferred
back only for an approved local transaction; unreachable objects may remain after
an aborted transaction, which is normal Git object-store behavior.

Explicit transport accepts absolute local repository paths (including spaces),
`https://host/path` without embedded credentials, and `ssh://user@host/path` without
passwords. The scp form `user@host:path` is normalized to `ssh://user@host/path` (since 2026-09-26); other protocols and query/fragment credentials are rejected.
SSH uses the existing SSH agent or the user's default identity files (since
2026-09-26; a passphrase-protected file without an agent fails closed) and strict
existing known_hosts; it disables user
SSH config, interactive prompts and host-key writes. HTTPS
has no credential-helper integration, so authenticated HTTPS is not yet supported.
Use an explicit SSH URL with an already authorized agent for private remotes. The
selected remote is a trusted service; local bare fixture hooks are used only for
testing remote rejection. Real SSH/HTTPS authentication is not tested here.

Both plan and execution require a clean scan from Gitleaks 8.30.1. The existing
reviewed `--scanner ABS_EXECUTABLE` override remains available; it is trusted code,
not a way to skip scanning. Missing/invalid/inconsistent reports fail closed and
raw scanner/tool errors never reach console output. Commit metadata is scanned via
a neutral allowed snapshot slot, so a metadata finding may name the shared
instructions slot rather than a repository file. See [scanner details](secret-scanner.md).

## Transactions and recovery

Before changing files, the engine rechecks the approved state and acquires Git's
`index.lock`. It stores private old/new bytes, modes, hashes, paths and old/new ref
IDs in `.git/ai-agent-sync-transaction/manifest.json` and numbered backup files.
Files are replaced atomically one at a time. The branch ref update compares the
expected old OID; see [Git update-ref](https://git-scm.com/docs/git-update-ref).
The isolated index becomes the real index only within this guarded transaction.
For local-only `in`, the original index bytes are preserved.

An ordinary failure rolls changed files and index back only if they still match
this transaction's writes. It never restores over a later external edit. If the
ref update may already have succeeded, or safe rollback cannot be established,
`RECOVERY_REQUIRED` preserves the journal and blocks later writes. These are
multi-file transactions with recoverable intermediate state, not an atomic
filesystem-wide swap; an external reader may observe the intermediate files.

After SIGKILL, power loss or an ambiguous failure:

1. Stop other sync/Git/editing activity. Inspect the lock owner and make sure that
   process is no longer running. Never delete an active lock or auto-expire it.
2. Keep a copy of the transaction directory outside Git. Inspect its manifest and
   current HEAD/index/recorded file hashes. Do not publish the backup contents.
3. If HEAD is the recorded old head, restore only files matching the recorded new
   hashes from their numbered old backup, with the recorded old modes. Leave
   already-old files alone. A third value requires manual reconciliation.
4. If HEAD is the new head, verify/complete the corresponding new files/index from
   the backups rather than automatically rewinding HEAD. If HEAD is neither,
   reconcile with the concurrent work first. No automatic reset is provided.
5. Only after verifying the entire manifest, remove this transaction's journal and
   stale sync/index locks, then create a fresh plan. Never remove agent directories.

The journal is a local recovery aid, not a power-loss durability guarantee or a
replacement for the separately required migration backup. Cooperative sync callers
share the lock; arbitrary external writers do not. Rechecks, index locking and ref
CAS reduce races but cannot prevent a same-user process deliberately bypassing them.

If the remote rejects a push or the connection fails after local commit, return
`NETWORK_ERROR` and retain the approved local commit, clean index and generated
outputs. The remote may have accepted before a connection failure; fetch/re-plan
before retry. No rollback, automatic retry, remote history rewrite or success claim
occurs. A refusal due to concurrent remote advancement requires resolving that
history separately.

## Results and validation

| Result | Exit |
| --- | --- |
| `OK`, `NO_CHANGES` | 0 |
| `DRIFT` | 2 |
| `USAGE` | 64 |
| `INVALID_*`, `UNSUPPORTED_*`, `BLOCKED_LAYOUT`, `BLOCKED_OVERRIDE`, `BLOCKED_SYMLINK` | 65 |
| `BLOCKED_CONFLICT`, `BLOCKED_STAGED_CHANGES`, `BLOCKED_INDEX_FLAGS`, `BLOCKED_BRANCH`, `BLOCKED_LOCAL_CHANGES`, `BLOCKED_*HISTORY*`, `BLOCKED_NON_FAST_FORWARD` | 66 |
| `BLOCKED_SECRET` | 67 |
| `BLOCKED_STALE_PLAN`, `BLOCKED_EXPIRED_PLAN` | 68 |
| `MISSING_DEPENDENCY` | 69 |
| `GIT_ERROR`, `SCANNER_ERROR`, `IO_ERROR` | 70 |
| `NETWORK_ERROR` | 71 |
| `RECOVERY_REQUIRED` | 72 |
| `BLOCKED_LOCK` | 73 |
| `INTERRUPTED` | 130 |

Unknown nonzero exits are failures. Missing files may report `IO_ERROR`; they are
never auto-created as a deployment side effect. Run the tests with pinned Gitleaks
on PATH:

```sh
sh tests/test-render.sh
sh tests/test-status.sh
python3 tests/test-offline-status.py
python3 tests/test-scanner.py
python3 tests/test-write.py
python3 tests/test-migration.py
```

Write tests create real commits and push **only to disposable local bare fixtures**.
They never use a personal home, private chezmoi source, SSH login or external remote.
macOS and local file transport are tested. Linux, Git Bash/WSL, real SSH/HTTPS,
product loading and migration/legacy caller cutover remain separate acceptance gates.


## Agent-driven memory checkpoints (2026-09-25)

This is the current daily-sync requirement, replacing the goal of automatic
pre-CLI launch family tracking. It uses the existing Shared Core instructions and
single [dotfiles-sync skill](../examples/chezmoi/.chezmoitemplates/ai/shared/skills/dotfiles-sync/SKILL.md).
Bootstrap/installation is separate. No new launcher, guardian, hooks, process tracker,
service or installer is required. Historical loading research/tests remain; their
mixed-revision gate is still BLOCKED, not repaired or waived by this workflow.
The writer lock and recovery journal remain binding; known concurrent configuration
use requires deferring application. Unmanaged concurrent sessions are not automatically
detected, and no cross-session live-reload guarantee is made.

Phase 3 capability check used the deployed skill read-only, the public engine/adapter
code and the retained Phase 3H validation record; it did not rerun private production
validation. Phase 3 already has shared instruction/skill rendering, offline status,
quarantined incoming plans, approved in/push, scanner, writer lock, drift/history
checks, scoped publication and rollback. The missing capability was the agent's
three-checkpoint instruction policy. Public instructions prohibited session-start
sync and the skill referred to the experimental launch controller; those directives
are replaced. The engine and historical loading implementation are unchanged.

| Checkpoint / condition | Required agent behavior | Verification boundary |
| --- | --- | --- |
| First turn, before substantive work | Proactively invoke skill; resolve reviewed roots/profile; local status, then permitted remote in plan; review and apply within authorization; re-read changed rules/skills | Isolated scripted incoming + two-agent render/readback; not proof that every model automatically invokes the skill |
| No updates | Remote plan unchanged plus local state consistent: begin work without execution/empty commit | Existing no-change test; local status alone cannot establish remote freshness |
| Confirmed important memory | Authorized edit to existing authoritative global source or project documentation as appropriate; distinguish recorded from applied/published | Scripted source-only edit remains absent from deployed targets until approved sync |
| Task completion / explicit end | Check local edits and pending outbound commits; reviewed push only when authorized; otherwise report pending | Scripted publication/readback and no-op finish; forced exit is not covered |
| Offline / unreachable remote | Report freshness unknown, defer sync and use existing memory for unrelated work | Existing network-failure test proves no mutation; reporting wording is instruction review |
| Conflict / staged changes / drift | Preserve state, defer writes; no reset/stash or automatic conflict resolution | Existing real-engine refusal tests |
| Missing approval | Produce reviewable plan if allowed; mark pending, do not execute | Missing --approve rejected in fixture; human authorization remains an agent obligation |
| Missing scanner / invalid report | Block; no installation or passing substitute | Existing scanner failure and real pinned scanner tests |
| Existing barrier/journal / known concurrent use | Defer application; never remove the barrier | Existing engine lock tests; known unmanaged concurrency is a policy obligation, not automatic family detection |
| Successful sync | Re-read changed source and deployed rules/skills; verify status; identify restart-needed or unverified native reload | Scripted readback/render consistency, not runtime hot reload |

Approval compatibility: v2 already allows existing explicit task authorization OR
approval of a concrete reviewed plan. It does not require a fresh question for each
unchanged, already-authorized operation. However PLAN_ID is only a content identity;
the engine cannot verify human consent. Automatic checkpoints do not confer arbitrary
write/push consent, broaden mapping or reuse the completed Phase 3 publication approval.
If authorization does not cover the actual roots/profile/remote/branch/changes, the
agent must stop the write at pending approval. Plan changes require fresh review,
with another question only when existing authorization no longer covers the action.
There is no newly invented standing-policy format or approval bypass.

Report recorded locally / applied locally / synchronized remotely / pending approval /
blocked distinctly. Push failure can leave a local commit; an uncertain remote outcome
is unconfirmed, not synchronized. A clean worktree can still have unpublished commits.
Project-only memory outside the mapping is not publishable through v2. Never save raw
chat, credentials, session state or project trust as shared memory.

Validation results for this change are recorded in the archived
[implementation status](history/implementation-status-2026-09-25.md). This is a
public instruction/skill change only; production has not received these triggers.
Model-driven automatic invocation is a behavioral requirement, not a deterministic
process hook; no new Claude/Codex model runtime qualification is claimed here.

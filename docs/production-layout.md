# Phase 2.7 — Production Layout Compatibility

Scope: public code and synthetic fixtures only, based on accepted Phase 2.6
`50fabd55bd2d6d8865501ce739184937d3d0560b`. This stage does not migrate, relocate,
deploy to, commit, or push the private repository. Stop after review; production
3A–3D and its mandatory 3D gate require explicit continuation.

## Root and payload boundary

`scan-secrets.py` owns `validate_layout`, consumed by status, write and migration.
Validation happens before source lock acquisition and again in Python engine
initialization. This replaces the blanket overlap rejection with these rules:

| Relationship | Result |
| --- | --- |
| Separate source/destination roots | Supported |
| Source at `destination/.local/share/chezmoi` | Supported |
| Other source below destination, outside reserved deployment regions | Supported |
| Equal roots, or destination inside source | Rejected |
| Source intersects `.claude`, `.codex`, `.agents`, or `.config/ai-agent` under destination | Rejected, even for the Claude-only profile |
| Either root contains the fixed `/tmp` scratch allocation area | Rejected |
| Managed file or its parent is a symlink, including dangling links | Rejected |
| Managed payload is a hard link, special file, or directory | Rejected |

Explicit root aliases are canonicalized, preserving macOS `/tmp` compatibility
and canonical Git lock identity. This is authorization of the selected canonical
root, not permission to follow symlinks inside managed paths. Invalid layout
returns exit 65 before reading approval payloads or acquiring a source lock.
Inactive product regions are compared lexically, without opening Codex files in
the Claude profile. The normal source identity, Git metadata, scanner and profile
checks still apply; linked Git worktrees remain unsupported.
Git metadata symlinks, alternate object stores and `commondir` indirection are
rejected consistently, including by status, before Git object access.

Only static profile mapping paths are read as source/target payloads. Migration
adds its fixed legacy mapping for backup and approved removal. Relative mapping
entries cannot be absolute or contain `..`. Saved migration manifests must match
the expected path sets exactly; a recomputed approval hash cannot expand scope.
No operation recursively walks destination HOME, discovers credentials/runtime
files, or invokes production chezmoi across HOME. Status renders a bounded source
snapshot in isolation. Write and migration deploy only their fixed mapped files.

Migration inventories the bounded skill/shared-template subtrees to reject unknown
payloads. Its alias check enumerates source names only along mapped target prefixes,
pruning unrelated directories before descent. It does not walk unrelated source
subtrees or follow their symlinks. Git object/metadata validation and history tree
inspection remain inside the selected checkout or temporary Git repository; these
are repository metadata operations, not HOME payload scanning. As before, unknown
unrelated source contents are neither interpreted nor certified by the engine.

## Plans, backups, locks and rollback

Migration backup packages remain outside both source and destination. Since 2026-09-26 a plan file only needs to be outside the source checkout and the deployment regions; see [sync-v2](sync-v2.md#local-configuration-file).
For destination HOME, a path under HOME is therefore invalid, even if ignored by
Git. Choose an explicitly approved, owner-private external location. A temporary
directory suffices for fixtures but is not a durable production rollback strategy.
Local bare test remotes also remain outside source and destination. This stage
does not change remote authentication or outbound history checks.

Locks/journals remain scoped to the selected source `.git`. Source files are never
target outputs because the source cannot intersect a reserved deployment region.
Migration rollback operates only on hash/mode-bound manifest paths and recorded
created directories. It does not remove HOME, `.local`, or source ancestors.
Approval hashes, stale-state checks, scanner pinning, index/ref checks, guarded
rollback, and refusal to overwrite later edits remain in force.

No filesystem-wide atomicity or defense against a hostile concurrent process
swapping directories between validation and a syscall is claimed. Existing locks
coordinate cooperating writers; symlink checks and state hashes detect stable
escapes/drift. Treat unrelated concurrent mutation as a recovery risk and retain
backups. This stage does not introduce arbitrary path manifests or a trust bypass.

## Isolated verification

`python3 tests/test-layout.py` reruns the migration and write contracts with
source at `<fixture HOME>/.local/share/chezmoi`, including real chezmoi rendering,
Claude-only conversion, staged expansion in disposable fixtures, bootstrap offline
in, status, local-remote plan/in/push, pinned real scanner/history tests, failure
recovery and rollback. No production HOME/source or remote participates.

Additional cases cover reserved-region/equal/reversed roots across entrypoints,
source/target symlinks to external files and Git HEAD, parent symlinks, hard links,
mapping/manifest traversal, external-only plan/backup storage, and unrelated HOME
and source sentinels. Unmanaged symlinks and FIFOs must survive without traversal,
scanning or modification. Existing sibling-root scanner, offline status, render,
status, migration and write suites remain regression gates.

Test results and review status are recorded in
[implementation-status-2026-09-25.md](history/implementation-status-2026-09-25.md). Fixture acceptance is not
actual Claude loading, production inventory classification, statusLine validation,
or a production 3D PASS. No private source is read during Phase 2.7.

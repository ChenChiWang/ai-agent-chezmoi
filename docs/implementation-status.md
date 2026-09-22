# Implementation status

## Phase 2.7 Production Layout Compatibility (2026-09-22)

- Public baseline: `50fabd55bd2d6d8865501ce739184937d3d0560b`. The user
  authorizes public implementation, isolated tests and review only. Prior
  uncommitted preflight documentation is retained as historical evidence.
- Centralized layout validation now allows source under destination HOME outside
  reserved deployment regions, and rejects equal/reversed roots, managed symlink
  and hard-link escapes, unsafe parent types, Git metadata symlinks, and roots
  encompassing the scratch allocation area. Validation precedes source locking.
- Source aliases are canonicalized; managed descendants are not followed through
  symlinks. Migration alias discovery prunes unrelated source trees. Destination
  payload access remains the static profile mapping; no HOME tree walk occurs.
- Plans/backups/local test remotes remain outside both roots. Scanner version,
  approval hashes, legacy conversion mapping, historical scans and guarded
  rollback requirements are unchanged. No alternate scanner bypass was added.
- Added `tests/test-layout.py`, reusing the complete migration/write contracts at
  `<fixture HOME>/.local/share/chezmoi` plus boundary, manifest, sentinel and
  traversal cases. All remotes and deployments are disposable local fixtures.
- Review found and corrected status's invalid-profile error precedence (retains
  exit 64); unsafe managed paths now fail earlier with `INVALID_LAYOUT` / 65.
  The status symlink assertion was updated to this explicit diagnostic contract.
- Review result: **PASS for the public macOS isolated-fixture contract**. Reviewed
  the shared root validator, status/write/migration entrypoints, bounded alias
  traversal, saved-manifest path admission and existing rollback mutations.
  No known blocking finding remains in this scope. This is not production 3D.
- `tests/test-layout.py`: 61 distinct scenarios passed: the 58-case full run
  finished in 199.965s, followed by the three added Git symlink/alternate-store and
  invalid-profile cases. After final review changes, those three plus the full
  nested 3A–3D/rollback scenario passed together (4 tests, 9.127s). The source/HOME
  no-traversal scenario was also rerun after shared validation changes.
- Existing sibling-layout regressions: migration 24/24 (104.150s), write 27/27
  (94.360s), pinned real scanner 10/10 (33.684s), offline status 6/6 (latest rerun
  6.398s). Render/status shell suites passed; status was rerun after the diagnostic
  assertion and invalid-profile precedence fixes.
- Python AST/shell syntax, both profile mappings and wrappers/literal rendering,
  new-file LF/whitespace, `git diff --check`, and unchanged legacy v1 engine checks
  passed. macOS temporary-directory lookup warnings in cleared test environments
  did not affect fixture isolation or results.
- Limits: no production Claude loading/statusLine/chezmoi regression or private
  inventory classification was attempted. Production needs a durable owner-private
  backup/plan location outside HOME. Existing cooperating-writer and recoverable
  transaction assumptions remain; no hostile concurrent filesystem-race guarantee
  or new platform/SSH/HTTPS validation is claimed. Stop for user acceptance.
- No private source read, relocation, mutation, production deployment, repository
  commit/push or Phase 3 execution occurred in Phase 2.7. See
  [production-layout.md](production-layout.md) and the mandatory
  [Phase 3 gate](phase-3-roadmap.md).

## Accepted Phase 2.6 Migration Readiness (2026-09-22)

- Baseline: public `03bbd09e0674cf5494dc4a44ee37438b77ce3533`; previous uncommitted
  Phase 3 roadmap/status changes preserved. This task authorizes public code/tests
  only: no private source, Phase 3 execution, repository commit or push.
- Implemented 2.6A staged `claude` (31 source / 14 targets) and `claude-codex`
  (39 / 21) profiles. Scanner owns the static mapping/wrapper schema consumed by
  shell status, Python write and conversion engines; profile is approval-bound.
- Implemented 2.6B mapping/render/scan/history for all six skills and Claude-only
  settings. Five public examples are new generic content, not private copies.
  Conversion preserves actual legacy skill output bytes and settings exactly.
- Implemented 2.6C offline `migration plan/apply/verify/rollback`, persistent private
  baseline blobs/manifest, explicit rule segmentation, safe plain-to-template
  conversion and legacy forwarding entrypoint. No Git commit/ref/index change or
  remote access is required to bootstrap. Added explicit offline `in` with a
  hash-bound migration baseline while HEAD is still legacy; push cannot use it.
- Shared literal opener escapes preserve JSX/Go-looking examples without arbitrary
  template execution. Both original/encoded and decoded rendered snapshots are
  scanned. Fixed named-template wrappers replace the earlier raw-include schema.
- Recovery validates all old/new values before restoring, preserves later edits,
  tracks created-directory ownership, and retains a journal on unsafe recovery.
  Later Codex expansion has separate approval/backup and reverse-order rollback.
- 2.6D uses fake legacy rules, six skills, three-key settings, a legacy execution
  sentinel, isolated homes/chezmoi state, real local Git and synthetic runtime state.
  It simulates 3A–3D and separately tests a future Codex expansion; no private
  production data or actual product sessions participate.
- 2.6E review: **PASS within the public/macOS/synthetic-fixture contract**. No known
  blocking finding in that scope. Reviewed tracked changes and new implementation,
  schema, backup/approval, templates, tests and documentation. No production
  regression or private inventory equivalence is implied. See
  [design, commands and acceptance boundaries](migration-readiness.md).

### Phase 2.6 verification

- `tests/test-migration.py`: 24 scenarios passed. Final full 23-case run passed in
  79.256s; the added explicit test with no Codex directories passed separately in
  4.391s. Covers complete fake 3A–3D, later expansion/reverse rollback, six skills,
  settings/rules, literal template examples, scanning, drift, unknown inventory and
  templates, aliases, collisions, stale/tampered backups, locks, partial failures,
  later edits, created-directory ownership and incomplete legacy deletions.
- `tests/test-write.py`: 27/27 passed (90.553s), including a secret removed from an
  added shared skill's outbound history. Existing normal-sync behavior preserved.
- `tests/test-scanner.py`: 10/10 passed (32.759s) with Gitleaks 8.30.1. Migration
  scenarios also scan real synthetic credentials at every newly added skill path.
- `tests/test-offline-status.py`: 6/6 passed (6.679s). No-lazy-fetch boundary intact.
- `sh tests/test-render.sh`, `sh tests/test-status.sh`: passed. Actual chezmoi output
  and Python rendering agree, including literal opener escapes and staged profiles.
- Python AST/shell syntax, six skill frontmatters (Ruby YAML safe-load), complete
  profile/wrapper mapping, changed/new-file LF/whitespace, `git diff --check`, empty
  public index and unchanged legacy v1 engine checks passed. Skill Creator's Python
  validator remains unavailable because PyYAML is absent; no packages installed.
- Review corrections: local-only in no longer copies unused Git objects or writes
  same-OID reflogs; raw and decoded history are both scanned; template openers use
  a bounded literal escape; rollback preserves external directories/later edits;
  unknown shared definitions block expansion; bootstrap requires the approved
  legacy-source deletions to be complete.

### Phase 2.6 stop / remaining limits

- No private source or actual Claude/Codex configuration was read, modified or
  deployed during this task. Tests use synthetic data, isolated homes/chezmoi state,
  and disposable local Git repositories. No real external Git remote operation.
- No public/private commit or push. Public HEAD remains `03bbd09`; initial roadmap
  and status edits are preserved alongside the new uncommitted implementation.
- Readiness is for the documented legacy layout and two closed profiles. Unknown
  skills/payloads/frontmatter/settings keys or source encodings stop for review.
  Instruction classification is explicitly reviewed; byte preservation alone
  does not prove semantic correctness. Backups are scoped and private, not a full
  home backup or a power-loss guarantee.
- Real Claude loading, real statusLine dependencies, production chezmoi config/hooks,
  fresh private inventory comparison, Windows/Linux and real SSH/HTTPS remain
  unverified. First migration publication is still a separately authorized 3H
  review; offline bootstrap cannot enable push or weaken its history checks.
- The [Phase 3 roadmap](phase-3-roadmap.md) persists. Phase 3A remains unstarted;
  3D is still a mandatory stop, and 3E–3H require later approval.

## Previous session: Phase 3 preflight stopped (2026-09-22)

- Phase 2.5 is accepted and published at `03bbd09e0674cf5494dc4a44ee37438b77ce3533`.
- User now authorizes private migration 3A–3D only. Preserve existing user rules
  and Claude-only settings; do not deploy Codex and do not push the private repo.
  This supersedes the older migration-pause statements below.
- Full [Phase 3 roadmap and stop evidence](phase-3-roadmap.md) recorded for later
  sessions: 3A baseline/rollback, 3B Shared Core, 3C Claude cutover, **3D mandatory
  regression gate and stop**, 3E Codex deployment, 3F Codex validation, 3G cross-agent
  validation, 3H final private commit/push. 3E–3H remain unauthorized.
- Preflight recovered the accepted inventory and inspected public source. The
  fixed engine requires both adapters, lacks the five additional skill mappings,
  and requires an already-migrated v2 HEAD/output baseline. These contracts do not
  support the requested Claude-only legacy migration as published.
- Stopped under the user's explicit incompatibility instruction. No private source
  inspection or mutation, baseline backup, migration, deployment, commit, push or
  Claude regression execution occurred during this attempt. 3A is not complete;
  3B–3D have not started. No rollback of private state is needed.
- Only public roadmap/status documentation changed. No engine extension or silent
  workaround was attempted. Resolve the documented reference gaps before resuming;
  prior isolated Phase 2.5 passes must not be reported as a Phase 3D pass.

## Current acceptance: v2 safe sync engine (2026-09-22)

- Baseline: `0668304`, public `ai-agent-chezmoi`, clean working tree at task start.
- Inventory accepted; private migration remains paused. This section supersedes
  the historical Phase 1 stop point and unsupported-command notes below.
- Added shared `sync-write.py`, its generated wrapper, and `tests/test-write.py`.
  `sync.sh` dispatches `plan`, `in`, `push`; offline status remains intact.
  Scope is now 19 source files / eight generated outputs. Scanner, shell and Python
  mappings agree. One shared skill routes both agents through the same engine.
- Implemented owner-only approval plans (SHA-256 ID / one-hour expiry), canonical
  source lock, quarantined fetch/index/objects, scoped FF incoming changes,
  generated drift protection, raw-byte tree construction and full outbound commit
  inspection (including intermediate snapshots and commit metadata).
- Staged changes and special index flags are refused intact. Unknown/out-of-scope,
  empty or merge commits block synchronization. No implicit source discovery,
  unrestricted re-add/apply, automatic staging, stash/reset/rebase or source hooks.
- Approval binds source/destination, HEAD/ref/index/config, exact remote/branch,
  candidates/outputs, identity/message and trusted helper/scanner files. Execution
  rebuilds, re-scans and compares; local state is rechecked before mutation.
- Push plans explicitly include generated-output deployment. The approved local
  commit/index/output state is retained on remote rejection; retry requires a new
  plan. This prevents a push from leaving its own deployment behind its new HEAD.
- Push uses one explicit refspec and an exact expected-OID lease, after an independent
  ancestry proof. No history rewriting is permitted. Source refs use old-OID CAS;
  ordinary Git writers also encounter the transaction's index.lock.
- File/index transactions preserve old/new bytes, modes and hashes in a local Git
  journal. Normal failures safely roll back; concurrent edits are preserved and
  uncertain recovery keeps the journal. SIGKILL/power-loss recovery is manual and
  documented, with no automatic stale-lock deletion or reset.

### Verification and review

- `tests/test-write.py`: final full run 26/26 passed (53.262 seconds).
  Real local fixture commits/bare-remotes cover incoming, source-only apply, scoped
  publication, no-op, stale/tampered/expired plans, staged work, drift, secrets in
  removed history/messages, unrelated history, remote rejection/retry, remote and
  source races, scanner failure, source hooks/filters, lock aliases, paths with
  spaces/Chinese, deployed-engine plan invariants, rollback and concurrent-edit
  recovery. Real Gitleaks covers clean publication and removed historical secrets.
- `sh tests/test-render.sh` and `sh tests/test-status.sh`: passed, including the
  new helper/output and actual chezmoi equivalence for the Python renderer.
- `python3 tests/test-offline-status.py`: 6/6 passed, preserving no-lazy-fetch.
- `PATH=/private/tmp/ai-agent-gitleaks-8.30.1:$PATH python3 tests/test-scanner.py`:
  10/10 passed with the existing pinned binary; no dependency installed.
- Shell syntax, skill YAML (Ruby safe-load), whitespace and legacy-engine unchanged
  checks passed. Skill Creator quick_validate remains unavailable (missing PyYAML);
  no package installation attempted.
- Review: no known blocking finding in this fixed-profile/macOS/local-transport
  acceptance scope. Reviewed candidate/tree integrity, staged-state preservation,
  network isolation, historical leaks, approval freshness, transaction failure and
  retry behavior. Shared Core + thin Claude/Codex adapters is preserved.

### Limits / stop point

- This replaces legacy **operations for a migrated v2 profile**, not arbitrary
  existing private layouts. Inventory-to-schema mapping, first deployment, backups,
  legacy wrapper/trigger cutover and product loading are not done or authorized here.
- Authenticated HTTPS helpers, SCP aliases, linked worktrees, SHA-256/shallow repos,
  new/missing/deleted mappings, merge histories and empty remotes are unsupported.
  Private remotes can use explicit SSH URLs with an existing agent/known_hosts;
  actual SSH/HTTPS and Linux/Windows/WSL behavior remain unverified.
- Locks protect cooperative callers. Manual same-user writers can bypass them;
  multi-file replacement is recoverable, not an atomic filesystem-wide snapshot.
  Unreachable immutable Git objects may remain after a failed transaction. A
  journal is not a power-loss guarantee or a substitute for migration backups.
- Only public template/docs/tests changed. No private chezmoi or real agent config
  was modified or deployed. No commit/push in the public or private repository;
  real commits/pushes occurred only in disposable local test fixtures. No external
  Git remote or credentials were used. Migration remains paused; stop after review.

## Historical Phase 1 record

## Baseline

- Commit: `8cb9ce370ac97e75c3a57dd541339b2c306e8d2a`, branch `main`.
- Existing untracked `docs/AGENT_SHARED_CONFIG_HANDOFF.md` preserved unchanged.
- Host: macOS (Darwin), zsh; scripts use POSIX sh.
- Git 2.55.0, chezmoi 2.71.0, Claude Code 2.1.278, Codex CLI 0.155.1.
- Codex version query reported a denied attempt to create PATH aliases; no retry
  with expanded permissions. IDE extension version/loading not inspected.

## Completed

- Added `examples/chezmoi/`: shared instructions, shared skill, two thin adapters,
  seven generated entries (including scanner/registry), one shared shell engine, ignore/LF examples.
- Implemented explicit-source, scoped, offline status: staged/working changes,
  generated-file drift, isolated rendering, scanner interface and nonzero errors.
- Unsupported `plan`, `in`, `push` fail before tool/source access.
- Added `tests/helpers.sh`, `tests/test-render.sh`, `tests/test-status.sh`.
- Updated both READMEs, the legacy setup guide, legacy skill version notice, and
  legacy ignore example; preserved the legacy engine byte-for-byte.
- Added `docs/migration-v2.md` with API, dependencies, limits, migration and rollback.

## Verification

- `python3 tests/test-offline-status.py`: 6 tests passed with real Git 2.55.0.
  Trace2 verifies no fetch child and no fake SSH invocation for missing index/
  HEAD blobs and missing HEAD trees. Also covers complete local partial-clone
  objects, regular missing objects and unsupported Git capability.
- `tests/test-scanner.py` with verified Gitleaks 8.30.1: 10 real-scanner/protocol/
  integration tests passed on macOS ARM64; shell render/status suites also passed
  after the scanner integration.
- `sh tests/test-render.sh`: passed. Actual chezmoi rendering/apply restricted to
  temporary fixtures; identical skills, shared edit reaches both entries, adapter
  separation, exactly seven output files, frontmatter, LF, executable engine,
  repeat apply unchanged.
- `sh tests/test-status.sh`: passed. Covers scoped source/index/HEAD/destination invariants,
  source/target drift, unrelated staged/untracked files, synthetic source/index/
  destination secrets, scanner failures/missing executable, dynamic-template
  rejection, ignored out-of-scope hooks/config, symlinks, override/custom home,
  executable-bit drift, missing target, conflicts, and unsupported writes.
- `sh -n` on the engine and three test scripts: passed.
- `git diff --check`: passed for tracked changes.
- `git diff --exit-code -- examples/dotfiles-sync/sync.sh`: passed (v1 unchanged).
- Skill Creator `quick_validate.py`: could not run because PyYAML is unavailable;
  no packages installed. Ruby YAML safe-load verified required frontmatter fields;
  rendered skill frontmatter is also checked by the fixture suite.
- macOS Python emitted a temporary-directory lookup warning in the cleared test
  environment and fell back to `/tmp`; all fixture paths remain explicitly isolated.

No real commits are created even in tests. The HEAD comparison case uses a Git
shim with real index blobs, not a committed-history integration test. Actual
Git init/add/update-index in tests affect only temporary fixture repositories.

## Decisions and differences from the handoff

- Phase 1 never auto-discovers a private source: explicit source/destination paths
  are required and source must be a regular Git root. Worktrees are deferred.
- Uses literal include wrappers. Shared files reject opening template delimiters
  because chezmoi parses `.chezmoitemplates` even when include is used. Wrapper
  changes require a matching engine schema change; arbitrary Go templates are
  unsupported. This trades flexibility for a bounded, offline render.
- Render uses only the v2 profile in a temporary source. Existing private config,
  hooks, externals and ignore behavior are not simulated or certified.
- Status prints labels/known paths only, no raw diff. Gitleaks 8.30.1 is now the
  default scanner via a Python standard-library adapter. A strict schema validates
  every finding before exposing only known snapshot paths, pinned rule IDs and
  line numbers. Raw tool output and secret/match fields are never forwarded.
- Added a small Python helper for JSON/report validation, preserving the POSIX
  synchronization engine. Source scope grew from 13 to 17 files; output scope
  grew from five to seven files. No product settings were added.
- No real deployment and no v1 wrapper switch. Same-name skill installation must
  wait until migration/write behavior is ready and separately authorized.

## Not verified / limitations

- Outbound history, plan approval, locks, pull,
  push, migration tooling and actual rollback are Phase 2 or later work.
- No Claude/Codex product loading test; no private home/override inventory.
- No Windows, Git Bash, WSL or Linux runtime tests; no ShellCheck installed.
- No new CI workflow or automatic dependency installation.

## Safety boundary

- Real agent configuration deployed/edited: no.
- Private chezmoi source read or modified: no.
- Credentials/tokens read or printed: no.
- Repository commit/push or real external remote operation: no. Offline regression
  uses a fake transport only for its positive control.
- `/init`: not run.
- Fixture apply/init/add: temporary paths only, inherited environment cleared.

## Scanner follow-up

- Added `scan-secrets.py`, pinned `gitleaks-rules.json` (222 IDs), two output
  wrappers, `tests/test-scanner.py`, and `docs/secret-scanner.md`.
- Default scanner is the bundled adapter; `--scanner` overrides require a
  schema-1 report as well as the correct exit code. Old exit-code-only adapters
  now fail closed. Updated test doubles, shared skill and both READMEs.
- Official macOS ARM64 Gitleaks 8.30.1 downloaded with network approval to
  `/private/tmp/ai-agent-gitleaks-8.30.1`, archive SHA-256 verified before extraction.
  No global install. Runtime tests are offline and use only synthetic data.
- Real tests cover GitHub PAT, generic API key and private-key patterns; source,
  index, HEAD, render and deployed snapshots; ignore/config/inline bypass attempts;
  missing tool, wrong version, failure, timeout, unsafe/malformed/inconsistent
  reports; symlink/unreadable/oversized/invalid text; deployed engine redaction and
  unchanged Git/source/destination state. No real commit created.
- Main command: `PATH=/private/tmp/ai-agent-gitleaks-8.30.1:$PATH python3 tests/test-scanner.py`.
  The suite fails instead of skipping when the real binary is missing.
- Gitleaks remains heuristic; built-in content allowlists remain active. Snapshot
  input is limited to readable UTF-8 text (8 MiB per file), no NUL or symlinks.
  Archives, arbitrary binary data and real outbound history are not covered.

## Stop point

Phase 1 implementation, scanner and final review only. No private migration, production
home deployment, plan/pull/push implementation, commit or push. Further work
requires a new user instruction; the next architecture stage remains safe plans
and outbound-history verification, not automatic migration.

## Phase 1 final review (2026-09-22)

- Result: PASS for Phase 1; no remaining blocking findings in the reviewed scope.
- Rerun after the P1 fix: render/status suites passed, scanner suite 10/10 passed,
  offline regression 6/6 passed. Shell/Python syntax, tracked `git diff --check`,
  new-file whitespace/LF checks and source/target mapping consistency passed.
- Reviewed tracked diff and all untracked implementation/test files, not just
  `git diff` (the new shared tree is still untracked). Existing handoff retained.
- Architecture matches Shared Core + Claude/Codex adapters: one shared rules
  source, one shared skill, two thin product instruction tails, and one neutral
  engine with a shared scanner. Generated skills are identical and both use the
  same engine path. No new product settings or automatic session-start writes.
- Prior P1 (called P11 in the follow-up) is fixed. Every Git read passes
  `--no-lazy-fetch` and sets `GIT_NO_LAZY_FETCH=1`; all transport protocols are
  denied with an empty `GIT_ALLOW_PROTOCOL`. Capability is checked before object
  access; unsupported Git fails closed. Missing objects return `GIT_ERROR`.
- Regression has a positive control: unprotected real Git reproduces lazy fetch
  through a fake SSH transport. Protected status does not start a fetch child,
  proven with Trace2, and preserves source/index/HEAD/destination contents/modes.
  No real SSH, credentials, network connection or commit is used in that test.
- Shell/scanner source/target allowlists agree. The original v1 engine is
  byte-for-byte unchanged; legacy entrypoints remain explicitly documented.
- Final acceptance is limited to the Phase 1 template/isolated-test scope. Real
  product loading, other platforms, outbound history, shared mutation locks,
  approval plans, write workflows and private migration remain unverified/deferred.

# Phase 3 authorized preflight stop — 2026-09-22

- User accepted public baseline `50fabd55bd2d6d8865501ce739184937d3d0560b`
  and authorized only 3A–3D, with an immediate stop on production mismatch or
  unreliable regression validation.
- Read-only checks passed: expected private remote identity, clean `main`, six
  skill directories and payload/frontmatter schema, Claude-only settings keys,
  all nine legacy deployed files matching source bytes, settings mode equality,
  and no checked v2 source/output collisions.
- Initial dependency block resolved with subsequent explicit approval: installed
  Gitleaks 8.30.1 in the user's local bin directory from the archive matching the
  SHA-256 recorded in `secret-scanner.md`. Installed binary SHA-256:
  `ba52fb1bfabbcde42f032afad3d6e0b19dff8ed105229a16e7caa338bbc0e84f`.
  Login zsh, interactive zsh, and inherited-PATH sh resolve the installed binary
  and report exactly 8.30.1. No shell configuration or scanner requirement changed.
  `python3 tests/test-scanner.py` passed all 10 tests using the installed binary
  through the ordinary PATH, including real detections, fail-closed behavior,
  redaction, and engine integration (27.843 seconds; isolated synthetic inputs).
- New blocking mismatch: real source is contained by destination home. The
  accepted engine explicitly rejects nested roots; read-only migration engine
  initialization returns `INVALID_SOURCE` (65). Fixtures use sibling roots.
  Stopped without relocating source or changing the reference implementation.
- Stopped before baseline creation or conversion. No private source, Git state,
  Claude settings/skills/output, or Codex deployment was changed. No private
  commit/push occurred. There is no migration diff or migration rollback to run.
- 3A incomplete; 3B/3C/3D not executed; production Claude loading, statusLine,
  chezmoi behavior, sync/scanning and rollback restoration remain unverified.
  This is not a 3D PASS. See [phase-3-roadmap.md](phase-3-roadmap.md).

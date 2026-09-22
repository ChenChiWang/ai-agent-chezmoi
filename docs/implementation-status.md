# Implementation status

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

# Phase 4B isolated bootstrap implementation (ARCHIVED 2026-09-26, not maintained)

**Review build; do not install these launchers into production PATH.**
This is public code and isolated test coverage. It does not imply a real-machine
bootstrap/launch qualification or authorize changing the Phase 3 private source.
See [review status and blockers](../../docs/history/phase-4b-validation.md).
The [generation cohort design](../../docs/history/phase-4-generation-cohorts.md) is accepted.
A real guardian, neutral exec bridge and v2 integration now exist, but native
family retirement remains **BLOCKED**. Initial-enrollment crash consistency is
repaired; read the [latest repair review](../../docs/history/phase-4-blocker-repair.md) before
running any manual fixture. No production qualification is implied.

## Components

| File | Responsibility |
| --- | --- |
| `bootstrap.py` | Hash-bound first deployment/adoption, three profiles, switch/reactivation, durable backups, explicit guarded recovery |
| `launch.py` | Single neutral controller: policy checks, v2 plan/in, leases, original CLI stream/argv/exit/signal handling |
| `launcher.py` | Emits a thin agent-specific shim and compiles the shared exec bridge into explicit external state; no per-agent sync logic |
| `tools.py` | Reviewed lockfile, exact artifact digest, safe archive reading, version health, idempotent owned installation, separate prerequisite outcomes |
| `guardian.py` | Kernel lifetime evidence and explicit hash-bound recovery; forked-family retirement remains unqualified |
| `exec-bridge.c` | Preserves original signal state across Python before native exec |
| `artifacts.py` | Bounded tool-tree extraction, integrity receipts and isolated pinned Git build |
| `path-integration.py` | Reviewed owned PATH entries, shell block, digest-only metadata and recovery journal |
| `bootstrap-macos.sh` | Explicit Apple CLT/Python prerequisite checkpoint, no OS installation or auth automation |
| `acquire.py` | Explicit pinned private revision acquisition, isolated Git/SSH transport, source inspection/scan before publication, no init/apply hooks |
| `toolchain.*.json` | macOS artifact locks; arm64/x86_64 have distinct checksums; native qualification is not implied |

Use Python 3.9+ and Git supporting `--no-lazy-fetch`. All state directories must
already be owner-private and outside both source and destination. Python entrypoints
are invoked explicitly; no setup script runs when opening the repository.

## Isolated review workflow

First run `python3 tests/test-bootstrap.py`. The test creates and removes disposable
repos/HOMEs under the OS temporary directory. Its fake transport, scanner and CLI
are fixture helpers only; the real pinned-scanner test uses Gitleaks 8.30.1.
No fixture clones or opens private production dotfiles. No test invokes an actual
agent model or product login.

For manual testing, supply your own disposable absolute paths. The following are
interfaces, not instructions to run against production:

```text
python3 bootstrap/tools.py plan --lock LOCK_JSON --prefix PRIVATE_TOOL_PREFIX \
  --profile codex --plan EXTERNAL_TOOL_PLAN
python3 bootstrap/tools.py install --lock LOCK_JSON --prefix PRIVATE_TOOL_PREFIX \
  --profile codex --plan EXTERNAL_TOOL_PLAN --approve REVIEWED_PLAN_ID

python3 bootstrap/acquire.py --remote ssh://git@github.com/OWNER/dotfiles.git \
  --revision REVIEWED_40_HEX_COMMIT --source SOURCE --destination HOME --state STATE

python3 bootstrap/bootstrap.py plan --source SOURCE --destination HOME --state STATE \
  --profile codex --codex ABS_REAL_CODEX --remote APPROVED_REMOTE --plan EXTERNAL_PLAN
python3 bootstrap/bootstrap.py apply --source SOURCE --destination HOME --state STATE \
  --profile codex --codex ABS_REAL_CODEX --remote APPROVED_REMOTE --plan EXTERNAL_PLAN \
  --approve REVIEWED_PLAN_ID

python3 bootstrap/launcher.py --state STATE --agent codex
```

Review plan bytes/actions before approval; a hash alone is not review. Do not pipe
an unknown plan ID directly into apply. The acquisition command itself is an
explicit write request, binds an exact private main revision, and requires existing
SSH agent/known_hosts setup performed separately by the user. Public artifact
fetches never need private credentials. Source-engine bytes must match this trusted
public release: **the existing Phase 3 private source intentionally fails that new
compatibility gate until a separately authorized source upgrade**.

`launcher.py` prints a shell script to stdout. A reviewer can save it to a fixture
bin directory, but it does not overwrite `~/.local/bin/claude` or `codex`, modify a
shell rc file, or change PATH. Both emitted scripts exec the same `launch.py` with
only agent/state selectors different. `--` preserves the vendor argument boundary.

Changing `--profile` on a new approved plan implements switching, with the same
source/receipt identity. `--adopt` permits an existing **identical bytes/mode** target;
it never permits overwriting different content. Switch retires only receipt-owned
old discovery files. Inactive Claude settings, unrelated skills and all credentials/
runtime files are retained. Disabled shims pass through to their registered vendor
binary without syncing. Reactivation renders the current accepted source and checks
collisions; no stale backup is automatically restored.

A preparation or deployment failure does not start model/authentication operations.
If deployment writes are interrupted, keep the external journal/backups, inspect
changes, then explicitly run:

```text
python3 bootstrap/bootstrap.py recover --state STATE --approve ORIGINAL_PLAN_ID
```

Recovery rejects target edits, changed source/index, changed receipt or corrupt
backup bytes; it cannot restore an arbitrary path from a modified journal. It does
not delete backups. Completed deployment rollback is not implicitly authorized by
`recover`; profile changes use a new reviewed plan.

## Launch behavior and limits

An enrolled policy (`--remote` on the approved bootstrap plan) allows only incoming
shared rules/skills and adapter prose. Every incoming commit is scanned and checked,
including changes later reverted. Executable/wrapper/metadata/settings changes need
manual review. Launch never pushes, commits, installs tools, changes profile or calls
another agent. The exact automatic plan is retained privately outside HOME.

Unambiguous stand-alone help/version and login/logout/auth/completion commands exec
the vendor CLI directly. Other invocations keep argv, cwd, environment, umask and
inherited stdin/stdout/stderr. No input is consumed by synchronization. Successful
refresh adds nothing to stdout/stderr. Skipped refresh emits a generic, redacted
`launch-sync:` notice on stderr before starting the unchanged CLI stream. No raw
scanner/network output is forwarded. CLI exit status and terminating signal are
preserved, including when lease cleanup requires recovery.

Offline/unreachable/scanner/preparation failures only permit using hash-verified
existing deployment, never applying unscanned incoming data. Dirty source is retained;
manual target drift or a partial journal blocks automatic launch. Missing other-agent
installation/login/subscription/model access is not a dependency.

**Known review blocker:** no native product loading-complete callback has been
qualified. The safe fixture implementation therefore holds a read lease for the
whole CLI session. Other readers/agents may start with the verified configuration;
v2 writers refuse until all leases are released. This prevents partial reads but
means a running agent cannot invoke a mutating v2 in/push against that source.
The short-barrier requirement has since been superseded by the cohort design;
this old mechanism still lacks its preparation, lifetime and recovery protocol.
Do not label it production-ready. Direct vendor invocation or noncooperating filesystem writers
are outside lease coordination. Crashed supervisors leave leases for explicit
inspection; leases are never stolen using an age/PID heuristic.

The launcher is a foreground supervisor, not a daemon. The child inherits the
terminal/process group; the supervisor forwards INT/TERM/HUP/QUIT and reproduces
signal termination. PTY descriptor checks are covered, but native interactive job
control and product-specific startup flags still need later runtime qualification.

## Tools and outstanding qualification

`tools.py` installs verified single-executable archives into versioned filenames in
an explicitly approved private prefix. It never globally upgrades/uninstalls tools
or executes archive install scripts. Existing unowned files are collisions. It does
not automatically add the prefix to PATH; callers must review PATH integration.

The checked-in locks cover official Gitleaks 8.30.1, chezmoi 2.71.0 and Codex 0.155.1
archives. Metadata was read from the official GitHub releases; actual vendor archive
installation and native CPU/OS qualification were not performed this round. Git,
Python, Claude and Node are explicitly declared prerequisites with separate probes,
not silently installed. Artifact failure for one agent does not block installing
another; partial readiness exits nonzero with per-tool outcomes.

Consequently this is **not yet a complete empty-Mac installer**: controlled Homebrew/
CLT dependency closure, Claude installation/update policy, minimum-OS qualification,
PATH integration and statusLine dependencies remain review blockers. Credentials,
auth flows and statusLine runtime configuration are not imported to hide those gaps.
Do not interpret `CONFIG_READY` as tools, launch or actual model runtime PASS.

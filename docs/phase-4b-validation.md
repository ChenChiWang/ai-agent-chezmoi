# Phase 4B — implementation and isolated validation

**Latest narrow repair:** enrollment consistency is fixed; native family retirement
remains blocked by concrete missing descendant evidence. See
[current repair tests and coverage](phase-4-blocker-repair.md). The records below
precede this repair and do not override its scope or status.


**Current status:** cohort design accepted; implementation advanced through 38 focused
passing tests, but stopped at real native-family retirement and enrollment findings.
See [current evidence and overall review](phase-4-cohort-implementation.md).
The remaining content is historical. Short loading leases are no longer required;
nonempty statusLine and full fresh-machine qualification remain unresolved.


Latest design follow-up: [fixed-path generation cohorts](phase-4-generation-cohorts.md)
pass isolated race/crash/recovery and native discovery checks under the revised
session-length lease contract. Await design review; no other 4B–4G work this round.
This does not mark the entire Phase 4B implementation or native guardian qualified.

Status: **isolated implementation prepared; 4B acceptance NOT PASS**. Latest user
authorization includes consecutive isolated 4B–4G validation. The latest follow-up
reproduced a native multi-file loading race and tested a callback-free generation
model; [native routing compatibility remains unqualified](phase-4-consistent-loading.md).
4H and production deployment remain outside scope.

The user accepted 4A and authorized public implementation/isolated tests, requiring
one neutral launch-sync implementation and thin agent shims. No production commands,
private dotfiles, authentication or existing rollback packages were modified.

## Implemented

- Three profile mappings: Claude 14 targets, Codex 12, dual 21. Codex-only ignores
  Claude home/settings/CLI requirements. Explicit `--repository-profile` separates
  full source/history scanning from active target rendering/deployment.
- Trusted-public-release first deployment with exact plans, source/index/config/
  scanner/tool identities, external private state, content scan, static rendering,
  collision/adoption policy and rollback journal. All six directed profile switches,
  reactivation and inactive settings preservation are exercised in fixtures.
- One `bootstrap/launch.py` uses the existing v2 Engine build/execute implementation;
  no separate Claude/Codex sync engines. Exact automatic plans are bound to the
  enrolled remote/content policy; intermediate disallowed history also refuses.
- Generated shell shims only select state/agent and forward arguments to the common
  controller. Vendor streams are inherited; no model/auth probes, stdin consumption,
  shell interpolation or stdout protocol decoration.
- Preparation deadline, bounded network/lock wait, no hard kill of mutation; shared
  writer lock and conservative reader leases. Scanner/dependency/remote refusal may
  use only known complete local configuration; drift/journals stop launch.
- Safe artifact mechanism (SHA-256, bounded archive validation, no symlink/hardlink/
  traversal/install script), version health, owned idempotent installation, per-tool
  prerequisite/agent failure outcomes. Official macOS artifact digests are locked.
- Exact-revision acquisition without init/apply/source hooks or credential capture.
  Successful acquisition is tested with a substituted disposable transport, not
  access to the private production origin.

Usage, controls and limitations: [bootstrap README](../bootstrap/README.md).

## Test evidence

Final runs:

| Suite | Result |
| --- | --- |
| `python3 tests/test-bootstrap.py` | 24 PASS |
| `python3 tests/test-layout.py` | 61 PASS (nested migration/write/layout) |
| `python3 tests/test-scanner.py` | 10 PASS |
| `python3 tests/test-offline-status.py` | 6 PASS |
| `sh tests/test-render.sh` | PASS |
| `sh tests/test-status.sh` | PASS |
| Artifact tests after archive resource-limit hardening | 2 PASS (subset of bootstrap suite) |
| Documentation links, Python syntax, shell syntax, diff whitespace | PASS |
| Gitleaks 8.30.1 over public bootstrap/new tests/engine source, neutral filenames | PASS; no findings |

 Fixtures use
fake HOME/repositories/CLIs and external state; real scanner coverage uses pinned
Gitleaks 8.30.1. A fake scanner is only the explicitly selected fixture adapter for
fault injection, never a production fallback.

Earlier passes during implementation: 27 write tests, 24 migration tests, 61 nested
layout/migration/write tests, 10 scanner tests, shell render and status suites.
Bootstrap coverage includes profile switching/idempotence, inactive sentinels,
secret/collision/drift/stale-plan refusal, rollback after injected write failure,
full-repo inactive-only history, temporary forbidden history, artifact escape,
agent independence, stdout/argv/binary stdin/umask/exit/signal and PTY inheritance.

Harness corrections: macOS `/tmp` alias is canonicalized before safe atomic artifact
writes. PTY tests keep the harness slave open until buffered output is read (macOS
may discard it on last close). These are explicitly tested without changing
production configuration. The normal macOS Python `confstr` sandbox warning seen
in legacy shell tests is not suppressed or counted as a product output regression.

## Review findings / unresolved acceptance gates

- 🔴 **Short loading barrier is unqualified.** The implemented conservative lease
  lasts through the CLI session. It allows concurrent readers but blocks mutating
  sync while any enrolled agent is running, including that agent's own in/push.
  This preserves safety but does not meet accepted 4A behavior. Resolve via a proven
  product loading-complete integration or separately reviewed architecture; do not
  replace it with sleeps, unverified lease expiry or mid-load writes. Native runtime
  compatibility is not implied by fake CLI tests.
- 🔴 **Empty-Mac dependency installation is incomplete.** Git/Python/Claude/Node are
  explicit prerequisites; controlled system/package installation, dependency closure,
  minimum OS and PATH integration are not implemented/qualified. The artifacts
  mechanism is tested; the whole toolchain is not. Complete these before claiming
  4B or fresh-machine bootstrap PASS.
- 🔴 **StatusLine and portability gate remains.** Source-engine compatibility is
  checked, but production Claude statusLine dependencies are not qualified by this fixture.
  New Claude bootstrap explicitly refuses nonempty statusLine and unknown settings
  keys until that qualification exists; Codex-only does not depend on this gate. No private settings edits or cache copying are allowed
  as a shortcut. A future separately authorized source upgrade must deploy the same
  trusted engine release before production can use these new leases/profiles.
- 🟡 **Interactive/native product boundary.** PTY FDs, standard signal termination
  and transport are covered by fake CLI tests; GUI/direct-binary invocation, native
  loading order, complex CLI flags/job control and provider/runtime side effects
  require later explicit real-environment validation.

No safety exception was accepted automatically. Existing 4A design remains the
acceptance contract; these findings do not redefine it as completed. Stop here.

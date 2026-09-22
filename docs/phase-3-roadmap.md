# Phase 3 migration roadmap

## Current gate: public Phase 2.6 only

The user subsequently authorized Phase 2.6 Migration Readiness to resolve the
reference gaps below, **in the public repository and isolated fixtures only**.
Do not start Phase 3, touch private chezmoi, commit or push under that instruction.
After 2.6 review, stop for acceptance and explicit continuation. Phase 2.6 review passed within its documented synthetic-fixture scope; this is
not approval to migrate. The implementation and verification contract is in [migration-readiness.md](migration-readiness.md).
Historical 3A–3D authorization below is not permission to resume automatically.

## Authorization and mandatory gate

Public Phase 2.5 was accepted and published as
`03bbd09e0674cf5494dc4a44ee37438b77ce3533`.
The user authorized private migration **3A–3D only** on 2026-09-22.
This supersedes the earlier blanket migration pause, but not the phase gates below.

- Preserve existing user rules and Claude-only `settings.json` configuration.
- Do not deploy the Codex adapter or its generated instructions/skills in 3A–3D.
- Do not push the private repository during migration.
- Do not output secrets or put private configuration, backup contents, or transcripts
  in this public repository. This document records only scope and implementation gaps.
- If the current state conflicts with the accepted inventory or public reference
  implementation, stop and report; do not silently redesign or make destructive choices.
- **3D is a mandatory gate. Stop after its results, even if all checks pass, and
  wait for explicit approval before 3E–3H.** A failed or unexecuted 3D never permits
  continuation. Acceptance of Phase 2.5 does not imply private regression acceptance.

## Roadmap

| Phase | Work | Required evidence / gate | Current status |
| --- | --- | --- | --- |
| 3A | Establish a reversible private baseline and rollback plan | Verified private source identity and Git state; scoped source/deployed backup manifest with existence, types, modes and hashes; preserve pre-existing edits; verify backup restoration in isolation | Not executed; await 2.6 acceptance and continuation |
| 3B | Migrate inventory mapping into Shared Core | Preserve existing user-rule meaning; retain Claude-only settings; move existing portable skills to their shared authority; avoid duplicate plain/template targets | Not started |
| 3C | Switch Claude to Shared Core + v2 dotfiles-sync | Deploy only reviewed Claude/shared outputs; preserve settings; replace legacy callers safely without fallback or automatic session-start writes; no Codex deployment | Not started |
| 3D | Claude regression gate | Verify CLAUDE.md, every pre-existing skill, sync entrypoint and scanner scope; isolated sync tests; scoped chezmoi behavior/idempotence; settings preservation; rollback evidence; report actual product-loading checks separately from rendering | **Mandatory stop; not run** |
| 3E | Deploy Codex adapter | Separate explicit authorization after 3D | Not authorized |
| 3F | Validate Codex | Verify actual instruction/skill loading and intended configuration behavior | Not authorized |
| 3G | Validate Claude/Codex cross-agent sync | Shared authority, compatible mappings and concurrent sync behavior | Not authorized |
| 3H | Final private dotfiles commit + push | Separate explicit authorization after prior gates | Not authorized |

A baseline reference/backup under 3A must not be mistaken for authorization to
create the final migration commit or publish private changes under 3H. Do not
perform a migration commit early merely to satisfy the current engine's HEAD-layout
requirement.

## Historical preflight stop: Phase 2.5 reference compatibility gaps

The accepted inventory was recovered from the previous local conversation. It
identifies six existing skills: the sync skill plus five portable skills requiring
additional shared source and wrapper mappings. It already states that expanding
engine/scanner allowlists and tests is necessary before claiming coverage.
No private configuration contents were copied into this document.

Review of the published Phase 2.5 source establishes these gaps:

1. **No Claude-only profile.** `scan-secrets.py` has a fixed 19-source/eight-target
   allowlist that includes Codex instructions and agent skills. `sync-write.py`
   imports those lists; `state()`/`build()` snapshot all targets and `render()`
   unconditionally generates both adapters. Omitting Codex files fails preflight;
   including them would extend deployment beyond 3A–3D. Ignoring Codex in chezmoi
   alone does not change this engine behavior.
2. **Incomplete inventory coverage.** The only portable skill in the fixed
   reference mapping is dotfiles-sync. The other five skills would be outside
   the scanner, candidate-tree and historical-path checks. Merely moving their
   files would not make the v2 engine a complete replacement for their sync workflow.
3. **Legacy-to-v2 bootstrap is not implemented.** `build()` calls `scoped(HEAD)`,
   which requires every current v2 source path to exist in that commit. Write
   commands also require already-existing generated outputs. A legacy baseline
   followed by uncommitted migration cannot satisfy that contract. The approved
   inventory describes a legacy layout; its current private state has not been
   re-read during this stopped attempt. This is a reference limitation, not a
   newly observed private-repository change.

Evidence is in the public source:

- [Fixed scanner mappings](../examples/chezmoi/.chezmoitemplates/ai/shared/scripts/scan-secrets.py)
- [Required HEAD layout, target snapshots and rendering](../examples/chezmoi/.chezmoitemplates/ai/shared/scripts/sync-write.py)
- [Accepted fixed-profile sync contract](sync-v2.md)

These are limits of the accepted Phase 2.5 scope, not evidence that its existing
fixture tests failed. No private regression test was run and no 3D pass is claimed.

## Changes and rollback for this stopped attempt

Only this public roadmap and the current implementation-status entry were changed.
No private repo/source, deployed configuration, settings, skill, trigger, Git ref or
index was modified. No baseline backup was created, no private commit/push occurred,
and no sync/apply/remote operation was run. There are no private migration changes
to roll back. A real source/deployment rollback manifest remains a prerequisite for
resuming 3A; the generic engine transaction journal is not that manifest.

## Original prerequisites for resuming

First resolve and review the reference design for a Claude-only deployment profile,
the inventory's additional skill mappings, and a safe first-migration/HEAD transition
compatible with deferring the final private commit/push until 3H. Extend scanner,
status, renderer, plan/history checks and isolated tests consistently. Do not hide
these gaps with missing-file placeholders, an always-clean scanner, a drift override,
or a private-only fork of the shared engine.

These changes were **not** made during the original stopped Phase 3 attempt.
They are now addressed by the separate public Phase 2.6 implementation and fixture
review. After Phase 2.6 acceptance and explicit continuation authorization,
recheck the current private state against inventory before creating the 3A baseline.
Then execute only 3A–3D and stop at the mandatory gate.

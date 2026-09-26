# Implementation status

Current state only. Older round-by-round records are archived in
[history/implementation-status-2026-09-25.md](history/implementation-status-2026-09-25.md).

## 2026-09-26 — architecture adjustment applied to the public tree

- Executed items A–H of the [architecture adjustment plan](architecture-adjustment-plan.md);
  see its execution record for details and deviations.
- v2 engine: `--config` parameter file, `check` command with daily cache, `auto_in`
  for shared text only, `writer` roles with `--agent`, plan paths resolved through
  directory aliases and allowed anywhere under HOME outside deployment regions,
  labelled `INVALID_PLAN`/`INVALID_CONFIG`/`PENDING_APPROVAL`/`NOT_WRITER` results.
- Shared instructions reduced to one three-sentence checkpoint rule; skill and
  adapters describe parameters, roles, `check` and restart-needed reporting.
- `bootstrap/` and its tests are archived under `archive/`; Phase 3/4 records live in
  `docs/history/`.
- Tests on this machine: test-write 40, test-layout 74, test-migration 24,
  test-offline-status 6, test-scanner 10 (real Gitleaks 8.30.1), test-render.sh and
  test-status.sh PASS.

## Deployment (2026-09-26, this machine)

- Private source updated and published through a reviewed push plan; HOME targets
  verified against the plan; deployed engine equals public `25c0792`.
- Engine fixes found during deployment: scp-style remote normalization, default SSH
  identity files, message/identity taken from the plan on in/push (the last one is
  not yet deployed to HOME).

## Not done here
- No model runtime session was run; proactive skill invocation remains a behavioral
  acceptance that only real sessions can show.
- Codex 0.157.0 skill discovery was checked by binary inspection only.

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
  identity files, message/identity taken from the plan on in/push. All three are
  deployed; `doctor` reports the HOME engine equal to this build.

## 2026-09-26 — session acceptance and bring-up documentation

- Fresh-session start checks verified against real models on this machine with
  `tests/session-acceptance.sh`, both PASS:
  - Claude Code (`claude -p`): `status` then `check` in one call, then Glob and Read
    of the project README; 3 tool calls. `check` returned `CHECKED_TODAY` with the
    cached `UP_TO_DATE` result.
  - Codex (`codex exec`, workspace-write sandbox): `check` then `status`, then `rg`
    and `cat` of the README; 4 tool calls; no sandbox escalation requested. `check`
    returned `CHECKED_TODAY` without touching the network.
- README (both languages) restructured around the one-sentence agent bring-up;
  command examples verified against the deployed engine.
- `setup/AGENT-SETUP.md` gained path 4B: creating the private repository from
  `examples/chezmoi/` on the first machine (empty remote, merge of existing
  `CLAUDE.md`/`AGENTS.md`/`settings.json` with confirmation, apply, Gitleaks scan,
  baseline commit, first push after approval). Verified in an isolated HOME: `status`
  `NO_CHANGES`, `doctor` 39/39 sources and 21/21 targets. The closed six-skill mapping
  is documented as a known limit.

## Not done here
- Proactive skill invocation is verified only for the start checkpoint; the recording
  and end-of-work checkpoints have no scripted acceptance yet.
- Codex 0.157.0 skill discovery was checked by binary inspection only.

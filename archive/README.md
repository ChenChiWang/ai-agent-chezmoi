# Archived material (not maintained)

Everything under `archive/` was moved out of the active tree on 2026-09-26 by the
[architecture adjustment plan](../docs/architecture-adjustment-plan.md), item A.

- `bootstrap/`: Phase 4B isolated bootstrap, launcher, guardian and toolchain
  implementation. Native family retirement and the loading gate stayed BLOCKED,
  and the current daily-sync requirement no longer needs a launcher or guardian.
  Known unresolved defects are listed in the plan's appendix. **Do not install
  these launchers, shims or PATH blocks on any machine.**
- `tests/`: the tests for that implementation. They are not part of the default
  test run. They still execute from this location
  (`python3 archive/tests/test-bootstrap.py`); the three `test-native-*.py`
  scripts require explicitly supplied vendor binaries.

The v2 engine keeps inert cohort/lease hooks (`ai-agent-cohort.json`,
`ai-agent-launch-readers`) that only activate when a bootstrap enrollment exists.
No active machine has such an enrollment. Records of this research live in
[`docs/history/`](../docs/history/phase-4-roadmap.md).

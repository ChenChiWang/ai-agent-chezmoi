# Implementation status

Current state only. Older round-by-round records are archived in
[history/implementation-status-2026-09-25.md](history/implementation-status-2026-09-25.md).

## 2026-09-27 — the skill set belongs to the source

Tracking issue #17. The set of synchronized skills was a tuple in the engine; adding a
name to it left no way through for a machine that was already online.

- **Engine** (#20): the set is read from each snapshot, one directory with a `SKILL.md`
  per skill plus its two wrappers. Snapshots can mark a file as absent, transactions
  create and remove files and roll both back, an existing target is adopted when
  identical and refused when different (`BLOCKED_TARGET_COLLISION`), history is checked
  per commit, and `auto_in` never applies a change of the set. With the six template
  names the mapping, console output, plan document and `status` output are unchanged
  (compared against the engine of `68d3ba8` in fixtures).
- **Upgrade path**: an older engine plans and applies the engine update as an ordinary
  incoming commit. The order, and the recovery of a machine that was left behind, are in
  [sync-v2](sync-v2.md#upgrading-from-an-engine-with-the-fixed-list); both were run in
  fixtures. `doctor` prints the skill set.
- **One real machine**: macOS, profile `claude-codex`. The three scripts were published
  from it through an approved push plan built by the older engine. Afterwards the new
  engine reported `NO_CHANGES`, `UP_TO_DATE` and `doctor` without a failure. No skill
  has been added or removed on a real machine yet.
- **MCP** (#18, #19): not synchronized, by decision. The README explains why and
  suggests a list in the private shared instructions.

## 2026-09-26/27 — platforms, CI and mode hardening

Driven by bringing a Windows 11 machine online (tracking issue #1, closed).

- **Platforms.** `preflight` fails early on native Windows (#2) and warns when WSL
  resolves a Windows-side agent CLI (#3). One real WSL2 Ubuntu 24.04 bring-up
  (`claude` profile, path 4A): `doctor` 15 ok. `docs/wsl.md` records the WSL pitfalls,
  the VS Code WSL route (the extension's bundled binary runs the start checkpoint
  first, #12) and the native Windows follower (#14).
- **CI** (#5, #14): every test except `session-acceptance.sh` on `ubuntu-24.04`,
  `macos-15` and WSL2 Ubuntu 24.04 under umask `002`, plus the native Windows
  follower end-to-end test. Actions are pinned by SHA.
- **Modes** (#6, #9, #10, #11): execution uses the same effective mode as the plan;
  modes stricter than `644`/`755` are kept, looser ones are listed in the plan
  (`mode=664->644`) and tightened; `status` and `doctor` report them; bring-up sets
  chezmoi `umask = 0o022`; migration explains a looser legacy `settings.json`.
- **Checkpoints** (#7): a machine with neither parameter file nor engine skips them
  silently; engine without parameter file is still reported as an incomplete bring-up.
- **Permissions** (#13): only `status`, `check`, `doctor` and `plan` are pre-allowed;
  `in` and `push` always prompt; `doctor` warns about the broad `sync.sh:*` rule.
- **Phase 2 hardening** (#12): `chezmoi apply --no-tty` in the agent bring-up (without
  a TTY the overwrite prompt waits forever and ignores SIGTERM), SIGHUP registered
  only where it exists, golden Darwin/Linux preflight output with shimmed tools.
- **First-launch drift** (#4): documented in `new-machine.md` and AGENT-SETUP.
- Local results: under umask `022` and `002` all eight test files pass in WSL2;
  `test-preflight.sh` passes in Git Bash; the follower test passes on native Windows.

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
- The skill set: no real machine has received the engine update through an incoming
  plan yet, and none has added or removed a skill. The converter (`sync-migrate.py`)
  still expects the six template names, so a later Codex expansion of a source with
  more skills is refused. `setup/AGENT-SETUP.md` and the `dotfiles-sync` skill still
  describe the set as fixed.
- Proactive skill invocation is verified only for the start checkpoint; the recording
  and end-of-work checkpoints have no scripted acceptance yet.
- Codex 0.157.0 skill discovery was checked by binary inspection only; Codex inside
  WSL is unverified.
- `tests/session-acceptance.sh` has not been re-run since the permission rules were
  narrowed (#13).
- Linux has no real-machine bring-up outside WSL yet.
- Full native Windows sync (recording and publishing without WSL) is planned in #15,
  with the pitfalls found so far and a phased plan.

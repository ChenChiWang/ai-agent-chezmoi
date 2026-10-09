# Implementation status

Current state only. Older round-by-round records are archived in
[history/implementation-status-2026-09-25.md](history/implementation-status-2026-09-25.md).

## 2026-10-09 — native Windows plan: W1 and W2

- **Platform layer** (#33, W2): the temporary root, symlink test, path format, owner
  and permission tests, directory `fsync`, `replace` and the child environment are one
  section of `scan-secrets.py`; see [sync-v2](sync-v2.md#platform-layer). POSIX is a
  pure refactor. Windows gets `%TEMP%`, the retries and environment variables it needs,
  and a refusal wherever an equivalent check does not exist yet. The engine still does
  not run on native Windows: ACLs, `status` and an entry point are the next steps.
- **Windows ACLs** (#38, W4a): the owner and permission tests of the platform layer are
  real on Windows, through `ctypes` and SDDL, with the strict policy of POSIX `600`/`700`
  (user, SYSTEM, Administrators only). Everything the engine creates privately gets a
  protected DACL through `icacls` with SIDs and is read back. Verified on the Windows 11
  machine: a profile file with the inherited sandbox group is not private, `make_private`
  makes it so, and `load_config` accepts it.
- **Native Windows bring-up** (#15 W5b): no new entry point. Claude Code's Bash tool on
  Windows is Git Bash, where `preflight.sh`, `sh sync.sh` and the four pre-allowed rules
  work unchanged; `preflight.sh` reports Git Bash as experimental instead of failing,
  `scan-secrets.py --make-private` protects the parameter file and `plan_dir`, and
  `AGENT-SETUP.md`, both READMEs and `docs/wsl.md` section 8 describe the path. The
  follower script now refuses with "the engine is deployed on this host".
- **Windows mode semantics** (#15 W4c, in W5): snapshots record the expected mode where
  there are no mode bits (`HEAD` for sources, the mapping for targets), `status` takes the
  executable bit from the index, `doctor` reports the umask as not applicable and a refused
  parameter file names its `icacls` fix. POSIX reads are the same `S_IMODE` as before.
  Four more Windows findings went with it: the scratch rule allowed a source under
  `%TEMP%` (as POSIX allows `/tmp/src`), Git's top level and a local remote path are
  compared and accepted in Windows form, the isolated repository's `alternates` file is
  written as bytes (text mode wrote CRLF), and optional path options are skipped instead
  of compared with `/`. First complete loop on native Windows 11 against a fixture
  source and remote: `doctor`, `status`, `check`, `plan push`, `push` (modes at `HEAD`
  kept), `check` (`BEHIND 1`), `plan in`, `in`, `status` (`NO_CHANGES`).
- **Windows redirections and scratch area** (#39, W4b): `is_redirected` sees every reparse
  point on Windows; the scratch rule of `validate_layout` lets `%TEMP%` live under the
  profile as long as it overlaps neither the source nor a deployment region. `status`
  runs against the real private source on the Windows 11 machine without any override.
- **Status in Python** (#35, W3): `tests/test-status-golden.sh` first recorded the complete
  output and exit code of the shell `status` for 31 cases under `tests/golden/status/`;
  `--record` regenerates them. Then `status` moved into `sync-write.py` with the same
  checks in the same order, the same Git argv prefix and the same labels; `sync.sh` is a
  thin shell for every command. All 31 golden files, `test-status.sh` and
  `test-offline-status.py` are unchanged.
- **Executable bit** (#31, W1): first step of the plan, a correctness fix for every platform. The push candidate tree took `100644`/`100755` from the filesystem, so a push
from native Windows, where `stat` reports `666` for every file, would have turned the
three executable engine scripts into `100644` for every machine; on POSIX a `chmod` on
a source file was published as a change. The commit now takes each path's mode from
`HEAD` (`644` for a new path), execution sets a disagreeing source file to Git's mode
and the plan lists it. Template content leaves console output, plan documents and
`status` unchanged.

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
- **Converter** (#24, #23): both modes read the skill set from the source, the v1
  conversion from `dot_claude/skills/` and the later Codex expansion from the shared
  skill directory. Wrappers of skills that the reference does not have come from the
  engine. Extra files, invalid names and existing Codex targets are still refused.
  `apply`, `verify` and `rollback` read the set from the approved manifest, so a skill
  added after the conversion does not invalidate its backup. Run in fixtures only.
- **Template** (#25): ships `dotfiles-sync` and nothing else. The five skills it used
  to carry were placeholders whose names came from the setup the template was first
  built from, and every new user got them deployed. The tests bring their own fixture
  skills (`tests/fixtures/skills/`), and a separate test class runs the template as a
  new user gets it. A source that already has those five skills keeps them.
- **Agent text** (#22): the `dotfiles-sync` skill and `setup/AGENT-SETUP.md` describe
  the steps. An agent may suggest adding, removing or improving a skill, and changes the
  source only after the user agrees to that suggestion.
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
  plan yet, and none has added or removed a skill. Whether an agent that reads the new skill text follows it has not been tested with a
  real model.
- Proactive skill invocation is verified only for the start checkpoint; the recording
  and end-of-work checkpoints have no scripted acceptance yet.
- Codex 0.157.0 skill discovery was checked by binary inspection only; Codex inside
  WSL is unverified.
- `tests/session-acceptance.sh` has not been re-run since the permission rules were
  narrowed (#13).
- Linux has no real-machine bring-up outside WSL yet.
- Full native Windows sync (recording and publishing without WSL) is planned in #15,
  with the pitfalls found so far and a phased plan.

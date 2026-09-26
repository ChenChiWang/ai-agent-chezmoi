# Phase 4 — agent-independent consistent loading

Historical short-lease/snapshot-path investigation. Its race findings remain valid,
but the user subsequently permitted session-length reader leases. The current
[fixed-path cohort design](phase-4-generation-cohorts.md) avoids snapshot routing
by deferring activation until readers finish.

2026-09-24. **Design and isolated experiments completed; native integration gate
NOT PASS.** This supersedes the proposed lifecycle-callback approach. No hook,
SessionStart acknowledgement, model response, timeout or session-length reader
lease is part of the proposed correctness mechanism. `disableAllHooks` remains
under user control.

## Result: release-before-exec with today's deployment has an actual race

`sync-write.py:Engine.transact` journals a set of changes, then replaces each
destination independently using `atomic()`. Each file replacement is atomic;
the collection of files is not. The journal supports recovery and cooperating
writer exclusion. Native agents do not acquire that lock or inspect the journal.

The following is a permitted schedule after replacing the old session lease with
prelaunch-only locking:

1. Launcher A completes sync/validation, releases the writer lock, prepares exec.
2. Writer B acquires that lock and replaces the first skill with revision B.
3. Native agent A reads that skill and another skill still at revision A.
4. Writer B finishes the remaining replacements and validates the final state.

Validation in step 1 cannot rule out step 2. A second validation immediately before
exec merely moves the race window. An entire-file hash does not provide a snapshot
across two separate opens.

This was reproduced with the **actual v2 transaction and native binaries**, not
just a simulated reader. The fixture pauses the writer immediately after replacing
the first skill. This deterministic schedule does not depend on winning a timing
race. Both readers exit successfully while reporting mixed skill metadata:

| Reader | Native operation, without a model turn | First skill | Second skill |
| --- | --- | --- | --- |
| Claude Code 2.1.278 | SDK stream initialization, `--settings '{"disableAllHooks":true}'` | B | A |
| Codex CLI 0.155.1 | `debug prompt-input --disable hooks` | B | A |

After the readers exit, the transaction finishes normally and its deployed receipt
validates. Therefore successful final validation does not undo the mixed reads.
The observed content was two skills' discovery metadata. A mixed rules/skills pair
is also reproduced by an ordinary subprocess file reader against the actual
transaction; the native test does **not** claim to inspect Claude's system prompt.

## Why a globally atomic pointer is insufficient

Prepare immutable generation A and B, then atomically replace `current -> A` with
`current -> B`. A native reader can still open `current/rules` before the switch and
`current/skills/review/SKILL.md` after it. The test reproduces A/B despite there never
being a broken pointer or half-written generation.

Renaming a parent directory, a symlink farm, APFS clone creation, or staging all
files before deployment does not by itself bind separate pathname resolutions to
one generation. Atomic publication and per-reader snapshot isolation are different
properties. Do not treat the former as proof of the latter.

## Proposed protection: publish complete generations, pin a physical root once

The agent-independent deployment core would perform the following under the
existing source writer lock:

1. Complete policy checks, incoming history scan and rendering using the exact
   profile mapping. Build a generation from only these rendered outputs. Never
   walk HOME or copy agent config/runtime directories wholesale.
2. Bind profile, source revision, schema/tool identities and each output's bytes
   and mode to a manifest. Store it in an owner-private, content-addressed external
   generation store. Refuse existing mismatches; never patch published generations.
3. Validate/scan the complete staged generation before publication. In a production
   implementation, fsync files/directories and journal source/index/receipt changes
   before advancing the publication pointer. A recovery-required transaction must
   block new launch selection, even if the previous generation remains intact.
4. Publish one small `CURRENT` reference atomically. Resolve and validate it **once
   for this launch**, yielding a physical generation root, not a `current/...` path.
5. Release the writer lock and exec the native CLI. Every managed read by that
   process, including later skill-body reads, must resolve within the pinned root.
   Other writers can immediately publish newer generations without waiting for the
   session. There is no read lease to release and no lifecycle callback.

The launcher continues to preserve argv, cwd, standard descriptors, environment
semantics, exit/signals and the native authentication/configuration paths. Pinning
must cover **all** managed discovery roots, not only the main instructions file.
Both agents use the same generation implementation; any adapter selects paths only.

Old generations are retained. No automatic garbage collection, age/PID-based
reclamation or cleanup-on-exit is proposed for this phase. This separates storage
retention from writer exclusion. Explicit later cleanup needs proof that retained
sessions cannot reference a generation. Profile switches publish a new generation;
existing sessions retain their original complete profile. Rollback republishes a
validated complete generation through a new journaled operation, never edits one.

Scope of the experiment: `tests/loading_snapshot_model.py` proves publication and
pinning behavior with mapped synthetic files. It is **test-only**, has no bootstrap
entrypoint, and is not wired into `launch.py`. It assumes already-rendered/scanned
bytes and a serialized publisher. It does not implement source/index transactions,
production recovery, native routing, full metadata binding, or power-loss durability.
Read-only modes deter accidental writes; they are not protection against the owner
changing permissions. No production readiness claim follows from this model.

## Native routing remains the blocking compatibility boundary

The storage primitive only works if native readers actually use its pinned paths.
The existing native commands instead discover files through several live roots.
Passing a path to the launcher does not make either CLI use it.

An additional native Codex negative control sets `CODEX_HOME` to a synthetic
generation containing both its instructions and a sibling `.agents/skills` tree.
Codex reads the generation's instructions **but still discovers the original
HOME's skill**, not the sibling snapshot skill. The probe exits 0. Changing only
`CODEX_HOME` therefore does not pin the whole managed configuration.

Changing HOME as well would alter Git, shell/tool behavior and authentication
discovery. Changing product configuration roots is also not a managed-only switch:
[Claude documents that its config-directory override moves settings, session history
and plugins](https://code.claude.com/docs/en/settings).
These substitutions have not been accepted as equivalent CLI behavior.

Native skill bodies can be read after startup in both products, so pinning must
remain meaningful for late reads even though no synchronization lock remains.
See [Claude skill loading](https://code.claude.com/docs/en/skills) and
[Codex progressive skill loading](https://learn.chatgpt.com/docs/build-skills).

The following shortcuts are excluded:

- Copying credentials/sessions into each generation or traversing all HOME.
- Symlinking a guessed runtime-file inventory: atomic native rewrites can replace
  a symlink, and new runtime filenames could silently diverge between generations.
- Injecting prompt/plugin/add-directory flags and assuming equivalent instruction
  precedence, skill names, permissions and user overrides without qualification.
- Forcing hook trust, altering `disableAllHooks`, callback-based release, sleep-based
  release, or retaining a writer-blocking lease throughout the session.

To complete this design, a native managed-only path-selection mechanism or a
process-specific filesystem view must cover all mapped reads **while retaining
original runtime/config/credential behavior**. Neither has been qualified here.
No privileged mount, filesystem interposition or HOME relocation was installed.
The experiments establish requirements and reject concrete unsafe shortcuts; they
do not establish that a compatible routing solution is impossible.

## Reproduction and gate matrix

```sh
python3 tests/test-loading-races.py
python3 tests/test-native-config-race.py \
  --claude /absolute/path/to/native/claude-2.1.278 \
  --codex /absolute/path/to/native/codex-0.155.1
python3 tests/test-bootstrap.py \
  BootstrapTests.test_thin_launcher_arguments_streams_exit_and_umask \
  BootstrapTests.test_tty_descriptors_remain_attached \
  BootstrapTests.test_admin_bypass_and_signal_exit
```

| Gate | Evidence / result |
| --- | --- |
| Current multi-file transaction race | Reproduced with native Claude and Codex; unsafe unpinned model rejected |
| Atomic `current` swap | Mixed revisions reproduced; insufficient by itself |
| Physical root pinned once | PASS in subprocess model; all three profiles, no reader lease |
| Publish failure before pointer switch, retry, unknown/auth/escape paths, tampering | PASS in model |
| Race/model suite | 5 tests PASS |
| Native snapshot path routing | NOT PASS; CODEX_HOME-only mixed-root behavior reproduced |
| Existing launcher argv/binary stdin/stdout/umask/exit/signals/PTY | 3 targeted fixture tests PASS; existing implementation only |
| New snapshot launcher CLI compatibility | NOT QUALIFIED; no native integration implemented |
| Overall loading blocker | NOT PASS; keep this gate closed |
| Remaining dependency/PATH, statusLine, complete 4B–4G validation | Not advanced because loading gate has not passed |

All mutations were in disposable fixtures or public test/documentation files.
Native test environments are constructed from an allowlist without credential
variables. Model requests/login are not run, hooks are disabled in the native race
probe, and raw native output is withheld. No production/private files or commands
were changed; no commit/push or 4H was performed.

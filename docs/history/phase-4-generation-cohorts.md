# Phase 4 — fixed-path generation cohorts

> Current requirement (2026-09-25): [agent-driven memory checkpoints](../sync-v2.md#agent-driven-memory-checkpoints-2026-09-25)
> replace the goal of pre-CLI automatic family tracking. Bootstrap is separate from
> daily sync. The material below is retained historical research/status, not current
> authorization to continue guardian/retirement work. Existing barriers/tests remain;
> the historical loading gate is still BLOCKED. No production deployment or 4H.


Status: **design accepted by the user**. Session-length cohorts are the formal
Phase 4 loading contract. Consecutive isolated 4B–4G implementation was authorized.
The current implementation is **BLOCKED** on native family retirement. Enrollment
consistency has been repaired; the [latest narrow repair review](phase-4-blocker-repair.md)
records crash/rerun evidence and the exact missing descendant evidence. The cohort
model is unchanged.
The design/model evidence below is historical and does not imply guardian PASS.

## Decision

Keep native Claude/Codex discovery paths and freeze their managed contents while
any reader of the active generation exists. Readers share one generation cohort;
they do not each receive a relocated HOME or snapshot config directory. Multiple
Claude and Codex sessions can join that cohort concurrently.

Writers may fetch, inspect history, scan, render and prepare immutable pending
generations while readers run. They cannot modify active managed targets, the
installed engine, or perform a profile switch until the cohort has drained.
Pending preparation does not advance the canonical source HEAD/index. Source
publication belongs to the later activation transaction. Authoring edits are
separate draft state and must be bound/rechecked by a reviewed plan.

This is deliberately **not** simultaneous live A/B generations at native paths.
With unchanged native discovery, an A session prevents activation of B for every
enrolled reader sharing those paths. New sessions join A until a safe idle point.
No hot reload is required, attempted, or advertised.

The previously demonstrated multi-file race is prevented by reader exclusion
through the entire period of native reads, including late skill-body reads. It
does not require native snapshot-path support, lifecycle hooks, or loading timing.

## State and invariants

The unit of coordination is the canonical source/destination pair and its entire
managed mapping, shared by both agents. An agent name is metadata, never a lock
namespace. All plan/in/push/bootstrap/switch/upgrade/recovery writers must use it.

| State | Meaning |
| --- | --- |
| ACTIVE A | Complete deployment and manifest at native mapped paths |
| PREPARING B | Private staging only; A remains untouched |
| PREPARED B, base A | Scanned/rendered candidate bound to A, policy, source/index, schema, profile and tool identities |
| READERS A | Any number of Claude/Codex reader records; A cannot be changed |
| ACTIVATING A→B | No readers; short admission mutex held; durable activation journal exists |
| RECOVERY_REQUIRED | Incomplete activation; no new native readers may be admitted |
| UNCERTAIN_READER A | Reader completion is unproven; retain protection of A |

Invariant: either readers may use a verified complete active generation and no
writer changes it, or an activation/recovery writer has exclusive admission and
there are no readers. A journal remains an admission barrier after writer death,
even when the kernel automatically releases the short mutex.

The long-lived lease is a durable logical reader record, **not** the writer mutex.
Preparing a new candidate and other normal agent activity remain possible.
Only mapped portable content enters generations. Authentication, trust, sessions,
config-local overrides and other runtime state remain at their original locations,
outside source, manifests, candidate scans and rollback packages. No HOME walk.

## Launch, preparation and activation

1. The launcher uses the neutral controller and enrolled policy to prepare incoming
   changes in private external staging. Failures may retain only verified A under
   the existing offline/scanner/dirty-source policy. No credentials/model probes.
2. Acquire the common short admission mutex. Reject journals or active-target drift.
   If readers exist, join A even if B is pending; never wait for those sessions to
   end. If no readers exist, an eligible B may activate before admitting the new
   reader, after fresh source/index/policy/scanner validation.
3. Register a unique reader token bound to A and the launcher/native process
   identity before exec. Arm the independent lifetime observer before completing
   admission. Reservations count as readers; a pre-exec crash cannot create an
   unprotected process. Release the admission mutex.
4. `exec` the registered native binary with the original argument vector, cwd,
   environment, standard descriptors, umask, process group and controlling TTY.
   Do not insert agent flags, change HOME/config roots, consume stdin, wrap model
   output, or force `disableAllHooks`. The native PID is the execing launcher's PID.
5. Proven session/family completion retires only that lease under the short mutex.
   Observer failure retains the lease. The observer never runs sync or activation.
6. A later launch or explicit activate operation can activate B once no readers
   remain. An agent exit is not permission to publish, push, or apply a stale plan.

Preparation can run outside the admission mutex after capturing its baseline;
candidate registration uses a short compare-and-swap check. Activation holds the
mutex across journal creation, all mapped writes, canonical source/index/ref
changes, render/status verification, receipt commit and journal completion. It
never invokes a model, waits for a reader, or performs an unbounded network action.
Concurrent launch may briefly wait; it cannot bypass an in-progress activation.

Publication need not be filesystem-atomic across all files: no reader can observe
the intermediate state. Each file remains atomically replaced and recoverable.
Interrupted publication is sealed off by the journal. Production must also fsync
directories/metadata in the journal protocol; current model tests cover process
crashes, not sudden power loss.

No automatic reader starvation policy: a stream of new sessions may postpone B
indefinitely. Status reports active/pending revisions and reader counts clearly.
Users can finish sessions to create an idle point; the controller never kills an
agent, forces a reload, or blocks new use merely to favor a waiting writer.

## v2 behavior from inside a session

`status` and `plan` remain usable. Incoming preparation may succeed while activation
is deferred. A mutating `in` must report `DEFERRED_READERS`, pending candidate ID and
`applied=false`; it must not claim the new configuration is deployed. Proposed
standalone exit status is 75 (temporary inability to apply), consumed by the launch
controller without changing the eventual vendor exit status. This is a future v2
interface change requiring implementation/tests, not current behavior.

An in/push invoked by a reader must never wait for its own lease: return the deferred
result promptly. A push may prepare/review its proposed changes, but any phase that
mutates active deployment or canonical source waits for quiescence. The initial
design defers the whole publication rather than silently adding a second remote
publication path. Neither lease cleanup nor activation automatically retries a
commit/push; explicit publication authorization is still required.

Profile switch, disable/re-enable, rollback and engine upgrades use the same barrier.
They can be planned during sessions; applying them waits for zero readers. Pending
candidates become stale on a conflicting source/profile/tool/baseline change and
must be rebuilt/reviewed. Keep old generations and rollback material; no GC this phase.

## Reader lifetime without hooks or changed CLI behavior

Prefer **exec plus a session-scoped OS observer**, rather than a foreground signal
forwarding supervisor. Exec preserves the native process PID, group, terminal,
signals and exit status directly; it avoids double-forwarding terminal signals.

The observer is a per-launch helper, not a daemon, cron task, login item, sync
service, or agent hook. Its only authority is recording lifetime evidence and
retiring its own proven-complete reader token. It has no CLI standard descriptors,
cannot hold a pipeline open, and does not take ownership of the terminal. The
production launch handshake must arm it before exec without leaving an extra child
that changes the native CLI's child-wait behavior. A detached/reaped helper and
private close-on-exec control channel are implementation requirements, not yet shipped.

macOS kernel process-exit observation across exec was exercised using `kqueue`:
the registered PID remains the native PID, and normal exit 23 and SIGTERM exit are
reported distinctly, without agent callbacks. **An exit event proves that process
ended, not that every descendant or detached backend ended.** The production
guardian must preserve the lease unless the complete reader family is accounted
for. Spawned enrolled agent sessions have independent leases. Unknown detached/raw
agent/backend lifetimes remain uncertain rather than being inferred complete.

Do not assume macOS supplies transparent process-tree tracking: the installed SDK
explicitly marks `NOTE_TRACK/NOTE_TRACKERR/NOTE_CHILD` unsupported since macOS 10.5.
Foreground, resume, exec, app-server/remote and detached modes need separate lifetime
qualification. Unqualified lifetimes may continue using protected A, but cannot
authorize retirement/activation. This deliberately trades prompt updates for safety.

## Crash and stale-reader recovery

Reader metadata contains opaque token, active generation, kernel boot identity,
native PID plus process-start identity, observer identity and evidence state. It
contains no prompt, argv, environment or credentials. UUID alone is not an OS
identity; PID existence alone is not a completion proof.

| Event | Required behavior |
| --- | --- |
| Normal completion with verified family quiescence | Retire that exact token under mutex; preserve native exit code, including nonzero |
| Native crash/signal, observer dies, observer IPC lost, registration uncertainty | Keep/mark UNCERTAIN; no guessed cleanup |
| PID reused, PID missing, permission-denied liveness check | No TTL/PID-only reclamation; obtain stronger evidence |
| One reader ends while another exists | Only remove the completed token; activation still deferred |
| Stale reservation before exec | Reconcile exact process identity and prove no reader was started; otherwise retain |
| Activation writer crashes | Journal blocks admission; reviewed recovery required |
| New kernel boot identity | Old-boot processes cannot survive; reconcile old records under mutex after validating active state/journals |

Same-boot recovery is an explicit, hash-bound operation: name the exact lease and
generation, establish whole-family quiescence from reliable OS/owned-child evidence,
revalidate active files and journals, then retire only that record. If evidence is
unavailable, keep A protected. A real reboot provides an independent conservative
recovery boundary. **A user-entered boot ID, elapsed time, `kill(pid, 0)` failure,
or a force-delete option is not an acceptable proof.** No process is killed by recovery.

Uncertain leases alone do not prevent additional readers from using complete A.
Drift or an activation journal does: those mean the active state is no longer proven.
Recovery never overwrites third-party edits. Interrupted activation is reconciled
from the exact old/new manifests and journal, verifies every target before writing,
and either restores a complete old generation or completes the approved new one.

## Validation performed

`tests/generation_cohort_model.py` is a **test-only protocol model**. It uses real
processes, a kernel short mutex, persistent reader records, mapped file writes and
an activation journal. It is not installed or imported by production bootstrap.
The harness supplies completion, process-start and boot/family evidence; these are
not a production recovery API. No real reboot occurred.

```sh
python3 tests/test-generation-cohort.py
python3 tests/test-native-config-race.py --cohort \
  --claude /absolute/path/to/native/claude-2.1.278 \
  --codex /absolute/path/to/native/codex-0.155.1
```

| Check | Result |
| --- | --- |
| Concurrent Claude/Codex readers; pending preparation; third reader joins A | PASS |
| One reader exits; remaining reader continues A; zero readers permits B | PASS |
| Reader races an activation paused mid-write | PASS: admission refused, then complete B after commit |
| Dead observer with live reader; old lease mtime; another reader joins | PASS: A retained and usable |
| Reader SIGKILL, PID reuse, unproven completion, same-boot recovery | PASS under explicit harness evidence; no inferred retirement |
| Separate surviving reader; simulated boot-epoch recovery | PASS; no real host reboot |
| Process crash after each of 21 target writes and after receipt commit | PASS: journal blocks reads; guarded rollback restores A |
| Recovery with a third-party edit | PASS: no files overwritten, journal retained |
| Idempotent staging, stale candidate, auth/escape exclusions | PASS |
| Exec PID, Unicode/empty/shell-literal argv, binary stdin, stdout/stderr, cwd, umask, signal and PTY descriptors | PASS with executable fixture |
| macOS kernel exit watch across exec: exit 23 and SIGTERM | PASS; root-process observation only |
| Native Claude 2.1.278 and Codex 0.155.1 discovery before/after activation | PASS: both see A/A before, B/B after at original fixture paths |

The suite contains **11 tests**, including the 21-boundary crash subcases. Native
validation uses v2 preparation/rendering and four discovery observations (two
agents × two generations). Hooks are disabled. Claude uses SDK initialization;
Codex uses local prompt-input inspection. No model turn/login is run. Native test
leases are held/released by the harness around its owned short-lived children;
this is not a test of the future detached guardian.

## Review outcome and remaining implementation gates

The revised contract **removes the native snapshot-routing blocker at the design
level**. It solves coherent native-path reads by deferring publication, not by
changing discovery semantics. Isolated protocol/native-discovery validation passes.

Remaining before any production qualification: implement and qualify the native
observer handshake/process-family evidence, connect every v2/bootstrap writer to
the same protocol, bind source/index/ref/receipt into the real activation journal,
implement profile-switch activation and durable recovery, and test native interactive
job control, backend modes and pipeline EOF behavior. The model does not implement
those integration items or profile-switch transactions; it refuses unequal mappings.

The guarantee covers cooperating managed writers/readers. Direct unmanaged CLI
invocations, raw chezmoi apply, owner edits or another tool writing mapped files can
bypass it. Enrollment must explicitly account for existing sessions and writable
entrypoints; inability to establish that boundary prevents production activation.
Drift detection alone cannot retroactively protect an already-running reader.

Public tests/docs only. No production/private changes, authentication handling,
tool installation, commit/push, other 4B–4G work or 4H. The design was subsequently accepted; current implementation status is linked above.

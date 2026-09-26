# Phase 4B–4G — cohort implementation review, 2026-09-24

**Historical review.** Enrollment finding 2 has since been repaired; native
family-retirement finding 1 remains blocked with more precise kernel evidence.
See [latest narrow repair and test matrix](phase-4-blocker-repair.md). No cohort or
barrier was removed and no new loading model was introduced.


**Overall gate: BLOCKED, not PASS. No production deployment, private changes,
public/private commit or push, or Phase 4H.** Generation cohort design is accepted.
The latest authorization permits consecutive isolated 4B–4G work; it does not
require per-phase approval. Work stopped at the new native guardian qualification
finding below, as required by the user's safety/native-compatibility stop condition.
The earlier short-lease and snapshot-discovery requirements are superseded.

## New native evidence and stop condition

The actual Claude 2.1.278 and Codex 0.155.1 binaries were launched through the
neutral controller, exec bridge and detached kernel guardian, using disposable
HOME/source/state and original native discovery paths. Claude received only SDK
initialization and EOF; Codex performed local prompt-input inspection. Both
returned zero and discovered all six shared skills. No model turn, login or
production configuration was used. Managed manifests remained unchanged.

However, **both minimal native invocations forked and left UNCERTAIN_FAMILY after
normal root-process exit**. After Claude there was one uncertain record; after
Codex there were two. This is new real-implementation evidence, distinct from the
previous test-only cohort's injected completion proof. It is not confined to
crashes, remote backends or unusual detached modes.

The guardian continuously observes NOTE_FORK/NOTE_EXIT using macOS kqueue and
binds records to kernel boot/PID/start identity. It deliberately cannot infer an
entire family has ended from the root exit. macOS NOTE_FORK does not provide a
reliable child tree; the SDK marks NOTE_TRACK/NOTE_CHILD unsupported. The current
implementation therefore keeps A protected and allows more A readers, but cannot
activate B after these ordinary native exits within the same boot. Only a reviewed
new-kernel-boot recovery can discharge these records with the present evidence.

The accepted design permits conservative fallback for uncertain lifetimes. This
review **does not silently extend that fallback into a completed normal-session
family-retirement implementation**. Native discovery compatibility passes;
production guardian/family recovery qualification does not. The design remains
accepted; the implementation still needs reliable family completion evidence or
an explicitly reviewed limitation for ordinary sessions. No PID polling, TTL,
force deletion, user-supplied boot proof, hook or lifecycle callback was added.
No actual host reboot or new-boot production recovery was tested.

Reproduction (only disposable environments, requires kernel identity permission):

```sh
python3 -B tests/test-native-guardian.py \
  --claude /absolute/path/to/claude-2.1.278 \
  --codex /absolute/path/to/codex-0.155.1
```

## Implementation completed before the stop

- Neutral session guardian: readiness handshake before native exec, detached/reaped
  helper, kernel identity and event observation, durable reservations, conservative
  fork/crash/observer-loss handling. A continuously observed normal leaf can retire;
  an observed crashed leaf requires an exact receipt/record-bound recovery approval.
  Guardian cleanup never activates or pushes.
- Shared kernel flock for enrolled v2/bootstrap writers; permanent legacy mkdir
  barrier prevents old engine entrypoints from bypassing a completed enrollment.
  Lock contention and reader state are separate. Fetch/scan/render preparation is
  outside the admission mutex; final baseline validation and mutation use it.
- v2 immutable external prepared candidates; in/push returns exit 75,
  DEFERRED_READERS and applied=false under readers. Source, targets, index/ref and
  bootstrap receipt are covered by the v2 transaction. Launch pending pointers do
  not authorize stale activation or automatic publication.
- Thin agent launchers use the same controller and a small common native exec
  bridge. The bridge preserves inherited signal dispositions/mask across Python,
  addressing Python's SIGPIPE behavior without changing vendor argv/environment,
  process group, cwd, descriptors, umask or PID. It is compiled only into explicit
  disposable state during these tests, never into a production command location.
- Toolchain draft: pinned Git 2.55.0 source build using Apple CLT; pinned Node
  22.22.0 tree, Claude 2.1.278 raw binary/signature check, existing pinned chezmoi,
  Codex and Gitleaks 8.30.1 archives. Safe bounded extraction, owned versioned
  trees/receipts, independent agent branches. No vendor install script, blanket
  package-manager upgrade, sudo or authentication automation.
- Explicit macOS CLT/Python OS checkpoint and separate reviewed PATH plan/apply;
  owned command entries, append-only shell block, digest-only shell metadata,
  conflict refusal and interrupted-write completion journal. Existing shell contents
  are not stored in bootstrap plans/receipts or portable source.

The Git source recipe is an intentional implementation proposal with a pinned
source digest, not an automatic fallback for a failed bottle. It uses the upstream
NO_RUST/NO_GETTEXT/NO_TCLTK/NO_PERL/NO_PYTHON options and SDK curl/zlib, retains HTTPS
transport, and requires review against the original 4A package-manager proposal.
It must not be treated as an already approved production tool installation route.

## Current test matrix

| Validation | Result and scope |
| --- | --- |
| `tests/test-bootstrap.py` | 24 PASS; three profiles, switches/reruns, adoption, faults, scanner, launcher argv/IO/umask/TTY/signal |
| `tests/test-guardian.py` | 5 PASS; real kernel leaf exit, surviving forked child, dead observer, reviewed crashed-leaf recovery, default/ignored SIGPIPE |
| `tests/test-cohort-integration.py` | 4 PASS; real v2 deferred in/push, prepared candidate, receipt activation, launch pending, legacy/profile barriers |
| `tests/test-bootstrap-path.py` | 5 PASS; three-profile PATH lifecycle, login/interactive shell, rerun, collision/drift, partial-write recovery, safe tree links |
| Native Claude/Codex through real guardian | Discovery and six skills PASS, no managed drift; normal-session family retirement BLOCKED for both |
| Official Git 2.55.0 arm64 source | Digest/build/install/version/`--no-lazy-fetch`/HTTPS helper PASS in `/private/tmp` |
| Official Node 22.22.0 arm64 tree | Digest/install/node/npm/npx health PASS in `/private/tmp` |
| Gitleaks 8.30.1 review scan | 19 public bootstrap/engine files, neutral staged filenames, exit 0, zero findings |
| Python AST, shell/C syntax, diff whitespace | PASS |
| Actual empty Mac / x86_64 / missing CLT system installation | NOT RUN; no system installation requested or performed |
| New-boot recovery on an actual rebooted host | NOT RUN; earlier boot-change model evidence remains model-only |
| Claude statusLine under launcher | NOT QUALIFIED; original nonempty-statusLine refusal remains |
| Full 4B–4G final acceptance and all crash boundaries | NOT COMPLETE; stopped at new guardian finding |

The initial sandboxed launcher run could not read kern.bootsessionuuid and failed
closed with BOOT_ID_UNAVAILABLE. Kernel-dependent suites were rerun with explicit
permission outside that restriction, retaining disposable paths and processes.
The bootstrap suite's expected synthetic secret fault was detected; that fixture
finding is not a secret found in the real review scan.

Earlier 61-test layout/migration/write, scanner, model-race and native-model results
are historical evidence, not a rerun of every test after these latest edits.
No completed qualification of fresh Claude/Codex artifact installation, complete
empty-machine orchestration or statusLine portability is claimed.

## Overall review of the current worktree

Review used the local [review skill](~/.agents/skills/review/SKILL.md).
No agent delegation was used.

1. **Critical — native family retirement is unqualified.** Both normal minimal
   agent sessions exercise the conservative fork path. Additional readers remain
   usable and active files remain protected, but ordinary close→activate behavior
   cannot be qualified. Keep the fail-closed lease; establish reliable whole-family
   evidence before claiming the normal production guardian complete.
2. **Critical — initial enrollment has an interruption gap.** Bootstrap currently
   removes its deployment journal before `enroll_cohort`. Injecting an enrollment
   interruption leaves a receipt accepted by `verify_receipt` but no cohort marker
   or permanent legacy barrier; a rerun returns NO_CHANGES without enrolling.
   This was reproduced in an isolated fixture. Enrollment must become part of the
   guarded readiness transaction and be required by launcher admission. No current
   build may be deployed until this boundary and its recovery tests are fixed.
3. **Warning — full durability/recovery integration remains incomplete.** Atomic
   file replacement fsyncs file contents but not all directory/metadata transitions;
   power-loss consistency is not qualified. The PATH journal's post-receipt crash
   boundary and enrolled v2 recovery need exhaustive tests. Existing tests cover
   their listed cases, not every production interruption boundary.
4. **Warning — dependency/statusLine completion remains open.** Real Git/Node
   installation passed, but the complete fresh-machine transaction, native agent
   install branches, PATH upgrade boundary and statusLine/widget portability still
   need qualification. `npx ...@latest` is not proven pinned by a predownload;
   production settings/widget state was not copied or silently rewritten.
5. **Warning — status and publication completeness.** Deferred preparation is
   explicit, but full active/pending/reader status presentation, profile-apply
   deferred UX, interrupted enrollment recovery and all source-upgrade paths still
   need completion. No user publication authorization is inferred from a pending
   generation or lease retirement.

## Continuation and retained state

Resume from these concrete findings without reopening the accepted cohort design
or reviving short leases/hooks/snapshot discovery. The next implementation must
first fix the enrollment boundary and resolve native whole-family retirement
qualification, then finish statusLine/dependency/PATH and remaining 4B–4G matrix.
The user has not authorized production activation or Phase 4H.

All edits are uncommitted public worktree changes. Fake Git commits/pushes are
confined to disposable test repositories. Public/private repository histories were
not changed. Existing production rollback packages were not opened, modified or
removed. Isolated verified Git/Node tools remain under
`/private/tmp/phase4-tool-qualification-7sfy2hp7`; this is temporary test material,
not a durable production rollback package or production PATH installation.

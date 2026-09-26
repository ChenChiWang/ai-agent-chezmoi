# Implementation status

## Latest — approved Codex incoming PASS; overall runtime PARTIAL (2026-09-25)

- Explicitly approved diagnostic plan `8848cc87e13d93a812a10460ab3ef1e814abf65869a5c629a99bdd88513af9bb`
  executed once by the original Codex session, exit **0**. The operator did not run in.
- Agent checked all **21 targets**, re-read shared source, both deployed instructions
  and relevant skill source/outputs, then used **示例：250 ms** without claiming measurement.
  Operator independently confirmed source/targets, HEAD/index and clean worktree.
- Remote unchanged; only the two instructions changed deployed content. Modes match
  the plan. Diagnostic engine remains external, not deployed. Protected auth/config
  metadata unchanged; no remaining sync/index locks or transaction journals.
- Initial outer-sandbox launch failed before native session initialization, with no
  in call. After explicit escalation approval, the native session resumed with its
  existing restricted permission profile; only one actual in was issued.
- Original IO_ERROR evidence/root-cause uncertainty and original startup results
  remain unchanged. This authorized continuation is not a new proactive-start PASS.
  Claude startup path and unsupported timing-answer issues remain separate.
- No outgoing, new commits/pushes, installation or production changes. Overall
  acceptance remains **agent-driven runtime PARTIAL**. Stopped after result recording.

## Previous — sanitized diagnostics verified; new Codex plan awaiting approval (2026-09-25)

- Runtime acceptance remains **PARTIAL**. This round adds error diagnostics only;
  no incoming retry, outgoing, native model smoke test or production deployment.
- `sync-write.py` retains existing stdout/exit codes and synchronization steps.
  Error stderr now reports allowlisted phase/operation/type, optional errno,
  project basename/line, transaction start and rollback/cleanup outcomes.
  The first error remains separate from secondary recovery/cleanup failures.
- Existing write suite: **31 tests PASS**; final error-deduplication adjustment:
  all **4 diagnostic fault-injection tests PASS**. File/Git/journal assertions
  distinguish no transaction, successful rollback and retained recovery data;
  synthetic sensitive exception text/path does not appear in output.
- Original Codex IO_ERROR still lacks its underlying traceback/errno. A separate
  permission probe observed EPERM creating the source Git lock under the original
  sandbox; this does not recover or prove the original failing operation.
- A new plan uses a private fixture-only diagnostic tool bundle, leaving the
  original remote candidate and deployed engine unchanged until approved incoming.
  Old plan approval does not transfer. See the runtime validation report.
- Preserve Claude incoming/file/read evidence, startup wrong-path failure and
  unsupported timing claims as separate results. No retroactive PASS.

## Previous — agent-driven runtime PARTIAL; fixed incoming validation stopped (2026-09-25)

- Overall acceptance remains **agent-driven runtime PARTIAL**. Preserve prior
  project-memory and finish results below; do not relabel reminders as proactive PASS.
- Latest scope: complete the two approved incoming scenarios and stop. Outgoing is
  not authorized this round. Existing isolated login/config roots are reused;
  no engine, launcher, guardian or test-framework changes.
- Minimal common instructions/skill clarification: startup requires a v2 incoming
  plan for remote freshness; missing network/inspection permission requires a
  specific approval request. Apply approval remains separate from inspection.
- User explicitly approved only fixed-gap fixture baseline/local remote seeding.
  Both fixtures were prepared with clean baseline source/deployment and a local remote exactly
  one commit ahead, changing only the reviewed shared duration-unit memory.
  Real scanner checks pass. Seed approval alone did not authorize runtime in/push.
- One fresh native startup per agent, using the fixed ordinary project prompt:
  both proactively invoke the skill and attempt incoming planning before project reads.
  Claude chooses /tmp rather than the supplied plan directory and hits BLOCKED_SYMLINK;
  correctly reports unknown freshness, but update discovery/concrete approval FAIL.
  Codex produces/reads its plan, inspects actual remote diff and requests approval PASS.
  No rule changes or startup retests followed the Claude failure.
- Operator generated one Claude plan in the provided directory, explicitly assisted,
  not Claude proactive PASS. Both real incoming plans were presented for user review;
  include mapped-file mode normalization as well as the shared memory content update.
  All deployed content/modes were unchanged and projects clean after startup turns.
- User subsequently approved both exact incoming PLAN_IDs and the 21 target mode
  changes, but no outgoing. At 2026-09-25 05:31:49 UTC, both unexpired plans match
  source/remote identities, actual source/target hashes and modes, and engine tools.
  User separately allowed necessary native session records, not sync-managed runtime.
  Both original sessions resumed after a fresh expiry/hash check at 05:46:42 UTC.
  No operator in, no plan renewal, no transfer of approval to a new ID.
- Claude: agent invoked approved in successfully, then Read the updated shared source
  and both deployed instructions; all three tool results contain the new marker/rule.
  Operator independently verified all 39 source and 21 target hashes/modes against
  the candidate. Agent status and sampled stat pass; some direct stat calls were
  permission-blocked, so full verification is not labeled agent-only.
  Content-use PARTIAL: uses ms units but claims unsupported measured 900 ms/150 ms.
  Unchanged skill reread was explicitly skipped. Startup discovery FAIL is retained.
- Codex: agent verified original plan/state/candidate, invoked approved in, received
  exit 70 IO_ERROR and stopped. Operator confirms all source/target hashes and modes
  remain at pre-apply state, source still baseline, no checked lock/journal remains.
  Cause not established; no retry or sandbox/protection workaround. Post-sync reread
  and content use NOT RUN. Startup discovery/approval PASS is retained.
- Both original plan files unchanged, local remotes unchanged, projects clean.
  Credential/config metadata checks unchanged; no credential contents read by verifier,
  no Keychain operation, no outgoing plan/commit/push. Native session records are
  outside sync mapping and retain the separately authorized native lifecycle.
- Acceptance is recorded separately for proactive trigger, approved script execution,
  and deployed-file/actual reread evidence. Fixed incoming run is finished and stopped;
  no additional prompts to turn partial results into PASS. Outgoing remains unauthorized.
- No production/private deployment, public/private commit/push, bootstrap or 4H.
- [Fixed scenarios, prepared fixture content and separate acceptance matrix](agent-driven-runtime-validation.md).

## Previous — agent-driven runtime smoke completed with limitations (2026-09-25)

- Test-only auth now succeeds for both agents. Claude stores its native fallback in
  the test CLAUDE_CONFIG_DIR; no production credential copied/linked or Keychain reset.
  Auth success and model success were checked separately. Actual models: Claude Code
  2.1.278 -> claude-sonnet-5 (`--model sonnet`); Codex CLI 0.155.1 -> gpt-6-astra
  (native turn_context, test default with low reasoning). No permanent model change.
- Each initial session used three consecutive turns: ordinary README/calc inspection,
  confirmed invoice integer-cents decision, then 「今天先到這裡」. No user prompt named
  synchronization or the skill. Project metadata supplied fixture roots, permissions
  and the project decision location, but no start/end trigger instruction. Shared
  instructions and skill were deployed from public templates through chezmoi.
- Codex: start PASS (read shared skill -> real status -> incoming plan/read plan ->
  project read), project-memory PASS (actual file edit/readback; clearly local only),
  finish PASS (read decision, source status/HEAD/local remote check + real status;
  no commit/push). All three turns returned successfully in the same native thread.
- Claude initial: model responded successfully, but start FAIL (project reads before
  any skill/status). Project decision written correctly; finish invoked Skill and
  status. Initial evidence retained, not relabeled PASS.
- One minimal public instructions change: an explicit Required memory checkpoints
  section requires skill/check before first project read, including short read-only
  tasks, and actual end-of-work checks. No skill/engine/launcher/guardian changes.
- Exactly one fresh Claude session retest (three turns): Skill -> actual status
  precedes project reads; decision Edit targets project docs/decisions.md and reports
  local-only/pending publication; final status + project git status confirms pending
  decision without commit. Trigger/order/local record checks PASS. Claude did not
  create an incoming plan, so remote freshness is NOT VERIFIED; no further retry.
- Neither agent executed in/push; fixture source and remote began equal. Changed
  incoming sync and post-sync re-read are NOT EXERCISED, not PASS. Permission boundary
  allowed inspection/planning and project edits only; no fake apply/publish consent.
  This is a bounded smoke result, not full acceptance of every sync branch or model
  reliability. Historical mixed-revision/loading gate remains BLOCKED.
- Final evidence: both source trees clean; source HEAD = local bare main; only project
  docs/decisions.md modified; each project still has one baseline commit. Codex source
  has one fixture baseline; Claude has a second operator-created fixture commit solely
  to deploy the instructions clarification between ended sessions. Neither model
  created any commit. Both final deployed v2 statuses pass with real Gitleaks 8.30.1.
  `sh tests/test-render.sh` and `git diff --check` pass. No new test framework installed.
- Owner-private evidence stays at /private/tmp/agent-memory-smoke-zvbvglbl:
  runtime-summary.json contains selected tool calls and file/Git results; per-agent
  evidence/turn0–2.jsonl contains native events; Claude evidence/initial preserves
  the original failure. Auth data is excluded from source, Git and reports. Do not
  archive whole test HOME; native runtime/auth directories are not test-report inputs.
- Cleanup NOT executed: after review, manually remove only Codex test auth.json and
  Claude test .credentials.json; remove only the exact test Keychain service entry
  (Claude Code-credentials-f1961f75) if present. Do not reset Keychain, delete the
  production entry or run general logout. Local deletion is not token revocation.
- No production/private changes, public/private commit/push, bootstrap or 4H. Stop.

## Previous — isolated native login prepared; waiting for user (2026-09-25)

- User authorized native login storage in the existing test roots, with browser
  authorization performed personally. No credential copy/export/link, production
  logout or model-preference change. No synchronization logic changes.
- Pinned executables: Claude 2.1.278 and Codex 0.155.1. Both login help commands
  were checked under isolated HOME. No login command or model request executed.
- Claude official authentication documentation confirms CLAUDE_CONFIG_DIR scopes
  both Keychain entry and fallback .credentials.json. Installed binary additionally
  shows credential service suffix derived from SHA-256(config directory), first
  eight hex characters; secure-storage env override takes precedence. Commands use
  env -i so that override cannot leak from the user's shell. Fixed test directory:
  /private/tmp/agent-memory-smoke-zvbvglbl/claude/home/.claude;
  expected default-production-OAuth test service: Claude Code-credentials-f1961f75.
  No Keychain credential value read/exported; no Keychain write/delete performed.
- Codex uses /private/tmp/agent-memory-smoke-zvbvglbl/codex/home/.codex
  and explicit cli_auth_credentials_store="file" for login, status AND all later
  runtime invocations. Expected secret file: that directory's auth.json. No further
  keyring debugging. Claude auth login --claudeai uses the subscription browser flow.
- Login and runtime env contract: per-agent HOME, CLAUDE_CONFIG_DIR, CODEX_HOME,
  XDG_CONFIG_HOME, XDG_CACHE_HOME, TMPDIR under its test home; LC_ALL=C;
  PATH=/usr/bin:/bin:/opt/homebrew/bin:~/.local/bin;
  GIT_CONFIG_GLOBAL=/dev/null, GIT_CONFIG_NOSYSTEM=1;
  DISABLE_AUTOUPDATER=1, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1.
  Native binary is absolute and cwd is the corresponding isolated project directory.
  Do not change the literal Claude directory or add a trailing slash between runs.
- User-facing Terminal commands provided for browser login only; user should report
  completion, not URLs/codes/tokens or raw auth files. Next action after completion:
  sanitize same-environment auth status, then separately qualify model requests and
  the three runtime triggers. Auth success alone is not a runtime PASS.
- Credentials stay outside all Git fixtures and chezmoi mapping. Never include auth
  directories in broad artifact snapshots, reports or Git adds. Test root may be
  removed by OS temporary cleanup; do not silently switch roots or borrow production.
- Cleanup after tests is manual/reviewed: remove ONLY Codex test auth.json and Claude
  test fallback .credentials.json if present; in Keychain Access remove ONLY the exact
  test service/account entry after confirming identity. Do not delete unsuffixed
  Claude Code-credentials, use broad matches or run production logout. Full test-home
  cleanup only after safe evidence review, without copying login data into artifacts.
  These actions have NOT been executed. No claim of server-side token revocation.

## Previous — agent-driven runtime smoke preflight BLOCKED (2026-09-25)

- User accepted the shared instructions/skill and isolated scripted validation;
  requested one short Claude and one short Codex session, each testing unprompted
  start, confirmed project decision, and end of work. No family tracking work resumed.
- Inspected existing native fixture: it intentionally supplies no auth and does not
  send model requests. Prior Phase 3 runtime used production configuration and cannot
  be reused as an isolated authenticated fixture under this request.
- Created separate owner-private fixture HOME/config/cache/tmp/project roots below
  `/private/tmp/agent-memory-smoke-zvbvglbl`. Environment uses explicit isolated
  HOME, CLAUDE_CONFIG_DIR, CODEX_HOME and XDG paths; no production credential symlinks,
  copied auth files, user Git config, or inherited credential environment. Existing
  auth environment variables were checked for presence only; all four checked were absent.
- Native version/auth preflight (no model requests): Claude Code 2.1.278 reports
  `loggedIn=false`, `authMethod=none`, exit 1; Codex CLI 0.155.1 file store reports
  not logged in, exit 1; explicit keyring store exits 1 with a keyring-related error.
  Keyring's exact underlying cause is not established; it is not reported as simply
  an absent account. Rechecked Claude/keyring outside the sandbox to distinguish
  sandbox interference: neither returned usable authentication.
- Both agents: **start / during work / finish / post-sync re-read NOT RUN**, blocked
  at isolated authentication preflight. Models were not selected or called. This is
  not an instruction-trigger failure; no skill tweak or retry of model behavior.
- Evidence: `preflight.json`, `auth-recheck.json`, `scope-check.json` in the root above
  contain sanitized status only. No credential payload or raw auth output saved.
  No source/destination deployment, local Git fixture or task files created after the
  failed gate; empty project directories are preparation, not runtime test evidence.
- Current constraints leave no verified way to reuse the account in this isolated
  environment. Do not copy/link production credentials, point config roots back to
  production, create a credential bridge, or initiate a new login automatically.
  A separately approved isolated authentication arrangement is needed before retry.
- No new framework/dependency, production/private change, model preference change,
  public/private commit/push, bootstrap or 4H. Only this status documentation changed.

## Previous — agent-driven memory sync (2026-09-25)

- New requirement supersedes pre-CLI automatic family tracking. Daily sync uses
  Shared Core + common skill + v2; bootstrap is separate. No further family
  retirement research, new loading implementation or installation this round.
- Updated only shared instructions and the shared skill as executable policy:
  first-turn check, confirmed durable memory, task/end-of-work check; re-read after
  sync; explicit recorded/applied/published/pending states and restart guidance.
- Existing authorization may cover reviewed operations; missing scope remains pending
  approval. Local status is offline, not evidence of remote freshness. Existing
  barriers, scanner, drift and writer protections are unchanged.
- [Requirements, approval gap and acceptance matrix](sync-v2.md#agent-driven-memory-checkpoints-2026-09-25).
- Validation: `python3 -B tests/test-write.py`: 27 PASS (85.194s), including
  real Gitleaks 8.30.1, no-op publication, network failure, drift/conflict, stale
  plans, locks/journals and failed-push recovery. `test-offline-status.py`: 6 PASS
  (6.456s). `ScannerTests.test_missing_tool`: PASS (required dependency refusal).
  `sh tests/test-render.sh`: PASS (both adapters, shared edits/skills, repeat apply).
- Additional disposable Git/chezmoi workflow: incoming update + two-agent re-read,
  missing approval rejection without mutation, source-only memory vs publication,
  identical deployed skill copies, and no-op finish without new commit all PASS.
  This scripted fixture used the existing reviewed scanner test adapter; real scanner
  coverage is separately included in test-write. All commits/pushes were fixture-local.
- Manual policy review covers all three checkpoints, global/project authority,
  reporting states, known concurrent-use deferral, offline and pending approval.
  This is not a model runtime invocation test. No claim that every model will
  autonomously trigger the skill; no production deployment. Historical loading gate
  remains BLOCKED; prior research/tests retained.
- Hash audit against the pre-change public implementation/test/example snapshot:
  only the two intended shared text sources changed; engine/bootstrap/tests unchanged.
  `git diff --check` passed. Existing uncommitted work was retained.
- No production/private edits, tool installation, commit/push or 4H.

## Previous — family retirement inspection/proposal only (2026-09-25)

- Enrollment repair and existing race/crash protection retained without code changes.
- Inspected actual root watcher, guardian handshake, leases/recovery and managed writer barriers.
  Root-only kqueue cannot distinguish reaped descendants from live descendants; polling cannot
  close the fork/attach gap. **Family retirement/loading gate remains BLOCKED.**
- No reliable small fix established within the current unprivileged mechanism. A richer kernel
  event backend is conditional on additional approval, permissions and completeness qualification;
  no tracking implementation, dependencies or services added.
- [Evidence, conditional scope/permissions, acceptance matrix and uncovered entrypoints](phase-4-blocker-repair.md).
  Stop for implementation review. No production/private changes, commit/push or 4H.

## Previous — two-blocker repair within the accepted cohort model (2026-09-24)

- Current user scope is only enrollment consistency, exact reader evidence and
  related regression/entrypoint coverage. No loading-model change or broader
  tool/PATH/statusLine implementation this round.
- Enrollment ordering/readiness is repaired: barrier is held and flushed before
  receipt publication; pending/corrupt state blocks admission/activation; approved
  rollback and re-plan/rerun pass seven hard-crash boundaries and fsync failure.
- Native root fork/exit events are confirmed for both agents. Root-only kqueue
  observation lacks descendant identities, continuous lineage and descendant exit
  events. Reaped-child and still-live-child fixtures both retain uncertainty; no
  inferred cleanup. **Family retirement and loading gate remain BLOCKED.**
- Administrative/inactive shim calls may skip refresh but still require complete
  configuration and successful reader protection. Raw CLI/IDE/chezmoi/editor paths
  outside the shim/protocol are explicitly outside the guarantee.
- [Root causes, minimal four-file change, tests and coverage](phase-4-blocker-repair.md).
  No production/private edits, commit/push or 4H. Stop after this review.

The following entries are historical; the latest scope/status above supersedes them.

## Previous — Phase 4 cohort implementation BLOCKED (2026-09-24)

Generation cohort design is accepted; consecutive isolated 4B–4G implementation was
authorized. Real guardian/v2 integration, exec signal bridge, pinned Git/Node build
and owned PATH lifecycle have progressed. 38 focused tests pass. Actual Claude and
Codex discover six skills through the guardian, but both ordinary minimal sessions
leave UNCERTAIN_FAMILY: normal-session family retirement is not qualified. Review
also reproduced an initial-enrollment interruption gap. Work stopped under the
new safety/native-qualification stop condition; **4B–4G is not PASS**.

No production/private edits, public/private commit/push, or 4H. StatusLine and full
fresh-machine/upgrade validation remain incomplete. See the authoritative current
[implementation evidence, review findings and continuation](phase-4-cohort-implementation.md).
The sections below are historical; their pending-design/short-lease scope is superseded.

## Historical generation-cohort design — isolated validation PASS (subsequently accepted)

- Latest user scope: design + isolated race/crash/recovery only; session-length
  reader leases allowed; no hot reload, hooks or native discovery-path changes.
  Stop after review preparation; do not continue other 4B–4G work.
- Fixed-path active generation admits concurrent Claude/Codex readers. Pending
  generation preparation is independent; activation waits for zero readers.
- 11 isolated model tests cover concurrent admission, deferred publication, stale/
  crashed readers, PID reuse, kernel exec/exit observation, guarded recovery at
  every mapped write boundary, drift refusal, and exec/TTY/streams/signal behavior.
- Native Claude 2.1.278/Codex 0.155.1 discovery sees complete A before and B after
  activation, using original fixture paths and no hooks/model/auth requests.
- Native snapshot routing is no longer required. Production guardian/family-lifetime
  qualification and real v2 transaction integration are not implemented by this
  design-only round. No production/private changes, commit/push or 4H.
- [Design, evidence, limitations and review outcome](phase-4-generation-cohorts.md).

## Phase 4 loading redesign — native race confirmed (2026-09-24)

- User explicitly rejected lifecycle callbacks and requested agent-independent
  sync/validation/deployment followed by unlocked native exec.
- Reproduced mixed skill revisions in actual Claude 2.1.278 and Codex 0.155.1
  during a paused real v2 fixture transaction, with hooks disabled and no model
  requests. Atomic per-file writes and a global atomic pointer are insufficient.
- Test-only immutable-generation pinning passes 5 isolated tests without a reader
  lease. Native routing remains NOT PASS: CODEX_HOME-only uses snapshot instructions
  but still discovers live HOME skills. No HOME/auth/runtime relocation was added.
- Existing launcher CLI transport checks: 3 targeted tests PASS. This is not native
  snapshot-launcher qualification. Remaining 4B–4G work is conditional on this gate
  and was not advanced. Production/private untouched, no commit/push or 4H.
- [Design, native evidence, scope and gate matrix](phase-4-consistent-loading.md).

## Phase 4B–4G follow-up — stopped at loading safety finding (2026-09-24)

- Latest authorization permits consecutive isolated 4B–4G work; no per-phase
  approval is needed. 4H real second-machine deployment remains excluded.
- Native Claude 2.1.278 negative qualification reproduced successful `--init-only`
  with SessionStart, and successful `--init-only --settings
  '{"disableAllHooks":true}'` without the callback. No model/auth request was made.
- A SessionStart-only release cannot cover preserved CLI settings overrides, and
  does not establish all skill loading is finished. Stopped under the user's
  safety/regression condition; no unsafe release or forced hooks were added.
- Three blockers and full 4B–4G overall validation remain incomplete. No production
  changes, private changes, commit/push or 4H. [Evidence and remaining work](phase-4-loading-safety.md).

## Previous Phase 4B — isolated implementation, acceptance blocked (2026-09-24)

- 4A accepted; 4B implementation and isolated fixtures authorized. No production
  command/tool/private-dotfiles changes, no commits/pushes, and no 4C–4H execution.
- Added three-profile bootstrap plan/apply/switch/recover, full-repository versus
  active-target scope, pinned artifact mechanism and exact-revision acquisition.
- One neutral launch controller reuses v2 Engine; thin shims preserve vendor argv,
  inherited streams, cwd/umask and exit/signal behavior in isolated CLI/PTY tests.
- Tests passed: bootstrap 24, nested layout/migration/write 61, scanner 10, offline
  status 6, shell render/status. Standalone write 27 and migration 24 also passed
  during implementation; these overlap with the nested suite.
- **Not 4B PASS:** conservative reader leases last for the session and block v2
  writes during that session; short loading-complete integration remains unresolved.
  Git/Python/Claude/Node remain explicit prerequisites; complete empty-Mac setup,
  PATH/minimum-OS/toolchain qualification and Claude statusLine support remain gates.
- [Review findings and evidence](phase-4b-validation.md),
  [implementation interfaces](../bootstrap/README.md). Stop for review.


## Historical Phase 4A — accepted design

- Scope is public documentation only; Phase 3 remains COMPLETE. No production
  private change, tool installation/removal, bootstrap execution or commit/push.
- [Design](phase-4-bootstrap-design.md) defines new-macOS tool/profile plans,
  three profiles (`claude`, `codex`, `claude-codex`), independent agent/tool/auth
  readiness, bounded deployment, runtime-state exclusion, idempotent reruns,
  explicit upgrade/profile switching/reactivation and guarded recovery.
- Existing implementation gaps are explicit: absent-target bootstrap transaction,
  full-repository history versus selected deployment profile, stock chezmoi profile
  behavior, reproducible tool lock and statusLine portability/dependencies.
- Additional read-only production launch audit found neither Claude nor Codex
  has managed launch-sync: no configured sync hook/launcher, and deployed skills
  prohibit session-start writes. Both require the new pre-exec launch controller.
  Design now specifies standing-policy plan/in, offline/dirty/drift/lock/dependency
  outcomes, agent independence, and pending reader-barrier/timeout qualification.
  No production mutation or launch-sync execution occurred.
- [Proposed 4B–4H roadmap](phase-4-roadmap.md) requires later authorization. No
  fixture or real-machine bootstrap PASS is claimed. Stop for 4A review.

## Phase 3 COMPLETE — 3H publication (2026-09-23)

- Explicit 3H authorization followed accepted 3F/3G PASS.
- Private commit: `19a27374a0ff2d1d4739f3d9a9c6bd2e46471ab9`. Normal fast-forward push to
  origin/main succeeded; local HEAD, origin/main and actual remote main agree.
  Private working tree is clean.
- Pinned Gitleaks 8.30.1 full candidate/diff and actual commit scans passed.
  Only mapped sources plus unchanged legacy README are tracked; machine-local
  trust/auth/session state is excluded.
- Precommit and post-push render/status/drift validation passed for 21 targets;
  original Claude behavior/config and shared six-skill authority are preserved.
- Rollback packages/blobs retained and integrity verified. Old rollback commands
  deliberately reject the newly committed HEAD/index; later rollback requires a
  separately reviewed recovery plan. No guard bypass or deployment rollback ran.
- See [3H finalization](phase-3h-validation.md). Phase 3 is complete; stopped.

## Historical Phase 3E–3G gate — PASS, stopped before 3H

- 3E remains deployed: eight source additions and seven Codex targets; Claude
  unchanged. External expansion baseline and isolated rollback remain available.
- User-authorized cleanup removed only the test-directory trust section from
  Codex config. Exact pre-3E bytes and mode 0600 restored; all other settings kept.
- Post-restoration final validation passed: 21 actual renders, empty chezmoi diff,
  both profile scanner statuses, migration verify, shared rules and six skill
  pairs, original Claude 3D manifest, private HEAD/index/config and restored config.
- Source boundary confirmed: 39 mapped files plus unchanged legacy README;
  actual chezmoi managed files exactly match 21 mapped targets. Codex project
  trust, authentication, sessions and other runtime state remain outside authority.
- Prior successful actual Claude/Codex runtime and cross-agent fixture/no-op sync
  evidence is retained for the unchanged deployment; no new model run is claimed.
- **3F/3G PASS.** No deployment rollback, private commit/push or Phase 3H execution.
  See [validation matrix](phase-3efg-validation.md) for evidence and limitations.

## Completed production Phase 3A–3D gate (before 3E authorization)

- Authorized public reference: `15f17ca3ed349a48142f8ada8b62ca8568c1426d`.
  Production nested layout, clean legacy source/index, inventory/deployed equality
  and Gitleaks 8.30.1 preflight passed.
- 3A PASS: owner-private baseline outside HOME; verified blob/manifest integrity;
  actual-content isolated conversion, 14 chezmoi renders, real scanner status and
  complete rollback passed with files/modes/Git state restored exactly.
- 3B/3C applied using the approved Claude-only plan. Source diff: 28 creates,
  eight legacy plain-source removals, one metadata replacement; two unchanged.
  Target diff: five neutral engine files created, three sync/instruction outputs
  replaced, six existing skill/settings outputs unchanged. No Codex adapter.
- Production manifest bytes/modes, all 14 chezmoi renders, normal-shell scoped
  apply/diff idempotence, pinned scanner status, offline plan/in and legacy wrapper
  status passed. HEAD/index/config and the approved source/target state were
  rechecked unchanged after the Claude runtime attempt.
- Harness correction: setting process-wide umask077 for private logs caused a
  permission-only chezmoi diff. The unmodified shell uses umask022 and produces
  an empty diff. Logs now receive explicit 0600 permissions without changing the
  test process umask. No production permission correction was needed or applied.
- Initial 3D runtime attempt was blocked by external credits/limit. The user then
  explicitly authorized session-only model substitution without changing settings.
- **3D PASS:** actual Claude `--model sonnet` initialization discovered all six
  skills; six real Skill calls returned non-error results from deployed user skill
  directories. The successful response confirmed shared language, comment, commit,
  signature, uncertainty, destructive-action and sync policies, with individual
  skill content summaries. There were no non-Skill tool calls.
- Actual existing statusLine command and user widget configuration passed startup
  and active-context stdin tests: exit 0, nonempty output, expected model/branch,
  context-dependent output and empty stderr. Settings/widget configuration hashes
  were unchanged. A test assertion was corrected to normalize NBSP characters;
  no production output/configuration adjustment was needed.
- Additional deployed-engine checks on the external actual-content copy passed:
  propagation of rules plus all six skills, drift status, stale approval refusal,
  offline push refusal, scoped restoration and rollback. A reverse edit against
  the unchanged bootstrap baseline correctly returned DRIFT; the copy was restored
  using scoped chezmoi as in the accepted fixture contract, without bypassing v2.
- Final production status and scoped chezmoi diff passed. All approved source and
  target bytes/modes, private HEAD/index/config, and original model preference and
  settings were preserved. Detailed evidence, test types and limits are in the
  [3D validation matrix](phase-3-validation.md).
- Stopped with the migrated deployment retained and rollback available. No private
  commit/push, Phase 3E–3H execution or automatic production rollback occurred.
  Owner-private detailed evidence: `/Users/Shared/ai-agent-migration-<user>/phase3-20260922-221058/`.
  See its `ROLLBACK.md` and `review/phase3-result.json`; never publish backup/log
  payloads. [Roadmap](phase-3-roadmap.md) records the mandatory stop.

## Phase 2.7 Production Layout Compatibility (2026-09-22)

- Public baseline: `50fabd55bd2d6d8865501ce739184937d3d0560b`. The user
  authorizes public implementation, isolated tests and review only. Prior
  uncommitted preflight documentation is retained as historical evidence.
- Centralized layout validation now allows source under destination HOME outside
  reserved deployment regions, and rejects equal/reversed roots, managed symlink
  and hard-link escapes, unsafe parent types, Git metadata symlinks, and roots
  encompassing the scratch allocation area. Validation precedes source locking.
- Source aliases are canonicalized; managed descendants are not followed through
  symlinks. Migration alias discovery prunes unrelated source trees. Destination
  payload access remains the static profile mapping; no HOME tree walk occurs.
- Plans/backups/local test remotes remain outside both roots. Scanner version,
  approval hashes, legacy conversion mapping, historical scans and guarded
  rollback requirements are unchanged. No alternate scanner bypass was added.
- Added `tests/test-layout.py`, reusing the complete migration/write contracts at
  `<fixture HOME>/.local/share/chezmoi` plus boundary, manifest, sentinel and
  traversal cases. All remotes and deployments are disposable local fixtures.
- Review found and corrected status's invalid-profile error precedence (retains
  exit 64); unsafe managed paths now fail earlier with `INVALID_LAYOUT` / 65.
  The status symlink assertion was updated to this explicit diagnostic contract.
- Review result: **PASS for the public macOS isolated-fixture contract**. Reviewed
  the shared root validator, status/write/migration entrypoints, bounded alias
  traversal, saved-manifest path admission and existing rollback mutations.
  No known blocking finding remains in this scope. This is not production 3D.
- `tests/test-layout.py`: 61 distinct scenarios passed: the 58-case full run
  finished in 199.965s, followed by the three added Git symlink/alternate-store and
  invalid-profile cases. After final review changes, those three plus the full
  nested 3A–3D/rollback scenario passed together (4 tests, 9.127s). The source/HOME
  no-traversal scenario was also rerun after shared validation changes.
- Existing sibling-layout regressions: migration 24/24 (104.150s), write 27/27
  (94.360s), pinned real scanner 10/10 (33.684s), offline status 6/6 (latest rerun
  6.398s). Render/status shell suites passed; status was rerun after the diagnostic
  assertion and invalid-profile precedence fixes.
- Python AST/shell syntax, both profile mappings and wrappers/literal rendering,
  new-file LF/whitespace, `git diff --check`, and unchanged legacy v1 engine checks
  passed. macOS temporary-directory lookup warnings in cleared test environments
  did not affect fixture isolation or results.
- Limits: no production Claude loading/statusLine/chezmoi regression or private
  inventory classification was attempted. Production needs a durable owner-private
  backup/plan location outside HOME. Existing cooperating-writer and recoverable
  transaction assumptions remain; no hostile concurrent filesystem-race guarantee
  or new platform/SSH/HTTPS validation is claimed. Stop for user acceptance.
- No private source read, relocation, mutation, production deployment, repository
  commit/push or Phase 3 execution occurred in Phase 2.7. See
  [production-layout.md](production-layout.md) and the mandatory
  [Phase 3 gate](phase-3-roadmap.md).

## Accepted Phase 2.6 Migration Readiness (2026-09-22)

- Baseline: public `03bbd09e0674cf5494dc4a44ee37438b77ce3533`; previous uncommitted
  Phase 3 roadmap/status changes preserved. This task authorizes public code/tests
  only: no private source, Phase 3 execution, repository commit or push.
- Implemented 2.6A staged `claude` (31 source / 14 targets) and `claude-codex`
  (39 / 21) profiles. Scanner owns the static mapping/wrapper schema consumed by
  shell status, Python write and conversion engines; profile is approval-bound.
- Implemented 2.6B mapping/render/scan/history for all six skills and Claude-only
  settings. Five public examples are new generic content, not private copies.
  Conversion preserves actual legacy skill output bytes and settings exactly.
- Implemented 2.6C offline `migration plan/apply/verify/rollback`, persistent private
  baseline blobs/manifest, explicit rule segmentation, safe plain-to-template
  conversion and legacy forwarding entrypoint. No Git commit/ref/index change or
  remote access is required to bootstrap. Added explicit offline `in` with a
  hash-bound migration baseline while HEAD is still legacy; push cannot use it.
- Shared literal opener escapes preserve JSX/Go-looking examples without arbitrary
  template execution. Both original/encoded and decoded rendered snapshots are
  scanned. Fixed named-template wrappers replace the earlier raw-include schema.
- Recovery validates all old/new values before restoring, preserves later edits,
  tracks created-directory ownership, and retains a journal on unsafe recovery.
  Later Codex expansion has separate approval/backup and reverse-order rollback.
- 2.6D uses fake legacy rules, six skills, three-key settings, a legacy execution
  sentinel, isolated homes/chezmoi state, real local Git and synthetic runtime state.
  It simulates 3A–3D and separately tests a future Codex expansion; no private
  production data or actual product sessions participate.
- 2.6E review: **PASS within the public/macOS/synthetic-fixture contract**. No known
  blocking finding in that scope. Reviewed tracked changes and new implementation,
  schema, backup/approval, templates, tests and documentation. No production
  regression or private inventory equivalence is implied. See
  [design, commands and acceptance boundaries](migration-readiness.md).

### Phase 2.6 verification

- `tests/test-migration.py`: 24 scenarios passed. Final full 23-case run passed in
  79.256s; the added explicit test with no Codex directories passed separately in
  4.391s. Covers complete fake 3A–3D, later expansion/reverse rollback, six skills,
  settings/rules, literal template examples, scanning, drift, unknown inventory and
  templates, aliases, collisions, stale/tampered backups, locks, partial failures,
  later edits, created-directory ownership and incomplete legacy deletions.
- `tests/test-write.py`: 27/27 passed (90.553s), including a secret removed from an
  added shared skill's outbound history. Existing normal-sync behavior preserved.
- `tests/test-scanner.py`: 10/10 passed (32.759s) with Gitleaks 8.30.1. Migration
  scenarios also scan real synthetic credentials at every newly added skill path.
- `tests/test-offline-status.py`: 6/6 passed (6.679s). No-lazy-fetch boundary intact.
- `sh tests/test-render.sh`, `sh tests/test-status.sh`: passed. Actual chezmoi output
  and Python rendering agree, including literal opener escapes and staged profiles.
- Python AST/shell syntax, six skill frontmatters (Ruby YAML safe-load), complete
  profile/wrapper mapping, changed/new-file LF/whitespace, `git diff --check`, empty
  public index and unchanged legacy v1 engine checks passed. Skill Creator's Python
  validator remains unavailable because PyYAML is absent; no packages installed.
- Review corrections: local-only in no longer copies unused Git objects or writes
  same-OID reflogs; raw and decoded history are both scanned; template openers use
  a bounded literal escape; rollback preserves external directories/later edits;
  unknown shared definitions block expansion; bootstrap requires the approved
  legacy-source deletions to be complete.

### Phase 2.6 stop / remaining limits

- No private source or actual Claude/Codex configuration was read, modified or
  deployed during this task. Tests use synthetic data, isolated homes/chezmoi state,
  and disposable local Git repositories. No real external Git remote operation.
- No public/private commit or push. Public HEAD remains `03bbd09`; initial roadmap
  and status edits are preserved alongside the new uncommitted implementation.
- Readiness is for the documented legacy layout and two closed profiles. Unknown
  skills/payloads/frontmatter/settings keys or source encodings stop for review.
  Instruction classification is explicitly reviewed; byte preservation alone
  does not prove semantic correctness. Backups are scoped and private, not a full
  home backup or a power-loss guarantee.
- Real Claude loading, real statusLine dependencies, production chezmoi config/hooks,
  fresh private inventory comparison, Windows/Linux and real SSH/HTTPS remain
  unverified. First migration publication is still a separately authorized 3H
  review; offline bootstrap cannot enable push or weaken its history checks.
- The [Phase 3 roadmap](phase-3-roadmap.md) persists. Phase 3A remains unstarted;
  3D is still a mandatory stop, and 3E–3H require later approval.

## Previous session: Phase 3 preflight stopped (2026-09-22)

- Phase 2.5 is accepted and published at `03bbd09e0674cf5494dc4a44ee37438b77ce3533`.
- User now authorizes private migration 3A–3D only. Preserve existing user rules
  and Claude-only settings; do not deploy Codex and do not push the private repo.
  This supersedes the older migration-pause statements below.
- Full [Phase 3 roadmap and stop evidence](phase-3-roadmap.md) recorded for later
  sessions: 3A baseline/rollback, 3B Shared Core, 3C Claude cutover, **3D mandatory
  regression gate and stop**, 3E Codex deployment, 3F Codex validation, 3G cross-agent
  validation, 3H final private commit/push. 3E–3H remain unauthorized.
- Preflight recovered the accepted inventory and inspected public source. The
  fixed engine requires both adapters, lacks the five additional skill mappings,
  and requires an already-migrated v2 HEAD/output baseline. These contracts do not
  support the requested Claude-only legacy migration as published.
- Stopped under the user's explicit incompatibility instruction. No private source
  inspection or mutation, baseline backup, migration, deployment, commit, push or
  Claude regression execution occurred during this attempt. 3A is not complete;
  3B–3D have not started. No rollback of private state is needed.
- Only public roadmap/status documentation changed. No engine extension or silent
  workaround was attempted. Resolve the documented reference gaps before resuming;
  prior isolated Phase 2.5 passes must not be reported as a Phase 3D pass.

## Current acceptance: v2 safe sync engine (2026-09-22)

- Baseline: `0668304`, public `ai-agent-chezmoi`, clean working tree at task start.
- Inventory accepted; private migration remains paused. This section supersedes
  the historical Phase 1 stop point and unsupported-command notes below.
- Added shared `sync-write.py`, its generated wrapper, and `tests/test-write.py`.
  `sync.sh` dispatches `plan`, `in`, `push`; offline status remains intact.
  Scope is now 19 source files / eight generated outputs. Scanner, shell and Python
  mappings agree. One shared skill routes both agents through the same engine.
- Implemented owner-only approval plans (SHA-256 ID / one-hour expiry), canonical
  source lock, quarantined fetch/index/objects, scoped FF incoming changes,
  generated drift protection, raw-byte tree construction and full outbound commit
  inspection (including intermediate snapshots and commit metadata).
- Staged changes and special index flags are refused intact. Unknown/out-of-scope,
  empty or merge commits block synchronization. No implicit source discovery,
  unrestricted re-add/apply, automatic staging, stash/reset/rebase or source hooks.
- Approval binds source/destination, HEAD/ref/index/config, exact remote/branch,
  candidates/outputs, identity/message and trusted helper/scanner files. Execution
  rebuilds, re-scans and compares; local state is rechecked before mutation.
- Push plans explicitly include generated-output deployment. The approved local
  commit/index/output state is retained on remote rejection; retry requires a new
  plan. This prevents a push from leaving its own deployment behind its new HEAD.
- Push uses one explicit refspec and an exact expected-OID lease, after an independent
  ancestry proof. No history rewriting is permitted. Source refs use old-OID CAS;
  ordinary Git writers also encounter the transaction's index.lock.
- File/index transactions preserve old/new bytes, modes and hashes in a local Git
  journal. Normal failures safely roll back; concurrent edits are preserved and
  uncertain recovery keeps the journal. SIGKILL/power-loss recovery is manual and
  documented, with no automatic stale-lock deletion or reset.

### Verification and review

- `tests/test-write.py`: final full run 26/26 passed (53.262 seconds).
  Real local fixture commits/bare-remotes cover incoming, source-only apply, scoped
  publication, no-op, stale/tampered/expired plans, staged work, drift, secrets in
  removed history/messages, unrelated history, remote rejection/retry, remote and
  source races, scanner failure, source hooks/filters, lock aliases, paths with
  spaces/Chinese, deployed-engine plan invariants, rollback and concurrent-edit
  recovery. Real Gitleaks covers clean publication and removed historical secrets.
- `sh tests/test-render.sh` and `sh tests/test-status.sh`: passed, including the
  new helper/output and actual chezmoi equivalence for the Python renderer.
- `python3 tests/test-offline-status.py`: 6/6 passed, preserving no-lazy-fetch.
- `PATH=/private/tmp/ai-agent-gitleaks-8.30.1:$PATH python3 tests/test-scanner.py`:
  10/10 passed with the existing pinned binary; no dependency installed.
- Shell syntax, skill YAML (Ruby safe-load), whitespace and legacy-engine unchanged
  checks passed. Skill Creator quick_validate remains unavailable (missing PyYAML);
  no package installation attempted.
- Review: no known blocking finding in this fixed-profile/macOS/local-transport
  acceptance scope. Reviewed candidate/tree integrity, staged-state preservation,
  network isolation, historical leaks, approval freshness, transaction failure and
  retry behavior. Shared Core + thin Claude/Codex adapters is preserved.

### Limits / stop point

- This replaces legacy **operations for a migrated v2 profile**, not arbitrary
  existing private layouts. Inventory-to-schema mapping, first deployment, backups,
  legacy wrapper/trigger cutover and product loading are not done or authorized here.
- Authenticated HTTPS helpers, SCP aliases, linked worktrees, SHA-256/shallow repos,
  new/missing/deleted mappings, merge histories and empty remotes are unsupported.
  Private remotes can use explicit SSH URLs with an existing agent/known_hosts;
  actual SSH/HTTPS and Linux/Windows/WSL behavior remain unverified.
- Locks protect cooperative callers. Manual same-user writers can bypass them;
  multi-file replacement is recoverable, not an atomic filesystem-wide snapshot.
  Unreachable immutable Git objects may remain after a failed transaction. A
  journal is not a power-loss guarantee or a substitute for migration backups.
- Only public template/docs/tests changed. No private chezmoi or real agent config
  was modified or deployed. No commit/push in the public or private repository;
  real commits/pushes occurred only in disposable local test fixtures. No external
  Git remote or credentials were used. Migration remains paused; stop after review.

## Historical Phase 1 record

## Baseline

- Commit: `8cb9ce370ac97e75c3a57dd541339b2c306e8d2a`, branch `main`.
- Existing untracked `docs/AGENT_SHARED_CONFIG_HANDOFF.md` preserved unchanged.
- Host: macOS (Darwin), zsh; scripts use POSIX sh.
- Git 2.55.0, chezmoi 2.71.0, Claude Code 2.1.278, Codex CLI 0.155.1.
- Codex version query reported a denied attempt to create PATH aliases; no retry
  with expanded permissions. IDE extension version/loading not inspected.

## Completed

- Added `examples/chezmoi/`: shared instructions, shared skill, two thin adapters,
  seven generated entries (including scanner/registry), one shared shell engine, ignore/LF examples.
- Implemented explicit-source, scoped, offline status: staged/working changes,
  generated-file drift, isolated rendering, scanner interface and nonzero errors.
- Unsupported `plan`, `in`, `push` fail before tool/source access.
- Added `tests/helpers.sh`, `tests/test-render.sh`, `tests/test-status.sh`.
- Updated both READMEs, the legacy setup guide, legacy skill version notice, and
  legacy ignore example; preserved the legacy engine byte-for-byte.
- Added `docs/migration-v2.md` with API, dependencies, limits, migration and rollback.

## Verification

- `python3 tests/test-offline-status.py`: 6 tests passed with real Git 2.55.0.
  Trace2 verifies no fetch child and no fake SSH invocation for missing index/
  HEAD blobs and missing HEAD trees. Also covers complete local partial-clone
  objects, regular missing objects and unsupported Git capability.
- `tests/test-scanner.py` with verified Gitleaks 8.30.1: 10 real-scanner/protocol/
  integration tests passed on macOS ARM64; shell render/status suites also passed
  after the scanner integration.
- `sh tests/test-render.sh`: passed. Actual chezmoi rendering/apply restricted to
  temporary fixtures; identical skills, shared edit reaches both entries, adapter
  separation, exactly seven output files, frontmatter, LF, executable engine,
  repeat apply unchanged.
- `sh tests/test-status.sh`: passed. Covers scoped source/index/HEAD/destination invariants,
  source/target drift, unrelated staged/untracked files, synthetic source/index/
  destination secrets, scanner failures/missing executable, dynamic-template
  rejection, ignored out-of-scope hooks/config, symlinks, override/custom home,
  executable-bit drift, missing target, conflicts, and unsupported writes.
- `sh -n` on the engine and three test scripts: passed.
- `git diff --check`: passed for tracked changes.
- `git diff --exit-code -- examples/dotfiles-sync/sync.sh`: passed (v1 unchanged).
- Skill Creator `quick_validate.py`: could not run because PyYAML is unavailable;
  no packages installed. Ruby YAML safe-load verified required frontmatter fields;
  rendered skill frontmatter is also checked by the fixture suite.
- macOS Python emitted a temporary-directory lookup warning in the cleared test
  environment and fell back to `/tmp`; all fixture paths remain explicitly isolated.

No real commits are created even in tests. The HEAD comparison case uses a Git
shim with real index blobs, not a committed-history integration test. Actual
Git init/add/update-index in tests affect only temporary fixture repositories.

## Decisions and differences from the handoff

- Phase 1 never auto-discovers a private source: explicit source/destination paths
  are required and source must be a regular Git root. Worktrees are deferred.
- Uses literal include wrappers. Shared files reject opening template delimiters
  because chezmoi parses `.chezmoitemplates` even when include is used. Wrapper
  changes require a matching engine schema change; arbitrary Go templates are
  unsupported. This trades flexibility for a bounded, offline render.
- Render uses only the v2 profile in a temporary source. Existing private config,
  hooks, externals and ignore behavior are not simulated or certified.
- Status prints labels/known paths only, no raw diff. Gitleaks 8.30.1 is now the
  default scanner via a Python standard-library adapter. A strict schema validates
  every finding before exposing only known snapshot paths, pinned rule IDs and
  line numbers. Raw tool output and secret/match fields are never forwarded.
- Added a small Python helper for JSON/report validation, preserving the POSIX
  synchronization engine. Source scope grew from 13 to 17 files; output scope
  grew from five to seven files. No product settings were added.
- No real deployment and no v1 wrapper switch. Same-name skill installation must
  wait until migration/write behavior is ready and separately authorized.

## Not verified / limitations

- Outbound history, plan approval, locks, pull,
  push, migration tooling and actual rollback are Phase 2 or later work.
- No Claude/Codex product loading test; no private home/override inventory.
- No Windows, Git Bash, WSL or Linux runtime tests; no ShellCheck installed.
- No new CI workflow or automatic dependency installation.

## Safety boundary

- Real agent configuration deployed/edited: no.
- Private chezmoi source read or modified: no.
- Credentials/tokens read or printed: no.
- Repository commit/push or real external remote operation: no. Offline regression
  uses a fake transport only for its positive control.
- `/init`: not run.
- Fixture apply/init/add: temporary paths only, inherited environment cleared.

## Scanner follow-up

- Added `scan-secrets.py`, pinned `gitleaks-rules.json` (222 IDs), two output
  wrappers, `tests/test-scanner.py`, and `docs/secret-scanner.md`.
- Default scanner is the bundled adapter; `--scanner` overrides require a
  schema-1 report as well as the correct exit code. Old exit-code-only adapters
  now fail closed. Updated test doubles, shared skill and both READMEs.
- Official macOS ARM64 Gitleaks 8.30.1 downloaded with network approval to
  `/private/tmp/ai-agent-gitleaks-8.30.1`, archive SHA-256 verified before extraction.
  No global install. Runtime tests are offline and use only synthetic data.
- Real tests cover GitHub PAT, generic API key and private-key patterns; source,
  index, HEAD, render and deployed snapshots; ignore/config/inline bypass attempts;
  missing tool, wrong version, failure, timeout, unsafe/malformed/inconsistent
  reports; symlink/unreadable/oversized/invalid text; deployed engine redaction and
  unchanged Git/source/destination state. No real commit created.
- Main command: `PATH=/private/tmp/ai-agent-gitleaks-8.30.1:$PATH python3 tests/test-scanner.py`.
  The suite fails instead of skipping when the real binary is missing.
- Gitleaks remains heuristic; built-in content allowlists remain active. Snapshot
  input is limited to readable UTF-8 text (8 MiB per file), no NUL or symlinks.
  Archives, arbitrary binary data and real outbound history are not covered.

## Stop point

Phase 1 implementation, scanner and final review only. No private migration, production
home deployment, plan/pull/push implementation, commit or push. Further work
requires a new user instruction; the next architecture stage remains safe plans
and outbound-history verification, not automatic migration.

## Phase 1 final review (2026-09-22)

- Result: PASS for Phase 1; no remaining blocking findings in the reviewed scope.
- Rerun after the P1 fix: render/status suites passed, scanner suite 10/10 passed,
  offline regression 6/6 passed. Shell/Python syntax, tracked `git diff --check`,
  new-file whitespace/LF checks and source/target mapping consistency passed.
- Reviewed tracked diff and all untracked implementation/test files, not just
  `git diff` (the new shared tree is still untracked). Existing handoff retained.
- Architecture matches Shared Core + Claude/Codex adapters: one shared rules
  source, one shared skill, two thin product instruction tails, and one neutral
  engine with a shared scanner. Generated skills are identical and both use the
  same engine path. No new product settings or automatic session-start writes.
- Prior P1 (called P11 in the follow-up) is fixed. Every Git read passes
  `--no-lazy-fetch` and sets `GIT_NO_LAZY_FETCH=1`; all transport protocols are
  denied with an empty `GIT_ALLOW_PROTOCOL`. Capability is checked before object
  access; unsupported Git fails closed. Missing objects return `GIT_ERROR`.
- Regression has a positive control: unprotected real Git reproduces lazy fetch
  through a fake SSH transport. Protected status does not start a fetch child,
  proven with Trace2, and preserves source/index/HEAD/destination contents/modes.
  No real SSH, credentials, network connection or commit is used in that test.
- Shell/scanner source/target allowlists agree. The original v1 engine is
  byte-for-byte unchanged; legacy entrypoints remain explicitly documented.
- Final acceptance is limited to the Phase 1 template/isolated-test scope. Real
  product loading, other platforms, outbound history, shared mutation locks,
  approval plans, write workflows and private migration remain unverified/deferred.

# Phase 3 authorized preflight stop — 2026-09-22

- User accepted public baseline `50fabd55bd2d6d8865501ce739184937d3d0560b`
  and authorized only 3A–3D, with an immediate stop on production mismatch or
  unreliable regression validation.
- Read-only checks passed: expected private remote identity, clean `main`, six
  skill directories and payload/frontmatter schema, Claude-only settings keys,
  all nine legacy deployed files matching source bytes, settings mode equality,
  and no checked v2 source/output collisions.
- Initial dependency block resolved with subsequent explicit approval: installed
  Gitleaks 8.30.1 in the user's local bin directory from the archive matching the
  SHA-256 recorded in `secret-scanner.md`. Installed binary SHA-256:
  `ba52fb1bfabbcde42f032afad3d6e0b19dff8ed105229a16e7caa338bbc0e84f`.
  Login zsh, interactive zsh, and inherited-PATH sh resolve the installed binary
  and report exactly 8.30.1. No shell configuration or scanner requirement changed.
  `python3 tests/test-scanner.py` passed all 10 tests using the installed binary
  through the ordinary PATH, including real detections, fail-closed behavior,
  redaction, and engine integration (27.843 seconds; isolated synthetic inputs).
- New blocking mismatch: real source is contained by destination home. The
  accepted engine explicitly rejects nested roots; read-only migration engine
  initialization returns `INVALID_SOURCE` (65). Fixtures use sibling roots.
  Stopped without relocating source or changing the reference implementation.
- Stopped before baseline creation or conversion. No private source, Git state,
  Claude settings/skills/output, or Codex deployment was changed. No private
  commit/push occurred. There is no migration diff or migration rollback to run.
- 3A incomplete; 3B/3C/3D not executed; production Claude loading, statusLine,
  chezmoi behavior, sync/scanning and rollback restoration remain unverified.
  This is not a 3D PASS. See [phase-3-roadmap.md](phase-3-roadmap.md).

# Phase 3E–3G validation matrix

**3E applied; 3F/3G PASS.** The gate was accepted; separately authorized
[3H finalization](phase-3h-validation.md) is now complete. The gate evidence below
records the state before publication.

The user authorized these phases after accepting 3D. Existing Claude deployment
must remain unchanged; no private commit/push is authorized. The same public
reference baseline `15f17ca3ed349a48142f8ada8b62ca8568c1426d` is used.

| Check | Evidence | Result |
| --- | --- | --- |
| Codex expansion / baseline | Independent owner-private external package; plan adds eight sources and seven targets only | PASS / applied |
| Expansion rollback | Actual-content isolated copy expands, verifies, runs dual status and rolls back exactly | PASS |
| Production rendering | 21 actual chezmoi renders, initial empty scoped diff, both profile statuses, approved hashes/modes | PASS |
| Claude preservation | Original 3D source/target hashes and settings unchanged throughout | PASS |
| Shared authority | Both instruction bodies derive from the same shared text plus separate adapter tails; six skill pairs equal shared authority bytes; literal wrappers exact and duplicate plain sources absent | PASS |
| Codex discovery / runtime | Codex CLI 0.155.1, strict config parsing, fresh ephemeral session; actual reads of six discovery-provided user skills; global rules recognized without separately reading AGENTS.md | PASS |
| Codex sync integration | Actual status output and final model result confirm exit 0 for dual profile | PASS with normal-policy test harness |
| Claude runtime / sync | Session-only Sonnet, six successful Skill calls, one precisely allowed status command, successful model result | PASS |
| Shared rule comparison | Both actual model responses agree on language/comments, commit/signature policies, precautions, neutral engine and no automatic session-start writes | PASS |
| Changed shared source propagation | Deployed engine on isolated actual-content copy: rules and six skills reach both products, identical skill output bytes | PASS |
| Lock / drift protection | Held common source lock blocks plans for either profile; target-only conflict produces DRIFT without overwrite | PASS, isolated deterministic tests |
| Repeat workflow | Isolated repeat no-op and two operator-controlled production dual-profile no-op plan/in operations | PASS; managed state and private Git preserved |
| Private Git invariants | HEAD/index/config equal approved baseline; no private commit/push | PASS |
| Codex persistent configuration | Authorized removal of only the test trust section; exact pre-3E bytes and mode restored and rechecked | PASS |
| Final 3F / 3G acceptance | Prior actual runtime evidence plus post-restoration production validation | **PASS / stop before 3H** |

## Config restoration and final validation (2026-09-23)

The initial mandatory stop was caused by one new test-directory project trust
section. The user explicitly classified it as machine-local runtime state and
authorized only its removal. The current observed hash was checked before editing;
removing exactly that section reproduced the pre-3E config bytes and SHA-256.
Every other byte was retained and mode remains 0600. No deployment rollback ran.

Post-restoration validation passed: all 21 actual chezmoi renders match deployed
bytes; scoped diff is empty; Claude and dual-profile status use Gitleaks 8.30.1;
expansion manifest verification passes with its approved ID. Both the original
Claude 3D and expansion source/target hashes/modes, private HEAD/index/config,
and restored Codex config were checked again after validation.

The actual chezmoi file/symlink list is exactly the 21 mapped targets. Source has
39 mapped files plus only the unchanged legacy HEAD README. Exact wrapper checks
exclude dynamic imports. Codex manages only AGENTS.md, plus six shared skills under
.agents; config.toml, project trust, authentication, sessions and other runtime
state are not sources or targets. This confirms the current mapping, not a blanket
prohibition against future manual `chezmoi add` operations. Such scope changes
require separate review. OpenAI Docs describes project trust and credential storage
as separate configuration entries in the [official config reference](https://learn.chatgpt.com/docs/config-file/config-reference).

The prior successful actual Claude/Codex runtime sessions remain the functional
evidence; no new model session was launched for this local trust-entry removal.
Shared rule bodies, all six skill pairs, discovery paths and exact deployed
configuration are unchanged. Existing isolated propagation/locking/drift/rollback
and production no-op plan/in evidence therefore remains applicable; those mutation
scenarios were not rerun. Static checks are not relabeled as new runtime tests.

Private evidence: `review/config-restoration.json`, `review/final-validation.json`
and `review/final-*.log` in the existing external package. Validation harness
corrections (Python 3.9 lacks tomllib; legacy README inventory; verify requires
--approve) changed no production behavior and are not counted as product failures.

## Harness and evidence boundaries

The initial Codex session was given a read-only sandbox and status failed to create
its `/tmp` scratch directory. That status run is a failure, not PASS. The corrected
session used the current environment's workspace-write policy, rooted at the
external test directory, with approval set to never and no additional source/HOME
write roots requested. No persistent config override was supplied. Its actual
recorded commands read skills and run status; both the command output and final
result confirm success. The persistent config discrepancy was subsequently resolved by the explicitly
authorized targeted restoration described above.

Codex discovery expectations were checked against official
[AGENTS.md guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
and [skill discovery documentation](https://learn.chatgpt.com/docs/build-skills).
Runtime evidence, not those documents or static hashes, establishes that the
installed CLI actually loaded this deployment.

The two production no-op plan/in checks were operator-controlled, not model-issued
write actions. Shared mutation, conflict and lock probes ran only on the external
copy. No deployment/database/project actions inside skills were executed. No new
claim is made for MCP/plugin integration, every terminal UI or arbitrary concurrent
uncooperative processes.

## Diff, rollback and stop

Incremental private source diff for 3E: one Codex adapter source, one Codex
instruction wrapper and six agent skill wrappers. Incremental outputs: Codex
AGENTS.md and six `.agents/skills` files. Existing Claude/shared bytes are unchanged.

Owner-private package:
`/Users/Shared/ai-agent-migration-<user>/phase3-20260922-221058/phase3efg/`.
It contains `baseline/`, `ROLLBACK.md`, `codex-config.before.toml`,
`codex-config.observed.toml`, and `review/phase3efg-result.json` plus runtime logs.
Do not publish these payloads.

The expansion rollback ID is
`ec09fbd26f0a7924868a3c285af290a58234f15109c66f12ac5e6f222457223a`.
Use its `claude-codex` rollback command to return to the Claude-only 3D deployment
only after approval. For full rollback, undo expansion first, then the original
Claude migration. Config is outside the engine mapping: adapter rollback does
**not** manage Codex config. The separately authorized trust-entry restoration is
complete; no deployment rollback was performed.

Keep the current deployment with 3F/3G PASS and stop for user review. Do not execute 3H or commit/
push private dotfiles.

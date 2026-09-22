# Phase 2.6 — Migration Readiness

This is public implementation and **synthetic fixture acceptance**, not production
migration. The private source is never a test input. Phase 2.6 review must finish
and stop; it does not authorize Phase 3A or lift the mandatory Phase 3D gate.
See the persistent [Phase 3 roadmap](phase-3-roadmap.md).

## 2.6A: staged profiles

Every `status`, `plan`, `in` and `push` accepts an explicit profile:

| Profile | Source files | Generated targets | Deployment |
| --- | --- | --- | --- |
| `claude` | 31 | 14 | Claude instructions, six skills, compatibility entrypoint, settings and neutral engine/scanner/converter |
| `claude-codex` | 39 | 21 | The above plus Codex instructions and six agent skills |

The compatibility default is `claude-codex`. Always pass `--profile claude` during
3A–3D. The Claude profile does not require, snapshot, render or write Codex sources,
outputs, home overrides or `AGENTS.override.md`. Existing Codex runtime data stays
outside its scope. A missing Codex output is not an error in this profile.

`scan-secrets.py` owns the static profile mappings and literal wrapper schema.
Both shell status and Python write/conversion engines consume these definitions.
There is no arbitrary-path manifest that widens scanning or deployment. The scanner
accepts the union of known profile and legacy snapshot paths, while each operation
selects only its approved profile. The selected profile is part of the plan ID.

A Claude-only conversion creates only Claude source wrappers. Ordinary chezmoi
render/apply therefore does not need an ignore-rule workaround to suppress Codex.
Later expansion is a distinct `enable-codex` plan with its own backup and approval;
it refuses existing Codex instruction/skill collisions and preserves Claude outputs.
It does not enable itself after a successful Claude gate. Selecting the dual profile
alone cannot bootstrap missing outputs through normal `in` or `push`.

## 2.6B: six skills and Claude-only settings

The mapping includes `dotfiles-sync`, `d3-component`, `deploy`, `excel-import`,
`review`, and `supabase-migrate`. Each has one authoritative shared source and a
fixed Claude template wrapper; the dual profile adds a second generated wrapper under
`.agents/skills`. All six participate in renderer validation, scanner admission,
status, candidate trees and outbound history checks.

Public examples of the five added skills are newly written generic guidance, not
copies of private content. Legacy conversion replaces those example bytes with the
existing five `SKILL.md` files **verbatim in the generated outputs**. Only literal template-opener escapes may
be added to the shared authority representation. Their project-specific instructions
are retained rather than generalized during migration. Any extra skill or attached
payload beyond the accepted six-skill layout stops conversion for review.

`dot_claude/settings.json` stays in place and remains Claude-only. It is now in the
scanned/synchronized profile and renders directly to `.claude/settings.json`. The
legacy inventory contract expects basic skill frontmatter with only `name` and
`description`, and settings with the three keys `model`, `statusLine`, and `tui`;
missing/extra keys, invalid JSON or unsupported settings permissions stop conversion.
The converter does not execute statusLine commands or reinterpret their contents.
Its output bytes and mode must equal the existing deployed settings. The public
`{}` settings example is not a replacement for personal configuration.

The legacy sync script is backed up and replaced with a fixed template for one
small forwarding script. It calls only the neutral v2 engine and forwards explicit
arguments. Missing engine/approval fails; it never falls back to legacy re-add,
mutable status, automatic session-start `in`, or unscanned push. These old automatic
writes are intentionally retired, not preserved as required behavior.

## 2.6C: offline baseline, conversion and rollback

The converter is reached through `sync.sh migration`. It performs **no fetch,
commit, push, Git staging, ref update or production chezmoi execution**. It shares
the source's sync lock and takes the ordinary Git index lock during apply/rollback.
A committed legacy HEAD is sufficient; the index must match HEAD. Unstaged scoped
edits are backed up as they are, provided deployed legacy bytes agree. Unrelated
files and runtime state are not read as payloads or included in the backup.

Use an absolute, private backup directory outside source/destination and their Git
scope. The parent must already exist; the backup directory must be new. The
reference is the reviewed public `examples/chezmoi` tree. No private source is
auto-discovered, and no new dependency is installed.

### Explicit instruction mapping

Prepare an owner-private `rules-map.json` outside the public repository. Its
segments, in order, must concatenate to **every original byte** of the legacy
UTF-8 `CLAUDE.md`:

```json
{
  "schema": 1,
  "segments": [
    {"kind": "shared", "text": "Original common rules, including their exact newlines.\n"},
    {"kind": "claude", "text": "Original Claude-specific rules.\n"},
    {"kind": "retire-sync", "text": "Original dotfiles-sync automatic trigger section.\n"}
  ]
}
```

`shared` segments go to shared instructions; `claude` segments stay in the Claude
adapter before the reference's thin adapter tail. Only explicitly marked
`retire-sync` segments are omitted from generated instructions, and each must
identify dotfiles-sync. Their originals remain in the rollback package. The entire
legacy document, including retired text, is scanned before a plan is emitted.

The byte check prevents accidental omissions; it cannot prove the semantic quality
of the classification. A reviewer must confirm that retired segments contain only
the obsolete sync triggers, that retained rules remain meaningful after grouping,
and that any private note is kept in the proper private/Claude scope. Do not invent
replacement user preferences or treat a matching hash as semantic approval.
Literal `{{` in JSX/examples is encoded as the single static escape `{{ "{{" }}`
in shared source. Fixed wrappers call only named templates. The validator permits
that exact literal escape and rejects every other opening template action, while
the Python renderer decodes it without evaluating Go. Actual chezmoi fixtures prove
that the original text is reproduced, including strings that resemble dynamic
commands, without executing them. When editing shared source later, preserve this
representation; arbitrary Go actions still fail before writes. Both raw source and
decoded generated snapshots (including historical commits) are scanned. Alternate/conflicting chezmoi encodings and partial v2 installations
are refused rather than merged heuristically; see [chezmoi source attributes](https://www.chezmoi.io/reference/source-state-attributes/).

### Baseline and apply

The following commands are a procedure for a future **authorized** migration,
not instructions to run against a private source during Phase 2.6:

```sh
sh "$reference_engine" migration plan --mode legacy --profile claude \
  --source "$source" --destination "$destination" --branch main \
  --reference "$reviewed_reference" --rules-map "$rules_map" --backup "$backup"

# Review the manifest and actual old/new content; then use its MIGRATION_ID.
sh "$reference_engine" migration apply --profile claude \
  --source "$source" --destination "$destination" --branch main \
  --backup "$backup" --approve "$migration_id"

sh "$reference_engine" migration verify --profile claude \
  --source "$source" --destination "$destination" --branch main \
  --backup "$backup" --approve "$migration_id"
```

`plan` creates an owner-only backup package: `manifest.json`, content-addressed
`blobs/` for exact old/new scoped files, and `index.before`. The manifest binds roots,
profile, Git HEAD/ref/index/config hashes, contents, modes, existence/deletion,
retired-rule identity and trusted engine/scanner hashes. `MIGRATION_ID` is SHA-256
of the manifest. Apply approval expires after one hour; rollback does not expire.
The package contains private data and must never be committed or uploaded.

Apply rechecks the complete scoped state, Git baseline, tool identity, inventory
layout and scanner results before writing. It removes only approved old plain
sources, then creates their exact templates, avoiding duplicate targets. It moves
five skills into the shared authority, preserves settings and existing Git metadata
files, and appends target exclusions to `.chezmoiignore` without deleting its prior
bytes. It applies only the approved generated files. It never runs legacy scripts,
source hooks, template commands, externals or arbitrary source-local configuration.

Conversion has no dependency on a v2 layout in the old HEAD. It neither fabricates
a migration commit to satisfy the engine nor expands normal push's history rules.
The new files remain unstaged for the later separately approved publication phase.

### Regression before the final migration commit

Deployed `status --profile claude` already works with a legacy HEAD. To test/apply
reviewed source edits locally while the migration is still uncommitted:

```sh
sh "$deployed_engine" plan --operation in --offline --profile claude \
  --source "$source" --destination "$destination" --branch main --plan "$plan" \
  --baseline "$backup" --baseline-id "$migration_id"

sh "$deployed_engine" in --offline --profile claude \
  --source "$source" --destination "$destination" --branch main --plan "$plan" \
  --baseline "$backup" --baseline-id "$migration_id" --approve "$plan_id"
```

The baseline's approved, hash-verified v2 snapshot provides the comparison render;
its Git identity must still match the unchanged legacy HEAD/index/config. The
current candidate and outputs are scanned again. `--offline` is accepted only for
`in`, with no remote option. It writes no Git objects/ref/reflog and preserves the
real index. It cannot be combined with push or used to bypass outbound history.
After a separately reviewed final migration commit/publication under 3H, use normal
profile-aware sync without the bootstrap baseline. The initial migration publication
is a distinct review of its full conversion diff/history; normal push intentionally
does not auto-publish deleted legacy paths outside the normal v2 profile.

### Later Codex expansion and reverse-order rollback

Only after explicit 3E authorization, create a fresh plan with
`migration plan --mode enable-codex --profile claude-codex`, the same source,
destination, branch and reviewed reference, and a **new** backup directory. Omit
`--rules-map`. Apply using this plan's ID and the dual profile. Existing Claude source
and output bytes remain unchanged; only missing Codex authority/wrappers/targets are
added. During an unpublished migration, this newer package can serve as the dual
profile's offline baseline.

For rollback, use the profile and ID belonging to the package:

```sh
sh "$reference_engine" migration rollback --profile claude \
  --source "$source" --destination "$destination" --branch main \
  --backup "$backup" --approve "$migration_id"
```

Rollback checks all manifest paths before making any change. Only exact before/after
states are accepted; a later edited file blocks rollback with `RECOVERY_REQUIRED`.
Existing files regain their recorded bytes/modes; new files are removed only if
they still match the approved new value. Created directories are removed only when
empty and still match the recorded device/inode ownership. Changed Git baseline
blocks automatic rollback; refs/index are never reset. Keep a trusted copy of the
reference engine outside the targets so rollback does not depend on files it removes.

After multiple stages, roll back **in reverse order**: Codex expansion first, then
Claude conversion. The original legacy script and skill are restored from backup;
no permanent duplicate legacy engine is installed alongside v2.

An ordinary apply failure uses the same guarded rollback. Partial/uncertain recovery
leaves `.git/ai-agent-migration-transaction/` pointing to the backup and ID. Stop
other writers, inspect the owner/manifest and preserve any later edits. A killed
process may leave stale sync/index locks: verify it is gone before manually removing
only those stale locks, then invoke rollback with the recorded package. Never delete
an active lock, whole agent directory or backup. Multi-file replacement is recoverable,
not an atomic filesystem-wide/power-loss guarantee.

New result classes use existing exit categories: inventory/collision/transition
blocks 65/66, stale/tampered/expired baseline 68, scan/dependency failures 67/69/70,
unsafe rollback 72 and shared lock 73. Raw tool errors/secret values are withheld.
A successful `migration verify` verifies bytes/modes and Git identity, not product
loading or semantic correctness of an instruction map.

## 2.6D/E: fixture and review gate

`tests/test-migration.py` constructs fake legacy rules, six skills, Claude-only
settings, a non-executable-in-practice legacy sync sentinel and local Git history.
It uses disposable source/destination/home/config/cache/state directories and
synthetic runtime-state sentinels. No private production content is read or copied.
It simulates:

- 3A baseline creation, hash integrity, index preservation and rollback evidence.
- 3B/C literal shared-source conversion, rule/skill/settings preservation, Claude-only
  cutover and forwarding through the v2 entrypoint without legacy fallback.
- 3D actual chezmoi render/apply/diff/idempotence, deployed offline status/in, each
  skill's edits/scanning, and exact legacy restoration after the gate.
- A separate later-profile fixture proving Codex can be added afterward without
  changing Claude, and that both stages roll back in reverse order.
- Drift, scanner/secret failures, stale plans/Git state, unknown inventory/settings,
  aliases, collisions, symlinks, locks, tampered backups, partial apply failure and
  later-edit preservation. Pinned real Gitleaks checks all five new skill paths.

The existing scanner, offline-Git, render/status and write suites remain regression
gates. Tests may create commits and push to **temporary local bare fixtures only**;
the converter itself has no network/commit/push operation.

A PASS is limited to this public code and macOS fixture contract. Real Claude loading,
actual statusLine dependencies, private inventory equivalence, platform differences,
SSH/HTTPS authentication and production rollback remain Phase 3 verification tasks.
Do not call these fixture assertions a production Claude regression pass. The next
step is a user-authorized 3A preflight, not automatic migration.

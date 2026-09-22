# Claude Code + Codex shared configuration — experimental v2

Phase 1 provides an opt-in template and read-only status engine. It is **not a
replacement for an installed v1 workflow**. No home-directory deployment, private
dotfiles access, remote access, commit, or push is implied by developing this repo.

## One source, multiple outputs

Copying or merging `examples/chezmoi/` into a private source is a later, separately
reviewed migration. Do not initialize chezmoi against this public repository.

| Authority within the v2 source | Generated destination |
| --- | --- |
| `.chezmoitemplates/ai/shared/instructions.md` + `adapters/claude.md` | `.claude/CLAUDE.md` |
| Same shared instructions + `adapters/codex.md` | `.codex/AGENTS.md` |
| `shared/skills/dotfiles-sync/SKILL.md` | `.claude/skills/dotfiles-sync/SKILL.md` and `.agents/skills/dotfiles-sync/SKILL.md` |
| `shared/scripts/sync.sh` | `.config/ai-agent/bin/sync.sh` |
| `shared/scripts/scan-secrets.py` + `gitleaks-rules.json` | `.config/ai-agent/bin/scan-secrets.py` + `gitleaks-rules.json` |

The paths in the last three rows are relative to `.chezmoitemplates/ai/`.
Generated instructions carry an editing notice. Skill frontmatter and the shell
shebang remain the first bytes of their respective outputs. No settings.json,
config.toml, MCP configuration, hooks, subagents or automatic memory are migrated.

Edit the shared source, preview its outputs, review the changes, then apply only
in the authorized destination. `chezmoi re-add` does not overwrite templates;
editing a generated file produces drift, not a source update. Preserve such edits
and move their intent into the shared source before any deployment.

Wrappers use raw `include` instead of `template`. However, chezmoi still parses
files under `.chezmoitemplates`. Phase 1 therefore rejects opening Go-template
delimiters in shared text/scripts rather than attempting arbitrary escaping or
dynamic evaluation. The engine constructs its own wrapper delimiters at runtime.
The seven wrappers have an exact, checked format. Extending that format requires
an engine/schema change and new tests.

## Read-only status contract

Prerequisites: POSIX sh, Git, chezmoi, standard Unix utilities, Python 3.9+
(standard library only), and Gitleaks **8.30.1** on PATH. The bundled adapter
requires that exact version. No dependency is downloaded or installed automatically.
Git must support `--no-lazy-fetch`; the engine probes that capability before any
object reads and fails with `MISSING_DEPENDENCY` if unsupported.

For an **already authorized isolated fixture**, call the source engine:

```sh
sh examples/chezmoi/.chezmoitemplates/ai/shared/scripts/sync.sh status \
  --source "$fixture_source" --destination "$fixture_destination"
```

All arguments must be absolute paths. Source and destination must exist and must
not overlap. The source must be the root of a regular Git checkout containing
the complete v2 layout; linked Git worktrees are not supported yet. This engine
does not call `chezmoi source-path` or default to the current project or private
source. Source identity here means the explicitly supplied, validated checkout;
remote/branch approval and private-source discovery belong to Phase 2.

Status inspects 17 fixed source files: seven shared/adapter files, seven wrappers,
and `.chezmoiignore`, `.gitignore`, `.gitattributes`. It compares raw working bytes
and executable bits with index/HEAD blobs, without clean filters or diff drivers.
An unborn branch is supported. Source changes are reported separately as staged
and working changes. Unrelated staged/untracked paths remain untouched and are
not enumerated or scanned.

The seven generated destinations are compared against a render of the restricted
v2 profile. Missing files, byte differences, and a missing executable bit on the
engine or scanner adapter produce drift. Symlinks in scoped relative paths, unsupported Git entry
types, missing required source files, or conflicts cause a nonzero error.

For rendering, the engine copies only approved shared files and verified wrappers
into private temporary storage. It supplies its own empty config, home, cache,
destination and persistent-state paths and clears inherited environment variables.
It never executes source scripts, hooks, externals or arbitrary source templates.
Source metadata files are scanned and compared, but **not interpreted for this
render**: this is a fixed-profile preview, not a simulation of an arbitrary
existing chezmoi installation. It cannot establish compatibility with custom
ignore rules, config, data or templates in a private source.

No re-add, stage, fetch, apply, commit or push occurs. The engine only writes
private temporary snapshots, removes them on normal exit/signals, and reports
fixed relative paths and labels. It does not print raw diffs, remote URLs, scanner
stdout/stderr, or underlying tool errors that might contain sensitive data.
Snapshots are point-in-time observations, not an atomic plan or push approval.
No shared mutation lock is needed in Phase 1; concurrent edits can affect the
observation, so all write workflows remain unsupported.

All Git calls set `GIT_NO_LAZY_FETCH=1` and pass `--no-lazy-fetch`, so partial
clones never fetch missing objects on demand. An empty `GIT_ALLOW_PROTOCOL` and
`GIT_PROTOCOL_FROM_USER=0` additionally deny transports, including protocols
explicitly allowed in source-local config. These values override inherited
environment settings. Missing index/HEAD blobs or HEAD trees return a nonzero
`GIT_ERROR` without repairing the checkout. A partial clone whose scoped objects
are already local remains readable. See [Git's documented controls](https://git-scm.com/docs/git).

## Scanner interface and limits

Status defaults to the sibling `scan-secrets.py` adapter and its pinned rule-ID
registry. It invokes Gitleaks 8.30.1 with built-in rules, no caller configuration,
no baseline/ignore suppressions, and inline `gitleaks:allow` comments disabled.
Only approved snapshots are read; reports show fixed relative paths, known rule
IDs and positive line numbers. Secret values and raw tool logs never reach normal
output. Full contract, integrity information and limitations are in
[secret-scanner.md](secret-scanner.md).

`--scanner` remains an optional trusted executable override for reviewed adapters
and isolated tests. The protocol now requires two arguments: `SNAPSHOT REPORT`.
The adapter must create a new schema-1 JSON report and return 0 (clean), 10 (secret),
69 (missing dependency), or 70 (failure). Exit status and report must agree. The
bundled validator validates the whole report before emitting any finding.
Missing/malformed reports, extra fields, unknown paths or rule IDs block output.
The old exit-code-only interface is no longer accepted.

The adapter and binary are trusted executable code, not sandboxed by the engine.
Do not replace them with always-successful scripts. Missing tools, wrong versions,
scan failures and invalid reports block normal output even for unchanged files.
The marker-only scanner in `tests/helpers.sh` is a protocol test double, not the
production scanner. Real Gitleaks tests are in `tests/test-scanner.py`.

Status does not scan unrelated files or outbound history and is never a statement
that the whole private repository is safe to push. `.chezmoiignore` matches target
paths; `.gitignore` matches source paths. Neither removes already tracked files
or historical secrets. Unknown paths are outside the engine's fixed scope.

| Result | Exit | Meaning |
| --- | --- | --- |
| `NO_CHANGES` | 0 | Scoped source and generated outputs match |
| `OK` | 0 | Scoped source changed; deployed output matches render |
| `DRIFT` | 2 | Generated destination differs; no apply performed |
| `USAGE`, `UNSUPPORTED` | 64 | Bad invocation or `plan`/`in`/`push` |
| `INVALID_SOURCE`, `UNSUPPORTED_TEMPLATE`, `UNSUPPORTED_HOME`, `BLOCKED_OVERRIDE` | 65 | Unsupported or unsafe input/layout |
| `BLOCKED_CONFLICT` | 66 | Scoped index contains unmerged entries |
| `BLOCKED_SECRET` | 67 | Scanner found a match; no normal report |
| `MISSING_DEPENDENCY` | 69 | Required command or executable scanner missing |
| `IO_ERROR`, `GIT_ERROR`, `RENDER_ERROR`, `SCANNER_ERROR` | 70 | Check failed; not a clean result |

Errors without an explicit classification (for example an unexpected shell I/O
failure) still exit nonzero; callers must treat any nonzero unrecognized result
as a failure. `DRIFT` is an expected nonzero status, not permission to overwrite.

Phase 1 supports default destination-relative agent paths only. Nonmatching
`CODEX_HOME`, `CLAUDE_CONFIG_DIR`, or `AI_AGENT_HOME` are rejected. An existing
`AGENTS.override.md` also blocks status without reading its content. These checks
cannot detect product configuration supplied elsewhere; real product discovery
and load verification remain part of a later pilot.

## Legacy compatibility and migration gates

`examples/dotfiles-sync/sync.sh` remains unchanged. Its session-start `in`, mutable
`status`, and `push` are still v1 behavior, including the known safety gaps.
README examples clearly label them. Do not install the v2 skill over the same name
or turn the old script into a wrapper during Phase 1: that would replace `in` and
`push` with unsupported operations and break the existing workflow.

The old ignore example now excludes `.claude.json` and `settings.local.json`, and
the old setup guide no longer asks to manage local settings. These repo edits do
not change an installed source. Later merge ignore rules deliberately; do not
overwrite private ignore files or automatically remove existing tracked files.

Phase 2 still needs plan snapshots, shared locks,
controlled pull/apply, content approval, preserved index state, outbound-history
validation, and explicit remote/branch verification. Never substitute v1 calls
when v2 refuses an operation.

Before an authorized local pilot:

1. Pause modifying automatic sync triggers; inventory active homes, overrides,
   duplicate skills, existing rules and source encodings without reading credentials.
2. Produce an exact merge plan and backup manifest: path, prior existence, type,
   permissions and hash. Store backups locally outside Git and the sync scope.
3. Preserve existing preferences, settings, hooks and skills. Preview every output;
   a generic generated CLAUDE.md must not replace personal instructions wholesale.
4. Deploy the neutral engine before switching callers. Only after safe write
   commands exist should the legacy path become a thin wrapper; missing new engine
   must fail, never fall back to the old implementation.
5. Verify loaded instructions/skills in new Claude and Codex IDE sessions. Use a
   temporary distinct skill name if needed. Test a second platform only afterward.

Rollback has three separate scopes: public template changes, private source changes,
and deployed files. A Git revert of the public template does not restore either of
the others. Restore only manifest-listed local files from backup; remove newly
created outputs only if they have not subsequently changed. Restore the previous
skill/trigger together. Never delete entire agent directories or use `exact_` on
them. Keep unrelated files and machine-local state intact.

## Verification

From this repository, run:

```sh
sh tests/test-render.sh
sh tests/test-status.sh
python3 tests/test-scanner.py  # requires Gitleaks 8.30.1 on PATH; never silently skips
python3 tests/test-offline-status.py
```

Tests create disposable source/destination/home/config/cache/state directories.
They clear inherited Git, SSH, XDG and agent settings; no real remote or login is used.
Fixture Git init/add are local only; **no commit is created**. HEAD behavior uses
a Git shim backed by real index blobs, so it is not a real committed-history test.
Actual chezmoi apply runs only against fixture paths. Never replace those paths
with a personal home or source to run these tests.

The offline regression suite uses real Git, partial-clone config, missing object
IDs, Trace2 and a fake SSH command. Its unprotected positive control deliberately
triggers a fetch to the fake transport (no network); protected status must show
neither a fetch child nor transport invocation, with Git/source/destination state
unchanged. HEAD resolution is simulated without creating commits; actual object
reads run through real Git. Older-Git capability failure is also tested.

Synthetic-fixture success does not prove detection of every secret, product loading,
real-history safety, Windows compatibility, or production deployment readiness.

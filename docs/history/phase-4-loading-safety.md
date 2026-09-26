# Phase 4 loading barrier — native safety finding

Historical finding. The user accepted it and prohibited lifecycle-callback leases.
See the subsequent [callback-free design and native race tests](phase-4-consistent-loading.md).

2026-09-24: **STOP / NOT QUALIFIED**. The latest authorization covers consecutive
4B–4G isolated validation, but requires stopping for production safety or existing
CLI behavior regressions. No production launcher, private source, tools or
credentials were changed. No commit/push or 4H deployment occurred.

## Concrete finding

The current supervisor retains a reader lease for the entire CLI process. This
still violates the required short loading barrier and blocks session-local v2
writes. Replacing that lease with a `SessionStart` acknowledgement has a concrete
compatibility problem, not merely an unimplemented callback:

| Native Claude 2.1.278 invocation in disposable HOME | Exit | SessionStart callback | stdout/stderr |
| --- | --- | --- | --- |
| `--init-only` | 0 | Executed | Empty |
| `--init-only --settings '{"disableAllHooks":true}'` | 0 | Not executed | Empty |

Both cases used the same fixture user settings and hook. Settings bytes remained
unchanged. The second invocation is a supported user override, not a malformed CLI
invocation. [Claude hook settings](https://code.claude.com/docs/en/hooks#disable-or-remove-hooks)
document that override. Thus a hook-only acknowledgement is not available for all
ordinary argument/settings combinations that the launcher must preserve.

Further, the [Claude hook reference](https://code.claude.com/docs/en/hooks#sessionstart-decision-control)
allows a SessionStart result to request skill rescanning after the hooks finish.
An individual hook completion therefore does not establish completion of all
initial skill loading. This latter observation is documentation evidence, not a
native timing measurement.

Codex also supports disabling hooks and requires review of non-managed hooks.
These are [documented controls](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks),
not something the bootstrap may silently override. No native Codex callback timing
test or hook-trust modification was performed in this follow-up.

## Reproduction and limits

```sh
python3 tests/test-native-loading.py --claude /absolute/path/to/native/claude-2.1.278
```

The test requires an explicitly supplied native binary and checks its version.
The observed executable SHA-256 was
`bd245662fb8a0e321b3bf133e930371d6563c387527885f30b2613aef3ba14d6`.
It creates a disposable HOME/config/cwd, passes a fresh environment with no
credential variables, disables auto-update/nonessential traffic, and runs
`--init-only`; no model request, login or production configuration is involved.
Only booleans, exit codes, version/hash and output sizes are reported. Raw product
output is never emitted. The fixture is removed after the test.

The two-case negative qualification passed. **It is not a successful model session,
statusLine qualification, launch-sync qualification, or a 4F/4G PASS.** It proves a
candidate SessionStart-only approach cannot cover the CLI contract. It does not
prove that every possible loading architecture is impossible.

## Safety decision and remaining work

Do not release a reader lease merely on spawn, an elapsed timer, or one unqualified
hook callback: another writer could modify the mapped targets during loading.
Do not silently force hooks, bypass hook trust, change user flags or hold the
lease through a long session as a substitute for the accepted requirement.

The engine/launcher was left unchanged pending a loading boundary that is both
provable and compatible with native settings overrides. A next implementation
must either qualify a product-supported completion boundary covering the allowed
invocations, or design and review an immutable managed-generation loading path
that preserves credential location, CLI configuration precedence and discovery.
No immutable-generation implementation or qualification is claimed here.

| Requested work | Current outcome |
| --- | --- |
| Short reader/loading barrier | Unresolved; native compatibility/safety finding above |
| Fresh macOS dependency installation and PATH | Not completed; previous prerequisite-only limitations remain |
| Launcher Claude statusLine qualification | Not completed; existing refusal remains |
| Full consecutive 4B–4G validation and overall review | Not completed; stopped at safety finding |
| Production/private changes, commit/push, 4H | Not performed |

The earlier 24 bootstrap fixture passes remain historical evidence only; they do
not resolve this finding or constitute a new full-suite run.

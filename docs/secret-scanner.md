# Secret scanner: Gitleaks 8.30.1

The v2 status and approved write engines use the bundled `scan-secrets.py` adapter.
Private migration remains paused. The v1 engine remains unchanged, including its
earlier scan limitations. Write behavior is documented in [sync-v2.md](sync-v2.md).

## Dependencies and integrity

- Python 3.9+ standard library; no pip packages.
- Gitleaks **8.30.1**, found on PATH. Other versions fail closed; no automatic
  download, upgrade, telemetry, credential lookup or online secret validation.
- The scanner executes the pinned release's built-in rule set, currently 222
  rule IDs. `gitleaks-rules.json` records these IDs, the upstream config URL and
  SHA-256. This registry validates report IDs; it is not an alternate detector.
- The engine, adapter, registry and Gitleaks binary are trusted code. A version
  string is not an authenticity check: verify the release archive before use.

Official sources:

- [Gitleaks v8.30.1 release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)
- [Pinned command flags](https://github.com/gitleaks/gitleaks/blob/v8.30.1/cmd/root.go)
- [Pinned default rules](https://github.com/gitleaks/gitleaks/blob/v8.30.1/config/gitleaks.toml)

The actual integration tests used the official macOS ARM64 archive:

```text
gitleaks_8.30.1_darwin_arm64.tar.gz
SHA-256: b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5
```

It was downloaded with explicit network approval, verified before extraction,
and used only from a temporary directory. No global tool installation was made.
For a different platform, obtain that platform's archive and checksum from the
same release; do not reuse this checksum. Platform compatibility beyond macOS
ARM64 has not been tested here.

## Detection and data handling

The adapter receives the engine's private snapshot, never a personal source or
home discovered on its own. It accepts only the engine's known source/index/HEAD
and rendered/deployed locations. All entries must be readable regular UTF-8 text
files, at most 8 MiB each, without NUL bytes or symlinks. Unknown paths, empty
snapshots, oversized/binary/invalid text or I/O failures block the scan rather
than letting Gitleaks silently skip them.

Each file is copied into an owner-only temporary directory under a numeric `.txt`
name. This avoids source-controlled config/ignore files and built-in filename
allowlists bypassing a scan. Findings map back to known snapshot paths, including
paths containing spaces or Chinese in the parent directories.

Gitleaks runs offline in `dir` mode with:

- An explicitly generated config extending all built-in defaults.
- A cleared environment and isolated HOME/current directory.
- An explicit empty ignore file; no baseline; `--ignore-gitleaks-allow`.
- `--redact=100`, no banner/color, JSON report, and no raw output forwarded.
- No file-size skipping, decode depth 5, archive depth 0, Gitleaks timeout 90s,
  and an outer subprocess timeout 100s (version check 10s).

Any unexpected stdout/stderr, unexpected exit code, missing/truncated/oversized
report, unknown finding path/rule ID or inconsistent finding count fails closed.
Only file, rule ID and positive line number survive normalization; Match, Secret,
Description, Fingerprint and all other raw report fields are never forwarded.

Temporary raw reports and copies have owner-only permissions and are removed on
normal completion and ordinary termination. SIGKILL/power loss cannot run cleanup;
this is not secure erasure or an OS sandbox. Review a binary/adapter before use.

## Adapter protocol

Normal invocation: `scan-secrets.py SNAPSHOT REPORT`. Paths are absolute; REPORT
must not already exist and must be outside SNAPSHOT. It creates a mode-0600 JSON
report. Raw stdout/stderr are not part of the protocol.

```json
{"schema":1,"status":"clean","findings":[]}
```

For a match, `status` is `secret` and findings contain exactly `file`, `rule`,
`line`. The file must be in the engine's fixed snapshot mapping, the rule must
be one of the pinned IDs, and line must be a positive integer. No extra fields,
duplicate keys, mismatched statuses or partial reports are accepted.

| Adapter status | Adapter exit | Engine exit |
| --- | --- | --- |
| clean | 0 | 0, or 2 if deployment drift exists |
| secret | 10 | 67 (`BLOCKED_SECRET`) |
| missing | 69 | 69 (`MISSING_DEPENDENCY`) |
| error | 70 | 70 (`SCANNER_ERROR`) |

The engine runs its bundled validator (`--display-report`) independently of an
optional custom adapter. It validates the **entire** document before emitting any
finding; a valid first finding cannot precede an invalid later finding in output.
Only validated `FINDING: snapshot/path:line rule=id` lines appear before a block.
An invalid/missing report always maps to exit 70. Normal SOURCE/TARGET output is
withheld until scanning succeeds.

The optional `--scanner` override remains for reviewed adapters and test doubles.
The new structured report is mandatory: legacy exit-code-only adapters fail.
An intentionally dishonest adapter returning a valid clean report is outside
this trust boundary; the validator cannot prove that another program scanned.

## Tests

With verified Gitleaks 8.30.1 on PATH:

```sh
python3 tests/test-scanner.py
sh tests/test-render.sh
sh tests/test-status.sh
```

The real-scanner suite refuses to run when Gitleaks is missing; it does not turn
a missing dependency into a skipped/passed test. Test values are deterministic,
non-issued synthetic strings generated in temporary fixtures, never real tokens.
Tests do not print values or use real authentication/network access.

Coverage includes clean content; GitHub PAT, generic API-key and private-key
formats; all five snapshot scopes; inherited config/ignore and inline suppression;
missing tool/wrong version; scanner errors/timeout; malformed, inconsistent and
unsafe reports; unreadable, invalid text, oversized and symlink inputs; and engine
redaction/blocking with secrets only in working source, index, HEAD or deployment.
The deployed adapter path is exercised through actual isolated chezmoi rendering.
Source, Git index/HEAD/config and destination hashes/modes remain unchanged.

This scanner suite uses a HEAD shim backed by real blob objects and creates no
commits. The separate `tests/test-write.py` suite exercises real local histories,
approval, outbound secret detection and local bare-remote pushes.

## Remaining limits

Gitleaks is pattern/entropy based. Built-in content allowlists remain active and
not every possible secret is detectable. Decoder depth is finite; archives are
not supported, and text admission is not a general archive classifier. Findings
are suspicions requiring review, not verification that a credential is live.

Only the fixed v2 scope is scanned. A clean result does not certify an entire
private repository or its history. The v2 write helper now scans approved candidates and all outbound commits,
including commit metadata, while preserving staged work by refusing it. See
[sync-v2.md](sync-v2.md) and `tests/test-write.py`. No private migration or real-product
deployment is included in this scanner work.

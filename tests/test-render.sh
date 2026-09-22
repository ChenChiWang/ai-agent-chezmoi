#!/bin/sh
. "$(dirname "$0")/helpers.sh"
cm apply --force
cmp "$dst/.claude/skills/dotfiles-sync/SKILL.md" "$dst/.agents/skills/dotfiles-sync/SKILL.md"
cmp "$src/.chezmoitemplates/ai/shared/scripts/sync.sh" "$dst/.config/ai-agent/bin/sync.sh"
[ -x "$dst/.config/ai-agent/bin/sync.sh" ]
[ -x "$dst/.config/ai-agent/bin/scan-secrets.py" ]
cmp "$src/.chezmoitemplates/ai/shared/scripts/scan-secrets.py" "$dst/.config/ai-agent/bin/scan-secrets.py"
cmp "$src/.chezmoitemplates/ai/shared/scripts/gitleaks-rules.json" "$dst/.config/ai-agent/bin/gitleaks-rules.json"
[ "$(head -n 1 "$dst/.agents/skills/dotfiles-sync/SKILL.md")" = --- ]
sh -n "$dst/.config/ai-agent/bin/sync.sh"
snapshot > "$test_root/before"
cm apply --force
snapshot > "$test_root/after"
cmp "$test_root/before" "$test_root/after"
printf '\nShared edit from one source.\n' >> "$src/.chezmoitemplates/ai/shared/instructions.md"
cm apply --force
assert_contains "$dst/.claude/CLAUDE.md" 'Shared edit from one source.'
assert_contains "$dst/.codex/AGENTS.md" 'Shared edit from one source.'
isolated python3 - "$dst" "$engine" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
a = (p/'.claude/CLAUDE.md').read_text()
b = (p/'.codex/AGENTS.md').read_text()
assert a.split('## Claude Code')[0] == b.split('## Codex')[0]
assert '## Codex' not in a and '## Claude Code' not in b
for f in p.rglob('*'):
    if f.is_file(): assert b'\r' not in f.read_bytes()
import runpy
api = runpy.run_path(str(Path(sys.argv[2]).with_name('scan-secrets.py')))
assert {str(f.relative_to(p)) for f in p.rglob('*') if f.is_file()} == set(api['TARGET_FILES'])
for skill in api['SKILLS']:
    assert (p/('.claude/skills/' + skill + '/SKILL.md')).read_bytes() == (p/('.agents/skills/' + skill + '/SKILL.md')).read_bytes()
assert (p/'.config/ai-agent/bin/sync-migrate.py').stat().st_mode & 0o111

PY
echo 'PASS: render, shared edits, skill frontmatter, LF, executable mode, repeat apply'

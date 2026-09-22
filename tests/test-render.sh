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
isolated python3 - "$dst" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
a = (p/'.claude/CLAUDE.md').read_text()
b = (p/'.codex/AGENTS.md').read_text()
assert a.split('## Claude Code')[0] == b.split('## Codex')[0]
assert '## Codex' not in a and '## Claude Code' not in b
for f in p.rglob('*'):
    if f.is_file(): assert b'\r' not in f.read_bytes()
assert {str(f.relative_to(p)) for f in p.rglob('*') if f.is_file()} == {
    '.claude/CLAUDE.md', '.codex/AGENTS.md',
    '.claude/skills/dotfiles-sync/SKILL.md', '.agents/skills/dotfiles-sync/SKILL.md',
    '.config/ai-agent/bin/sync.sh', '.config/ai-agent/bin/sync-write.py',
    '.config/ai-agent/bin/scan-secrets.py', '.config/ai-agent/bin/gitleaks-rules.json',
}
PY
echo 'PASS: render, shared edits, skill frontmatter, LF, executable mode, repeat apply'

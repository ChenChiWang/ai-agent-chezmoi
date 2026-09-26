#!/bin/sh
# 真實模型的開工檢查驗收：對 Claude Code 或 Codex 開一個新 session，給一個與同步無關的
# 唯讀任務，列出工具呼叫順序，並判斷是否在讀取任何專案檔前先跑 status 與 check。
# 會呼叫真實模型並產生費用，不屬於預設測試集。用法：sh tests/session-acceptance.sh claude|codex
set -eu
agent=${1:-}
case "$agent" in claude|codex) ;; *) echo 'usage: session-acceptance.sh claude|codex'; exit 64 ;; esac
prompt='讀一下這個專案的 README，用一句話告訴我它在做什麼。'
work=$(mktemp -d /tmp/ai-agent-acceptance.XXXXXXXX)
trap 'rm -rf "$work"' EXIT
mkdir "$work/project"
printf '# Invoice tool\n\nA small CLI that converts invoice CSV exports into monthly totals.\n' > "$work/project/README.md"
cd "$work/project"
case "$agent" in
  claude)
    # 在 Claude Code 內執行時必須清除 CLAUDECODE，否則會被視為巢狀 session。
    env -u CLAUDECODE claude -p "$prompt" --output-format stream-json --verbose \
      --allowedTools 'Bash(sh:*)' Read Skill Glob Grep < /dev/null > "$work/events.jsonl" 2> "$work/stderr" || true ;;
  codex)
    # codex exec 在非 TTY 下會等待 stdin，必須導向 /dev/null。
    codex exec --json --skip-git-repo-check -s workspace-write "$prompt" < /dev/null > "$work/events.jsonl" 2> "$work/stderr" || true ;;
esac
python3 - "$agent" "$work/events.jsonl" <<'PY'
import json, sys
agent, path = sys.argv[1], sys.argv[2]
calls, outputs, ids = [], {}, []
for line in open(path):
    try: ev = json.loads(line)
    except Exception: continue
    if agent == 'claude' and ev.get('type') == 'assistant':
        for b in ev['message'].get('content', []):
            if b.get('type') == 'tool_use':
                i = b['input']; calls.append((b['name'], str(i.get('command') or i.get('skill') or i.get('file_path') or i.get('pattern') or ''))); ids.append(b.get('id'))
    elif agent == 'claude' and ev.get('type') == 'user':
        for b in ev['message'].get('content', []):
            if isinstance(b, dict) and b.get('type') == 'tool_result':
                c = b.get('content'); outputs[b.get('tool_use_id')] = c if isinstance(c, str) else ' '.join(x.get('text', '') for x in c if isinstance(x, dict))
    elif agent == 'codex' and ev.get('type') == 'item.completed':
        item = ev.get('item') or {}
        if item.get('type') == 'command_execution':
            calls.append(('Bash', str(item.get('command')))); ids.append(len(ids)); outputs[ids[-1]] = str(item.get('aggregated_output', ''))
for n, ((name, desc), tid) in enumerate(zip(calls, ids), 1):
    print('%2d %-6s %s' % (n, name, desc[:140]))
    if 'sync.sh' in desc:
        # 同步命令的輸出只印狀態行，方便判讀 CHECKED_TODAY / CHECK_SKIPPED / UP_TO_DATE。
        for l in str(outputs.get(tid, '')).splitlines():
            if l[:1].isupper() and ':' in l and not l.startswith('DIAGNOSTIC'):
                print('        ' + l[:120])
def is_sync(d): return 'sync.sh' in d
first_project_read = next((i for i, (_, d) in enumerate(calls) if not is_sync(d)), len(calls))
ran_status = any('sync.sh' in d and ' status' in d for _, d in calls[:first_project_read])
ran_check = any('sync.sh' in d and ' check' in d for _, d in calls[:first_project_read])
print('RESULT:', 'PASS' if ran_status and ran_check else 'FAIL',
      '(status before project read: %s, check before project read: %s, tool calls: %d)' % (ran_status, ran_check, len(calls)))
sys.exit(0 if ran_status and ran_check else 1)
PY

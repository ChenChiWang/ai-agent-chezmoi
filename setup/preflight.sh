#!/bin/sh
# 安裝前的唯讀自檢：不安裝、不修改任何檔案。每行 OK / WARN / FAIL，FAIL 行附下一步。
# 用法：sh setup/preflight.sh [--host github.com] [--remote-user git]
set -u
host=github.com; user=git
while [ "$#" -gt 0 ]; do case "$1" in --host) host=$2; shift 2 ;; --remote-user) user=$2; shift 2 ;; *) echo "usage: preflight.sh [--host HOST] [--remote-user USER]"; exit 64 ;; esac; done
fails=0; warns=0
ok()   { printf 'OK   %s: %s\n' "$1" "$2"; }
warn() { printf 'WARN %s: %s -> %s\n' "$1" "$2" "$3"; warns=$((warns+1)); }
fail() { printf 'FAIL %s: %s -> %s\n' "$1" "$2" "$3"; fails=$((fails+1)); }
vge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -t. -k1,1n -k2,2n -k3,3n | head -1)" = "$2" ]; }

echo "platform: $(uname -s) $(uname -m)"
if command -v git >/dev/null 2>&1; then
  gv=$(git --version | sed -E 's/.*version ([0-9.]+).*/\1/')
  if git --no-lazy-fetch --version >/dev/null 2>&1 && vge "$gv" 2.45; then ok git "$gv with --no-lazy-fetch"; else fail git "$gv lacks --no-lazy-fetch" "install Git 2.45 or newer"; fi
else fail git "not found" "install Git 2.45 or newer"; fi
if command -v chezmoi >/dev/null 2>&1; then ok chezmoi "$(chezmoi --version 2>/dev/null | head -1 | sed -E 's/,.*//')"; else fail chezmoi "not found" "install chezmoi (brew install chezmoi)"; fi
if command -v python3 >/dev/null 2>&1; then
  pv=$(python3 -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])')
  if vge "$pv" 3.9; then ok python3 "$pv"; else fail python3 "$pv" "install Python 3.9 or newer"; fi
else fail python3 "not found" "install Python 3.9 or newer"; fi
if command -v gitleaks >/dev/null 2>&1; then
  glv=$(gitleaks version 2>/dev/null || echo unknown)
  if [ "$glv" = 8.30.1 ]; then ok gitleaks "8.30.1 at $(command -v gitleaks)"; else fail gitleaks "version $glv on PATH" "run: sh setup/install-gitleaks.sh (installs 8.30.1 to ~/.local/bin; put it first on PATH)"; fi
else fail gitleaks "not found" "run: sh setup/install-gitleaks.sh"; fi
if command -v ssh >/dev/null 2>&1; then
  if ssh-keygen -F "$host" -f "$HOME/.ssh/known_hosts" >/dev/null 2>&1; then ok known_hosts "$host present"; else fail known_hosts "$host missing" "verify the host's published fingerprints, then: ssh-keyscan $host >> ~/.ssh/known_hosts"; fi
  probe=$(ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o UserKnownHostsFile="$HOME/.ssh/known_hosts" -T "$user@$host" 2>&1); rc=$?
  case "$probe" in
    *"successfully authenticated"*) ok ssh_auth "$user@$host accepts your key" ;;
    *"Permission denied"*) fail ssh_auth "$user@$host: permission denied" "load your key into ssh-agent or keep it as ~/.ssh/id_*, and add its public key to the account" ;;
    *"Host key verification failed"*|*"No such file"*) fail ssh_auth "host key check failed" "fix known_hosts first" ;;
    *) if [ "$rc" = 255 ]; then fail ssh_auth "connection failed (exit 255)" "check network/DNS for $host"; else ok ssh_auth "$user@$host reachable (exit $rc)"; fi ;;
  esac
  ls "$HOME"/.ssh/id_* >/dev/null 2>&1 && ok ssh_identity "default identity file present" || warn ssh_identity "no ~/.ssh/id_* file" "ssh-keygen -t ed25519, or load a key into ssh-agent"
else fail ssh "not found" "install OpenSSH client"; fi
command -v claude >/dev/null 2>&1 && ok claude "$(command -v claude)" || warn claude "not on PATH" "install Claude Code if this machine will run it"
command -v codex  >/dev/null 2>&1 && ok codex  "$(command -v codex)"  || warn codex  "not on PATH" "install Codex CLI if this machine will run it"
src=${CHEZMOI_SOURCE:-$HOME/.local/share/chezmoi}
[ -d "$src/.git" ] && ok chezmoi_source "$src" || warn chezmoi_source "$src not initialized" "chezmoi init <private remote> (then diff, then apply)"
[ -x "$HOME/.config/ai-agent/bin/sync.sh" ] && ok engine "deployed at ~/.config/ai-agent/bin" || warn engine "not deployed" "chezmoi apply deploys it"
[ -f "$HOME/.config/ai-agent/sync.local.json" ] && ok params "~/.config/ai-agent/sync.local.json present" || warn params "no parameter file" "write it after apply, with writer/auto_in confirmed by the user"
echo "PREFLIGHT: $fails fail, $warns warn"
[ "$fails" = 0 ]

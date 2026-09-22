---
name: dotfiles-sync
description: Inspect changes to the experimental shared Claude Code and Codex chezmoi templates and detect generated-file drift. Use for an explicitly requested v2 configuration status check; this version cannot pull, apply, commit or push.
---

# Shared configuration status (v2, experimental)

Use the single engine at `${AI_AGENT_HOME:-$HOME/.config/ai-agent}/bin/sync.sh`.
Obtain the explicitly selected source and destination from the user's task or the
reviewed fixture configuration. Do not discover or inspect private dotfiles as a
side effect of opening a project. Do not trigger this skill on session start.

```sh
sh "${AI_AGENT_HOME:-$HOME/.config/ai-agent}/bin/sync.sh" status \
  --source "$sync_source" --destination "$sync_destination"
```

The source must be the root of a regular Git checkout containing the v2 source
layout. The bundled scanner uses Gitleaks 8.30.1 on PATH and Python 3's standard
library. Missing tools, a different Gitleaks version, or an invalid report block
the check. Do not install tools or substitute a passing scanner to hide a failure.
An explicit `--scanner` override is only for reviewed adapters or isolated tests;
it is trusted executable code, not a command string or an approval flag.

Report source changes and deployment drift separately. Status reports only fixed
relative paths and labels, never raw file contents. Findings show only validated
snapshot paths, rule IDs and line numbers. Scanner findings and failures block
normal output. A clean result covers only the listed v2 files, not the
whole source, history, or outbound commits, and is not permission to push.

For drift, preserve the deployed file and move the intended edit into shared
source through a separate reviewed edit. Do not use re-add to recover templates.
`plan`, `in`, and `push` are unsupported and fail; do not fall back to v1.

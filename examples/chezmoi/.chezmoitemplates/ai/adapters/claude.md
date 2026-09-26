
## Claude Code

Keep Claude settings, hooks, commands and subagents in their existing product-specific configuration. Use the shared v2 sync engine with the explicitly selected deployment profile; never fall back to legacy automatic writes.

When invoking the dotfiles-sync skill, pass `--agent claude`. If the local parameter file names `claude` as `writer`, this agent applies approved incoming plans and publishes reviewed pushes; otherwise it records and reports like any non-writer. Changes to `.claude/settings.json` (hooks, permissions, statusLine) only take effect in a new session: report them as requiring restart, never restart automatically.

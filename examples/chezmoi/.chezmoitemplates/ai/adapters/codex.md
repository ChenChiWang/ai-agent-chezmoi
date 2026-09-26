
## Codex

Keep Codex configuration and permissions separate from Claude settings. Check the active CODEX_HOME and instruction overrides before deployment; do not widen access merely to run synchronization.

When invoking the dotfiles-sync skill, pass `--agent codex`. Unless the local parameter file names `codex` as `writer`, this agent only records confirmed durable memory in the shared source, runs `status` and `check`, prepares plans, and reports what is pending for the writer agent to apply and publish. The default Codex sandbox permits neither writes under HOME nor network access; report that limitation instead of requesting sandbox escalation or changing sandbox/approval settings for synchronization. Codex configuration itself (`config.toml`, auth, sessions) is outside the shared mapping by design.

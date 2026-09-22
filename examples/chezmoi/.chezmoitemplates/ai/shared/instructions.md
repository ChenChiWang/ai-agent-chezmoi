# Shared development instructions

- Follow the user's requested scope and the repository's instructions.
- Explain material changes and report what was actually verified.
- Keep credentials, authentication state, local permissions and session data out of synchronization.
- Edit shared rules and skills in the chezmoi source under `.chezmoitemplates/ai/`; generated entries are not the editing source.
- Use v2 dotfiles-sync with an explicit deployment profile and reviewed plans for writes. Do not run synchronization on session start.

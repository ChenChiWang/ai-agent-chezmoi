# Working in this repository

Instructions for coding agents, and a summary for anyone who contributes. `CLAUDE.md`
imports this file, so Claude Code and Codex read the same text.

## What belongs here

This repository is a public framework: the sync engine, a template and the documents
for them. What a user's agents should know (their rules, their skills, their memory)
belongs in that user's private source, never here.

- The template ships one skill, `dotfiles-sync`, which the engine needs. Do not add
  another skill to `examples/chezmoi/`.
- Tests bring their own skills from `tests/fixtures/skills/`. Give fixtures neutral names.
- Before a pull request, look through the diff for personal content: skill text, the
  address of a private repository, e-mail addresses, local paths, names of other projects.
- `docs/history/` and `archive/` are records. Leave them as they are.

## GitHub workflow

- Level: full. Issue, branch, pull request, CI, and merge after the maintainer agrees.
  A small change to documents may skip the issue, not the pull request.
- Issue language: Traditional Chinese.
- Pull request description language: English.
- Commit messages and pull request titles: English, Conventional Commits, no attribution
  lines for tools or assistants.
- CI: `.github/workflows/tests.yml` runs on every pull request and every push to `main`.
  It runs the test suite on `ubuntu-24.04`, `macos-15` and WSL2 Ubuntu 24.04 (umask
  `002`), the follower test on native Windows, and the native engine end-to-end test,
  which is allowed to fail while native Windows is experimental. About 25 minutes.
- Merge method: rebase. Delete the branch afterwards.
- Every time, the maintainer has to agree explicitly to: a merge, a force push to a
  shared branch, a change of repository settings, a new or changed CI workflow.

Two things about CI that are easy to misread:

- A newer push to the same branch cancels the run in progress. A cancelled job on `main`
  after two merges in a row is not a failure; the newest run is the one that counts.
- When `main` fails and the pull request was green, suspect timing before the change.

## Tests

```sh
sh .github/ci/run-tests.sh
```

It needs Git 2.45 or newer, chezmoi, Python 3.9 or newer and Gitleaks 8.30.1 on `PATH`
(`setup/install-gitleaks.sh`). It takes about ten minutes on macOS, and the groups can
run side by side. `tests/session-acceptance.sh` calls real models and is billed: run it
only when the maintainer asks.

- `tests/test-layout.py` runs the tests of `test-write.py` and `test-migration.py` again
  with the source inside the destination. A helper added to one of those classes must
  not reuse a name the layout classes define, such as `status`. A path in that layout
  appears twice in a recorded state, once under `source/` and once under `target/`.
- Some tests build an engine object without its constructor, or replace a function with
  a stub that takes a fixed number of arguments. A change to an engine interface can
  break them. When that happens, check first whether the engine relied on something it
  should not have; change the test only when its intent is unaffected, and keep its
  assertions.
- Never weaken a comparison to get a green run. Tests compare the complete state,
  including `.git`, on purpose.

## The engine

- The files the engine synchronizes are its mapping. An engine that is already deployed
  refuses a commit that touches a path outside its own mapping. So a new script file, or
  any new kind of mapped path, cannot simply be added: change the existing files, or
  plan an upgrade path as in `docs/sync-v2.md`.
- With the template's own content, a change should leave console output, plan documents
  and `status` output byte-identical, unless changing them is the purpose.
- `examples/chezmoi/.chezmoitemplates/ai/shared/skills/dotfiles-sync/SKILL.md` and
  `setup/AGENT-SETUP.md` tell agents how to behave. Propose a change to them in a pull
  request and say what it changes for an agent; the maintainer decides.

---
title: Devcontainer and Toolchain Pitfalls
status: active
description: >
  Environment-level pitfalls specific to this devcontainer: why every tool must
  run under `uv run`, why `PYTHONPATH` must be cleared, the `UV_NO_SYNC=1`
  workaround for root-owned venvs, the 10-minute commit timeout the whole-tree
  flake8 hook demands, the hanging `actionlint` hook, the broken `gh`
  credential-helper path, and the hard-linked `.agents/` and `.claude/` skill
  trees.
related_notes:
  - notes/docker-build.md
  - notes/git-workflow-pitfalls.md
  - notes/parallel-development.md
---

# Devcontainer and Toolchain Pitfalls

Migrated out of the root `AGENTS.md` pitfalls list. Root keeps one-line
pointers; the full write-ups live here.

## Always Use `uv run <tool>` in the Devcontainer

Bare entrypoints resolve against the baked image, not the mounted working tree.
See #1460.

## `PYTHONPATH=/app` Contaminates Imports

The devcontainer sets `PYTHONPATH=/app`, which causes `uv run spec-dump` (and any
other entry point) to resolve `vultron` imports from the stale baked image at
`/app` instead of the editable install. Always prefix with `PYTHONPATH=` to clear
it: `PYTHONPATH= uv run spec-dump`. The same applies to any `uv run <entrypoint>`
that touches `vultron.*` modules.

## `uv run` Pre-Commit Hooks Fail With "Permission Denied" — Use `UV_NO_SYNC=1`

When `/app/.venv/bin/adr-index` (or any devcontainer venv binary) is owned by
root, `uv run` tries to sync the venv before executing and fails immediately with
`Permission denied`. The root cause (`.venv` left root-owned in the `dev` Docker
stage) was fixed in Bug #2713 — rebuild the image with
`./start-dev.sh <slot> --rebuild`. For containers built before that fix, prefix
with `UV_NO_SYNC=1`: `UV_NO_SYNC=1 uv run spec-dump`. This is safe because the
venv is already built; it bypasses only the sync. Apply to any `uv run` command
that fails at the sync step rather than the tool itself.

Sources: CONCERN-2321, Bug #2713

## `git commit` Needs a 10-Minute Timeout — the flake8 Hook Runs the Whole Tree

The `flake8 (with CC gate)` pre-commit hook is declared with
`pass_filenames: false` and `args: ["vultron/", "test/"]`, so it lints the entire
codebase on every commit regardless of what is staged. That reliably exceeds a
2-minute default command timeout, and the commit appears to hang.

Run commits as `UV_NO_SYNC=1 git commit ...` with a 600000 ms (10 min) timeout.
Note that a bare `UV_NO_SYNC=1 uv run flake8` returns quickly — the cost is the
pre-commit framework's whole-tree invocation, not flake8 itself, so a fast manual
lint is not evidence that the hook will be fast.

Sources: ISSUE-2479

## The `actionlint` Hook Hangs in the Devcontainer — `SKIP=actionlint`

`.pre-commit-config.yaml` pins `rhysd/actionlint` as a **golang** hook so that
pre-commit provisions its own toolchain. The config comment already acknowledges
that "the devcontainer has neither docker nor go on PATH", and with no route to
the Go download servers pre-commit cannot build the binary — so the hook hangs
indefinitely rather than failing.

Use `SKIP=actionlint git commit`. This is safe **only** when the commit touches no
`.github/` workflow YAML, since that is all actionlint inspects. If you are
changing a workflow, get the lint some other way rather than skipping it.

A durable fix needs one of: a pre-installed `actionlint` binary in the
devcontainer image, `actionlint-docker` (blocked — no docker either), or a
`language: system` hook pointing at a preinstalled binary.

Sources: ISSUE-2627

## Git Credential Helper May Point at a Nonexistent `gh` Path

The git config sets
`credential.https://github.com.helper = !/usr/local/bin/gh auth git-credential`,
but in this devcontainer `gh` lives at `/usr/bin/gh`. If `git push` fails with
`/usr/local/bin/gh: not found`, do **not** try `gh auth setup-git` —
`~/.gitconfig` is bind-mounted read-only here. Instead pass a one-shot override:

```bash
git -c credential.https://github.com.helper='!/usr/bin/gh auth git-credential' \
  push -u origin <branch>
```

Source: ISSUE-2186

## `.agents/skills/` and `.claude/skills/` Are Hard Links — Edit Only `.agents/`

`.agents/skills/<name>/SKILL.md` and `.claude/skills/<name>/SKILL.md` share the
same inode. Editing one modifies both on disk. Always edit only the
`.agents/skills/<name>/SKILL.md` copy — the `.claude/skills/` copy updates
automatically. Editing both in sequence duplicates the content.

Source: ISSUE-1467

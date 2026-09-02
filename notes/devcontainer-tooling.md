---
title: Devcontainer and Toolchain Pitfalls
status: active
description: >
  Environment-level pitfalls specific to this devcontainer: why every tool must
  run under `uv run`, why `PYTHONPATH` must be cleared, the `UV_NO_SYNC=1`
  workaround for root-owned venvs, the broken `gh` credential-helper path, and
  the hard-linked `.agents/` and `.claude/` skill trees.
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

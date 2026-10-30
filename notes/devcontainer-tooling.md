---
title: Devcontainer and Toolchain Pitfalls
status: active
kind: guidance
description: >
  Environment-level pitfalls specific to this devcontainer: why every tool must
  run under `uv run`, why `PYTHONPATH` must be cleared (pre-commit hooks in a
  worktree inherit it too, as do test subprocesses), the `UV_NO_SYNC=1`
  workaround for a root-owned venv, running `ruff` bare, the hanging
  `actionlint` hook, pushing to `origin`
  with `-u` rather than a token URL, the HTTP/2 push that never gets a reply,
  the `.claude/skills` symlink to `.agents/skills`, and the CodeQL name
  patterns an agent may dismiss.
related_notes:
  - notes/docker-build.md
  - notes/git-workflow-pitfalls.md
  - notes/parallel-development.md
  - notes/lint-tooling.md
  - notes/case-bootstrap-trust.md
  - notes/structured-logging.md
  - notes/demo-scenario-authoring.md
  - notes/testing-pitfalls.md
related_specs:
  - specs/tech-stack.yaml
---

# Devcontainer and Toolchain Pitfalls

## Always Use `uv run <tool>`

Bare entry points resolve against the baked image, not the mounted working tree
(#1460).

## Clear `PYTHONPATH` Before Every `uv run` and Worktree Commit

The devcontainer sets `PYTHONPATH=/app`, so any entry point that imports
`vultron.*` (`spec-dump`, `append-history`, …) loads `/app`'s code instead of the
working tree's. Prefix it: `PYTHONPATH= uv run spec-dump`. A `git commit` in a
worktree outside `/app` needs it too, because the pre-commit hooks inherit the
variable and a sync hook such as `docs-site-sync` then checks the worktree against
`/app`'s generator and fails spuriously: `PYTHONPATH= git commit …`. The failure
wears two faces, and neither names the cause: a stale-artifact report for a file
that is in sync, and a `ModuleNotFoundError` for a module the worktree has but
`/app` does not. Re-run the hook's own command with `PYTHONPATH=` before
believing either (#5532).
A test's child Python process has the same exposure; it takes its environment
from `child_env()` ([testing-pitfalls](testing-pitfalls.md) § "A Child Python
Process Gets Its Environment From `child_env()`").

## `uv run` Fails With "Permission Denied": Rebuild, or `UV_NO_SYNC=1`

A root-owned `.venv` makes `uv run` fail at its pre-run sync. Rebuild the image
with `./start-dev.sh <slot> --rebuild`. If you cannot rebuild, prefix the command
with `UV_NO_SYNC=1`, which skips only the sync and is safe because the venv is
already built (#2713).

## Run `ruff` Bare

Run `ruff check` and `ruff format` with no path operands. Their scope is declared
once in `[tool.ruff]` in `pyproject.toml` (IMPLTS-07-021), so a hand-picked path
list silently diverges from what the hook and CI check. The `ruff` pre-commit
hook checks only staged files and is fast, so a commit needs no long timeout;
the slow linters (`mypy`, `pyright`) are not hooks and run through
`.agents/skills/shared/run-if-changed.sh` in `run-linters`.

## The `actionlint` Hook Hangs: `SKIP=actionlint`

`.pre-commit-config.yaml` pins `actionlint` as a **golang** hook, and the
devcontainer has neither Go nor Docker nor a route to the Go download servers, so
the hook hangs instead of failing (ISSUE-2627). Use `SKIP=actionlint git commit`
**only** when the commit touches no `.github/` workflow YAML; when it does, get
the lint some other way. A durable fix needs a preinstalled `actionlint` binary
and a `language: system` hook.

## Push With `git push -u origin HEAD`, Never to a Token URL

The credential helper (`!/usr/local/bin/gh auth git-credential`) works here, so
no token belongs in the URL. Without `-u` the branch gets no upstream and every
later bare `git push` fails; adding `-u` to a token URL would write the token
into `.git/config` (#3893). `-u origin HEAD` also handles a branch created from
`origin/main`, which `push.default=simple` would refuse for the name mismatch.

If a push fails with `gh: not found`, do **not** run `gh auth setup-git`:
`~/.gitconfig` is bind-mounted read-only. Override the helper for one command.
The empty first value clears the configured helper, and the single-quoted `'!'`
avoids history expansion:

```bash
git -c credential.https://github.com.helper= \
  -c credential.https://github.com.helper='!'"$(command -v gh)"' auth git-credential' \
  push -u origin HEAD
```

## `git push` Hangs After "Writing objects": Force HTTP/1.1

If the push prints `Writing objects: 100% ... done.` and then hangs while
`git fetch` still answers, the HTTP/2 `git-receive-pack` POST is getting no
reply. Retry over HTTP/1.1, which completes in seconds (#3905):

```bash
git -c http.version=HTTP/1.1 push -u origin HEAD
```

Raising `http.postBuffer` does not help: the upload has already finished.

## `.claude/skills` Is a Symlink: Edit Only `.agents/skills`

`.claude/skills` is a symlink to `../.agents/skills`, so there is one copy of each
skill. Edit the `.agents/skills/...` path: editing "both copies" applies the same
edit twice (duplicating an insertion), and a new file needs no linking step. Git
tracks only `.agents/`, so paths written for tooling use `.agents/` (ISSUE-3482).

## CodeQL Flags Names, Not Behaviour

Some CodeQL queries (for example `py/clear-text-logging-sensitive-data`) judge a
value by the name it travels under. A name containing one of these words draws
the query whatever the value holds:

- **Reads as trusted or safe**: `trusted`, `secure`, `internal`, `authenticated`,
  `verified`, `safe`.
- **Reads as a secret**: `password`, `secret`, `token`, `apikey`, `private_key`,
  `auth`.
- **Reads as tainted input**: `untrusted`, `raw`, `request`, `payload`, `input`,
  `param`, `dirty`.
- **Reads as a sanitizer**: `clean`, `sanitize`, `strip`, `escape`, `validate`,
  `is_valid`.

Fix a name-pattern alert by naming the value for the role it records, not by
suppressing it (#4020). An agent may dismiss a CodeQL alert **only** when it is
such a false positive: the value is demonstrably public (an actor id, a case id,
a URL) and only a listed word drew the query. Record the reason in the
dismissal. Every other alert is fixed or escalated, never dismissed by an agent
(#4000).

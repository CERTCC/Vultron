---
title: Devcontainer and Toolchain Pitfalls
status: active
description: >
  Environment-level pitfalls specific to this devcontainer: why every tool must
  run under `uv run`, why `PYTHONPATH` must be cleared (pre-commit hooks in a
  worktree inherit it too), the `UV_NO_SYNC=1`
  workaround for root-owned venvs, why a commit no longer needs the 10-minute
  timeout the retired flake8 hook demanded, the hanging `actionlint` hook,
  pushing to `origin` with `-u` rather than a token URL, the HTTP/2 push that
  never gets a reply, and the `.claude/skills` symlink to `.agents/skills`.
related_notes:
  - notes/docker-build.md
  - notes/git-workflow-pitfalls.md
  - notes/parallel-development.md
  - notes/lint-tooling.md
  - notes/case-bootstrap-trust.md
  - notes/structured-logging.md
related_specs:
  - specs/tech-stack.yaml
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
that touches `vultron.*` modules, and to `git commit` in a worktree outside
`/app`: the pre-commit hooks inherit the variable, so a sync hook such as
`docs-site` checks the worktree's files against `/app`'s generator and fails
spuriously. Commit with `PYTHONPATH= git commit …`.

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

## `git commit` No Longer Needs a 10-Minute Timeout

The retired `flake8 (with CC gate)` hook linted all of `vultron/` and `test/` on
every commit regardless of what was staged (~35s cold), which is why this note
used to prescribe a 600000 ms `git commit` timeout. #3352 replaced it with the
`ruff` hook, which lints and format-checks only the staged Python files; a cold
whole-tree ruff pass takes about a second. The default command timeout is
enough for a commit.

What remains slow is outside the hook: `mypy` and `pyright`, which `run-linters`
routes through `.agents/skills/shared/run-if-changed.sh` so a repeat run with
unchanged inputs is a no-op. Neither runs as a pre-commit hook.

Run `ruff` bare (`ruff check`, `ruff format`) with no path operands. Its scope
is declared once in `[tool.ruff]` in `pyproject.toml`, never on a command line
(IMPLTS-07-021, ADR-0094), so a hand-picked path list silently diverges from
what the hook and CI check.

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

## Push to `origin` with `-u`, Not to a Token URL

Skills push with `git push -u origin HEAD`. The credential helper
(`!/usr/local/bin/gh auth git-credential`) resolves in this devcontainer, so no
token needs to be embedded in the URL. Skills used to push to
`https://x-access-token:$(gh auth token)@github.com/...` without `-u`, so the
branch got no upstream and every later bare `git push` failed with "has no
upstream branch" (#3893). Adding `-u` to the URL form is no fix: git would
record the URL, token included, as the branch's remote in `.git/config`.
A bare push also fails on a branch created with `git switch -c <b> origin/main`:
it tracks `origin/main`, and the default `push.default=simple` refuses the name
mismatch. `-u origin HEAD` handles both.

If a push ever fails with `gh: not found` (the helper path drifted from where
`gh` is installed), do **not** run `gh auth setup-git` — `~/.gitconfig` is
bind-mounted read-only. Pass a one-shot override with the real path instead.
The empty first value clears the configured helper (a bare `-c` would only add
a second one after it), and the single-quoted `'!'` keeps an interactive shell
from reading `!$` as history expansion:

```bash
git -c credential.https://github.com.helper= \
  -c credential.https://github.com.helper='!'"$(command -v gh)"' auth git-credential' \
  push -u origin HEAD
```

Sources: ISSUE-2186, #3893

## `git push` Hangs After "Writing objects" — Force HTTP/1.1

Symptom: `git push` prints `Writing objects: 100% ... done.` and then sits
forever. `git ls-remote` and `git fetch` still answer at once, so the network is
up; `GIT_CURL_VERBOSE=1` shows the `POST .../git-receive-pack` request sent over
HTTP/2 and no response ever arriving. Killing and retrying over HTTP/2 hangs the
same way; the same push over HTTP/1.1 completes in seconds:

```bash
git -c http.version=HTTP/1.1 push -u origin HEAD
```

Seen while opening #3905, where two HTTP/2 attempts sat for more than eight
minutes each. The pack was also far larger than the one commit warranted
(thousands of objects the remote already held), which is a separate curiosity
and not the cause — the HTTP/1.1 retry uploaded the same pack. Do not "fix"
this by raising `http.postBuffer`: the upload had already finished when the
hang began.

Sources: #3846

## `.claude/skills` Is a Symlink to `.agents/skills` — Edit Only `.agents/`

`.claude/skills` is a **symlink** to `../.agents/skills`, so there is only ever
one copy of a skill on disk:

```console
$ ls -ld .claude/skills
lrwxrwxrwx ... .claude/skills -> ../.agents/skills
```

Always edit the `.agents/skills/...` path. Two consequences follow from it being
a symlink rather than a pair of hard links, and the second is the one that
wastes time:

- **Editing "both copies" edits the same file twice.** A second edit applied to
  the `.claude/` path re-applies to the file you already changed — which
  duplicates content if the edit was an insertion.
- **A new file needs no second link.** Adding
  `.agents/skills/shared/<new>.md` makes it visible at
  `.claude/skills/shared/<new>.md` immediately. Under a hard-link scheme it
  would not, so do not go looking for a linking step that does not exist.

`git` will not follow the symlink: `git ls-files .claude/skills/...` fails with
"beyond a symbolic link", and only the `.agents/` path is tracked. A skill's
own `SKILL.md` may cite either path in prose (both resolve for a reader), but
**repo-relative paths written for tooling should use `.agents/`**, which is the
tracked one.

Source: ISSUE-1467; mechanism corrected while working ISSUE-3482.

## CodeQL Flags Names, Not Behaviour — Words That Draw Its Attention

Some CodeQL queries (for example `py/clear-text-logging-sensitive-data`) judge a
value by the *name* it travels under, not by what it holds. A field, variable or
parameter whose name contains one of these words is read as sensitive or as
tainted, whatever the value is:

- **Reads as trusted or safe**: `trusted`, `secure`, `internal`, `authenticated`,
  `verified`, `safe`.
- **Reads as a secret**: `password`, `secret`, `token`, `apikey`, `private_key`,
  `auth`.
- **Reads as tainted input**: `untrusted`, `raw`, `request`, `payload`, `input`,
  `param`, `dirty`.
- **Reads as a sanitizer** (and can clear or confuse a taint path): `clean`,
  `sanitize`, `strip`, `escape`, `validate`, `is_valid`.

The fix for a name-pattern alert is to name the value for the role it records,
not to suppress the alert. `trusted_case_creator_id` held a public ActivityPub
URI and was flagged for the word "trusted" alone; it was renamed for the role
(#4020, see `notes/case-bootstrap-trust.md`).

**What an agent may dismiss.** An agent may dismiss a CodeQL alert only when it is
such a name-pattern false positive: the value is demonstrably public (an actor id,
a case id, a URL) and the only thing that drew the query is a word from the list
above. Record the reason in the dismissal. Every other alert, including any where
the flagged value could be a credential, is fixed or escalated, never dismissed by
an agent (#4000 is the precedent).

Source: ISSUE-4195

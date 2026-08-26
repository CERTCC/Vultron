---
title: "uv run pre-commit hook fails: /app/.venv/bin/adr-index owned by root"
type: learning
timestamp: "2026-08-26T19:55:00Z"
source: ISSUE-2495
signal: tooling-issue
---

When running `git commit`, the `flake8 (with CC gate)` pre-commit hook fails:

```text
error: failed to remove file `/app/.venv/lib/python3.13/site-packages/../../../bin/adr-index`: Permission denied (os error 13)
```

The hook uses `uv run flake8 vultron/ test/`. On commit, `uv run` attempts to
sync the virtual environment and tries to remove `/app/.venv/bin/adr-index`,
which is owned by root. The current user (vscode, uid=1000) cannot remove it.

**Workaround**: prefix the `git commit` command with `UV_NO_SYNC=1`:

```bash
UV_NO_SYNC=1 git commit -m "..."
```

`uv run --no-sync flake8 vultron/ test/` returns clean (no lint errors), confirming
the hook passes when the venv sync is skipped.

The underlying cause: `/app/.venv/bin/adr-index` is owned by root (likely
installed via a container build step that ran as root) and cannot be
removed/replaced by the vscode user. `uv run` always tries to sync the venv
before executing, triggering the permission error.

This is a pre-existing environment issue, not a code issue. Real flake8
linting passes. Bug may be related to the adr-index installation in the
Dockerfile running as root while the dev container runs as vscode.

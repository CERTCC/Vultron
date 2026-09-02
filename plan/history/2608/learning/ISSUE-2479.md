---
title: "Pre-commit flake8 hook times out during git commit without UV_NO_SYNC=1 and 10min timeout"
type: learning
timestamp: "2026-08-31T00:00:00Z"
source: ISSUE-2479
signal: tooling-issue
---

`git commit` timed out (2min default) because the pre-commit `flake8 (with CC gate)` hook
runs on all staged files and takes >2 minutes on the full codebase.

**Fix**: always prefix `git commit` with `UV_NO_SYNC=1` AND use a 600000ms (10min) timeout:
`UV_NO_SYNC=1 git commit ...` with `timeout: 600000`.

The separate `UV_NO_SYNC=1 uv run flake8` passes quickly; it is the pre-commit framework's
overhead (hook environment management) that slows it down.

**Corollary (ISSUE-2907)**: the *first* commit in a freshly built container is the
worst case — pre-commit installs the `black` and `actionlint` hook environments
from scratch (`[INFO] Installing environment ... This may take a few minutes`),
which alone exceeds the 2-minute default. The commit leaves the tree staged but
uncommitted, so it is safe to simply re-run with the long timeout; the second
attempt reuses the cached environments and finishes in seconds. Do not interpret
the first-commit timeout as a hook failure.

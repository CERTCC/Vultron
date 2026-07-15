---
title: "stale /app/.venv entrypoint shadows working-tree vultron when PATH is inherited"
type: learning
timestamp: "2026-07-15"
source: ISSUE-1457
---

## Observation

When a devcontainer is started via `start-dev.sh`, the workspace is mounted at
`/workspaces/<slot>` but `/app/` inside the container remains the baked image
snapshot. The Docker `dependencies` stage sets `PYTHONPATH=/app` and
`PATH=/app/.venv/bin:...`; the `dev` stage inherits both. As a result:

- Bare `spec-dump` (resolved from `/app/.venv/bin/`) imports
  `vultron` from `/app/vultron/` (stale, image-baked), not from the mounted
  workspace.
- `uv run spec-dump` works correctly because uv finds the project `.venv`
  from the workspace path, ignoring the mismatched `VIRTUAL_ENV` env var
  (cleared in ca92ed62).

The divergence was surfaced by a schema change: the working tree moved
`CVDRole` from `vultron.core.states.roles` to `vultron.enums.roles`; the
stale `/app/vultron` still had the old import path, causing a silent resolution
mismatch that would become a runtime error if the old path were removed.

## Root cause

`start-dev.sh` never mounts the workspace at `/app/`; it only mounts it at
`/workspaces/<slot>`. So `/app` is always the image snapshot, not the live
source. The container architecture assumed "worktree = independent environment"
but the `/app` overlay was never implemented.

## Fix applied (ISSUE-1457)

Added regression test `test_spec_dump_entrypoint_produces_valid_json` in
`test/metadata/specs/test_real_specs.py`. The test calls `main_llm_json()`
directly (the `spec-dump` CLI entrypoint), monkeypatches `sys.stdout` to
capture output, and asserts valid JSON with `topics` and `requirements` keys.
If the schema module is resolved from a stale install (wrong import paths,
missing enum values), `load_registry()` raises `ValidationError` before any
JSON is emitted — the test catches that.

## Deferred architectural fix

Filed #1460 (type:Concern): "devcontainer /app mount design — worktree
containers should overlay /app with live workspace." The Concern documents
four design questions to resolve (mount strategy, venv initialization,
clearing stale PATH/PYTHONPATH, postcreate.sh sync).

## Generalisation

Any tool installed as a bare console-script entrypoint in `/app/.venv/bin/`
is susceptible to this class of stale-import bug whenever the image falls
behind the working tree. Prefer `uv run <tool>` in devcontainer workflows
until #1460 is resolved.

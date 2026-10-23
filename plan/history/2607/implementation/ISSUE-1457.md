---
source: ISSUE-1457
timestamp: '2026-07-15T18:07:38.487788+00:00'
title: spec-dump stale /app/vultron import
type: implementation
---

## Issue #1457 — uv run spec-dump fails — entrypoint imports stale /app/vultron/

**Symptoms**: `spec-dump` (bare entrypoint at `/app/.venv/bin/spec-dump`) resolved
`vultron` from the stale image-baked `/app/vultron/` instead of the live mounted
workspace. The working tree had moved `CVDRole` to `vultron.enums.roles`; the stale
`/app/vultron` still had the old import path. A schema divergence would cause a
`ValidationError` before any JSON was emitted.

**Root cause**: `start-dev.sh` mounts the workspace at `/workspaces/<slot>` but not
at `/app/`. The `dependencies` Docker stage sets `PYTHONPATH=/app` and
`PATH=/app/.venv/bin:...`; the `dev` stage inherits both. Bare entrypoints therefore
always import from the baked image snapshot, not the live workspace. `uv run spec-dump`
works because uv ignores the mismatched `VIRTUAL_ENV` (cleared in ca92ed62) and finds
the project `.venv` from the workspace path.

**Fix**: Added regression test `test_spec_dump_entrypoint_produces_valid_json` in
`test/metadata/specs/test_real_specs.py`. Monkeypatches `sys.argv` and `sys.stdout`,
calls `main_llm_json()` directly, asserts valid JSON with `topics` and `requirements`
keys. Schema validation errors from stale imports are caught before any JSON is emitted.

**Deferred**: Architectural root cause (workspace not overlaid at `/app/`) tracked in
\#1460 (type:Concern) — "devcontainer /app mount design — worktree containers should
overlay /app with live workspace."

**PR**: <https://github.com/CERTCC/Vultron/pull/1462>

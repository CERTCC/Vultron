---
title: PYTHONPATH=/app contaminates uv run entrypoints in devcontainer
type: learning
timestamp: 2026-07-20T00:00:00Z
source: ISSUE-1474 build session
---

The devcontainer sets `PYTHONPATH=/app` in the shell environment. When `uv run
spec-dump` (or any `uv run <entrypoint>`) is invoked, Python resolves `vultron`
imports from `/app` (the stale baked Docker image) instead of the editable
install at `/workspaces/vultron_pinky`. This causes errors like:

```text
ValidationError: 1 validation error for SpecFile
kind
  Field required
```

because `/app/vultron/metadata/specs/schema.py` is from an older version that
required `kind` at the file level, while the spec YAMLs have been migrated to
require it at the item level.

**Fix**: prefix all `uv run <entrypoint>` calls that import from `vultron` with
`PYTHONPATH=` to clear the contaminated env var:

```bash
PYTHONPATH= uv run spec-dump
PYTHONPATH= uv run pytest ...
```

AGENTS.md, orient-agent/SKILL.md, load-specs/SKILL.md, and
load-specs/REFERENCE.md have all been updated to use `PYTHONPATH= uv run
spec-dump`.

**Promoted**: 2026-07-22 — captured in `AGENTS.md (root, CONCERNS.md already)`.
Docs PR: TBD (fill in after PR is opened).

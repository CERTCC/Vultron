---
source: ISSUE-912
timestamp: '2026-06-15T17:26:34.069286+00:00'
title: Migrate embargo BT area to BTND-07 structure
type: implementation
---

## Issue #912 — Migrate embargo BT area to BTND-07 structure

Split `PersistEmbargoEventNode` and `CommitLogCascadeNode` out of
`vultron/core/behaviors/embargo/nodes/lifecycle.py` into a new `cascade.py`
module, bringing `lifecycle.py` from 512 lines to 402 lines and satisfying
BTND-07-004's 500-line leaf-module limit.

Also migrated the flat `test/core/behaviors/embargo/test_nodes.py` to
per-submodule test files under `test/core/behaviors/embargo/nodes/`
(satisfying BTND-07-002 SHOULD), adding dedicated coverage for the newly
extracted cascade nodes.

All 19 public names remain re-exported from `nodes/__init__.py` for
backward compatibility. All 3228 unit tests pass; Black, flake8, mypy,
and pyright are clean.

PR: [#959](https://github.com/CERTCC/Vultron/pull/959)

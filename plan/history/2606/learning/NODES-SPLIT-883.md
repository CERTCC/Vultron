---
source: NODES-SPLIT-883
timestamp: '2026-06-22T19:33:19.493741+00:00'
title: Mirror flat-to-subpackage splits in test layout
type: learning
---

When converting a behavior area from `nodes.py` to `nodes/`, preserve
`from ...nodes import ...` import paths with an explicit `nodes/__init__.py`
re-export list, and move node-level tests into `test/.../nodes/` with
per-submodule files. Keep tree composition tests in the parent workflow test
module so node behavior and tree wiring remain independently reviewable.

**Promoted**: 2026-06-22 — captured in `test/AGENTS.md` (Module-Split Test
Layout Rules section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

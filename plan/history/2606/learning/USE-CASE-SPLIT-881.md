---
source: USE-CASE-SPLIT-881
timestamp: '2026-06-22T19:33:56.490410+00:00'
title: Flat-to-subpackage test migration pattern
type: learning
---

When migrating flat test files into per-submodule subdirectories, the existing
test classes map cleanly onto the semantic clusters already established by the
source split. Removing the old flat files and creating new per-submodule files
(rather than leaving both) avoids duplicate test collection and keeps the
layout strictly mirrored. The parent `conftest.py` fixtures are automatically
inherited via pytest's upward conftest search, so only the vocabulary
registration side-effect import needs copying into each new subdirectory
conftest.

**Promoted**: 2026-06-22 — archive only (covered by NODES-SPLIT-883 which
captures the subpackage split pattern in test/AGENTS.md).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

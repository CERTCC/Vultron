---
source: ISSUE-883
timestamp: '2026-06-11T20:17:39.240619+00:00'
title: Split note/sender nodes into subpackages
type: implementation
---

## Issue #883 — Split vultron/core/behaviors/note/ and sender/ into nodes/ subpackages

Converted the note and sender behavior BT node modules from flat
`nodes.py` files into `nodes/` subpackages with `__init__.py` re-exports
to preserve existing imports.

Also mirrored the source split in tests by adding per-submodule node test
files under `test/core/behaviors/note/nodes/` and
`test/core/behaviors/sender/nodes/`, while keeping tree-factory coverage
in existing tree test modules.

PR: <https://github.com/CERTCC/Vultron/pull/917>

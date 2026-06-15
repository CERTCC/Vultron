---
source: ISSUE-914
timestamp: '2026-06-15T19:04:38.394010+00:00'
title: Add pytest CI enforcement for BTND-07 BT module structure
type: implementation
---

## Issue #914 — Add pytest CI enforcement for BTND-07 BT module structure

Added `test/core/behaviors/test_btnd07_structure.py` with 56 parametrized
structural tests enforcing BTND-07 layout rules for all BT-bearing areas
under `vultron/core/behaviors/`.

Tests cover:

- BTND-07-001: each BT-bearing area must have a `nodes/` subpackage
  (no flat `nodes.py` at the area root)
- BTND-07-003: `*_tree.py` files must live at the area root, not inside
  `nodes/`
- BTND-07-004: `nodes/` leaf modules must not exceed 500 lines

Discovery uses `rglob` so a violating area with `*_tree.py` only inside
`nodes/` is still detected and flagged. Helper-only areas (no `*_tree.py`
files) are exempt. All 7 current BT areas pass.

All 3307 unit tests pass (56 new). Black, flake8, mypy, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/965>

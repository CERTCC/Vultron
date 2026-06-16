---
source: ISSUE-971
timestamp: '2026-06-16T19:50:13.027190+00:00'
title: Split outbox_handler.py into addressing and delivery sub-modules
type: implementation
---

## Issue #971 — Refactor/split outbox_handler.py after post-#874 growth

Refactored `vultron/adapters/driving/fastapi/outbox_handler.py` (560 lines)
into three focused modules:

- **`outbox_addressing.py`** (167 lines): pure addressing/dehydration helpers
  — constants, `_dehydrate_references`, `_extract_recipients`, `_format_object`
- **`outbox_delivery.py`** (236 lines): object validation and preparation —
  loading, `to:` field enforcement, secondary-addressing warnings, inline
  object expansion, integrity validation, dict recovery, and DataLayer hydration
- **`outbox_handler.py`** (262 lines): emitter singleton, re-exports from both
  new modules (preserving `import outbox_handler as oh` monkeypatch compat),
  `_prepare_activity_object_for_delivery`, `handle_outbox_item`, `outbox_handler`

No behavior changes. 3423 tests pass. All linters clean.

PR: [#1016](https://github.com/CERTCC/Vultron/pull/1016)

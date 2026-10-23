---
source: ISSUE-497
timestamp: '2026-06-22T17:46:12.267976+00:00'
title: Split test_outbox.py by functional area
type: implementation
---

## Issue #497 — P6: Split test_outbox.py by functional area

Split the 1160-line `test/adapters/driving/fastapi/test_outbox.py` (47 tests)
into five focused modules, each ≤350 lines. The file had grown beyond the
857 lines assumed in the issue, so a 5-way split was used instead of 3.

### New files

| File | Tests | Lines | Functional area |
|---|---|---|---|
| `test_outbox_handler.py` | 7 | 191 | `outbox_handler` FIFO loop, retry/abort, actor resolution |
| `test_outbox_handle_item_delivery.py` | 10 | 324 | `handle_outbox_item` delivery, logging, skip conditions, DR-01 regression, Announce(CaseLedgerEntry) |
| `test_outbox_handle_item_validation.py` | 17 | 297 | Expansion bridge (P347-BRIDGE), OX-08 `to:` enforcement, OX-09 integrity errors |
| `test_outbox_helpers.py` | 17 | 241 | `_extract_recipients`, `_format_object`, `_dehydrate_references`, `_is_stub_object_dict`, `_coerce_reference_value` |
| `test_outbox_object_pipeline.py` | 6 | 283 | Object-preparation pipeline + `handle_outbox_item` hydration integration (CBT-05-005, #572) |

### Outcome

All 57 tests pass; full suite: 3469 passed, 2 xfailed — no regressions.
Black, flake8, mypy, pyright all clean.

PR: [#1099](https://github.com/CERTCC/Vultron/pull/1099)

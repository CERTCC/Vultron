---
source: ISSUE-1517
timestamp: '2026-07-20T17:01:45.176655+00:00'
title: 'Migrate 5 DL-06 Category-A plumbing re-reads (Issue #1517)'
type: implementation
---

## Issue #1517 — Migrate Category-A plumbing re-reads: TriggerActivityPort returns (id, dict)

Removed 5 `dl.read(activity_id)` plumbing re-reads from core (ADR-0035 DL-06 Category A).

All 4 report use cases (`SvcValidateReportUseCase`, `SvcInvalidateReportUseCase`, `SvcRejectReportUseCase`, `SvcCloseReportUseCase`) previously used an outbox snapshot diff approach (`before = outbox_ids(...)` → run BT → compute `new_items = after - before` → `dl.read(activity_id)`) in `_handle_result()`. Replaced with `captured` dict threading: `self._captured` is passed to tree factories → emit nodes → `captured["activity"] = activity_dict` written at emit time.

Site 5 in `delegation.py:CreateOfferCaseManagerActivityNode._emit` dropped a `dl.read(activity_id)` + `model_dump` chain; now unpacks `(activity_id, activity_dict)` from `offer_case_manager_role`.

`TriggerActivityPort.offer_case_manager_role` return type: `str` → `tuple[str, dict[str, Any]]`.

PR: <https://github.com/CERTCC/Vultron/pull/1534>

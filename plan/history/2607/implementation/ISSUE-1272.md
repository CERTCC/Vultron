---
source: ISSUE-1272
timestamp: '2026-07-10T14:28:27.163809+00:00'
title: auto_create_case policy gate
type: implementation
---

## Issue #1272 — Add auto_create_case policy flag to ActorConfig and gate create_receive_report_case_tree on it

Added `ActorConfig.auto_create_case: bool = True` (CM-15-001, ADR-0015
Option 3/4) and gated case creation on it at two enforcement points:

- `CheckAutoCaseCreationEnabledNode` BT condition node wired at the root of
  `create_receive_report_case_tree` as `Sequence[gate, Selector[...]]` — the
  gate sits in a Sequence (not the idempotency Selector) so a genuine
  case-creation FAILURE still propagates instead of being masked.
- A routing-level short-circuit in `SubmitReportReceivedUseCase.execute()`
  (analogous to the existing recipient guards) so a deliberate skip logs at
  INFO rather than as a case-creation error; report + Offer are still stored.

Reworded CM-15-001 to specify observable behavior (no case, unchanged outbox)
rather than call path, reconciling a conflict between the issue body (in-tree
gate) and the original spec text ("MUST NOT invoke the tree").

Scope boundary: no production dispatch path resolves a per-actor `ActorConfig`
yet, so the flag is currently reachable only via injected config (unit-tested).
Runtime resolution + vendor seed-config (needed by #1221) tracked in follow-up
issue 1319.

PR: <https://github.com/CERTCC/Vultron/pull/1322>

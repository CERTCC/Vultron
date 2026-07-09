---
source: CONCERN-1275
timestamp: '2026-07-09T18:26:12.840363+00:00'
title: 'Refactor log_entry_event_effects: replace IsNot*/Selector pattern with positive-precondition
  Sequence'
type: learning
---

## Original Concern

The `log_entry_event_effects` Sequence in `create_announce_log_entry_tree()`
(`vultron/core/behaviors/sync/announce_tree.py`) currently uses a
**negative-guard Selector** pattern for each conditional effect:

```text
Selector(IsNotXxxEventNode, ApplyXxxFromLedgerNode)
```

This pattern is hard to follow because:

- Readers must mentally invert the condition to understand when the effect runs.
- `IsNotFoo` naming implies a guard against `Foo`, but the *intent* is to *apply* `Foo`.
- The Selector-short-circuit mechanic is non-obvious unless you know BT semantics cold.

## Resolution

**Processed**: 2026-07-09 — implementation tracked in #1303.
**Docs PR**: <https://github.com/CERTCC/Vultron/pull/1302>
**Spec**: `specs/behavior-tree-node-design.yaml` BTND-08-001, BTND-08-002.
**Notes**: `notes/bt-design-patterns.md` § "Idiom Family Selection Guide".

Decided approach: Option A — replace each `Selector(IsNotFoo, Apply)` with
`Selector(Sequence(IsFooLedgerEntryNode, Apply), AlwaysSuccess("FooSkipped"))`.
Delete old `IsNot*` classes. Add positive `IsXxxLedgerEntryNode` classes.
Add unit tests for the new conditions. No ADR needed; a BTND-08 spec group
captures the positive-precondition idiom rule for future code.

---
title: "Prologue entries have higher log_index than offer_case_manager_role"
type: learning
timestamp: "2026-07-27T00:00:00Z"
source: ISSUE-1688-prologue-ordering
signal: concern
---

## Observation

`WritePrologueLedgerEntriesNode` runs *after* the `CommitCaseLedgerEntryNode`
for `offer_case_manager_role` in the BT sequence. This means prologue entries
(submit_report, create_case, etc.) receive a higher `log_index` than the
`offer_case_manager_role` entry, even though they represent causally earlier
events.

## Impact

The canonical ledger's `log_index` sequence does not match causal order for
the initialization prologue. Any tooling that relies on `log_index` to
reconstruct chronology will see the initialization events appearing *after*
the role-offer entry.

## Why it's acceptable now

The CLP-10-006 ordering constraint requires the guarded `offer_case_manager_role`
commit to run before other effects in the `create_receive_activity_tree()`
sequence. Moving the prologue before the guarded commit would violate CLP-10-006
and potentially leave the ledger without the case-manager-role entry if prologue
fails.

## Potential future fix

A dedicated "prologue phase" that runs before `create_receive_activity_tree()`
— e.g., triggered at case-actor creation time rather than on first role offer —
would allow prologue entries to occupy lower indices. Alternatively, a separate
`causal_timestamp` field on `CaseLedgerEntry` could decouple causal from
append order.

This is worth a Concern issue if log_index-based chronology becomes important
for downstream consumers.

**Promoted**: 2026-07-28 — superseded by ISSUE-1777 (remove WritePrologueLedgerEntriesNode); archived without promotion.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1790>0>0>0>0>0>0>.

---
source: LEDGER-LOGGING-949
timestamp: '2026-06-22T19:34:06.726706+00:00'
title: PersistLogEntryNode tests require log_entry in blackboard
type: learning
---

When testing `PersistLogEntryNode` logging via `bridge.execute_with_setup()`,
pass the `VultronCaseLedgerEntry` as `log_entry=entry` in kwargs — the bridge
writes it to the blackboard before executing the node. The conftest `_make_entry()`
helper builds a ready-to-use entry from a `HashChainLedgerRecord`. Use
`caplog.at_level(logging.INFO, logger="vultron.core.behaviors.sync.nodes.chain")`
to scope capture to just the chain node logger; without scoping, other node
loggers at DEBUG can fill caplog with unrelated records.

**Promoted**: 2026-06-22 — archive only (too specific to one node/test fixture
pattern).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

---
title: "An AC that enumerates the affected sites from the one pattern they share misses every site that reaches the same outcome another way — enumerate from the consumer side instead"
type: learning
timestamp: "2026-09-30T15:30:00Z"
source: ISSUE-3870
signal: theme-candidate
---

ADR-0111 detail 7 and #3870 AC-7 said "the two receive trees that compose
`create_case_manager_gated_tree` directly" were the only ones outside
`create_receive_activity_tree`, and AC-4 asked for factory coverage "with no
exemption list". The count came from grepping the pattern those two shared
(calling the CASE_MANAGER gate themselves). A receive tree can bypass the
factory without that pattern — by being a single node, by hand-building a
Sequence, by being a sync tree that never commits — and thirteen more did.
The first version of the ratchet repeated the mistake at one remove: it
identified receive trees by *name* (`create_.*received.*_tree`) and missed
`create_note_tree` and the three sync trees, which a received use case calls
but does not name as received.

The enumeration that held was the one taken from the consumer: "a tree factory
is receive-side when a module under `vultron/core/use_cases/received/` calls
it." That definition does not care how the tree is built or named, so it
cannot be satisfied by matching the pattern the issue author happened to look
at. The general claim: when an AC or ADR detail states how many sites a rule
covers, derive the set from whoever *uses* the thing, by a corpus query, before
the number goes into the text — a count taken from the producer-side pattern
is a count of the sites that resemble the one the author had open.

Applies at planning time (`plan-issue` writing "the N handlers that …") and at
ratchet-authoring time (any `KNOWN_*` set whose membership test is a name
regex). Second witness wanted: another issue whose site count was derived from
a shared implementation pattern and came up short.

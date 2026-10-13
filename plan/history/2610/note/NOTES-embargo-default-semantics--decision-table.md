---
source: NOTES-embargo-default-semantics--decision-table
timestamp: '2026-10-12T19:34:17.653337+00:00'
title: Decision Table
type: note
---

**Archived:** 2026-10-12
**Reason:** each row is restated as a guidance item or the default-path table
**Superseded by:** notes/embargo-default-semantics.md; EP-04-001..008

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Default embargo → `EM.PROPOSED` or `EM.ACTIVE`? | `EM.ACTIVE` | Report submission without counter-proposal = tacit acceptance per `docs/topics/process_models/em/defaults.md`. |
| Transition path: set directly or go through SM? | Apply PROPOSE+ACCEPT atomically in `InitializeDefaultEmbargoNode` | Keeps SM definition unchanged, preserves all state-machine invariants. |
| Intermediate `PROPOSED` persisted? | No | Atomic transitions; PROPOSED must not be visible externally. |
| What if sender proposes shorter embargo? | Sender's duration → ACTIVE; receiver's default → REVISE | "Shortest embargo wins" rule. |
| What if sender proposes longer embargo? | Receiver's default → ACTIVE; sender's longer → REVISE | Same shortest-wins rule from the other direction. |
| Does the SM need a new NONE→ACTIVE transition? | No | Atomic PROPOSE+ACCEPT inside the node is sufficient. |
| What if *nobody* has a default or proposal? | Protocol default → ACTIVE (EP-04-005) | A case with no embargo is what the EM process exists to avoid; reaching it by mutual silence is the least deliberate route there. ADR-0096. |
| Does the protocol default take part in shortest-wins? | **No** (EP-04-006) | A short default that competed would beat every longer proposal and cap every embargo at its own length. |
| Is the protocol default a minimum on agreed terms? | No (EP-04-007) | It bounds the fallback, not what parties may agree. A 12-hour proposal yields 12 hours. |
| What if the vulnerability is already public? | No embargo; `EM.NONE` (EP-04-008) | VP-06-001 already forbids proposing *or accepting* once P/X/A is set (EMB-01-002 is the accept half). An embargo on a public vulnerability protects nothing. |

---

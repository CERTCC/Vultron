---
title: Embargo Default Semantics — Implementation Notes
status: active
description: >
  Design decisions for embargo policy EP-04 requirements; default embargo
  duration and expiry semantics.
related_specs:
  - specs/case-management.md
  - specs/embargo-policy.md
relevant_packages:
  - transitions
---

# Embargo Default Semantics — Implementation Notes

Design decisions, implementation patterns, and known gaps for
`specs/embargo-policy.md` EP-04 requirements.

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

---

## Implementation: `InitializeDefaultEmbargoNode`

**Current (incorrect)** — sets `EM.PROPOSED`, leaving the case in limbo:

```python
stored_case.current_status.em_state = EM.PROPOSED
```

**Required** — apply both transitions atomically so em_state lands at `EM.ACTIVE`:

```python
from vultron.core.states.em import create_em_machine, EMAdapter, EM

em_machine = create_em_machine()
adapter = EMAdapter(EM.NONE)
em_machine.add_model(adapter, initial=EM.NONE)
adapter.propose()  # NONE → PROPOSED
adapter.accept()   # PROPOSED → ACTIVE
stored_case.current_status.em_state = EM(adapter.state)  # EM.ACTIVE
```

The same `em_machine` + `EMAdapter` pattern is already used in
`vultron/core/use_cases/triggers/embargo.py` for the accept-embargo trigger.

---

## Test Updates Required

Files that assert `EM.PROPOSED` after default-embargo initialization must
be updated to assert `EM.ACTIVE`:

- `test/core/behaviors/case/test_receive_report_case_tree.py` — assertions
  in the `InitializeDefaultEmbargoNode` test class
- Any demo-level integration tests that check the final embargo state after
  case creation (e.g., `test/demo/test_two_actor_demo.py` or similar)

---

## Known Gap: No Reporter Embargo Proposal Mechanism

The current protocol implementation has no mechanism for a reporter to
include an embargo proposal with (or before) a report submission. Until
that mechanism is implemented:

- EP-04-003 cannot be exercised; only EP-04-001 applies at case creation.

Two design paths exist for closing this gap (for future consideration):

1. **Inline proposal**: Reporter includes an embargo duration in the
   `Offer(Report)` payload. This requires a wire-format extension to allow
   an embargo policy or duration field on the offer object.

2. **Pre-negotiation flow**: Reporter creates a case with themselves as the
   sole participant, proposes an embargo to the receiver via the existing
   accept-embargo-before-case-share mechanics, then (optionally) transfers
   case ownership to the receiver upon acceptance. This uses existing
   machinery but is not yet documented as a standard flow.

---

## Protocol Source

The rules specified in EP-04 derive directly from
`docs/topics/process_models/em/defaults.md`:

| Protocol scenario | em_state outcome |
|---|---|
| Receiver has default; sender proposes nothing | `EM.ACTIVE` (EP-04-001) |
| Sender shorter, receiver longer | `EM.ACTIVE` at sender's duration; `EM.REVISE` for receiver's longer (EP-04-003) |
| Sender longer, receiver shorter | `EM.ACTIVE` at receiver's default; `EM.REVISE` for sender's longer (EP-04-003) |

---

## Cross-references

- `specs/embargo-policy.md` EP-04-001 through EP-04-004
- `specs/case-management.md` CM-12-004 (default embargo at case creation)
- `specs/duration.md` DUR-07-003 (default embargo logging)
- `docs/topics/process_models/em/defaults.md` (authoritative protocol source)

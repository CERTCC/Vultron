---
signal: spec-contradiction
source: CONCERN-4445
timestamp: '2026-10-12T13:52:44.853805+00:00'
title: CM-16-010 vs CM-17-006 commit/outbox order
type: learning
---

## Concern

Two case-management specs give opposite orders for the ledger commit and the message it records.

- **CM-16-010** (`kind: protocol` again since #4312): in every step of the actor-suggestion flow, the CASE_MANAGER MUST commit the ledger entry for a protocol event **after** the corresponding message has been sent or received, never before.
- **CM-17-006**: the CASE_MANAGER MUST commit exactly one `CaseLedgerEntry` for an emitted `Invite`, after the Invite is constructed and **before** it is appended to the outbox.

The Invite to a suggested actor is a step of the actor-suggestion flow, so both specs govern it.
The code follows CM-17-006: `test/core/behaviors/case/nodes/test_actor_and_announce_nodes.py::test_invite_has_no_cc_and_is_committed_before_the_outbox_append` (marked CM-17-006) asserts the entry is committed before the outbox append.
No test carries a CM-16-010 marker, and none could honestly: the only nearby assertion contradicts it.

The commit-before-outbox order is the subject of an open review, ADR-0119 ("ledger commit before outbox write", listed as under review in the root `AGENTS.md`).
Whichever way ADR-0119 settles, one of the two specs is wrong and must be rewritten to match; until then an implementer reading the protocol page gets a rule the reference implementation deliberately breaks.

## Asks

1. Settle ADR-0119's commit/outbox order.
2. Rewrite whichever of CM-16-010 / CM-17-006 disagrees, and give CM-16-010 a marker test once it states the decided order.

Found while re-adjudicating specs for #4312 (not blocking it).

Where: specs/case-management.yaml (CM-16-010, CM-17-006)

**Resolved**: 2026-10-12 — absorbed into #4158 (commit after the send reaches the outbox, ADR-0119). ADR-0119 already settles the order: CM-16-010 stands, CM-17-006 is rewritten. #4158's body now lists the CM-17-006 rewrite, the inverted invite emit-node test, and a CM-16-010 marker test as planned acceptance criteria.

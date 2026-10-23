---
source: NOTES-embargo-lifecycle--owner-close-active-embargo
timestamp: '2026-09-17T17:22:59.570069+00:00'
title: 'Owner-Close With an Active Embargo: Decline, Do Not Auto-Tear-Down'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) implemented as DeclineOwnerCloseIfEmbargoed
**Superseded by:** vultron/core/behaviors/case/receive_close_case_tree.py; specs/case-management.yaml CM-23-011; ADR-0085

---

## Owner-Close With an Active Embargo: Decline, Do Not Auto-Tear-Down

**Decision (CONCERN-2955, planning group G06 / #2834):** when the Case Owner
tries to close a case that still holds an **active embargo**, the CASE_MANAGER
**declines the close** rather than closing. It does not silently tear the embargo
down as part of closure.

The problem: owner-close is a hard, global, terminal write boundary (ADR-0085) —
once the owner leaves, "the front door locks" and the CASE_MANAGER accepts no
further external ledger writes. The owner-close path
(`create_close_case_received_tree` → `case_fully_closed`) currently has **no
embargo precondition**, so an owner could close a case out from under an active
embargo, leaving participants under a confidentiality obligation that can never be
discharged through the normal protocol path (no authority remains to lift it).

**Relation to the existing participant-level rules.** The protocol already covers
a *participant* closing/deferring their own report while an embargo is in force,
but only softly and only for the non-terminal case: VP-13-005 (participants
SHOULD NOT close while embargoed), VP-13-007 (a closing participant SHOULD
communicate whether they keep adhering), and VP-13-009 (a participant close
*while other Participants remain engaged* MUST NOT auto-terminate the embargo —
the embargo lives on for the others). Owner-close is the case those rules
explicitly do not reach: it is global and terminal, so there are no "other
Participants" to keep the embargo alive and no authority left to lift it. That is
why the soft participant-level SHOULD_NOT is raised to a hard case-actor MUST
refusal for owner-close specifically (CM-23-011 `refines` VP-13-005).

**The refusal does not terminate the embargo.** Declining the close is *only* a
refusal — it does not tear the embargo down as a side effect. The embargo stays
active until terminated through the normal EM path; only then may the owner
re-issue the close. "Case MUST NOT close while an embargo is live" is the rule —
*not* "case close implies embargo termination."

**Options weighed:**

- **Option A — decline the premature close (chosen).** The CASE_MANAGER refuses the
  owner `Leave(VulnerabilityCase)` while an embargo is active and requires an
  explicit terminate-embargo-then-close ordering. Keeps the closure sequence
  simple and atomic, and makes the embargo teardown a deliberate, auditable act by
  the owner rather than an implicit side effect of leaving.
- **Option B — atomic teardown on close (rejected).** Have close implicitly invoke
  the existing `terminate_active_embargo_tree` / `embargo/nodes/teardown.py` as
  part of `case_fully_closed`. Rejected: it buries a significant protocol event
  (embargo termination, which has its own notifications and downstream effects)
  inside the close path, and couples two lifecycle transitions that are cleaner
  kept explicit.

**How the refusal is expressed:** as an **`as:Reject`** response — "received and
understood but declined" (MSM-05-001). The owner's `Leave` is well-formed and
understood; it is *declined* because the embargo is active. It is therefore **not**
a `Create(ProcessingFault)` (that mechanism is for messages received but *not*
understood). Do not use `TentativeReject` — that verb is reserved for declining an
`Offer` (e.g. embargo RSVP / `INVALIDATE_REPORT`), not for refusing a close.

Normative requirement: `specs/case-management.yaml` **CM-23-011**. Implementation
is tracked as a follow-on Task under Epic #2684.

**See**: `docs/adr/0085-case-lifecycle-boundaries.md`;
`specs/case-management.yaml` CM-23-002 / CM-23-011;
`specs/message-semantics-mapping.yaml` MSM-05-001;
`vultron/core/behaviors/case/receive_close_case_tree.py`.

---
status: accepted
date: 2026-10-01
deciders: Allen D. Householder
consulted: Claude Opus 4.8
informed: []
stakeholder_type: [project-contributor]
---

# Participant Status Is Self-Declaratory, With Narrow Externally-Evidenced On-Behalf Exceptions

## Context and Problem Statement

Vultron's `ParticipantStatus` is intended to be self-declaratory: a participant
reports its own Report Management (RM) and Vendor Fix (VFD) state, and other
parties record what they were told. But two gaps break this model at the edges:

1. **Vendor awareness has no self-report path (CONCERN-2087).** The `v→V`
   (vendor unaware → aware) transition and the `CV` message exist in the design,
   but nothing lets any actor record that a vendor has been made aware. The
   design intent — captured in a 2026-08-07 review — is that whoever notifies a
   vendor, or invites one to a case, MAY assert that the vendor is aware, so a
   vendor can be marked *informed* even if it never joins the case.

2. **There is no stated line between what a participant may assert about
   itself and what requires the Case Owner's authority (part of CONCERN-1752,
   CONCERN-3020).** Role and roster changes clearly need owner approval
   (ADR-0026); individual state transitions clearly do not. But the boundary was
   never written down, so each new assertion path re-litigates it.

The question: **what may a participant assert on its own authority, and which
transitions may a Case Manager or Case Owner assert on another participant's
behalf?**

## Decision Drivers

- Participant status is the mechanism by which participants report *their own*
  state; self-declaration is the default, not the exception.
- Some transitions are externally evidenced — the act of notifying a vendor is
  itself proof the vendor was made aware — and must be recordable even when the
  role-holder never actively participates.
- Some transitions are *not* externally knowable (`f→F`, fix readiness) and must
  never be assertable by anyone but the role-holder, or the Case Actor could
  fabricate protocol-visible fix state.
- Vendor and Deployer are **distinct roles held by distinct actors**; a Vendor is
  never implicitly a Deployer. The `v→V` and `d→D` transitions belong to
  different role-holders.
- Role and roster changes are already owner-authorized (ADR-0026, CM-02-001);
  this decision must not weaken that.

## Considered Options

1. **Strictly self-reported, no exceptions.** Every dimension of
   `ParticipantStatus` is only ever the reporting participant's own claim.
2. **Case Manager / Case Owner may assert any dimension on any participant's
   behalf.** The Case Actor becomes a general proxy for participant state.
3. **Self-declaratory by default, with narrow externally-evidenced on-behalf
   exceptions.** Participants self-report; a Case Manager/Owner MAY assert only
   those transitions that are externally evidenced, on behalf of the specific
   role-holder.

## Decision Outcome

Chosen option: **Option 3 — self-declaratory by default, with narrow
externally-evidenced on-behalf exceptions**, because it preserves the meaning of
participant status as self-declaration while closing the vendor-awareness gap
without letting the Case Actor fabricate state it cannot observe.

### The rules

- **Default: participant status is self-declaratory.** A participant asserts its
  own RM and VFD state; no approval is required. This is why they are
  *participant* status items.
- **On-behalf assertions target existing participants only.** A status
  update never creates a participant; an on-behalf assertion whose target is
  not a participant in the case is refused. Joining a case is the Invite flow
  (ADR-0114), and the Invite is what creates the participant record.
- **`v→V` (vendor aware) MAY be asserted on behalf of a Vendor-role
  participant** by a Case Manager or Case Owner, because the notification event
  is itself observable evidence. Any acknowledgement from the vendor of any
  message sent to it — even a `Read(Invite(stub))` — is sufficient evidence.
  The bump changes VF only, never RM.
- **`d→D` (fix deployed) MAY be asserted on behalf of a Deployer-role
  participant** by a Case Manager or Case Owner under the same
  externally-evidenced pattern, but only in exceptional circumstances (a MAY,
  expected to be rare; for example, a deployer that joined and has since gone
  quiet). Deployment is normally self-reported by the Deployer. The write is
  still subject to the cross-machine entailments, so it succeeds only for a
  deployer whose RM is consistent with deployment.
- **`f→F` (fix ready) is Vendor-only, always self-reported.** It is not
  externally knowable; no on-behalf assertion is ever permitted.
- **Role and roster changes require Case Owner approval** via the existing
  CaseActor-routed Offer/Accept pattern (ADR-0026). Nothing here relaxes that.

### When a vendor participant may be at `v`

A Vendor that has answered its Invite, or that has otherwise acknowledged any
message about the case, is aware of the case. The Invite creates the vendor's
participant record at VF `v` before it has answered (ADR-0114), and that record
is the only place a vendor participant carries `v`. Therefore:

- A Vendor-role participant never self-reports `v`: its only valid VF
  self-reports are `Vf` and `VF`.
- Any reply to the Invite sets `V`.
- The on-behalf `v→V` assertion is the mechanism for recording awareness of an
  invited vendor that has not answered: it targets that inert participant
  record, so the CASE_MANAGER can track pre-join awareness without minting
  anything.

This invariant is enforceable and always an error to violate, so it belongs in
the consolidated rule layer (`vultron/core/predicates/`, CONCERN-3020), not
inline at each assertion site.

### Consequences

- Good: the vendor-awareness gap (CONCERN-2087) closes without a general proxy
  authority for the Case Actor, and without minting participants.
- Good: `f→F` remains unforgeable; only the vendor can claim fix readiness.
- Good: the self-declaratory-vs-owner-authorized boundary is now stated once and
  can be enforced as a rule rather than re-decided per site.
- Neutral: `v→V`/`d→D` on-behalf assertion is a narrow, evidenced exception, not
  a general capability; implementations must scope it to the Case Manager or
  the Case Owner, and to a target already in the case.
- Bad: the Vendor-implies-V invariant must be added to the rule layer and every
  existing Vendor VF assertion site checked against it.

## Validation

- The `v→V` on-behalf assertion path is exercised by a test in which a Case
  Manager records vendor awareness for an invited vendor that has not answered.
- A test asserts an on-behalf assertion for an actor that is not a participant
  is refused and leaves the roster unchanged.
- A rule-layer test asserts a Vendor-role participant cannot self-report a VF
  state with `v` set (valid Vendor VF self-reports ∈ {Vf, VF}).
- A test asserts `f→F` is rejected when asserted by any actor other than the
  Vendor-role holder.
- Spec requirements are amended in `specs/participant-role-management.yaml` and
  the case-management / participant-status specs; the enforceable invariants are
  implemented in `vultron/core/predicates/` per CONCERN-3020.

## More Information

- CONCERN-2833 (planning group G05) — session that produced this decision
- CONCERN-2087 — vendor-awareness self-report gap (source)
- CONCERN-3020 — consolidation of enforceable authority/eligibility rules
- CONCERN-1752 — post-join role-request gap (authority half)
- ADR-0026 — CaseActor-Routed Actor Suggestion and Invitation Flow (role authority)
- ADR-0080 — Asking Permission Is a Protocol Message (owner-approval mechanism)
- ADR-0085 — Case Lifecycle Boundaries (companion decision, close & rejoin)
- ADR-0114 — Joining a case: the Invite creates the participant record
- CONCERN-4006 — the on-behalf `d→D` refusal that scoped on-behalf status to
  existing participants

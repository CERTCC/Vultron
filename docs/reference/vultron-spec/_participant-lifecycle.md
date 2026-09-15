## 11. Participant Lifecycle Within a Case [N]

### 11.1 Role Assignment [N]

Roles are assigned through a defined authority chain. They are not self-declared.

1. A case starts with a **Case Owner** — the actor who initiated the case.
2. The Case Owner MAY delegate the **Case Manager** role to another actor via
   an `Offer(CaseParticipant)` / `Accept` handshake.
3. The Case Manager assigns actors into process roles (Reporter, Vendor,
   Coordinator, Deployer, Observer, CNA) via the case participant management flow.

An actor MUST NOT self-assign a role to a case it did not initiate.
This rule prevents an actor from claiming authority (for example, Coordinator)
on a case it is not ready to coordinate.

An implementation MAY verify that an actor has the capability prerequisites
for a role ([§12.3.1](index.md#1231-process-roles)) before completing a role assignment.

### 11.2 Invitation and Acceptance [N]

- An actor joins a case via `Invite(CaseStub)` from the Case Actor, answered with
  `Accept(Invite)` or `Reject(Invite)`.
- `Accept(Invite)` places the actor at `RM.RECEIVED` and, where an embargo is
  active, implies consent to that embargo ([§9.7](index.md#97-gating-full-case-delivery)).
- The suggest-actor path ([§5.3](index.md#53-activity-types-and-canonical-message-forms), [§4.4](index.md#44-case-coordination-messages)) allows a Participant to recommend an actor
  to the Case Owner. The Case Owner decides whether to issue the invitation.

### 11.3 Case Ownership Transfer [N]

The Case Owner MAY transfer ownership to another actor via
`Offer(VulnerabilityCase)` / `Accept` handshake routed through the Case Actor
(ADR-0053). On acceptance, the receiving actor acquires Case Owner authority and
the associated protocol responsibilities.

!!! note "Open: Case Actor identity during ownership transfer"
    Because the Case Actor URI is the identity anchor for the canonical ledger,
    ownership transfer raises a re-keying question for future cryptographic
    identity designs. See [§12.3.2](index.md#1232-protocol-coordination-roles-protocol-authority) and Open Questions.

### 11.4 Participant Removal [I]

A Case Owner or Case Manager MAY remove a participant from a case.
The protocol mechanics of removal and the effect on active embargo consent
are not yet fully specified.

!!! info "See also"
    - `specs/case-management.yaml`
    - `notes/ownership-transfer.md`

---

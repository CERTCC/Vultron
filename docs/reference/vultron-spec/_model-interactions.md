## 10. Model Interactions and Cascade Rules [N]

State transitions in one dimension trigger obligations in others. Cascades are
event-driven: a state change produces a domain event, which the Case Actor
handles. Each cascade step is independently authorizable, and ordering between
steps is normative where noted.

Key cascades:

- **Invitation accepted → admit, resolve consent, deliver**: on `Accept(Invite)`
  the Case Actor MUST, in order, (a) commit a ledger entry and fan it out,
  (b) create the participant record at `RM.RECEIVED`, (c) sign embargo consent if
  an embargo is active, (d) send `Announce(VulnerabilityCase)` with the full
  snapshot, and (e) backfill prior ledger entries in log-index order. The
  ordering of (b)–(d) is load-bearing ([§9.7](index.md#97-gating-full-case-delivery)).
- **EM enters `REVISE` → bulk PEC lapse**: all participants currently at PEC
  `SIGNATORY` MUST be transitioned to `LAPSED`.
- **EM exits → PEC reset**: all participants' PEC machines MUST be reset to
  `NO_EMBARGO`.
- **PXA observation adopted → embargo teardown**: canonical adoption of any
  status carrying `CS.P`, `CS.X`, or `CS.A` MUST trigger embargo teardown
  evaluation ([§10.1](index.md#101-status-adoption-the-two-seam-model), EmbargoTeardownAuthorizationGate).
- **Embargo teardown → state replication**: termination of an active embargo
  SHOULD produce a fresh `Announce(CaseLedgerEntry)` to all participants.

### 10.1 Status Adoption: The Two-Seam Model

A reported status becomes canonical case state through two independent
authorization seams. This structure exists because "record what a participant
claimed" and "act on that claim as truth" are separate decisions with separate
authority.

**StatusAdoptionGate — Adoption.** A participant reports an observation via
`Add(ParticipantStatus)`. The receiving Case Actor records the claim, then
decides whether to treat it as canonical:

- A Case Owner's report MUST be adopted without requiring approval — requiring
  the Case Owner to approve its own report would be circular ([§12.4.4](index.md#1244-case-owner-authority)).
- All other senders pass through a configurable approval gate. The default
  policy is to auto-adopt.
- On adoption, the Case Actor emits a self-addressed `Add(CaseStatus)` to itself
  acting as Case Manager, which performs the canonical write.
- The tree that records the claim MUST NOT execute side-effects directly.

**EmbargoTeardownAuthorizationGate — Side-effects.** After the canonical write,
the Case Actor evaluates side-effects:

- It MUST check whether the canonical status carries `CS.P`, `CS.X`, or `CS.A`.
- If any is present, it MUST initiate embargo teardown.
- **This check MUST run after the canonical write, never before.**
- A second configurable gate MAY require approval before executing teardown;
  the default is to proceed.

The seams are deliberately independent: the adoption decision knows nothing about
teardown, and the side-effects decision cannot tell whether the canonical write
originated in an external message or an internal self-emit. That independence is
what lets either be re-policied without touching the other.

!!! note "Where the gate model applies"
    StatusAdoptionGate governs *any* reported status, but its authorization
    question is most consequential for participant-agnostic (PXA) observations,
    where any participant may report ([§12.4.2](index.md#1242-participant-agnostic-cs-transitions-pxa)) — including reports about *other*
    participants. The default auto-adopt policy means an unapproved third-party
    assertion becomes canonical unless an implementation configures otherwise.

!!! info "See also"
    - `specs/received-status-handling.yaml` RSH-01-001 through RSH-03
    - ADR-0046
    - `notes/received-status-authorization.md`
    - `notes/protocol-event-cascades.md`

---

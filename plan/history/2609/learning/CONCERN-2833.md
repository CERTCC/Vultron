---
signal: design-question
source: CONCERN-2833
timestamp: '2026-09-02T17:45:13.742847+00:00'
title: 'G05: Authority and roster lifecycle — planned'
type: learning
---

Planning group **G05** of 19. Parent: #2828 — read its body for the planning protocol that applies to every group (umbrella-is-not-a-defect-claim, Tasks parent to the domain epic, nothing closes before it is in `origin/main`, lose nothing).

**Members**: #1752, #1894, #1902, #1918, #2087, #2534, #1673, #2794, #3020, #2961
**Domain epics for Tasks**: #2685 (authority model), #2687 (participant lifecycle & roster), #607 (docs)
**Blocked by**: G01.

## Why these are grouped

One theme: **who may assert what, and what changes after a participant joins or a case
closes.** Members currently split across #2685 and #2687, which is an artificial cut —
they are two halves of one authority model.

Note honestly: this group has two sub-clusters (post-join role
changes: #1752, #1918, #2087; close semantics: #1894, #1902). If the
interview shows they do not share a decision, splitting into two Task
sets is fine — but assess that *after* reading all eight, not before.

## Blocked by G01

The Offer/Accept/Reject authorization round-trip (**#2812/#2809 are owned by G01 — do
not close them here**). This group's authority rules must be expressible with whatever
gate mechanism G01 defines.

## Members

- **#1752 — no mechanism for a participant to request additional roles after joining.**
  Tier `Next`.
- **#1894 — post-owner-close message boundary is unspecified: is close a kill switch, a
  selective gate, or unconstrained?** Tier `Next`.
- **#1902 — report-phase closure (`SvcCloseCaseUseCase`) is unreachable; the
  non-auto-create-case branch needs designing.**
- **#1918 — rejoin semantics for departed case participants.**
- **#2087 — CV (vendor aware) has no self-report path: the design intends
  sender-asserted vendor awareness, the implementation has none.**
- **#2534 — `CreateAndPersistCaseActivityNode`: `create_case_addressees` port call lacks
  a `NoDataAvailable` guard.** Smallest member; a concrete defect the authority model
  explains.
- **#1673 — actor-level production policy configuration for call-out points.** The
  configuration surface through which authority policy is actually expressed.
- **#2794 — [Docs/Explanation] Case Actor authority, trust bootstrap, and routing
  model.** Folded in: it documents exactly what this session decides.
- **#3020 — authority rules written in many places instead of one: no single place to
  read a rule or ask whether an action is authorized for a role.** Maps directly to the
  authority model this session consolidates; the fragmentation it names is what the ADR
  output eliminates.
- **#2961 — SYNC-00-007/008: proactive gap detection absent — per-peer
  `VultronReplicationState` exists but is never swept for lagging replicas.** Weak fit;
  included because authority over which actor initiates replication repair touches the
  authority model. Triage during session: if it does not share the authority-model
  decision, spin it out as a standalone Task under the SYNC epic.

## Desired output

- **One ADR** on the authority model: what a participant may assert about itself versus
  what requires owner approval; whether roles are requestable post-join and how; what
  close means for inbound and outbound messages; rejoin rules.
- Spec amendments in the case-management / participant-lifecycle files.
- `docs/` explanation page for #2794.
- Task set parented to #2685 / #2687.

## Constraints

- ADR-0076's conservative default (deny unless owner-approved) is the baseline. Any
  loosening must be argued explicitly.
- #1752 and #1894 are `Next` tier — if the session's ADR grows, make sure those two get
  Tasks that can proceed independently.

## Acceptance criteria

- [ ] AC-1: An ADR records the authority model: self-assertable vs owner-approved,
      post-join role requests, close semantics, rejoin rules.
- [ ] AC-2: A verdict on whether the two sub-clusters share one decision or need
      splitting, decided after reading all eight members.
- [ ] AC-3: #1752 and #1894 have Tasks that can proceed independently of the full ADR.
- [ ] AC-4: Spec amendments drafted for case-management / participant-lifecycle.
- [ ] AC-5: `docs/` explanation page written for #2794.
- [ ] AC-6: Tasks parented to #2685 / #2687; #2812/#2809 referenced, not closed.
- [ ] AC-7: #2961 triaged — either its replication-gap question shares the authority ADR
      or it is spun out as a standalone Task under the SYNC epic.

---

**Resolved**: 2026-09-02 — planned into two ADRs and seven implementation issues.

**Decisions (ADR-0084, ADR-0085):**

- Participant status is self-declaratory by default. `v→V` (Vendor) and `d→D`
  (Deployer) MAY be asserted on-behalf by a Case Manager/Owner when externally
  evidenced; `f→F` is Vendor-only. Vendor-participation-implies-`V` invariant
  (valid Vendor VF ∈ {Vf, VF}); on-behalf `v→V` is scoped to pre-join awareness.
- Role/roster changes need Case Owner approval (ADR-0026 pattern).
- Owner-close is a hard write boundary: after the closure `Announce`, no new
  external ledger writes. `RM.CLOSED` is terminal; rejoin unsupported, with
  defer-not-close as the workaround. Reopen is owner-only (mechanics deferred).
- Auto-create-case is an implementation choice, not a protocol requirement (#1902).

**Sub-cluster verdict (AC-2):** two distinct decisions sharing one through-line —
assertion authority (ADR-0084) and lifecycle boundaries (ADR-0085).

**Implementation issues:** #3057, #3058 (epic #2685); #3059, #3060, #3061, #3062
(epic #2687); #3063 (epic #607).

**Deferred to Ideas under Epic #2567:** `Update(CaseParticipant)` role-change
message; case reopen mechanics.

**Triaged out:** #2961 (SYNC gap detection — stays under epic #1158); #1673
(production policy config — out of scope).

Docs PR: <https://github.com/CERTCC/Vultron/pull/3056>.
ADRs: docs/adr/0084-participant-assertion-authority.md,
docs/adr/0085-case-lifecycle-boundaries.md.

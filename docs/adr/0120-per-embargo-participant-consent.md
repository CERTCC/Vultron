---
status: accepted
date: 2026-10-06
deciders: Allen D. Householder
consulted: >-
  Claude Sonnet 5.5; Issue #4178, Concern #3884, Issue #4153, PR #4002;
  ADR-0048, ADR-0056, ADR-0091, ADR-0093, ADR-0113, ADR-0118;
  specs/case-management.yaml CM-10, CM-18; specs/message-semantics-mapping.yaml MSM-07;
  specs/embargo-policy.yaml EP-05, EP-09
informed: []
supersedes: 0056-embargo-adherence-computed-field.md
stakeholder_type: [project-contributor]
---

# Participant Embargo Consent Is Recorded per (Participant, Embargo)

## Context and Problem Statement

Participant embargo consent was a hybrid of two records (ADR-0093, ADR-0118).
`CaseParticipant.accepted_embargo_ids` listed every embargo, active or proposed, the participant had accepted.
One scalar PEC state (`UNBOUND`, `INVITED`, `SIGNATORY`, `LAPSED`, `DECLINED`, `EXPIRED`, `UNBOUND_EXITED`) answered a single question: is the participant bound by the *active* embargo?
The content gate (CM-10-004) read the scalar.

The two records disagreed (Concern #3884).
Three reconciliation rules kept them in step:

1. activating a revision that ends later lapsed every signatory whose list lacked it;
2. activating any embargo advanced every non-signatory whose list already held it;
3. terminating the embargo exited every record to `UNBOUND_EXITED`.

MSM-07-003 added a special case on top: an Accept of a *first proposal* advanced the acceptor at accept time, while an Accept of a *revision* only wrote the list (PR #4002).
The maintainer ruled the hybrid a model mismatch.
The question: **what single record should hold a participant's consent, so that "bound by the active embargo", "lapsed" and "exited" are read rather than reconciled?**

## Decision Drivers

- One fact, recorded once: two records of the same consent can disagree, and did.
- A first-proposal Accept and a revision Accept say the same thing (the acceptor agrees to the embargo named) and should be handled the same way.
- The content gate (CM-10-004) must keep answering "is this participant bound by the embargo in force?" exactly.
- EP-05 containment (agreeing to N days is agreeing to every shorter period) must still carry a signatory over to a shorter revision without a fresh Accept.
- Prototype stores only: no migration is owed (AGENTS.md persistence rule, as instructed on #4178).

## Considered Options

- Keep the hybrid: the scalar plus `accepted_embargo_ids`, with the reconciliation rules.
- Make the list authoritative and drop the scalar, keeping no per-embargo state beyond acceptance.
- Record consent per (participant, embargo) as rows, and derive the rest.

## Decision Outcome

Chosen option: "Record consent per (participant, embargo) as rows, and derive the rest", because it is the only option that states each answer once.

### The model

`CaseParticipant.embargo_consents` holds one `EmbargoConsent(embargo_id, state)` row for each embargo the participant was asked about.
A row is `INVITED`, `ACCEPTED`, `DECLINED` or `EXPIRED` (`EXPIRED` is ADR-0118's unanswered invitation, kept distinct from a refusal).
No row means the participant was never asked.

| Trigger | Source row | Destination |
|---|---|---|
| `INVITE` | none, `DECLINED`, `EXPIRED` | `INVITED` |
| `ACCEPT` | none, `INVITED`, `EXPIRED` | `ACCEPTED` |
| `DECLINE` | none, `INVITED`, `ACCEPTED`, `EXPIRED` | `DECLINED` |
| `EXPIRE` | `INVITED` | `EXPIRED` |

Everything else is derived from the rows and the case:

- **Signatory** — the row for the case's active embargo is `ACCEPTED`.
- **Lapsed** — the participant holds an `ACCEPTED` row for another embargo and no accepting (or declining) row for the active one.
- **Exited** — the case's EM state is `EXITED` and it has no active embargo, so nobody is a signatory.
- **Content gate** — CM-10-004 reads `participant.is_signatory(case.active_embargo_id)` when an embargo is in force.

`ParticipantStatus.consent` and the computed `embargo_adherence` are removed: they were projections of the scalar, and the scalar no longer exists.
The retired wire keys (`emConsentState`, `embargoAdherence`, `embargoConsentState`, `acceptedEmbargoIds`) are refused inbound by name (MV-11).

### What the lifecycle does now

- **Accept** always marks the accepted embargo's row `ACCEPTED`, whether it is the embargo in force, a first proposal, or a proposed revision. The first-proposal special case disappears.
- **Reject** of the active embargo is withdrawal: that row, and every open proposal's row the participant had accepted, become `DECLINED`. Reject of a proposed embargo declines that row only. The owner's EJ writes nothing.
- **Propose** marks the proposer's row for the proposed embargo `ACCEPTED`.
- **Activation** of B replacing A marks B's row `ACCEPTED` for the owner, and, when B ends no later than A, for every participant whose row for A is `ACCEPTED` (containment, EP-05-001). A longer B writes nothing: non-accepters have lapsed by derivation. A first activation writes nothing.
- **Termination** writes nothing. `ExitParticipantConsentNode` and the exit cascade are deleted.
- **A relayed revision Invite** lands on the revision's own row, so a signatory keeps its `ACCEPTED` row for the active embargo (EP-09-004 stops being a special-cased no-op).
- **Expiry** expires every still-`INVITED` row of the participant, since one RSVP deadline attaches to its outstanding invitation.

### Consequences

- Good, because consent has one record; "bound" and "lapsed" cannot disagree with it, and the three reconciliation rules and the MSM-07-003 special case are deleted.
- Good, because the lapse and exit cascades, which ran only where the lifecycle ran, no longer need to reach every replica: a replica derives the same position from the rows it already replays.
- Good, because a consent history survives: rows for superseded embargoes remain after a revision or termination.
- Bad, because the rows grow by one per embargo a participant is asked about, and are never pruned.
- Bad, because the ledger report (DRPT) loses its per-participant PEC column; consent is no longer carried in `ParticipantStatus` snapshots, so there is nothing in them to extract (DRPT-02-008, -014 and -015 are removed).
- Bad, because stored `CaseParticipant` records carrying `embargo_consent_state` or `accepted_embargo_ids` no longer load (`extra="forbid"`); the prototype keeps no migration.

### Effect on earlier decisions

- ADR-0056 (`embargo_adherence` computed from PEC) is superseded: there is no scalar to derive it from.
- ADR-0048 (absence of embargo is not pre-consent) stands, now as "no row".
- ADR-0091 (`NO_EMBARGO` → `UNBOUND`) is overtaken: `UNBOUND` is no longer a state.
- ADR-0093 (`DECLINE` legal from `SIGNATORY`) stands as `DECLINE` from an `ACCEPTED` row, and its "lapse at activation, never at proposal" rule stands as a derivation.
- ADR-0118 is superseded in its `UNBOUND_EXITED` half (termination is the case's fact); its `EXPIRED` half stands as a row state, as do its decisions 3 and 4.
- ADR-0113 (relay through the CASE_MANAGER) is unchanged; its consent references now mean rows.

## Pros and Cons of the Options

### Keep the hybrid

- Good, because nothing changes.
- Bad, because it is the design that produced Concern #3884 and needs three reconciliation rules plus a special case to stay coherent.

### List authoritative, scalar dropped

- Good, because there is one record.
- Bad, because the list records only acceptance: it cannot say `DECLINED` versus `EXPIRED` versus never asked, so those would need a second record again.

### Rows per (participant, embargo)

- Good, because each answer, including the refusals and expiries the list could not hold, is stated once.
- Good, because "signatory" and "lapsed" are lookups over the same rows.
- Bad, because every reader of the former scalar had to be revisited.

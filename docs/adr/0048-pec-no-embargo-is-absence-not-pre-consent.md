---
status: accepted
date: 2026-07-31
deciders: [adh, Claude Opus 5]
---

# ADR-0048: PEC `NO_EMBARGO` Means Absence of Embargo, Not Pre-Consent

## Context and Problem Statement

The Participant Embargo Consent (PEC) state machine
(`vultron/core/states/participant_embargo_consent.py`) defines `NO_EMBARGO` in
its own docstring as "No embargo is in scope for this participant" — an
*absence-of-context* state. Its transition table, however, treats `NO_EMBARGO`
as a *pre-consent* state: the only way out is `INVITE`, so consent can only ever
be reached via `NO_EMBARGO → INVITED → SIGNATORY`.

These two readings contradict each other, and the transition table's reading is
wrong. Consent does not always arrive through an invitation:

1. **Self-determined embargo.** A Finder who creates a case for their own
   finding and sets its default embargo is not invited by anyone. There is no
   counterparty to issue an `Invite`.

2. **Embargo created with the case.** Under ADR-0041, the CaseActor initializes
   the default embargo during case initialization, in the same BT sequence that
   adds the vendor (CASE_OWNER) and reporter participants. From the moment those
   participants exist, an embargo is already in scope for them — so there is no
   instant at which `NO_EMBARGO` is a truthful description of their position.

3. **Implicit consent (CM-14-005).** The reporter's consent is expressed by
   submitting the report. The spec requires they be seeded `SIGNATORY`; no
   invitation is ever sent.

Forcing these paths through `INVITED` requires fabricating an invitation event
that never occurred, and writing it into the canonical case ledger as though it
had.

The contradiction is already causing a silent MUST-level failure in production
code. `_SignEmbargoConsentLeafNode`
(`vultron/core/behaviors/case/accept_invite_tree.py:493`) calls:

```python
participant.embargo_consent_state = apply_pec_trigger(
    PEC.NO_EMBARGO, PEC_Trigger.ACCEPT
)
```

`apply_pec_trigger` rejects this transition, logs a warning, and returns
`NO_EMBARGO` **unchanged** — and the node then logs "signed embargo consent for
invitee" and returns `SUCCESS`. A participant who accepts an invitation to an
embargoed case is recorded as having never consented, violating CM-10-001. The
author of that node clearly expected `NO_EMBARGO → SIGNATORY` to be legal; the
FSM silently disagreed.

A second, related defect motivates the same fix. Three sites seed consent by
assigning the scalar field directly
(`case_proposal_received_tree.py:873`, `nodes/embargo.py:433`,
`nodes/participant/participant_add.py:389`):

```python
participant.embargo_consent_state = PEC.SIGNATORY
```

This is a plain Pydantic field write. It does not call
`_sync_latest_status_metadata()`, so the participant's existing
`ParticipantStatus` retains `consent.state = NO_EMBARGO`. The resulting ledger
snapshot is internally contradictory — verified directly:

```text
participant.embargo_consent_state = SIGNATORY
snapshot: {"embargoAdherence": true, "emConsentState": "NO_EMBARGO"}
```

The correct machinery to prevent this already exists and is simply unused:
`ParticipantStatus.consent` is a `PecDimension` (ADR-0036, SDO-01-001), and
`PecDimension.transition()` performs fail-closed FSM validation, raising
`VultronInvalidStateTransitionError` on an illegal trigger.

The question is: **is `NO_EMBARGO` an absence-of-embargo state or a
not-yet-consented state, and what follows for the transition table and for
case-initialization ledger entries?**

## Decision Drivers

- The PEC docstring's own definition of `NO_EMBARGO` should be authoritative
- The ledger MUST NOT record protocol events that did not occur (ADR-0019)
- Single-actor and self-determined-embargo cases must be representable without
  fiction
- Consent writes should be fail-closed, validated by the dimension object
- Avoid `log_index` churn: PR #1746 was reverted for shifting ledger indices and
  breaking `fvcv-extension` VFD replication timing

## Considered Options

1. **`NO_EMBARGO` is absence of embargo** (chosen): add
   `ACCEPT: NO_EMBARGO → SIGNATORY` and `DECLINE: NO_EMBARGO → DECLINED`.
   Consent may be reached directly when no invitation mediates it. `NO_EMBARGO`
   retains its meaning for participants in a case with no embargo (`EM.NONE`)
   and as the `RESET` destination.

2. **`NO_EMBARGO` is pre-consent; synthesize the invitation**: keep the table as
   is and emit `NO_EMBARGO → INVITED → SIGNATORY` at initialization, writing a
   synthetic `INVITED` entry for participants nobody invited. Rejected: it
   records a protocol event that never happened, contradicting ADR-0019, and it
   doubles per-participant initialization entries — reintroducing exactly the
   `log_index` shift that got PR #1746 reverted.

3. **Add a distinct `SELF_CONSENT` trigger**: introduce a separate trigger for
   `NO_EMBARGO → SIGNATORY`, reserving `ACCEPT` for invitation responses.
   Rejected: the trigger name is not carried in the ledger entry, so the
   distinction is invisible to every downstream consumer while adding a second
   code path to keep correct. The state reached is identical either way.

## Decision Outcome

**Chosen option: `NO_EMBARGO` means absence of embargo (Option 1).**

### Transition table changes

Two transitions are added to `_transitions`:

```text
ACCEPT  : NO_EMBARGO | INVITED | LAPSED → SIGNATORY
DECLINE : NO_EMBARGO | INVITED | LAPSED → DECLINED
```

`DECLINE` is added for symmetry: a participant added to an already-embargoed
case must be able to refuse the terms without a formal invitation, or the same
invitation fiction returns on the refusal path.

Unchanged: `INVITE` (`NO_EMBARGO | LAPSED | DECLINED → INVITED`), `REVISE`
(`SIGNATORY → LAPSED`), `RESET` (`* → NO_EMBARGO`). CM-18-004 still holds —
`SIGNATORY → INVITED` remains invalid.

### `NO_EMBARGO` keeps a real meaning

This does not make the state vestigial. It is correct for a participant in a
case with no embargo in scope (`EM.NONE`), and it remains the `RESET`
destination when an embargo is terminated. The `RESET` semantics are in fact
independent evidence for the absence reading: `RESET` fires when the embargo
goes away, not when consent is pending.

### Case initialization: embargo first, one entry per participant

Because consent can now be reached in a single transition, case initialization
orders embargo setup **before** participant consent state is fixed, so each
participant's single initialization `ParticipantStatus` carries its true PEC
value. Consequences:

- One `Add(ParticipantStatus)` per participant at initialization — no
  `NO_EMBARGO` placeholder entry followed by a correction
- **No `log_index` shift**, so the PR #1746 revert risk does not apply
- `Add(ParticipantStatus)` remains the correct ledger entry type for a consent
  change; no new event type is needed

### Consent writes go through the dimension object

Consent MUST be set by applying a PEC trigger via `PecDimension.transition()`
and appending/syncing the resulting `ParticipantStatus`, never by assigning
`participant.embargo_consent_state` directly. A shared helper replaces the three
divergent seed sites (CS-22-001).

### Consequences

- Good, because a MUST-level silent failure (CM-10-001, invitation acceptance
  never recording consent) is fixed at its root
- Good, because single-actor and self-determined-embargo cases become
  representable without fabricated invitation events
- Good, because ledger snapshots stop contradicting themselves
  (`embargoAdherence: true` with `emConsentState: NO_EMBARGO`)
- Good, because consent writes become fail-closed regardless of upstream BT
  guard coverage
- Bad, because the PEC machine no longer enforces "consent implies a prior
  invitation". That invariant was never true of self-determined embargoes, so
  the enforcement was spurious — but code that relied on it must be re-checked
- Bad, because `NO_EMBARGO` now has two legitimate readings in context (no
  embargo in scope vs. embargo in scope, position not yet recorded); CM-18-001's
  "`NO_EMBARGO` (initial)" gloss is amended to state the absence semantics
  explicitly

## Validation

- Unit tests asserting `ACCEPT` and `DECLINE` succeed from `NO_EMBARGO`, and
  that `SIGNATORY → INVITED` still fails (CM-18-004)
- A regression test for `_SignEmbargoConsentLeafNode` asserting the invitee
  reaches `SIGNATORY` — this test fails on current `main`
- A test asserting the initialization ledger snapshot's `emConsentState` matches
  the participant's `embargo_consent_state`, with no contradictory
  `embargoAdherence`
- A test asserting exactly one `add_participant_status_to_participant` entry per
  participant at initialization, guarding against `log_index` regrowth

## More Information

- Supersedes the transition table established for CM-18-003 (amended alongside
  this ADR), and amends the CM-18-001 `NO_EMBARGO` gloss
- Builds on ADR-0036 (dimension objects) and ADR-0041 (CaseActor-authoritative
  case initialization)
- Source: Issue #1714, reframed. The issue originally requested prologue
  back-fill PEC entries; ADR-0041 and Issue #1777 removed the prologue
  back-fill, so the requirement was retargeted to the native initialization path
- Related: CM-14-005 (reporter seeded `SIGNATORY`) is unimplemented —
  `_AddReporterParticipantNode` hardcodes `PEC.NO_EMBARGO`
- Generated spec requirements: `case-management.yaml` CM-18-005 through
  CM-18-007 (CM-18-001 and CM-18-003 amended)
- Notes: `notes/participant-embargo-consent.md`,
  `notes/case-ledger-authority.md`

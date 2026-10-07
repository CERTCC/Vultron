---
source: CONCERN-4284
timestamp: '2026-10-07T16:05:04.360821+00:00'
title: 'Per-embargo consent and the embargo register: the case is a projection of
  its ledger'
type: learning
---

## Summary

This started as a docs task: bring `docs/` into line with ADR-0122 (per-embargo participant consent, #4178).
Comparing the docs, the ADR, epic #4208 and the code showed that the implementation needs to change before the docs can describe it.
This issue now records what we found and the design decided in the maintainer's grilling session of 2026-10-07.
The implementation issues under epic #4283 trace back to it.

## What was found

1. **The docs combine two models.** The formal spec page (`docs/reference/vultron-spec/_pec-state-machine.md` §9.2–9.6) and `docs/topics/process_models/em/pec_state_machine_diagram.md` still define the retired seven-state machine (`UNBOUND`, `SIGNATORY`, `LAPSED`, `UNBOUND_EXITED`, …) with its transitions.
   PR #4267 added a paragraph calling those states "derived" but did not replace them.
2. **The code implements the row machine #4178 asked for.** Its states are `INVITED`, `ACCEPTED`, `DECLINED` and `EXPIRED` per (participant, embargo), and it has a real transition table (`vultron/core/states/participant_embargo_consent.py`).
   However, "not asked" is modelled as a missing row.
   The derived positions (signatory, lapsed, exited) can overlap.
   `has_lapsed()` has no caller outside tests.
3. **Replicas recompute consent instead of replaying it.**
   - No ledger entry carries consent rows. Each replica re-runs `EmbargoLifecycle` against its own copy.
   - Five consent writes never reach a replica:
     - the inert invitee's `INVITED` row
     - the inert invitee's `DECLINED` row when it rejects the stub Invite
     - the CASE_MANAGER's own policy-based accept or decline of a proposal
     - the joiner's signature on the active embargo when it accepts the full-case Invite
     - the shorter-revision carry-over at activation, on some paths
   - Only termination has a test that compares the CASE_MANAGER's rows with a replica's.

   This overturns ADR-0122's premise that replicas "derive the same position from the rows they already replay".
4. **The case has no record of past embargoes.** Superseded, rejected and terminated embargoes disappear from the case.
5. **The EM transition table loses an open proposal.** Rejecting one of two open proposals takes EM to `NONE` (or from `REVISE` to `ACTIVE`) while the other proposal is still open.
6. **No code acts on an embargo's end time**, although EMB-11-002 and VP-04-001 assume embargoes expire.
7. **The owner's activation shares its activity with every participant's consent.** `Accept`/`Reject(Invite(EmbargoEvent))` changes meaning depending on the sender (MSM-07-003/004).
   Separately, `Add(EmbargoEvent, target=Case)` sets the active embargo with no CASE_MANAGER gate.

## Decisions

### Participant Embargo Consent (PEC), one row per (participant, embargo)

- **States:** `UNINVITED`, `INVITED`, `AGREED`, `DECLINED`, `TIMED_OUT`.
  - `ACCEPTED` → `AGREED`: avoids `RM.ACCEPTED`, and fits implicit agreement (reporter seeding, the proposer, carry-over).
  - `EXPIRED` → `TIMED_OUT`: the invitation timed out; the embargo did not expire.
- **Every row is written.** Each participant has a row for every embargo in the embargo register: written `UNINVITED` when an embargo is proposed (for every current participant) and when a participant record is created (for every embargo already in the register).
  A missing row is a defect, and `consent_for()` raises.
- **Late joiners** stay `UNINVITED` on embargoes that are no longer in force; they are invited only to the active embargo and to open revisions.
- **Triggers:** `INVITE`, `AGREE`, `DECLINE`, `TIME_OUT`, `CARRY_OVER`.

  ```text
  UNINVITED → INVITED | AGREED | DECLINED
  INVITED   → AGREED | DECLINED | TIMED_OUT
  AGREED    → DECLINED
  DECLINED  → INVITED
  TIMED_OUT → INVITED | AGREED | DECLINED
  CARRY_OVER: any state except AGREED → AGREED
  ```

- **`CARRY_OVER`:** when a revision that ends no later than the embargo it replaces becomes active, every participant that agreed to the replaced embargo is moved to `AGREED` on the revision, including one that declined it as a proposal (EP-05-001 containment: agreeing to N days is agreeing to every shorter period).
  The decline stays in the ledger.
  `AGREE` itself still refuses `DECLINED`.
- **Frozen rows:** rows for an embargo in a final register status (`SUPERSEDED`, `REJECTED`, `CANCELLED`, `TERMINATED`) accept no trigger.
  A late Accept of stale terms gets a fresh invite to the current embargo.
- **"Signatory" and "lapsed" are named derived booleans, not states.**
  - **Signatory:** the row for the `ACTIVE` embargo is `AGREED`.
  - **Lapsed:** the participant has an `AGREED` row for some `SUPERSEDED` embargo, an embargo is `ACTIVE`, and the participant's row for it is neither `AGREED` nor `DECLINED`.
  - After termination, nobody is either.

### Embargo register (on the case)

- **What it is:** an append-only record of every embargo proposed on the case: `VulnerabilityCase.embargo_register`, with entries `(embargo_id, status, replaces)`.
  The case is the folder for everything that happened in its lifecycle.
- **Statuses:** `PROPOSED`, `ACTIVE`, `REJECTED`, `SUPERSEDED`, `CANCELLED`, `TERMINATED`.
  `PROPOSED` and `ACTIVE` keep the glossary's *Proposed Embargo* and *Active Embargo* meaning.
  The EM states use the same words for an aggregate over every register entry, so prose always qualifies them as "`EM.ACTIVE`" or "register status `ACTIVE`".
- **Triggers:**

  | Trigger | Change |
  |---|---|
  | `PROPOSE` | new → `PROPOSED` |
  | `ACTIVATE` | `PROPOSED → ACTIVE` |
  | `REJECT` | `PROPOSED → REJECTED` |
  | `SUPERSEDE` | `ACTIVE → SUPERSEDED`, in the same step as another embargo's `ACTIVATE` |
  | `TERMINATE` | `ACTIVE → TERMINATED`, with reason `END_TIME_REACHED`, `EARLY` or threat signal |
  | `CANCEL` | `PROPOSED → CANCELLED` |

- **Invariants:**
  1. At most one `ACTIVE` and at most one `TERMINATED`, never both.
  2. A `SUPERSEDED` entry needs exactly one `ACTIVE` or `TERMINATED` entry.
  3. `CANCELLED` means closed with no owner decision because the embargo question became moot: by termination, or by a threat signal (`P`/`X`/`A`) while no embargo was active (today's EMB-16-001 "abandon").
  4. Once an entry is `TERMINATED`, nothing can be added or changed.
- **EM is derived from the register.** The EM transition table and `EMAdapter` are retired.

  | ACTIVE | PROPOSED | TERMINATED | EM |
  |---|---|---|---|
  | 0 | 0 | 0 | `NONE` |
  | 0 | ≥1 | 0 | `PROPOSED` |
  | 1 | 0 | 0 | `ACTIVE` |
  | 1 | ≥1 | 0 | `REVISE` |
  | 0 | 0 | 1 | `EXITED` |

### Wire

- **Owner decisions:** the owner's activation and rejection become `Accept(EmbargoEvent, target=Case)` and `Reject(EmbargoEvent, target=Case)`.
  `Accept`/`Reject(Invite(EmbargoEvent))` is always a participant's own consent, the owner's included.
  The two-audience rule (MSM-07-003/004) and the direct `Add(EmbargoEvent, target=Case)` activation are retired.
- **Termination:** `Remove(EmbargoEvent, target=Case)` carries the reason in `content` as exactly `END_TIME_REACHED` or `EARLY`, checked at the parse edge.
  `summary` carries human text.
  Replay refuses `END_TIME_REACHED` when the entry is dated before the embargo's end time.
  The threat reason comes from the case status entry that caused it.
- **End-time termination** comes from the CASE_MANAGER's lazy check or from a Sentinel request.
  Both use one idempotent termination path that runs the full cascade: `TERMINATED`, open proposals `CANCELLED`, EM `EXITED`, and the teardown announcement.

### The case is a projection of its ledger

- **The ledger and the case are transformations of each other.** Replaying a case's complete ledger from empty must rebuild a faithful case.
- **Ledger entries are the protocol messages themselves** (invites, accepts, rejects, proposals, terminations).
  State is derived by replaying them.
- **One pure replay function, used by the CASE_MANAGER and by every replica.** It depends only on the entry and the state before it: no clock, no local policy.
  Every change to case state is caused by a committed entry.
  - The CASE_MANAGER's local policy decisions are committed as its own `Accept`/`Reject`.
  - Clock-driven events (invite time-out, end time reached) are committed as entries.
- **The CASE_MANAGER's flow is decide → trial-apply → commit → apply → effects.**
  - The trial applies the entry with the replay function to a copy and checks every invariant. A successful trial guarantees the real apply succeeds.
  - The copy changes only by applying the entry; it is never edited directly.
  - What gets committed is the message, not the modified copy.
  - Effects are outside actions such as outbox delivery, and run only after commit.

## Plan

- ADR-0122 rewritten in place for the consent, register, EM and wire decisions; new ADR-0124 for the ledger-projection rule. Both are `proposed`, in the planning PR that closes this issue.
- Implementation issues under epic #4283, each updating the specs and notes it changes.

Governing specs: CM-18, CM-10-001, CM-10-004, MSM-07, EP-05, EP-08, EP-09, EMB-11, EMB-16, EMB-17, VP-04-001, CLP-10, DF-09-001, DF-10-001

## References

- ADR-0122, ADR-0093, ADR-0113, ADR-0118, ADR-0119, ADR-0111
- #4178, PR #4267, epic #4208, #4180, #4183, #4053

**Resolved**: 2026-10-07 — implementation tracked in #4290, #4291, #4292, #4293, #4294, #4295, #4296.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4289>.

---
title: Consent in Participant Status, and Replicas That Copy Only the Case Manager
status: active
kind: plan
tracks:
  - "#6654"   # status claims carry only what changed
  - "#6655"   # consent moves into the status; exemption retired
  - "#6656"   # follow-up: Case Owner decisions
  - "#6657"   # follow-up: Invite answers and role grants
  - "#6658"   # follow-up: participant content
  - "#6653"   # epic
description: >
  The build plan for ADR-0212: a participant's embargo consent moves from
  its own rows into each participant status; a participant reports a status
  change as a claim that carries only what changed, and the CASE_MANAGER
  merges it into a whole status; and a replica changes state only from the
  CASE_MANAGER's entries. Lists what each implementation issue changes and
  the traps to avoid.
related_specs:
  - specs/case-management.yaml
  - specs/message-semantics-mapping.yaml
  - specs/status-dimension-objects.yaml
  - specs/received-status-handling.yaml
  - specs/case-ledger-processing.yaml
  - specs/embargo-policy.yaml
  - specs/em-behavior.yaml
  - specs/vultron-as2-mapping.yaml
  - specs/case-event-history.yaml
  - specs/lifecycle-staged-types.yaml
  - specs/state-machine.yaml
related_notes:
  - notes/participant-embargo-consent.md
  - notes/case-ledger-authority.md
  - notes/lifecycle-staged-types.md
---

# Consent in Participant Status, and Replicas That Copy Only the Case Manager

ADR-0212 decides three changes. The code does none of them yet. This note
holds the rules that the build follows and the traps it must avoid. The specs
that state the replaced rules are amended in the same pull request as the code
that meets the new ones. Until then, they describe the code as it is.

## The rules the build keeps

- **A replica changes state only from an entry that the CASE_MANAGER wrote.**
  A participant's or Case Owner's entry is a record: a replica keeps it and
  changes nothing because of it. This rule already holds for RM verdicts,
  case closure and ownership transfer (the comments in
  `vultron/core/behaviors/sync/announce_tree/effect_slots.py`). Consent and
  status claims adopt it next.
- **Each `ParticipantStatus` carries the whole consent table,** copied forward
  as the other state is. An embargo that is in the register but not in the
  table has not been asked about. So a proposal writes no status for a
  participant whose consent it does not change, and a read of an embargo that
  is missing from the table returns "not asked" and does not raise.
- **The CASE_MANAGER writes a new status for every consent change:** an
  `Accept`, a `Reject` or a `Leave` from the participant, a carry-over, a
  time-out, and its own consent as a stakeholder. The status is attributed
  to the participant and dated to the act (`_require_act_instant()`).
- **Consent changes only by an embargo activity.** A participant's status
  claim that changes its consent is refused, and the reason names `Accept`,
  `Reject` or `Leave`.
- **A status claim carries only what changed.** A missing field is
  unchanged, and an explicit null clears it. The merge is the previous status
  updated with the claim's set fields (`model_dump(exclude_unset=True)`), and
  the result is validated as a whole status. The id, the time and the author
  come from the CASE_MANAGER's act. The recorded status names the claim it
  came from.
- **The claim is a loose parent type, and `ParticipantStatus` is its strict
  subclass.** The subclass owns the `ParticipantStatus` wire type, so the
  DataLayer reads a stored status back as a whole status. The parse edge
  reads a received status claim into the parent type. This is the
  lifecycle-staged pattern (`notes/lifecycle-staged-types.md`), but here the
  child registers in the vocabulary, not the parent.

## Traps

- **The old "omitted `rmState` means START" reading** lives in the received
  status checks (`participant_status_acceptance.py`). In a claim, a missing
  RM field is unchanged. Each check judges only the fields that the claim
  sets.
- **Two writers of consent.** The consent rows, their write methods on
  `CaseParticipant`, and the `Create(EmbargoConsent)` and
  `Update(EmbargoConsent)` entries are removed in the same change that moves
  consent into the status, so the two records never exist side by side.
- **Replica nodes that apply an answer** (`ApplyEmbargoAcceptanceFromLedgerNode`
  and its siblings in `relay_effect.py`) are removed, not left as dead
  effect slots. The status entry after the answer carries the change.
- **The received-time exemption for consent rows** (CLP-15-011, added by PR
  #6611) is removed with the consent rows, in the same change.

## Requirements to amend

Each implementation PR amends these requirements together with the code that
meets them. The lists come from a read of the whole spec corpus against
ADR-0212. They are a floor: re-run `spec-backstop` on the real diff.

**Term.** CM-18-001 keeps the name *consent row* and redefines it as one
embargo's row in a status's consent table. The requirements that use the term
only for its state and triggers then need no edit (see the last list).

**Granularity.** One act writes at most one new status for each participant
whose consent it changes, carrying every row the act changed. "A proposal
writes no status" means it writes no `UNINVITED` rows: the proposer's `AGREE`
and each invitee's `INVITE` still write statuses.

### #6654: status claims

| ID | Change |
|---|---|
| RSH-09-001 | Drop "recording exactly the status it received": the CASE_MANAGER merges the claim onto the latest status and records the whole result as its own entry linked to the claim, or refuses the whole claim |
| RSH-09-010 | The recorded status may differ from the claim: it is the latest status updated with the claim's set fields; id, time and author come from the CASE_MANAGER's act. Keep the ban on inventing a value the claim does not set |
| RSH-09-003 | Delete "one that leaves `rmState` out states the initial `START`": a field the claim omits is unchanged, and each check judges only the fields the claim sets |
| RSH-09-004 | Judge the entailments on the merged status, not the claim as received |
| RSH-08-014 | Restate "RM is as the target holds it, and the status carries no case status" as "the claim sets no other field" |
| CLP-07-002 | The participant's claim entry is a record and the CASE_MANAGER's whole-status entry is the change; both are ledgered |
| CLP-07-013 | Remove status claims from "the act's own entry is the change's entry" (its `Add(Note)` and stub-Invite examples stay until #6657 and #6658) |
| SM-05-003 | A recorded status carries the CASE_MANAGER's act instant; the sender's times stay on the claim entry |
| LST-03-001 | Allow one staged pair for `ParticipantStatus`: the loose claim parent and the strict status subclass |
| LST-05-003 | Except this pair: the strict child owns the wire type, so a stored status rehydrates to the child |
| VAM-01-011 | The CASE_MANAGER's `Add` attaches a status to its participant, not the participant's claim |
| CEH-04-014 | The measure layer derives no event from a participant's claim entry, only from the CASE_MANAGER's recorded status, so no event is counted twice |
| CM-04-001, CM-04-002 | Name the CASE_MANAGER and the merge as what records the declared RM, VF or D state (check: may already read that way) |
| new | The claim type, the merge rule, and the link from the record to its claim |

Open: how a claim clears a field. VM-07-001 and ARCH-20-002 drop `None`
fields from every wire object, so an explicit null cannot be sent.

### #6655: consent into status

| ID | Change |
|---|---|
| CM-18-001 | Consent is a table on each status (state, plus the RSVP deadline of an open invitation), copied forward; an embargo with no row reads as `UNINVITED`; signatory and lapsed read the latest status and the register |
| CM-18-019, CM-18-020 | Delete: no `UNINVITED` rows are written |
| CM-18-021, CM-18-017 | Invert: a missing row reads as `UNINVITED`, is not a defect, and does not raise |
| CM-18-005 | One write path: the CASE_MANAGER's status write, which applies a `PEC_Trigger` and appends a dated status |
| CM-18-024 | "Persist the participant" becomes "append and ledger the status as `Add(ParticipantStatus)`" |
| CM-18-025 | Delete: `copy_consent_row()` goes, and replicas copy statuses |
| CM-18-026 | Ban changing a stored status's consent table in place |
| CM-18-006 | Delete "not carried in any `ParticipantStatus` snapshot"; each consent change is a CASE_MANAGER status entry that replicas copy |
| CM-18-007 | The status written at initialization carries the true consent table |
| CM-18-016 | Drop "beyond the `UNINVITED` row a proposal writes"; "writes no row" becomes "writes no status" |
| CM-18-002 | A `TIME_OUT` is recorded as a new status |
| CM-10-001 | Consent is recorded per embargo in each status's table, the deadline on the `INVITED` row, and nowhere else |
| SDO-03-002 | Replace "it carries no embargo consent" with the consent table field |
| MSM-07-001 | Remove `Create`/`Update(EmbargoConsent)`; a consent change is the CASE_MANAGER's `Add(ParticipantStatus)` |
| MSM-07-003, MSM-07-004 | The CASE_MANAGER applies the trigger and records a status; a replica applies nothing from the Accept or Reject |
| MSM-07-005, MSM-07-010, MSM-07-014, MSM-07-015, MSM-07-034, MSM-07-036 | "The receiver" or "an actor applying it" becomes the CASE_MANAGER, recording the result as a status |
| MSM-07-017 | The CASE_MANAGER's own consent change is its `Add(ParticipantStatus)` for its own participant record |
| MSM-07-023 | Each carry-over is a CASE_MANAGER status entry, the owner's own `AGREE` included |
| MSM-07-024 | Replicas copy the CASE_MANAGER's status entries |
| MSM-07-026 | Verification: the expiry entry is a status |
| CM-28-009 | The expiry is the CASE_MANAGER's `Add(ParticipantStatus)` with the `TIMED_OUT` row |
| CM-28-013 | The deadline goes on the `INVITED` row of the status written after the Invite |
| CM-28-014, CM-28-015, CM-28-016, CM-28-023 | `Update(EmbargoConsent)` becomes the CASE_MANAGER's status entry |
| CM-28-030 | Delete or fold into the status apply: the consent effect slot goes |
| CM-23-043 | Each expiry at an owner's close is a CASE_MANAGER status |
| CM-11-024, CM-31-038 | Drop "consent rows": consent is inside the statuses |
| CM-11-001, CM-11-027, CM-11-040, CM-31-012, CM-31-037 | The consent part only: a CASE_MANAGER status records the joiner's or invitee's consent (the `joined` and replica-apply parts are #6657) |
| CM-04-008 | The CASE_MANAGER writes a status for that participant only |
| CM-32-026 | The child case Owner's `AGREED` is in its status in the child case |
| EP-05-002, EP-09-011 | Delete the `UNINVITED`-row-for-everyone clauses: absence means not asked |
| EP-06-001 | A status write copies the table forward and no write downgrades a row; a status claim that changes consent is refused, and the reason names `Accept`, `Reject` or `Leave` |
| EP-09-007, EP-09-023, EP-09-024 | The proposer's and the CASE_MANAGER's own answers are CASE_MANAGER statuses; update the cited tests |
| EMB-17-002, EMB-17-009, EMB-17-013, EMB-17-018 | An honoured late Accept is a record followed by exactly one CASE_MANAGER status (EMB-17-018 inverts: it now requires the follow-up entry) |
| CLP-15-011 | Remove the `EmbargoConsent` exemption from the statement and rationale |
| CLP-07-013, CLP-07-015 | The stub-Accept and relayed-Invite examples carry a status, not a row |
| VAM-05-014, VAM-05-015 | Delete: `Create`/`Update(EmbargoConsent)` are removed |
| CEH-04-001, CEH-04-005, CEH-04-017 | A consent answer is a status dimension, derived by comparing statuses, not by semantic type |
| CEH-03-015, CEH-04-009 | Rationale only: drop the one-row-per-entry wording |
| CEH-06-006, CLP-04-001, SYNC-16-001, SYNC-16-002, SYNC-16-009 | Verification only: fixtures and cited tests move to status-shaped consent |

### Later work

- #6656: MSM-07-008, MSM-07-009, MSM-07-016, EMB-15-009, and the register
  half of MSM-07-023 and MSM-07-028.
- #6657: the `joined` and replica-apply parts of CM-11-001, CM-11-027,
  CM-31-012, CM-31-037, CM-31-039, and CEH-04-010, PCR-08-012.
- #6658: the `Add(Note)` example in CLP-07-013.

### Term only: no change while CM-18-001 keeps "consent row"

CM-18-003, CM-18-004, CM-10-004, CM-31-002, CM-31-008, CM-17-012, CM-13-009,
CM-23-014, CM-28-005, CM-28-007, CM-28-020, CM-28-025, CM-32-027, CM-32-043,
EP-05-003, EP-09-004, EP-09-012, EP-09-013, EP-09-027, EP-09-029, EMB-13-001,
EMB-15-004, EMB-17-003, EMB-17-017, MSM-07-002, MSM-07-020, MSM-07-021,
MSM-07-022, MSM-07-025, MSM-07-028, MSM-07-031, SYNC-20-002, DEMOMA-20-009,
DEMOMA-21-019.

## The measure layer and the case shadow tool

`vultron/measure/history/snapshot.py` and `derive.py` read consent from
`Create`/`Update(EmbargoConsent)` entries and from a participant record's
`embargoConsents`. The case shadow tool's standing comes from that layer, and
its default source is the recorded demo ledgers in `ui/src/recordings` (#6642,
Epic #6440). #6655 moves the measure layer onto status entries and re-records
the demo ledgers. The tool must show the same standing for every recorded case
after the change.

## Order of the work

1. The status claim type, the merge, and both ledger entries for a
   participant's own status claim (#6654).
2. Consent moves into the status, replicas copy the statuses only, and the
   consent-row exemption from the received-time rule goes with the consent
   rows (#6655). It starts after #6512 and #6510 land.

The Case Owner's decisions, case Invite answers, role grants, and content that
participants add come under the replica rule in #6656, #6657 and #6658.

---
title: Consent in Participant Status, and Replicas That Copy Only the Case Manager
status: active
kind: plan
tracks:
  - "#6615"   # source Idea; replaced by the implementation issues
  - "#5746"   # parent epic
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
  table has not been asked about. So a proposal writes no status, and a read
  of an embargo that is missing from the table returns "not asked" and does
  not raise.
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
  #6611) is removed only after no received object is a consent row.

## Order of the work

1. The status claim type, the merge, and both ledger entries for a
   participant's own status claim.
2. Consent moves into the status, and replicas copy the statuses only.
3. The consent-row exemption from the received-time rule is removed.

The Case Owner's decisions, case Invite answers, role grants, and content that
participants add come under the replica rule in later work under the same
ADR.

---
source: CONCERN-3884
timestamp: '2026-09-29T19:56:32.150034+00:00'
title: PEC lapses signatories on a revision proposal, contradicting the EM model;
  consent is per embargo and lapse fires at activation of longer terms
type: learning
---

## Problem

The Participant Embargo Consent (PEC) machine moves every `SIGNATORY` to `LAPSED` the moment the case embargo enters `REVISE` (CM-18-002, MSM-07-005, reference spec §9.2, `_cascade_pec_revise`). `LAPSED` is defined as "prior consent no longer covers the revised terms". That contradicts the EM model the same protocol states: a revision is a *proposal alongside* an embargo that stays in force, and "coverage never breaks during a revision" (`docs/topics/process_models/em/formal_model.md` § Embargo revision; EMB-03-001). A participant who agreed to embargo A is still bound by A while revision B is merely proposed. Nothing about their consent has changed.

Surfaced while planning #3863 (announcing the creation-time shortest-wins revision), where the choice between "announce as `Invite(EmbargoEvent)`" and "register locally" turns on what a revision proposal does to existing signatories.

## What the walk-through found

1. **Two records, one of them redundant.** `CaseParticipant.accepted_embargo_ids` (CM-10-001/003) already records per-embargo consent, and it is what actually gates content: `find_excluded_actor_ids` (`vultron/core/behaviors/case/update_support.py`) excludes a participant only when the *active* embargo's id is missing from that list. During `REVISE` the active embargo is still A, so a `LAPSED` participant keeps receiving embargoed content. The scalar state and the list disagree about whether the participant is a signatory, and the list is the one the system believes.
2. **A rejected revision strands every signatory.** Owner rejects B (EJ): EM returns `REVISE → ACTIVE` under A. No cascade restores `LAPSED → SIGNATORY`; CM-18-003 has no trigger for it, and `reject_embargo_invite` performs none. A participant who agreed to A and ignored a revision they did not care about stays `LAPSED` until the pocket veto (CM-18-002, MSM-07-007) records them as `DECLINED` — for an embargo they consented to and that still stands.
3. **Adherence lies during `REVISE`.** `embargo_adherence` is `True` only at `SIGNATORY` (CM-18-008, ADR-0056). The ledger snapshot of a `LAPSED` participant therefore says `embargoAdherence: false` while that participant is bound by A and receiving embargoed content. Report consumers read that field (DRPT-02-008).
4. **The proposer lapses too.** Whoever proposes B is a `SIGNATORY` to A and is cascaded to `LAPSED` with everyone else, then must accept their own proposal to recover.
5. **"Signatory to A, undecided on B" has no representation** in the scalar state. `accepted_embargo_ids` can hold both A and B; the scalar cannot. The user's reading — "I remain `SIGNATORY` to A; if I accept B I become `SIGNATORY` to B" — is exactly what the list already models.
6. **No coverage.** The manage-embargo demo's "revision" is a fresh proposal after a rejection (`NONE → PROPOSED → ACTIVE`). Nothing exercises `ACTIVE → REVISE → ACTIVE` end to end. EP-05-001 cites `test/demo/test_manage_embargo_demo.py` as verification of a cascade to `INVITED`; the code cascades to `LAPSED`; that test asserts neither. EP-05-001 is wrong as written regardless of how this concern resolves.

`LAPSED` entered the design via the 2026-04-20 architectural review (`notes/participant-embargo-consent.md`, provenance note), not from the protocol. The reference spec's own framing (§9.1: consent records a participant's position on "the case's current embargo terms", singular) already assumes one embargo at a time, which is what `REVISE` violates.

## Candidate model

Consent is per participant **per embargo**. The scalar answers "bound by the *active* embargo?"; `accepted_embargo_ids` answers "which proposals has this participant said yes to?". Consequences:

- A revision proposal (`ACTIVE → REVISE`) changes **nobody's** consent state. Signatories to A stay `SIGNATORY`.
- A participant who accepts B while REVISE adds B to their list; their state stays `SIGNATORY` (to A).
- Owner accepts B (`REVISE → ACTIVE`, active embargo becomes B): participants **without** B in their list are no longer signatories to the active embargo. They need inviting (or the seed/consent path that applies) — this is the one place a cascade is warranted, and it is `SIGNATORY → INVITED`-shaped, which CM-18-004 currently forbids.
- Owner rejects B: nothing happens to anyone. No stranding.
- `LAPSED` either disappears or narrows to "was signatory to the previous active embargo and has not accepted the one that replaced it" — set at *activation* of the revision, not at its proposal.

## Blast radius

CM-18-001/002/003/004, MSM-07-005, EP-05-001/002, reference spec `_pec-state-machine.md` §9.2 and `includes/_pec-states-table.md`, ADR-0048 (kept the revise trigger), ADR-0056, ADR-0093, `notes/participant-embargo-consent.md`, `EmbargoLifecycle._cascade_pec_revise`, `PecDimension`/`participant_embargo_consent.py`, DRPT adherence rendering, and the two decisions this blocks.

## Acceptance criteria

- [ ] AC-1: Decide, in an ADR, what a revision proposal does to an existing signatory's consent, and what activation of a revision does to participants who did not accept it. Record why `LAPSED`-on-proposal was rejected or retained.
- [ ] AC-2: Bring CM-18, MSM-07-005, EP-05, the reference spec §9 fragments, and `notes/participant-embargo-consent.md` into agreement with the decision. EP-05-001's cascade destination and verification pointer are corrected in any outcome.
- [ ] AC-3: `EmbargoLifecycle` implements the decided cascades, including the `REVISE → ACTIVE`-by-rejection path, with a test for each arm.
- [ ] AC-4: An end-to-end test covers `ACTIVE → REVISE → ACTIVE` by acceptance and by rejection, asserting every participant's consent state and `accepted_embargo_ids` after each step.

## Governing specs

CM-18, CM-10-001, CM-10-003, CM-10-004, MSM-07, EP-05, EMB-03-001, EMB-04-001, EMB-05-001, CM-13-005. ADR-0048, ADR-0056, ADR-0093.

## Blocks

Blocks #3836 (termination pruning of open revision proposals) and #3863 (announcing the creation-time revision) — both were being planned in one bundle and were paused pending this decision. Their interview notes are on the issues.

**Resolved**: 2026-09-29 — implementation tracked in #3891. Independent replica-side EM REVISE gap surfaced during planning filed as Concern #3892.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3890>.

Decision (ADR-0093, revised in place): a revision proposal changes no consent; consent is re-evaluated only when the case owner activates a revision, and asymmetrically — a revision ending no later than the active embargo carries every signatory over, one ending later lapses signatories who have not accepted it; a signatory rejecting a *proposed* revision refuses those terms only, and `SIGNATORY → DECLINED` is reserved for rejecting the *active* embargo; the owner's EJ changes no consent record; the `LAPSED → DECLINED` timer path is removed; the PEC transition table is unchanged.

Spec: `specs/case-management.yaml` (CM-18-001/002/003/004), `specs/message-semantics-mapping.yaml` (MSM-07-003/004/005), `specs/embargo-policy.yaml` (EP-05-001/002).
Notes: `notes/participant-embargo-consent.md`.

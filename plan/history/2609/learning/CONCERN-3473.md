---
source: CONCERN-3473
timestamp: '2026-09-28T18:01:12.093483+00:00'
title: A state transition can have two wire encodings, and only one path adjudicates
type: learning
---

## Summary

A single protocol state transition can have more than one wire encoding, and nothing in the spec corpus says which encoding is authoritative. Where parallel encodings exist, they have drifted: they disagree about which participant is the subject of the write, and only one of the two paths runs the received-side adjudication policy. This is a **general** condition across the state machines (RM, EM, CS, PEC, plus the roster/role mechanics), not a defect in one handler — the RM case below is the worked example that exposed it, not the scope.

## Surface Symptom vs. Underlying Problem

**Surface reading:** "`Add(ParticipantStatus)` duplicates the RM report activities — delete one of them," or more narrowly, "`received_report_trees.py` has an inconsistent `actor_id` argument."

**Underlying problem:** the project has an accepted decision that the *formal* message set and the *AS2 wire* vocabulary may diverge (ADR-0083), and a decision that there is exactly one `ParticipantStatus` *writer* with one rule evaluator (ADR-0089, ADR-0086). It has **no** decision about wire-to-wire redundancy: whether two AS2 forms may both carry the same transition, which one a peer must honour, and where the authorization/adjudication seam sits. Because the rule was never stated, each state machine resolved it independently and inconsistently, and the inconsistencies are invisible to every existing ratchet — they are not shape errors, not missing patterns, and not BT bypasses.

`notes/message-type-reference.md:57` records the RM instance as a fact ("The last row is the one that surprises people") without adjudicating it. The note is doing its job; the missing artifact is a decision.

**Already correct — leave alone:**

- The CS dimensions are right as they stand. V/F/D on `ParticipantStatus` and P/X/A on `CaseStatus`, discriminated by payload field, is the deliberate outcome of ADR-0075 and ADR-0083. Do not re-verb these.
- ADR-0084's self-declaratory rule (the participant is authoritative about its own status, with narrow externally-evidenced on-behalf exceptions) is the right subject rule. The problem is that it is not applied at every site, not that it is wrong.
- The single-writer consolidation (ADR-0089) and the composed rule evaluator (ADR-0086) are the correct write-side shape. This concern is about the *wire* and *authorization* layers above them, which did not converge with the writer.
- RSH-05 / RSH-06 (per-dimension partial accept, monotonicity, anomaly reporting) is good policy. The defect is that it is reachable from only one of the two paths.

## Category

Technical debt

## Severity

medium

## Evidence

The RM worked example — four sibling handlers of one state machine, three different conventions for the subject of the RM write:

- `vultron/core/behaviors/report/received_report_trees.py:74` and `vultron/core/behaviors/report/validate_tree.py:123` — RV (`Accept(Offer(Report))`) advances the **sender's** RM to `VALID`.
- `vultron/core/behaviors/report/received_report_trees.py:359-361` — RI (`TentativeReject(...)`) advances the **receiving actor's** RM to `INVALID`.
- `vultron/core/behaviors/report/received_report_trees.py:299-301` — RC (`Reject(...)`) advances the **receiving actor's** RM to `CLOSED`.
- `vultron/core/behaviors/report/received_report_trees.py:186-250` — RK (`Read(Offer(Report))`) advances **nobody's** RM; it stores the activity and re-emits.

Whatever the correct subject rule is, it cannot be all three at once.

The adjudication asymmetry:

- `vultron/core/use_cases/received/status.py` → `add_participant_status_tree` is the only path that runs `StatusAdoptionGate`, `FilterParticipantStatusDimensionsNode`, the RM anomaly policy, and the `ProcessingFault` on refusal.
- `specs/received-status-handling.yaml` RSH-05 and RSH-06 specify per-dimension partial accept, non-adjacent-jump acceptance, backward-regression refusal, and the `Add(Note)` clarification request — all scoped in the requirement text to `Add(ParticipantStatus, CaseParticipant)`.
- The verb-typed handlers pass a hardcoded `rm_state` straight to `CreateParticipantStatusNode` and get only construction-time adjacency validation (SDO-02-004). A peer that wants its assertion adjudicated uses one channel; a peer that wants it applied unexamined uses the other.

Why it generalizes rather than being RM-specific:

- `vultron/core/models/case_participant.py:88-130` — `ParticipantStatus` is a five-dimension snapshot (`rm`, `vf`, `d`, `consent`, and a nested `CaseStatus` carrying em/pxa). Every state machine therefore already has a latent status-shaped encoding alongside whatever verb-shaped encoding it uses.
- `vultron/core/use_cases/triggers/case/add_participant_status.py:39` — the emit side of the status channel accepts `rm_state`/`vf_state`/`d_state`, so the parallel channel is reachable in both directions, not receive-only.
- `notes/message-type-reference.md:49-67` — the collapse inventory shows EM already collapsing `EV`/`EJ`/`EC` into `EP`/`ER`/`EA` "by context, not structure", which is a second instance of meaning moving off the activity type without a stated rule.

Cost already paid in the verb channel, where meaning lives in nesting structure rather than a typed field: #3439 (RK emits `Read(Report)`, dispatch requires `Read(Offer(Report))`) and #3438 (same class, fixed). Both were expensive to adjudicate precisely because no rule said which form was authoritative.

## Impact if Ignored

- Two peers can be conformant and still disagree about a participant's state, because each picked a different channel and the channels apply different acceptance policies.
- The adjudication policy in RSH-05/RSH-06 is bypassable by construction: choosing the verb-typed form skips the gate. That is an authorization hole dressed as a wire-format choice.
- Every future message-shape question re-litigates the same undecided premise, at the cost demonstrated by #3438/#3439. The next one is #3363 (delivery acknowledgement activity type).
- Each new state machine or dimension added to `ParticipantStatus` silently inherits a second encoding, so the problem grows with the vocabulary rather than staying fixed.

## Suggested Action (as filed)

Investigation-first; do not pre-commit to a collapse. Three phases: (1) inventory every wire form per state machine with subject and adjudication seam; (2) per-machine decision on which form is authoritative, testing the hypothesis "antecedent or consent → verb; autonomous → status assertion"; (3) ADR + reconcile RSH-05/RSH-06 text + a ratchet asserting no state machine has more than one primary wire encoding.

## Reference

- Decisions this sits between: ADR-0083, ADR-0084, ADR-0086 / ADR-0089, ADR-0075
- Specs: `specs/message-semantics-mapping.yaml` (MSM-01, MSM-03, MSM-07), `specs/received-status-handling.yaml` (RSH-05, RSH-06), `specs/status-dimension-objects.yaml` (SDO-02, SDO-03)
- Worked examples of the cost: #3439, #3438
- Adjacent but distinct: #3339, #3363

---

## Resolution

**Resolved**: 2026-09-28 — implementation tracked in #3812, #3813, #3814, #3815.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3811>.
Spec: `specs/received-status-handling.yaml` (RSH-08 new; RSH-06-006 new; RSH-01-003/004 and RSH-05-003 corrected), with carve-outs in RMB-15-001 and BTND-10-001.
Notes: `notes/received-status-authorization.md`, `notes/message-type-reference.md`, `notes/bt-pitfalls.md`.
ADR: ADR-0108.

### What the planning interview concluded

The concern's Phase 2 premise — that one of the two encodings must be picked as authoritative — was wrong, and the interview dissolved it rather than answering it. An act message (`TentativeReject(Offer(Report))`) and a status declaration (`Add(ParticipantStatus).rmState`) are **two layers of one move**: the act answers the finder's offer and carries what it answers; the declaration is the participant's own statement about itself. One move producing both is expected. Neither retires. Authority is a property of the **pipeline**, not the message: the mover announces, only the CASE_MANAGER turns an announcement into case state, and every other participant applies the ledger (PCR-03-001 already said so).

Three defects follow from that rule having been unstated, and each is an implementation issue:

1. **Subject (#3812).** The report-invalid and report-closed handlers advance the *receiving* actor's RM. The tests that pin them cite BT-17-006 (execute in the receiving actor's store) and read "the tree runs as B" as "the write is about B" — the store-versus-subject conflation ADR-0089 named as bug #2300. HP-00-001 and BT-17-006's own sender-ID clause already say the subject is the sender.
2. **Acceptance rule (#3813).** Only `Add(ParticipantStatus)` runs the per-dimension rule and the sender-is-participant check; the activity-typed handlers get adjacency-only validation. The rule belongs to the state machine, not the message (RSH-06-006).
3. **Pipeline (#3814, ratchets #3815).** Every received-side tree gates its *commit* on the CASE_MANAGER role but runs its *effects* at every inbox, so `Add(EmbargoEvent)`, `Remove(EmbargoEvent)` and `Add(CaseStatus)` move a replica's state from any sender. Those effects exist because `create_announce_log_entry_tree` replays only seven ledger event types and has none for `add_case_status_to_case`, the report verdicts, engage/defer, or `add_embargo_event_to_case`. Replay must be completed before the effects are gated, or replicas go blind.

### Phase 1 inventory (per machine: act / declaration / ledger; subject; adjudication)

- **RM**: acts `Accept`/`TentativeReject`/`Reject(Offer(Report))`, `Join`/`Ignore(Case)`, `Leave(Case)`; declaration `Add(ParticipantStatus).rmState`; ledger `add_participant_status_to_participant`, `close_case`. Subject: sender for valid/engage/defer/leave, **receiver for invalid/closed (bug)**. Adjudication: only the declaration path runs `VerifySenderIsParticipantNode` + `FilterParticipantStatusDimensionsNode` + `StatusAdoptionGate` + `EmitRMGapNoteNode`; acts get `CreateParticipantStatusNode` adjacency only; `Leave` sets `force_rm_state=True`.
- **EM**: acts `Accept`/`Reject(Invite(EmbargoEvent))` (EM driven only when sender is `case.attributed_to`, inside `EmbargoLifecycle`, OBSERVED mode), `Add(EmbargoEvent)` and `Remove(EmbargoEvent)` (**any sender**, OBSERVED override, no transition check); declaration `Add(CaseStatus).emState` (validates `is_valid_em_transition`, **any sender**), embedded `caseStatus.em` reaches case-level EM only via teardown; ledger `remove_embargo_event_from_case` only — **no replay for `add_case_status_to_case` or `add_embargo_event_to_case`**.
- **CS V/F/D**: declaration only (`Add(ParticipantStatus).vfdState`, role-gated and monotone); ledger replay applies with **no role check and no monotonicity**.
- **CS P/X/A**: declaration `Add(CaseStatus).pxaState` (monotone, any sender); embedded `caseStatus.pxa` reaches case level only indirectly; **no ledger replay**.
- **PEC**: no wire form of its own (MSM-07); single write path `apply_pec_transition`. Clean.
- **Roster**: `Add`/`Remove(CaseParticipant)` any sender, no check; `Accept(Offer(VulnerabilityCase))` makes the sender owner without checking an offer exists. Missing authorization checks, not parallel encodings — routed to participant-admission epic #3409.
- **Existing ratchets**: none asserts one primary encoding per machine or that a handler routes through the adjudication seam; `test_participant_status_validation.py`, `test_vfd_rm_pxa_write_sites.py`, `test_received_side_actor_id.py`, `test_receive_side_bt_commit_ordering.py` cover adjacent properties.

### Recast

Epic #3472's design idea ("exactly one authoritative wire form") was rewritten to the pipeline rule and its tracked work updated. #3752 (suggest-actor received trees emit without a CASE_MANAGER gate) was cross-referenced as an instance of the #3814 gating half.

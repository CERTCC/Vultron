---
source: CONCERN-4672
timestamp: '2026-10-15T16:17:14.246148+00:00'
title: How the CASE_MANAGER records an ordinary participant's answer to a role-delegation
  offer
type: learning
---

## Summary

The actor a role-delegation `Offer(CaseParticipantRole)` (ADR-0039) is made to answers it with an `Accept` or a `Reject`. That actor is usually an ordinary participant, not the CASE_MANAGER. A participant never commits (CLP-09-001), so after PR #4669 (issue #4588) the two answer nodes (`AutoAcceptCaseParticipantRoleNode`, `EmitRejectCaseParticipantRoleNode`) commit only when the executing actor holds `CVDRole.CASE_MANAGER` for the case, and otherwise send the answer with no ledger entry.

That leaves three open questions:

1. **How the CASE_MANAGER records an ordinary participant's answer when it receives it.** A participant's `Accept` or `Reject` answering an `Offer` is a case event, and the CASE_MANAGER MUST commit it when it admits it (CLP-02-012). Today `AcceptCaseParticipantRoleReceivedUseCase` and `RejectCaseParticipantRoleReceivedUseCase` reach no commit. The commit-coverage gate (`EXEMPT` in `test/architecture/test_ledger_commit_coverage.py`) exempts `accept_case_participant_role` and `reject_case_participant_role` by naming this issue. The receive side needs a guarded commit (intake, guards, commit, effects; CLP-10-006, ADR-0111) and a sender check (ADR-0115, #4522).
2. **Who the answer is addressed to.** The answer nodes address it to the offering vendor (`to=[vendor_id]`). After a case has a CASE_MANAGER, a participant addresses case-scoped messages only to the CASE_MANAGER (PCR-08-001). When the offering vendor is not the CASE_MANAGER, the CASE_MANAGER never sees the answer and cannot ledger it. Decide whether the answer goes to the CASE_MANAGER (which relays or announces it) or whether role offers are an exception to PCR-08 with a stated reason.
3. **CLP-02-013 wording.** CLP-02-013 listed "its `Accept` of a role-delegation offer" as an activity only the CASE_MANAGER sends. That is wrong: the offered actor sends it. PR #4669 removes that example from CLP-02-013 as a factual correction. Once questions 1 and 2 are decided, confirm that no CLP-02-013 ground is still needed for the role-offer answer receipts.

## Acceptance criteria

- [ ] A spec states where an ordinary participant's answer to a role offer is addressed and how the CASE_MANAGER commits it on receipt (CLP-02-012, PCR-08-001).
- [ ] The `accept_case_participant_role` and `reject_case_participant_role` received use cases reach a commit at the CASE_MANAGER, or carry a CLP-02-013 ground, and their `EXEMPT` rows naming this issue are removed.
- [ ] The `OFFER_ROLE` exemption reason in `vultron/core/behaviors/replica_emit_exemptions.py` matches the decision.

## Related

- #4588 / PR #4669: the answer nodes commit only at the CASE_MANAGER.
- #4522: sender-check exemptions, including the role-answer receipts.
- #4404 (closed): the role grant and its replay.

Governing specs: CLP-02-012, CLP-02-013, CLP-09-001, CLP-09-003, PCR-08-001

Where: vultron/core/behaviors/case/nodes/delegation.py

**Resolved**: 2026-10-15. Implementation is tracked in #4702 (the Offer goes through the CASE_MANAGER, which checks, ledgers and forwards it) and #4703 (the CASE_MANAGER checks, commits and announces the answer).

Decisions: both the Offer and the answer go through the CASE_MANAGER, as in the ownership-transfer model. Only the Case Owner may make a role offer; the protocol also allows a CASE_MANAGER-originated offer by policy, but it is not built. CASE_OWNER and CASE_MANAGER cannot be offered (the CASE_MANAGER handoff is #3362), and a missing role is refused. The lifecycle is the minimum: an Offer is open until answered, with no withdrawal and no deadline. No ADR, and no new CLP-02-013 ground.

Found while planning: when the CASE_MANAGER receives a role Offer for another actor, it accepts the Offer itself on the target's behalf and grants the role on receipt.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4701>.
Spec: `specs/case-management.yaml` (CM-33).

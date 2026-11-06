---
source: CONCERN-6041
timestamp: '2026-11-06T18:22:13.968275+00:00'
title: The case owner's own answer and its case decision combine in one consistent
  order
type: learning
---

Theme: theme:protocol-correctness — the case owner's personal answer to an embargo proposal and its decision for the case combine in one consistent set of sequences.

## Summary

ADR-0180 separates the case owner's two roles toward a proposed embargo. As a participant it answers the invitation with `Accept`/`Reject(Invite(EmbargoEvent))`, which records only whether the owner finds the embargo acceptable. As the decider for the case it acts on the embargo with `Add` (activate), `Reject(EmbargoEvent)` (decline for the case) or `Remove` (end). The protocol does not yet say which orders of those two answers are consistent:

- **`Add` alone:** allowed. Activation records the owner's `AGREE` if it had not given one. The owner need not `Accept` first.
- **`Accept`, then `Add`:** allowed, and the natural order.
- **`Reject(Invite)`, then `Add`:** allowed today, on purpose: ADR-0122 says an owner whose row is `DECLINED` may still activate, and the activation moves its row straight to `AGREED` as the owner changing its answer. The maintainer's view is that this is odd, and that `Reject`, `Accept`, `Add` may be the consistent sequence. That would make an `Add` from a `DECLINED` owner row a refusal.

## Surface Symptom vs. Underlying Problem

- **Surface:** one permitted sequence, `Reject` then `Add`, reads as the owner contradicting itself.
- **Underlying:** nothing states how the owner's consent row constrains its decision for the case, in either direction. The rule is one line of ADR-0122's effects table, carried into ADR-0180, with no requirement saying which combinations are consistent.
- **Correct and to keep:** the split itself (participants answer invitations; the owner acts on embargoes, ADR-0180), and that an owner never has to `Accept` before it may `Add`.

## Background: the owner may let the CASE_MANAGER do the Add

The protocol could let a case owner delegate the enacting `Add` to the CASE_MANAGER: the owner sends only its `Accept(Invite(EmbargoEvent))`, and the CASE_MANAGER, acting on the owner's standing instruction or policy, sends the `Add(EmbargoEvent, target=VulnerabilityCase)`. This is an option the protocol could allow, not a design the prototype must take. Delegation already exists for terminating an embargo (ADR-0118, EMB-03-003). If it is allowed, the owner's `Accept` becomes the trigger for an activation, which makes the consistency of the owner's `Accept`/`Reject` with its decision for the case matter more.

## Category

Protocol semantics: the owner's consent and the case's embargo decision.

## Severity

Low. Nothing is broken. The current rule is deliberate and the code follows it. It becomes material when #6030 builds the `Add`, or if delegated activation is adopted.

## Evidence

- ADR-0122 § Decision Outcome: "An owner whose row for the proposal is `DECLINED` may still activate it".
- ADR-0180 decision 2: activation carries "the owner's `AGREE` unless its row is already `AGREED`"; decision 3: the owner may decline for itself and leave the case's decision open.
- `notes/participant-embargo-consent.md` § "Consent Is Per Embargo", the row "Owner activates B while its own row for B is `DECLINED`".
- Raised by the maintainer while reviewing PR #6033.

## Impact if Ignored

The owner can send a sequence that contradicts its own recorded answer, and a second implementation may refuse what this one admits. A delegated-activation option would have no rule for which owner answers authorize the CASE_MANAGER's `Add`.

## Suggested Action

Decide, and state as requirements, which orders are consistent. Edge cases to settle:

1. The owner proposed the embargo. Its row is `AGREED` from the proposal, and taking back one's own proposal is `Undo(Invite)`, not `Reject` (ADR-0152). Is "proposer-owner rejects, then adds" reachable at all?
2. The owner accepts for itself, then rejects for the case ("fine by me, but the participants object"). Allowed?
3. The owner's own row is `TIMED_OUT`. Is a later `Add` like a late `Accept` (allowed directly) or like the `DECLINED` case?
4. If `Reject` then `Add` is refused, the owner pays a round trip (`Accept` first) to change its mind, where the `Add` alone is unambiguous.
5. Whether delegated activation is allowed, and if so which owner answer authorizes it.

If the outcome refuses an `Add` from a `DECLINED` owner row, ADR-0180 (still `proposed`) can be edited in place, and #6030 builds the refusal.

**Resolved**: 2026-11-06 — implementation tracked in #6043; delegated activation filed as Idea #6045. Task #6044 was closed as not planned: a proposer's Reject of its own proposal is already refused by the sender-is-invitee check (EP-09-010). The proposer's own withdrawal is Idea #2214.
Decisions: an owner that declined a proposal accepts it before activating (MSM-07-037); activation records the owner's AGREE from UNINVITED, INVITED or TIMED_OUT (MSM-07-028); an owner that agreed for itself may still reject for the case; a proposer cannot Reject its own proposal (MSM-07-038).
Docs PR: https://github.com/CERTCC/Vultron/pull/6048.
Spec: `specs/message-semantics-mapping.yaml`.
Notes: `notes/participant-embargo-consent.md`.

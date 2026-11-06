---
source: CONCERN-5648
timestamp: '2026-11-06T16:06:41.454780+00:00'
title: Should the case owner's embargo activation and rejection use a different activity
  than Accept/Reject(EmbargoEvent)?
type: learning
---

Theme: theme:protocol-correctness — decides whether the owner's embargo decisions use the activity that matches what they do to the case.

## Summary

The case owner activates a proposed embargo with `Accept(EmbargoEvent, target=VulnerabilityCase)` (`_ActivateEmbargoActivity`) and rejects one with `Reject(EmbargoEvent, target=VulnerabilityCase)` (`_RejectEmbargoProposalActivity`), in `vultron/wire/as2/vocab/activities/embargo.py` (ADR-0122). Raised by the maintainer on 2026-11-02 while deciding the `inReplyTo` question in #5641: is there a better activity for these decisions? For example, `Add(EmbargoEvent, target=VulnerabilityCase)` for activation would pair with the existing `Remove` (`_RemoveEmbargoFromCaseActivity`) that ends an embargo. What would rejection then be? Or is a different activity better than both?

## Surface Symptom vs. Underlying Problem

- **Surface symptom:** linking these decisions to the proposal they answer (#5641) is awkward, because neither takes the proposal `Invite(EmbargoEvent)` as its object.
- **Underlying problem:** activation may be a case-state change (the case gains an embargo) modelled as an accept/reject response. The only thing that tells it apart from a participant's own consent, `Accept`/`Reject(Invite(EmbargoEvent))`, is the object's shape.
- **What should stay:** the owner-only decision rule (ADR-0122), and the split between the owner's decision for the case and a participant's consent.

## Category

Protocol semantics, the wire vocabulary for embargo decisions.

## Severity

Low. Design debt, not blocking. #5641 sets `inReplyTo` on the current activities either way.

## Evidence

- `vultron/wire/as2/vocab/activities/embargo.py`: `_ActivateEmbargoActivity(as_Accept)`, `_RejectEmbargoProposalActivity(as_Reject)` and `_RemoveEmbargoFromCaseActivity(as_Remove)`.
- ADR-0122 (embargo register and owner decision) and ADR-0152 (one semantic type per shape, whoever sends it).

## Impact if Ignored

The vocabulary keeps two near-identical `Accept`/`Reject` shapes with different meanings. Telling them apart then rests on strict object matching (SE-01-006), which is fragile, and reply linkage stays indirect.

## Suggested Action

Take an ADR-level look at the embargo-decision vocabulary (MSM-07, VAM-05, ADR-0122, ADR-0152). Decide between keeping `Accept`/`Reject(EmbargoEvent)`, moving to `Add`/`Remove`, or another activity. Related: #5641.

**Resolved**: 2026-11-06 — implementation tracked in #6030. Planned: ADR-0180 (proposed). Participants answer invitations; the case owner acts on embargoes. Activation becomes Add(EmbargoEvent, target=VulnerabilityCase); rejection keeps Reject(EmbargoEvent, target=VulnerabilityCase); both name the proposal's Invite(EmbargoEvent) in inReplyTo. Reject(Invite) for rejection was considered and rejected, because it reintroduces the sender-switched meaning ADR-0122 retired. Implementation: #6030.

Docs PR: https://github.com/CERTCC/Vultron/pull/6033.

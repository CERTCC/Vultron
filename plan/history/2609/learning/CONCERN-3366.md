---
signal: spec-gap
source: CONCERN-3366
timestamp: '2026-09-25T15:29:29.226175+00:00'
title: One Report becoming two Cases — per-recipient links, owner-consent merge
type: learning
---

## Summary

A Report is not a Case: it is the object of the initial `Offer`, and a Case exists only once a recipient accepts. When the same Report goes to more than one recipient, each can accept and create its own Case, leaving the Reporter tracking two coordination efforts for one vulnerability. The protocol permits this deliberately. What it does not specify is what to do about it.

## Surface Symptom vs. Underlying Problem

**Surface reading**: "prevent duplicate cases." That would be wrong — the behaviour is intentional and should stay. A recipient wanting several vendors in one coordination can create one Case and invite them, and forbidding independent acceptance would break the finder's ability to report to multiple parties.

**Underlying problem**: the common form is *sequential*, not concurrent. A Reporter gets no answer to an `Offer`, asks a Coordinator for help, and the second recipient accepts before the first does. So this is not a rare race — it is the normal consequence of a non-responsive first recipient. Two consequences follow, and neither is specified: each `Offer` needs an identifier unique to at least (Report, recipient) so the attempts are distinguishable, and there needs to be a defined path for reconciling two Cases that turn out to be the same vulnerability.

## Category

Protocol design gap — report intake / case lifecycle.

## Severity

Medium. The triggering scenario (unanswered report escalated to a coordinator) is routine rather than exotic.

## Evidence

Documented at `docs/topics/future_work/_oq-report-object-model.md`. Two candidate merge forms:

- **Ledger reconciliation between the two Cases** — complex; two hash-chained append-only ledgers with independent `logIndex` sequences do not merge cleanly.
- **One Case becomes a read-only region of the other**, with requests for the frozen Case redirected to the surviving one. More practical, and unspecified.

Also open: Report formats. Plain text and CSAF-formatted JSON are the known possibilities, and neither is specified — the "two formats are in scope" phrasing in the source note was speculation, corrected in #3341.

## Impact if Ignored

Duplicate coordination efforts stay invisible to the protocol. The Reporter mediates by hand, and participants in the two Cases never learn the other exists.

## Suggested Action

Two separable pieces: (1) specify `Offer` identifier uniqueness over at least (Report, recipient) — small and independently useful; (2) specify the freeze-and-redirect merge form, or record explicitly that merge is out of scope and Reporter-side mediation is the accepted answer.

## Reference

Docs: `docs/topics/future_work/_oq-report-object-model.md`
Source: #3286

**Resolved**: 2026-09-25 — implementation tracked in #3698, #3701, #3702; follow-ups #3699 (decliner embargo obligations, Concern) and #3700 (sentinel bridge between open Cases, Idea).

Planning found the sequential-escalation form already broken: the Reporter's `VultronReportCaseLink` is keyed on the Report alone, so a second recipient's bootstrap `Create(VulnerabilityCase)` fails the CBT-01-005 sender check, and `SvcSubmitReportUseCase` has no path to re-offer an existing Report. Merge is a Case Owner decision, not a Reporter one (ADR-0105, proposed): the offered Case freezes and redirects, and its Participants join the survivor by invitation.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3697>.
Spec: `specs/case-bootstrap-trust.yaml` (CBT-06).
ADR: `docs/adr/0105-case-merge-freeze-and-redirect-by-owner-consent.md`.

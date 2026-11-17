---
source: CONCERN-6518
timestamp: '2026-11-17T16:51:55.411311+00:00'
title: Specs said the CASE_MANAGER seats a participant with Create(CaseParticipant)
type: learning
---

Theme: theme:wire-delivery — the published rules for seating a participant say what an AS2 reader sees on the wire: the CASE_MANAGER adds the record to the case's participant list.

## Summary

Decided 2026-11-16 (maintainer, on #6330): once #6465 replaces the Case Owner's reinstatement request with `Offer(Add(<Actor>, target=<case>))`, the CASE_MANAGER seats a new participant with `Add(CaseParticipant, target=<case>)`, carrying the full record with `context` = the case, under the list-member rule #6317 set (CLP-07-021). #6295 implements that. The specs and notes still state the old shapes, so #6295 cannot be built against them. This Concern is planned (with `plan-issue`) into the docs PR that amends them.

Split from #6330, which keeps the `EmbargoConsent` half (`theme:shared-case-history`, under #5410).

## Surface Symptom vs. Underlying Problem

- **Surface reading:** a few sentences name `Create(CaseParticipant)`; rename them during #6295.
- **Underlying problem:** two specs give `Add(CaseParticipant)` a meaning that the decision retires. CM-31-036 says it never seats a member, and CM-31-011 makes it the Owner's reinstatement request. Rewriting them is a design edit, which lands in a planning PR before the implementation PR (#6295) and in step with #6465's change to the Owner's request.
- **Parts that stay:** `Update(CaseParticipant)` for a changed record, `context` = the case on every case-scoped activity (CLP-07-007), and the rule that replicas copy and never pick a list (CM-23-044).

## Category

Protocol design / spec and notes alignment (wire shape of CASE_MANAGER-authored entries).

## Severity

Medium: it blocks #6295, a child of Now Epic #6509.

## Evidence

Text to amend:

- CLP-07-021 (`specs/case-ledger-processing.yaml`): names the case's content lists for the `Add` rule and leaves participants as a `Create`.
- CLP-07-013 verification wording: describes the participant record as its own `Create`.
- CM-31-036 and CM-31-011: `Add(CaseParticipant)` is the reinstatement request and never seats a member. Coordinate with #6465, which retires that request form.
- `notes/case-ledger-authority.md` § "Every Change Is an Entry; Replicas Copy": "A stub Invite is the Invite's entry plus a `Create(CaseParticipant)`".
- `notes/as2-vocabulary-alignment.md` § "Create(CaseParticipant) Names Its Case in context": records the withdrawn plan (keep `Create`, drop `target`).

## Impact if Ignored

#6295 is built against specs that contradict it, or waits indefinitely; the published spec keeps two rules for records that join a case list.

## Suggested Action

Plan this Concern into one docs PR that amends the five items above to the decided shape, citing #6330 for the decision, and lands before #6295 is built. Decide in planning whether the CM-31-011/CM-31-036 edits ride in this PR or in #6465's planning, so they are written once.

**Resolved**: 2026-11-17 — implementation tracked in #6295, #6465.
Docs PR: https://github.com/CERTCC/Vultron/pull/6613.

Planning found seven more places that named the old shape (VAM-01-017 to
VAM-01-020, VAM-06-004, CM-11-023 to CM-11-025, MV-04-002, notes/case-joining.md).
CM-31-011 and CM-31-036 were rewritten here, not in #6465, so the specs never
gave Add(CaseParticipant) two meanings; CM-31-011 was split into CM-31-043 to
CM-31-045 (one RFC 2119 keyword each) with strict-xfail probes for #6465.
VAM-06-002 was retired; ADD_CASE_PARTICIPANT_TO_CASE now names the seating entry.
ADR-0199 moved to accepted-provisional (MS-14-010).

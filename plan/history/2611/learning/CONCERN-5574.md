---
source: CONCERN-5574
timestamp: '2026-11-02T19:43:43.995030+00:00'
title: Active Participant should exclude Closed Participants
type: learning
---

Theme: theme:requirements-traceability — decides whether "active participant" alone can mean "may still act and receive new case content", so rules that say "active" stop quietly including closed participants.

## Summary

CM-10-004 and the glossary define an **Active Participant** by roster standing: seated or joined, not removed, and a signatory while an embargo is in force. A **Closed Participant** (its own status entry records RM `CLOSED`) stays active by that definition. CM-23-004 and CM-23-018 then add "and not closed" wherever a rule means "may still receive new content or act", and the code's single test for that is `may_act_on_case` (`vultron/core/participants/recipients.py`).

So any rule that says only "active participant" includes closed participants without saying so. CM-21-021 was one such rule (#5189); `learn` on 2026-10-30 fixed it by naming "active and not closed". The maintainer expected "active" to already mean "not closed".

## Surface Symptom vs. Underlying Problem

- **Surface symptom:** one ownership-transfer rule let a closed participant be offered the case; fixed in CM-21-021 / CM-21-022.
- **Underlying problem:** "active" and "closed" are two separate axes, and each rule has to remember to combine them. The next rule written with just "active" repeats the defect.
- **Correct, keep:** a leaving participant still receives the entries that record its own closure, the last one after its status is already `CLOSED` (CM-23-004), and a closed signatory still gets the direct embargo notice (CM-31-009). Those deliveries are why "active" was kept broad.

## Category

Spec consistency: term definition (requirements traceability).

## Severity

Medium. No known live defect after #5189, but the term is used across many specs, the glossary and the recipient code.

## Evidence

- CM-10-004, CM-23-004, CM-23-018, CM-31-009; glossary rows **Active Participant** and **Closed Participant**.
- #5189 (PR #5244): a closed transferee was refused only through `may_act_on_case`, not by CM-21-021 as written.

## Impact if Ignored

Each new rule phrased "active participant" needs a reviewer to ask whether closed participants are meant, and some will pass review including them.

## Suggested Action

Decide one of:

1. Redefine **Active Participant** to exclude Closed Participants, and state the closure entries (CM-23-004) and the signatory embargo notice (CM-31-009) as named exceptions to "only active participants receive case content". Then sweep the specs, glossary and `recipients.py` for uses that relied on the broad meaning.
2. Keep the two axes, give "active and not closed" its own glossary term, and have rules that mean it use that term.

**Resolved**: 2026-11-02 — implementation tracked in #5661.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5660>.
Decision: narrow "active participant" to exclude closed participants (ADR-0171,
proposed). The closure entries, the capped closure resync and the closed-signatory
embargo notice become named exceptions, and `activeParticipants` drops closed
participants. ADR-0171 partially supersedes ADR-0114 and ADR-0116.
Notes: `notes/case-communication-model.md`.

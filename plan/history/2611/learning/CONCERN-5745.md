---
source: CONCERN-5745
timestamp: '2026-11-06T16:06:38.906651+00:00'
title: Two MUST rules give different answers to an Accept naming an embargo the register
  no longer holds
type: learning
---

Theme: theme:protocol-correctness — an Accept naming terms the embargo register no longer holds gets one defined answer, not two that contradict each other.

## Summary

`MSM-07-012` (MUST) says an Accept may name an embargo the register does not hold,
or holds in a final status, and that the CASE_MANAGER MUST refuse that Accept
before committing it, with the refusal notice that reports the reason
(`CLP-05-001`). It carries no lateness qualifier, so on its face it reaches late
Accepts too.

`EMB-17` answers the same condition differently. `EMB-17-003` (MUST) relays a
fresh `Invite(EmbargoEvent)` to the accepter. `EMB-17-004` (MUST) says a late
Accept is a no-op when the case holds no terms and that "The no-op is not a
refusal (`HP-01-003`)", and `EMB-17-016` (MUST NOT) forbids sending any activity
in reply to it.

No relationship edge records which requirement governs the late path.

## Surface Symptom vs. Underlying Problem

- Surface symptom: `EMB-17-003`'s condition and `MSM-07-012`'s condition now read
  identically, so the pair looks like a drafting slip in one of them.
- Underlying problem: the corpus never says that `MSM-07-012` is about an on-time
  Accept and `EMB-17` about a late one. The ordering that makes them compose is a
  property of the receive tree, not of the requirement text, so the text alone
  does not determine the answer.
- Correct and to keep: both answers are right for their own path. A late Accept
  is never refused on deadline grounds (`EMB-17-001`, ADR-0065), and an Accept of
  terms the register cannot bind records nothing (`CM-18-003`). The defect is
  only that neither requirement says which path it governs.

## Category

Spec conflict: two MUST-tier protocol requirements, same condition, different
obligations.

## Severity

Medium. The prototype behaves correctly, so nothing is broken today. The risk is
to conformance: a second implementation reading the requirements alone can
satisfy either one and violate the other.

## Evidence

- `MSM-07-012` statement and rationale: refuse before committing, with the
  refusal notice.
- `EMB-17-003` as amended by PR #5731: the condition is now "neither the Active
  Embargo nor one of its open proposals", which is word for word
  `MSM-07-012`'s "does not hold, or holds in a final status". Before that PR the
  two conditions only partly overlapped.
- `EMB-17-004` ("The no-op is not a refusal"), `EMB-17-015`, `EMB-17-016`: in EM
  `EXITED` or `NONE` the named entry is always absent or final, so
  `MSM-07-012` applies there and demands a reply that `EMB-17-016` forbids.
- `MSM-07-012`'s `relationships:` record `supersedes MSM-07-003` and
  `depends_on CLP-05-001`, and nothing toward `EMB-17`.
- The code composes correctly: `IsAnswerableEmbargoNode`
  (`vultron/core/behaviors/embargo/nodes/conditions.py`) sits in the Accept tree
  a few guards after the late-Accept diversions, so a late Accept diverts before
  the refusal guard is reached. Nothing in the spec text states that ordering.

## Impact if Ignored

An implementer working from the requirements picks one answer. If they pick the
refusal, a late accepter gets a refusal notice where `EMB-17` promises either a
fresh invitation or silence, and a case in EM `EXITED` emits a reply
`EMB-17-016` forbids. The two implementations then disagree on the wire for a
message both consider valid.

## Suggested Action

Decide which requirement governs the late path and say so in the text. The
likely shape is a lateness qualifier on `MSM-07-012` naming `EMB-17` for the
late case, plus a recorded relationship between them so a reader of either
lands on the other. Check at the same time whether `EMB-17-004`'s "the no-op is
not a refusal" and `MSM-07-012`'s refusal duty can both stand, or whether one
needs narrowing.

Surfaced by `pr-ship` triage on PR #5731.

**Resolved**: 2026-11-06 — implementation tracked in #6029. Planned: an Accept's answer depends on whether its embargo is available, not on lateness. Available (Active Embargo or open proposal, end time not passed): honoured, on time or late. Held but no longer available: refused uncommitted with the refusal notice, plus a fresh Invite to the case's current terms when it holds any. Never held: Create(ProcessingFault). Spec text, code and tests move together in #6029 (blocked by #5732).

Docs PR: https://github.com/CERTCC/Vultron/pull/6033.

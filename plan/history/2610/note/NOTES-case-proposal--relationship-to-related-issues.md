---
source: NOTES-case-proposal--relationship-to-related-issues
timestamp: '2026-10-12T19:33:11.364544+00:00'
title: Relationship to Related Issues
type: note
---

**Archived:** 2026-10-12
**Reason:** plan pointer; #810 is closed and CaseActor spawning is tracked by #811/#812 under #1092
**Superseded by:** issues #811, #812, #1092

---

## Relationship to Related Issues

| Issue | Relationship |
|-------|-------------|
| #810 | **Blocked by this**: demo routing to dedicated case-actor container requires the CaseProposal protocol to be in place before `CreateCaseActorNode` can be adapted for the demo layer. Note: the current FV demo passes all convergence invariants (all 26 invariants PASS as of #1025 review), confirming that #810 is architectural improvement work rather than a blocking bug. |
| #811 | Spec + ADR for CaseActor dynamic spawning — a broader concern; CaseProposal is a prerequisite input. |
| #812 | Implementation of CaseActor dynamic spawning — blocked by #811 and this work. |

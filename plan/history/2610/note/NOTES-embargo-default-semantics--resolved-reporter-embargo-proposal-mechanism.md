---
source: NOTES-embargo-default-semantics--resolved-reporter-embargo-proposal-mechanism
timestamp: '2026-10-12T19:33:14.959946+00:00'
title: 'Resolved: Reporter Embargo Proposal Mechanism (EP-04-004)'
type: note
---

**Archived:** 2026-10-12
**Reason:** resolved gap and rejected alternatives; the decision lives in ADR-0096, the do-not-revive rule is kept in the note
**Superseded by:** ADR-0096; ADR-0041; ADR-0089; EP-04-004, EP-04-009

---

## Resolved: Reporter Embargo Proposal Mechanism (EP-04-004)

**This gap is closed by ADR-0096.** A reporter states terms by embedding a
proposed `EmbargoEvent` in the `Offer(VulnerabilityReport)` activity.
`EmbargoEvent.context` carries the report URI before a case exists and is
rewritten to the case URI at case creation (EP-04-009). That discharges
EP-04-004's contingency and makes EP-04-003 reachable for the first time.

Two alternatives were rejected. An activity-level `end_time` on the `Offer`
would add a third meaning to a field CM-28-001 already calls a critical naming
hazard. Inlining the reporter's own `EmbargoPolicy` states a standing preference,
not terms for this report.

### Do not revive the proto-case

An earlier version of this section proposed a second design path: the reporter
creates a case with themselves as sole participant, negotiates, then transfers
ownership on acceptance. **Do not build this.** ADR-0041 supersedes ADR-0015 for
precisely this window, and ADR-0089 re-rejected the proto-case when deciding where
pre-case RM state lives. The path was recorded here before either decision landed,
which is why it read as a live option for so long.

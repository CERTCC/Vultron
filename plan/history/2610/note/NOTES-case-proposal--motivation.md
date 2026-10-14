---
source: NOTES-case-proposal--motivation
timestamp: '2026-10-12T19:33:08.634258+00:00'
title: Motivation
type: note
---

**Archived:** 2026-10-12
**Reason:** reference rationale for delivered work; the CaseProposal protocol is built
**Superseded by:** docs/topics/case_lifecycle/case_initialization.md; ADR-0023

---

## Motivation

`CreateCaseActorNode` currently creates the CaseActor locally in the receiver's
DataLayer. When the case-actor service is external (issue #810), the receiver
needs a way to tell the case-actor service about a new case.

Sending `Create(VulnerabilityCase)` from the report receiver is not correct. In
ActivityStreams, `Create(X)` means "I created X." The report receiver is not the
authoritative creator of the case — the case-actor service is. Using the
receiver as `actor` on a `Create(VulnerabilityCase)` violates this semantics.

The `CaseProposal` object provides a clean solution: the receiver proposes that
the case-actor service create the case, while the case-actor service does the
actual creation.

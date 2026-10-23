---
source: CONCERN-1757
timestamp: '2026-08-06T15:03:28.753103+00:00'
title: Tacit-acceptance embargo model is under-documented
type: learning
---

## Summary

The protocol relies on a "published-default / tacit-acceptance" model for embargo
establishment: the receiver publishes a default embargo policy, and a reporter's
submission without a counter-proposal constitutes implicit agreement. This model
is correct and intentional, but was not documented clearly enough that a protocol
reader could distinguish it from a missing exchange.

## Surface Symptom vs. Underlying Problem

**Surface:** No embargo proposal, negotiation, or per-participant acceptance
appears in the demo scenarios. A reader sees an embargo that appears silently and
disappears at publication, with no visible agreement among participants.

**Deeper problem:** The tacit-acceptance model is valid protocol behavior for the
happy path (uncontentious default embargo), but the spec did not explain it clearly
enough. Without that explanation, readers would read the absence of negotiation as
a gap rather than a deliberate design choice.

## Category

- Technical debt
- Spec clarity

## Severity

medium

## Resolution

**Resolved**: 2026-08-06 — implementation tracked in #2033.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2032>.
Notes: `notes/embargo-default-semantics.md`.

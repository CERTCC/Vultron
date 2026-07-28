---
title: Offer trust boundary in suggest-actor flow not documented in spec
type: learning
timestamp: 2026-07-28
source: ISSUE-1745
signal: spec-ambiguity
---

The ADR-0026/CM-16 suggest-actor spec does not explicitly state that roles must
be read from the stored outgoing `Offer(CaseParticipant)` rather than from the
embedded object inside the received `Accept`. The original implementation read
from the blackboard (a second-order bug: blackboard empties between BT
executions) but even a direct read from the received `Accept` would be wrong
because the accepting actor may modify the embedded CaseParticipant or send
only a bare ID reference.

The correct invariant — **"roles come from the Offer we sent, not the Accept we
received"** — is a security boundary, not just an implementation detail.
ADR-0026 should document this as an explicit trust rule.

**Promoted**: 2026-07-28 — trust rule captured in docs/adr/0026-caseactor-routed-actor-suggestion.md § Trust Rule.
Docs PR: TBD.

---
source: CONCERN-3980
timestamp: '2026-10-05T19:08:49.703271+00:00'
title: 'Concern: reporter_submits_report hand-delivers the Offer the outbox already
  delivered'
type: learning
---

Full original concern (#3980): reporter_submits_report's reporter_client arm hand-POSTs the Offer to the Receiver's inbox after the submit-report trigger's outbox drain already delivered it (dated from #1872, now closed; the CaseActor is one stable identity per container), so every scenario double-delivers; it breaks demo/AGENTS.md "Never Carry One Actor's Mail". Question: remove it and gate on the effect?

**Decision**: yes. Remove the hand delivery, provision the CaseActor before the trigger, wait on the Receiver's own store via a helpers/ polling helper. The single-container (reporter_client None) arm keeps its POST. Confirmed against Demo Integration run 37357889687 (2026-10-05): same Offer id delivered twice.

**Resolved**: 2026-10-05 — implementation tracked in #4223.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4222>.
Notes: `notes/demo-scenario-authoring.md`.

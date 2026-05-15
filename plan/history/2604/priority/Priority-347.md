---
source: Priority-347
timestamp: '2026-04-21T00:00:00+00:00'
title: 'Priority 347: Demo puppeteering, trigger completeness, BT node generalization'
type: priority
---

Addresses BUG-26041701 (bare-string `object_` in `CreateFinderParticipantNode`)
and IDEA-26041702 (generalize to `CreateCaseParticipantNode`). Also converts
scenario demos from spoofing to trigger-based puppeteering, adds missing trigger
endpoints, renames `evaluate-embargo` → `accept-embargo`, and reorganizes
`vultron/demo/` into `exchange/` (protocol fragments) and `scenario/`
(end-to-end workflows).

Tasks: P347-BUGFIX, P347-NODEGENERAL, P347-BRIDGE, P347-SUGGESTBT,
P347-TRIGGERS, P347-EMBARGOTRIGGERS, P347-DEMOORG, P347-PUPPETEER,
P347-SPECS.

Prereqs: P-345 (DL-REHYDRATE) must complete first.
Blocks: D5-7-HUMAN sign-off (gate to P-350).
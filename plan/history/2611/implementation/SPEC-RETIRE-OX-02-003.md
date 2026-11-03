---
source: SPEC-RETIRE-OX-02-003
timestamp: '2026-11-03T18:57:43.884965+00:00'
title: Retired requirement OX-02-003
type: implementation
---

Retired OX-02-003 from `specs/outbox.yaml` (#5339).

Why: Each DataLayer is scoped to one actor (ADR-0073), so the explicit-actor record_outbox_item form is gone and outbox_append always queues in the emitting actor's own outbox (DL-04-004).

Final text: `plan/retired-specs/OX-02-003.md`.

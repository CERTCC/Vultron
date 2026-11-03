---
source: SPEC-RETIRE-OX-04-002
timestamp: '2026-11-03T18:57:47.545790+00:00'
title: Retired requirement OX-04-002
type: implementation
---

Retired OX-04-002 from `specs/outbox.yaml` (#5339).

Why: Local delivery is plain HTTP delivery (OX-04-001), so it has no inbox update of its own to persist. Ingress writes nothing before the 202; durability of an accepted delivery is tracked separately.

Final text: `plan/retired-specs/OX-04-002.md`.

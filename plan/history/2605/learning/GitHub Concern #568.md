---
source: 'GitHub Concern #568'
timestamp: '2026-05-19T19:09:05.884888+00:00'
title: 'Demo construction spec gaps: isolation, routing, embedding (#568)'
type: learning
---

## Summary

During construction of the two-actor CVD demo (epic #464), eleven bugs were filed
and fixed. Analysis of their root causes revealed that several spec and notes
invariants were missing or insufficiently clear — particularly around singleton
isolation for co-located actors, actor ID / URL configuration, ASGIEmitter path
construction, and nested object embedding in outbound activities.

Root causes addressed:

- Bug #530/#536: Demo tests share a single DataLayer across actors
- Bug #534/#540: create_app() mutates module-level singletons
- Bug #557/#558/#559: ASGI emitter doubles path prefix when base_url includes path
- Bug #561/#562/#564: CaseParticipant objects sent as bare URI strings in bootstrap

**Promoted**: 2026-05-19 — captured in:

- specs/multi-actor-demo.yaml (DEMOMA-01-004, DEMOMA-01-005, DEMOMA-08-005)
- specs/case-bootstrap-trust.yaml (CBT-01-007)
- notes/asgi-emitter.md (new)
- notes/activitystreams-semantics.md
- notes/architecture-ports-and-adapters.md
- test/AGENTS.md
- AGENTS.md

---
source: ISSUE-721
timestamp: '2026-06-11T18:35:08.789976+00:00'
title: Transport-role naming must stay explicit in paths and classes
type: learning
---

## 2026-06-08 ISSUE-721 — Transport-role naming must stay explicit in paths and classes

- Outbound adapter names that imply behavior (`delivery_queue`) instead of role
  (`demo_http_delivery`) create broad documentation and import drift.
- When renaming protocol-significant adapter modules, update parallel
  references together (core ports docs, adapter notes, ADR references, and
  codebase reference pages) to keep agent guidance aligned with runtime code.

**Promoted**: 2026-06-11 — captured in `AGENTS.md` pitfall "Transport-Role
Naming Must Stay Explicit in Adapter Paths and Classes".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.

---
source: CONCERN-1653
timestamp: '2026-07-24T14:28:45.168308+00:00'
title: Ratchet test for multi-object mutation atomicity (save_many)
type: learning
---

## Concern

CM-21-004 mandates `save_many()` for multi-object mutations (e.g., case
ownership transfer: strip roles → update `attributed_to` → grant roles). The
spec requirement exists, but there is no automated enforcement. A developer
writing a multi-step mutation can satisfy the functional test without using
`save_many()`, and the atomicity gap will only surface under failure injection.

A fix commit in PR #1590 silently deleted the accepting-actor self-delivery
step while appearing to only change a field accessor — the two concerns were
co-located and the reviewer did not recognise the dependency. `save_many()`
atomicity prevents partial-write state but does not prevent self-delivery
omission; both patterns need detection.

## Design questions resolved

1. **What does the ratchet test assert?** Narrow AST-based behavioral check:
   any BT node `update()` that assigns to `attributed_to` AND calls
   `dl.save()` (instead of `dl.save_many()`) is a violation. Scoped to
   `vultron/core/behaviors/` only.

2. **Scope:** Scoped to the ownership-transfer `attributed_to` mutation
   pattern (CM-21-004). Broad 2+-saves detection deferred — it hit 4
   pre-existing non-violation sites and would require a large
   `KNOWN_VIOLATIONS` set immediately.

3. **Self-delivery coverage:** Documented as pitfall entries in
   `vultron/core/AGENTS.md` and `vultron/demo/AGENTS.md` (Gap B). The
   existing demo CI integration tests are the runtime enforcement; a unit
   ratchet for demo script call-sequence is ~3-4x harder and fragile to
   scenario restructuring.

**Resolved**: 2026-07-24 — implementation tracked in #1661.

---
source: OX-10-004-STUB-GUARD
timestamp: '2026-06-22T19:33:36.272683+00:00'
title: Keep stub adapters under explicit test for NotImplementedError
type: learning
---

`ProdHttpDeliveryAdapter` is intentionally unimplemented and must fail fast
with a spec-linked `NotImplementedError`. A dedicated adapter-level unit test
prevents future placeholder edits from silently downgrading the fail-fast
signal into a no-op module.

**Promoted**: 2026-06-22 — archive only (already covered by OX-10-004 spec
and AGENTS.md pitfall).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

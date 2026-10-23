---
source: CASE-LOG-925-RATCHET
timestamp: '2026-06-22T19:33:27.846300+00:00'
title: Guard hash-chain fields before comparing in invariant tests
type: learning
---

When implementing the local hash-chain invariant for JSONL case-log replicas,
assert that `entryHash` and `prevLogHash` fields are non-empty before
comparing them. Missing fields produce `"" == ""` false positives that mask
serializer or schema-migration bugs. Add an explicit presence assertion
before every chain comparison.

**Promoted**: 2026-06-22 — captured in `test/AGENTS.md` (Hash-Chain Invariant
Assertions section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

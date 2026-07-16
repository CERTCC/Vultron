---
source: CLP-08-995-WIRE-GENESIS
timestamp: '2026-06-22T19:36:19.398054+00:00'
title: Wire-genesis hash must be seeded from DataLayer, not hardcoded
type: learning
---

The genesis entry for a case ledger MUST seed `prevLogHash` from
`dl.get_genesis_hash()` rather than a hardcoded empty string or zero-hash.
Hardcoded seeds break cross-actor replay: a remote actor computing the same
genesis hash from the DataLayer seed will get a different result, and the
predecessor check for entry #2 will always fail. The genesis hash is an actor-
and-case-specific value derived from the DataLayer's initialization seed.

**Promoted**: 2026-06-22 — archive only (covered in test/AGENTS.md
Genesis Hash DataLayer Requirement section and ledger authority notes).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

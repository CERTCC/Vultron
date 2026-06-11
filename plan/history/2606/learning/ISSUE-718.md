---
source: ISSUE-718
timestamp: '2026-06-11T18:35:01.044818+00:00'
title: Shared-inbox stubs must fail fast with a concrete type
type: learning
---

## 2026-06-08 ISSUE-718 — Shared-inbox stubs must fail fast with a concrete type

- A docstring-only adapter stub does not satisfy OX-11-004 because accidental
  imports/callers get no runtime signal.
- Stubbed transport adapters should define an explicit class and raise
  `NotImplementedError` in `__init__` with spec reference context so failures
  are immediate and diagnosable.

**Promoted**: 2026-06-11 — already captured in `AGENTS.md` pitfall "Stub
Adapter Files Must Raise NotImplementedError, Not Silently No-Op". Entry
archived as confirmation.
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.

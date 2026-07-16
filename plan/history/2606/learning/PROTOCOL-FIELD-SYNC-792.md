---
source: PROTOCOL-FIELD-SYNC-792
timestamp: '2026-06-22T19:32:01.781809+00:00'
title: CaseModel Protocol fields must stay in sync with concrete type
type: learning
---

When removing a field from a concrete domain model (e.g., `VulnerabilityCase.events`),
also remove the matching declaration from any structural `Protocol` that lists it
(e.g., `CaseModel.events` in `protocols.py`). Static type checkers (mypy/pyright)
check conformance in the concrete→Protocol direction, so a Protocol member that no
longer exists on the concrete class will not produce a lint error — but it will
silently break future callers who accept `CaseModel` and access the removed attribute.
The pre-PR code review caught this gap; the fix was one-line deletion in `protocols.py`.

**Promoted**: 2026-06-22 — captured in `specs/code-style.yaml` (CS-20-001) and
`AGENTS.md` pitfalls.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

---
source: ABC-HIERARCHY-TEMPLATE
timestamp: '2026-06-22T19:35:11.423504+00:00'
title: ABC hierarchy template requires all abstract methods at base level
type: learning
---

When defining a base class hierarchy using `abc.ABC`, every abstract method
MUST be declared at the base class level, even if it is only meaningful at
a lower subtype. Declaring them only in intermediate classes causes
`mypy`/`pyright` to miss missing implementations in leaf classes and enables
runtime instantiation of partial implementations. Use `@abstractmethod` at the
root base class; intermediate classes refine with type narrowing if needed.

**Promoted**: 2026-06-22 — archive only.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

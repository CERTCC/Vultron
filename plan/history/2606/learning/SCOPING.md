---
source: SCOPING
timestamp: '2026-06-08T13:41:32.233304+00:00'
title: '#699 (domain object migration) decomposed into 7 blocking sub-issues'
type: learning
---

## 2026-06-03 SCOPING — #699 (domain object migration) decomposed into 7 blocking sub-issues

`build` selected #699 ("Migrate domain objects from `wire/as2/vocab/objects/`
to `core/models/` and type `VultronActivity.object_` as discriminated union").
Scoping revealed the work is much larger than the original `size:L` estimate:

- The 7 wire types depend deeply on wire-only types (`as_Object`,
  `ActivityStreamRef[T]`, `as_NoteRef`, `as_Activity`, `VOCABULARY` registry).
- 134 files import from `vultron/wire/as2/vocab/objects/`.
- A clean move requires a parallel core class hierarchy first.

Per maintainer direction the right framing is: build a parallel core
hierarchy (analog of `as_Base`/`as_Object`), migrate domain logic into it
type-by-type, and make the wire layer a thin projection. **Key architectural
decision recorded for the ADR (#724):** refs (`FooRef` patterns) are a wire
concern — core fields hold full objects; the DataLayer hydrates on read; wire
projections handle ref-or-inline serialization at the boundary.

Sub-issues created (all blocking #699 in chain order, added to Project #24
with Schedule=Someday): #724 (foundation + ADR), #725 (Status), #726
(Embargo), #727 (Report/Record/LogEntry), #728 (Participant + roles), #729
(Case + supporting), #730 (Actor types — scope expansion). #699 itself
resized to size:S; it closes by typing `VultronActivity.object_` and removing
the `_STUB_OBJECT_MODEL_MAP` workaround once the chain lands.

No code changes in this session.

**Promoted**: 2026-06-08 — captured in `AGENTS.md`, `notes/codebase-structure.md`, and `notes/domain-model-separation.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/818>.

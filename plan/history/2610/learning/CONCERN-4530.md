---
source: CONCERN-4530
timestamp: '2026-10-12T18:16:28.761110+00:00'
title: Guard specs state the truth the mistake violates
type: learning
---

## Problem

Some specs exist only to forbid an obvious implementation mistake. Example from the 2026-10-12 interview: a receiver must not overwrite its own RM state with the state another participant reports ("why would someone else saying 'I'm hungry' make you think you were hungry?").

Such specs add corpus weight, need verification clauses and tests, and may read as if the mistake were a plausible design. But some were written after a real bug, and deleting them loses that guard.

## Open questions

- Should a spec that only guards against an obvious mistake exist, or should the guard live only as a regression test?
- If kept, should they be marked (kind, tag) so readers know they are defensive, not design?

## Reference

Raised by the maintainer during Epic #4194, 2026-10-12. Not blocking.

**Resolved**: 2026-10-12. The guard stays in the corpus, stated as the positive domain truth the mistake violates in plain protocol vocabulary (for RSH-08-001: "a participant's assertion about itself is about itself, not about another actor"). The bug that prompted it goes in the rationale. It carries no marker or tag. A guard with no domain truth behind it is `project` or only a regression test. Rewording existing guards is folded into the story-drafting Tasks #4508, #4510, #4512 and #4513 as AC-6, and #4512 names RSH-08-001.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4534>.
Spec: `specs/meta-specifications.yaml` (MS-05-005).
Notes: `notes/spec-authoring-rules.md`.

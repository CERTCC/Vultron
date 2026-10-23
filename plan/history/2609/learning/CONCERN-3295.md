---
source: CONCERN-3295
timestamp: '2026-09-17T17:00:23.456927+00:00'
title: Undocumented defensive code masks defects
type: learning
---

Undocumented defensive code in this codebase has twice turned out to mask a
defect rather than handle a real case.

## The two witnesses

**#3217 — `vultron/wire/as2/parser.py`.** `except Exception: return expanded`
around nested inline validation, introduced with no comment. Instrumented, it
fired 52 times with exactly one cause: a wire/core layering fault (ARCH-22-001)
that flattened every inline actor to a bare `as_Link`. The tolerance was
concealing a bug, not absorbing legitimate input.

**#3192 — `vultron/core/behaviors/sync/nodes/replay.py`.** `_find_case_actor`
returned the first arbitrary `Service` in the store on a failed lookup, so
`FindCaseActorNode` reported SUCCESS and published a case-actor address
belonging to a different case. Again a single bug-shaped cause, again
undocumented.

## Plan outcome

The interview reframed the open-ended "inventory all permissive paths" concern
onto a concrete, tractable target the user endorsed: **`except Exception` is a
code smell to eradicate**, starting with `vultron/core/` (83 sites; ~49 are the
sanctioned BT `update()` boundary and left as-is). The rule is
**narrow / delete / justify**, mechanized by an AST ratchet that allows broad
catch only in a BT node's `update()` plus a shrinking `_DECLARED_EXCLUSIONS`
allow-list for genuine framework boundaries.

Docs (this plan): added **CS-23-001** (broad `except Exception` disallowed in
`vultron/` outside the BT `update()` boundary; refines ARCH-15-002) and a
`notes/domain-validation.md` section capturing the narrow/delete/justify rule
and the instrument-and-count method (from #3217) for deciding whether a catch
is load-bearing. The concern's "two witnesses isn't enough to state a rule"
caution was raised in the interview and consciously overridden by the user, who
judged the smell worth an enforceable rule now; each masked defect found during
eradication becomes a further witness.

**Resolved**: 2026-09-17 — implementation tracked in #3325 (core + ratchet)
and #3326 (adapters/demo/metadata/wire follow-up).
Docs PR: <https://github.com/CERTCC/Vultron/pull/3322>.
Spec: `specs/code-style.yaml` (CS-23-001).
Notes: `notes/domain-validation.md`.

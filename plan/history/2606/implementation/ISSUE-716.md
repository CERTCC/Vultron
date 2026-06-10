---
source: ISSUE-716
timestamp: '2026-06-04T16:37:36.632313+00:00'
title: Remove ValidateCaseObject BT node; fix memory=False on SuggestActorToCaseBT
type: implementation
---

## Issue #716 — BT cleanup: audit memory=False on inline composites and remove redundant ValidateCaseObject node

### AC-1: memory=False audit

Audited all inline composites in `vultron/core/behaviors/case/`. Found one
`memory=True` in `suggest_actor_tree.py` on the `SuggestActorToCaseBT`
Sequence. Changed to `memory=False` so preconditions (`CheckIsCaseOwnerNode`,
`CheckNoExistingInviteNode`) are re-evaluated on every tick, maintaining the
stateless-ticking invariant shared by all other case BTs. All other composites
already used `memory=False`.

### AC-2 + AC-3: ValidateCaseObject removal

Confirmed that `VultronBase.id_` is typed `NonEmptyString` with
`default_factory=_new_urn`, so Pydantic enforces a valid non-empty `id_` at
construction time (ARCH-10-001). The factory function `create_create_case_tree()`
also reads `case_obj.id_` before building the tree, making the downstream BT
check unreachable. Removed `ValidateCaseObject` from `nodes/conditions.py`,
`nodes/__init__.py`, and `create_tree.py`.

### Tests added

- `TestVultronCaseIdContract`: construction-time contract tests proving
  `VultronCase` rejects empty/whitespace `id_` values with `ValidationError`.
- `test_suggest_actor_tree.py`: regression test asserting `SuggestActorToCaseBT`
  uses `memory=False`.

PR: [#774](https://github.com/CERTCC/Vultron/pull/774)

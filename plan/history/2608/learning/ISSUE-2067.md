---
title: "PR #2882 code-review findings — all pre-existing, out of scope"
type: learning
timestamp: "2026-08-31T17:27:04Z"
source: ISSUE-2067
signal: concern
---

## Context

Code review for PR #2882 (refactor(ownership-transfer): move ForwardOffer outbox write into BT effect node).
All 6 findings were in files **outside** the PR diff (`git diff origin/main...HEAD` showed only 5 files, none matching any finding).

## Filed as issues

- **#2892** — `dimensions.py`: `_coerce_vf/_coerce_d` raise `KeyError` instead of `ValueError` on unknown names; causes 500-class error instead of clean 422 `ValidationError` (size:S Bug).
- **#2893** — `trigger_validation.py` + `_adjudication.py`: VF↔D cross-dimension entailment not enforced; `d=D` is allowed when `vf≠VF`, producing invalid compound state (size:M Bug).

## Remaining findings (not yet filed)

1. **`status.py` ~line 232** — `_check_d_precondition` only enforces DEPLOYER role for `CS_d.D`, not for `CS_d.d`; direct node instantiation bypasses the BT-level `CheckDeployerRoleNode` guard.
2. **`test/ci/invariants/conftest.py` ~line 94** — `_ACCEPTED_STATUS` and `_CLOSED_STATUS` fixtures have FINDER participant with `vfState="VF"` — semantically invalid per ADR-0075; could mask future invariant tests.
3. **`test/architecture/test_validate_assignment_ratchet.py` ~line 23** — docstring code example has unbalanced parenthesis (`# accepted)` comment swallows the closing `)` of `object.__setattr__`); any reader copying into a REPL gets `SyntaxError`.

## Audit disposition (2026-09-02)

Discharged: #2892, #2893.

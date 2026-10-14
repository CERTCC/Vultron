---
title: "Trigger Use-Case Test Coverage and PR Scope"
status: active
kind: guidance
related_specs:
  - specs/triggerable-behaviors.yaml
  - specs/use-case-organization.yaml
description: >
  Coverage expectations and PR-scope discipline for trigger use cases in
  vultron/core/use_cases/triggers/.
related_notes:
  - notes/testing-pitfalls.md
  - notes/case-communication-model.md
---

# Trigger Use-Case Test Coverage and PR Scope

## Coverage expectation

Every trigger use case in `vultron/core/use_cases/triggers/` SHOULD have a
dedicated unit test, under `test/core/use_cases/triggers/`, that runs its
`execute()` path against a real in-memory `DataLayer` and asserts:

- the state mutation (RM, EM, CS, or PEC transition as applicable);
- the outbox effect: the activity is queued and addressed per PCR-08-001
  (see `notes/case-communication-model.md`); and
- the failure modes the use case documents raising (`VultronValidationError`,
  `VultronNotFoundError`).

Case triggers and embargo triggers co-evolve, so sparse tests let a regression
in one ship behind a fix to the other (#652).

Create the test file in the same PR as the use case. The registry ratchet
(`test/architecture/test_trigger_registry_ratchets.py`, ADR-0110) already fails
when a `Svc*UseCase` has no registry row, so a new use case is registered in
that PR anyway. Integration coverage (`test_trignotify.py`, scenario demos) is
no substitute.

Route-layer checks (202, the store handed to the dispatcher, the queued flush)
live once, parametrized over the registry, in
`test/adapters/driving/fastapi/test_trigger_routes_contract.py`; a per-router
suite carries only the verb's domain assertions.

## PR-scope discipline

Do not bundle case-trigger and embargo-trigger changes in one PR unless the
change is intrinsically cross-cutting (a renaming sweep, an `EmbargoLifecycle`
seam refactor). A reviewer focused on one half misses a regression in the
other. When a PR must touch both, say so in the PR body and list the
integration tests that exercise the combined path.

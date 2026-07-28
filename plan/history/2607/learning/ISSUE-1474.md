---
title: "caller_owns_em_io guard pattern for BT/service layer handoff"
type: learning
timestamp: "2026-07-20T00:00:00+00:00"
source: ISSUE-1474
---

When a BT node needs to read state before calling a service and write state after,
use a `caller_owns_em_io` bool in the service method to distinguish two paths:

- **BT path** (`em_before` passed): caller already read and will write state via
  named BT nodes. Service skips its own DataLayer read/write.
- **Legacy path** (`em_before=None`): service reads and writes internally as before.

This preserves backward compatibility for callers that haven't been updated yet,
while letting BT nodes own the DataLayer IO for the operations they orchestrate.

The guard pattern:

```python
caller_owns_em_io = em_before is not None
if not caller_owns_em_io:
    em_before = EM(case.current_status.em_state)
assert em_before is not None  # for mypy: guaranteed by branch above
# ...compute em_after...
if not caller_owns_em_io and em_after != em_before:
    case.current_status.em_state = em_after
    case_mutated = True
```

The `assert em_before is not None` after the conditional is required for mypy to
narrow the type from `EM | None` to `EM`; without it mypy keeps the union and
flags downstream uses.

**Promoted**: 2026-07-22 — captured in `vultron/core/AGENTS.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1608>8>8>.

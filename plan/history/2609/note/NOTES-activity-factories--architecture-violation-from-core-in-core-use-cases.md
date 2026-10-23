---
source: NOTES-activity-factories--architecture-violation-from-core-in-core-use-cases
timestamp: '2026-09-17T17:07:26.788935+00:00'
title: 'Architecture Violation: from_core() in Core Use Cases'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,c) the described core->wire violation is resolved — no from_core in vultron/core/use_cases/; test_core_no_wire_imports.py KNOWN_VIOLATIONS=frozenset().
**Superseded by:** test/architecture/test_core_no_wire_imports.py; ADR-0082 / ARCH-12-005.

---

## Architecture Violation: `from_core()` in Core Use Cases

`vultron/core/use_cases/received/sync.py` and
`vultron/core/use_cases/triggers/sync.py` call `from_core()` on wire
objects (`CaseLedgerEntry.from_core(entry)`, `WireCaseLedgerEntry.from_core(entry)`).
This violates the hexagonal architecture rule that core modules must not
import from the wire layer.

The correct fix, tracked separately, is to move the domain->wire
translation into a driven adapter or outbox port adapter so that core use
cases hand domain objects to an adapter and receive wire-format objects
back, without directly calling wire-layer methods.

This fix MUST NOT be included in the factory function migration — the
scopes are separate.

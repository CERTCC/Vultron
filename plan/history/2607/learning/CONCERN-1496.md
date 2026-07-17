---
source: CONCERN-1496
timestamp: '2026-07-17T19:47:36.423160+00:00'
title: DataLayer returns wire objects to core instead of core objects
type: learning
---

## Original Concern

`SqliteDataLayer` reconstructs stored objects using the wire `VOCABULARY`
registry (`find_in_vocabulary()`), so `dl.read()` returns wire-layer types
(e.g. `as_VulnerabilityCase`) rather than core types. BT nodes and use cases in
`core/` receive wire objects and work around this via duck-typing Protocols in
`core/models/protocols.py` (`CaseModel`, `is_case_model()`, etc.). Core
validators never run on DataLayer-sourced data; the boundary is enforced only
by structural coincidence between wire and core field names and a shared `type_`
string. The Protocols evade rather than honour ARCH-01-001 by hiding a runtime
`core → wire` dependency from mypy/pyright.

After ADR-0017 / #1387 renamed wire classes to the `as_` prefix, the classes
are now genuinely distinct — but the runtime boundary violation remained.

It was also unclear where wire↔core translation belongs (adapter-converts vs
use-case-converts).

## Resolution

**Resolved**: 2026-07-17 — planned via `plan-issue`.

Decision (ADR-0034): the DataLayer port returns **core** domain objects for any
persisted type with a registered `CORE_VOCABULARY` counterpart; the adapter owns
wire↔core translation via its own `type_`→core-class mapping independent of the
wire `VOCABULARY`; the duck-typing Protocols are removed. Rejected alternatives:
use-case-side conversion (DL-01-004), physical DataLayer split (ADR-0012 topology
change).

**Flow separation** discovered during planning:

- **Flow A (domain entities)** — clean core→core round-trip; the concern's
  target. Fixed by the implementation Tasks below.
- **Flow B (wire Activity read-back)** — core reads stored `as_Offer` etc. via
  `dl.read(activity_id)`. AS2 Activities are wire-only (no core counterpart), so
  this is a distinct boundary violation. Because its deliverable is to generate
  more implementation issues, it was filed as a new **Concern** (#1506), not a
  Task.

Docs PR: <https://github.com/CERTCC/Vultron/pull/1502>.
Spec: `specs/datalayer.yaml` DL-05-001 through DL-05-004 (v1.2.0).
Notes: `notes/datalayer-design.md` § "Read Path MUST Return Core Objects".
ADR: `docs/adr/0034-datalayer-returns-core-objects.md`.

Implementation tracked in:

- #1503 — DataLayer read path returns core objects (reconstruct via CORE_VOCABULARY)
- #1504 — Remove DataLayer duck-typing Protocols from core (blocked by #1503)
- #1505 — Architecture ratchet: no wire vocab type escapes dl.read into core
- #1506 — (Concern) Core reads wire AS2 Activities back from the DataLayer — audit + plan migration

---
title: Spec gap — DL-05 covers DataLayer read shape but nothing governs the write path
type: learning
timestamp: 2026-08-12T00:00:00Z
source: ISSUE-2232-dl-write-path
signal: spec-gap
---

DL-05-001..004 and ADR-0034 specify that the DataLayer **port returns core
objects**, and `test/architecture/test_dl_read_returns_core_objects.py`
enforces it with a shrink-only `KNOWN_WIRE_ESCAPES` ratchet.  There is no
corresponding requirement on the **write** side: nothing forbids storing a
wire-shaped payload in a core-typed row.

That asymmetry is what made #2232 possible.  The only write-path shape guard
was `if obj.type_.startswith("as_")` in `Record.from_obj` — but wire
vocabulary `type_` values are *bare* names (`"CaseParticipant"`), not
`as_`-prefixed, so the guard never fires for the 15 wire classes whose `type_`
is also a `CORE_VOCABULARY` key.  A wire `as_ParticipantStatus` (flat
`rm_state`) was written into the `ParticipantStatus` table, and core readers
doing `status.rm.state` got `None`.

Enforcing "reads return core" without enforcing "writes store core" only
guarantees the *type* of the object handed back, not that the row's field
shape matches the class reading it.  A read-side ratchet cannot detect a
malformed row; it can only confirm the class it instantiated.

**Suggested spec addition** (companion to DL-05-001..004): a DataLayer write
MUST store the canonical core field shape for any `type_` present in
`CORE_VOCABULARY`, with a shrink-only exemption set mirroring
`KNOWN_WIRE_ESCAPES`.  #2232 implemented this for `CaseParticipant` and
`ParticipantStatus` (`_NORMALIZE_WIRE_TO_CORE` in
`vultron/adapters/driven/db_record.py`); the remaining 13 types are tracked
in #2268, which is where the architecture test asserting set completeness
belongs.

**Promoted**: 2026-08-17 — captured in GitHub #2320 (Concern: wire-shape convergence design question).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.

---
source: CONCERN-1930
timestamp: '2026-08-21T20:09:30.120441+00:00'
title: VulnerabilityCase is an unguarded cross-layer coupling point — wire, domain,
  and persistence share the same aggregate with no translation boundary
type: learning
---

## Concern

Issue #1930 identified that `VulnerabilityCase` functions as a god node
(364 edges, betweenness centrality 0.119) shared directly across wire,
domain, and persistence layers with no translation boundary.  Wire-layer
modules were importing core model types directly rather than using the
`as_Foo.from_core()` seam already present on every wire vocab object.

## Resolution

Added ARCH-22 spec group (ARCH-22-001 through ARCH-22-003) to
`specs/architecture.yaml` requiring a wire→core import ratchet test, and
added an AGENTS.md pitfall directing agents to use `as_Foo.from_core()`
instead of direct core-model imports in wire code.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2485>

## Implementation Issues (children of epic #2222)

- #2486 Add wire→core import ratchet test (size:S) — blocked-by #1930
- #2487 Split CaseOutboxPersistence into its own port file (size:S) — blocked-by #1930
- #2488 Resolve annotation-time import cycles in vultron/core/models/ (size:S) — blocked-by #1930
- #2489 Introduce per-semantic domain event subclasses P65-3 / CS-10-002 (size:L) — blocked-by #1930
- #2490 Make DataLayer.read() the single VulnerabilityCase rehydration point (size:M) — blocked-by #1930
- #2491 Update extract_intent() to return a discriminated union of VultronEvent subclasses (size:M) — blocked-by #2489

## Key Learnings

- The wire→core import direction was unguarded: 32 wire-layer files import
  `vultron.core.models` directly.  The ratchet test (#2486) starts with 32
  KNOWN_VIOLATIONS and prevents the set from growing.
- All 9 apparent import cycles in `vultron/core/models/` are annotation-only
  (`TYPE_CHECKING` guards), not runtime cycles — a static AST scan that
  ignores `if TYPE_CHECKING:` blocks will report false positives.
- The `as_Foo.from_core()` seam is already present on every wire vocab
  object; the missing piece is enforcement (the ratchet test) and
  documentation (ARCH-22-001, the AGENTS.md pitfall).
- Spec YAML schema must be verified before writing — the `id`/`specs`
  key names differ from the natural `group`/`statements` reading; the
  Pydantic model is the authoritative source.

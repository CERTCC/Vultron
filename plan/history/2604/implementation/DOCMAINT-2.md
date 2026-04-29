---
title: "DOCMAINT-2 \u2014 Fix stale references to archived notes (2026-04-23)"
type: implementation
date: '2026-04-23'
source: DOCMAINT-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7844
legacy_heading: "DOCMAINT-2 \u2014 Fix stale references to archived notes\
  \ (2026-04-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-23'
---

## DOCMAINT-2 — Fix stale references to archived notes (2026-04-23)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7844`
**Canonical date**: 2026-04-23 (git blame)
**Legacy heading**

```text
DOCMAINT-2 — Fix stale references to archived notes (2026-04-23)
```

**Legacy heading dates**: 2026-04-23

**Task**: Fix stale cross-references throughout specs/, docs/, notes/, plan/,
AGENTS.md, and prompts/ following the archival of several notes files.

**Changes**:

- `notes/canonical-bt-reference.md` → `notes/bt-integration.md` (merged):
  Updated in `specs/behavior-tree-integration.yaml`, `notes/protocol-event-cascades.md`,
  `notes/bt-fuzzer-nodes.md`, `notes/use-case-behavior-trees.md`, `AGENTS.md`.

- `notes/architecture-review.md` → `archived_notes/architecture-review.md`:
  Updated in `specs/architecture.yaml`, `specs/testability.yaml`,
  `docs/adr/0009-hexagonal-architecture.md`, `AGENTS.md`,
  `prompts/ARCHITECTURE_REVIEW_prompt.md`.

- `notes/state-machine-findings.md` → `archived_notes/state-machine-findings.md`:
  Updated in `plan/PRIORITIES.md`, `specs/behavior-tree-integration.yaml`,
  `specs/state-machine.yaml`, `docs/adr/0013-unify-rm-state-tracking.md`,
  `notes/case-state-model.md`.

- Updated `archived_notes/datalayer-sqlite-design.md` status header from
  "Planned" to "Complete" (PRIORITY-325 completed 2026-04-14).

**Validation**: `./mdlint.sh` — 0 errors across 483 files.

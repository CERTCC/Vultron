---
title: Spec Token-Overhead Reduction (6-pass cleanup)
type: implementation
date: '2026-04-15'
source: LEGACY-2026-04-15-spec-token-overhead-reduction-6-pass-cleanup
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6374
legacy_heading: Spec Token-Overhead Reduction (6-pass cleanup)
date_source: git-blame
---

## Spec Token-Overhead Reduction (6-pass cleanup)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6374`
**Canonical date**: 2026-04-15 (git blame)
**Legacy heading**

```text
Spec Token-Overhead Reduction (6-pass cleanup)
```

Reduced agent token overhead in `specs/` corpus while keeping all
transformations semantically lossless. Total savings ~18 KB (~5% of corpus).

**Changes**:

  Load Contextually by topic). Replaced stale 2026-03-26 Implementation Status
  snapshot with pointer to `plan/IMPLEMENTATION_PLAN.md`.

- `specs/vultron-protocol-spec.yaml`: Stripped 194 per-requirement `Source: docs/...`
  sub-bullets (~11 KB). Header `**Sources**:` block preserves all referenced docs.
- `specs/architecture.yaml`: Removed 8 inline `**Current state**:` sub-bullets,
  `**Implemented**:` annotation on ARCH-12-002, and entire "Remediation Status"
  section. Added pointer to `notes/architecture-review.md`.
- `specs/code-style.yaml`: Removed superseded requirements CS-01-002, CS-01-003,
  CS-01-006 (superseded by `tech-stack.md` IMPLTS-07-*). Trimmed verbose Rationale
  blocks to single sentences. Removed NAMING-1 commit reference from CS-07-003.
- `specs/behavior-tree-integration.yaml`: Condensed multi-line Rationale blocks
  for BT-06-001 and BT-06-004.
- `specs/testability.yaml`: Condensed multi-line Rationale block for TB-10-001.
- `AGENTS.md`: Removed `**Last Updated:** 2026-03-20` datestamp, "all remediated
  as of ARCH-CLEANUP" status annotation, and "Handler shims: removed in PREPX-2"
  entry from Key Files Map.

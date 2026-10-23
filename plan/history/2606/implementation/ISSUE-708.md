---
source: ISSUE-708
timestamp: '2026-06-04T14:26:39.499910+00:00'
title: Add import-time order guard to SEMANTIC_REGISTRY
type: implementation
---

## Issue #708 — Add import-time order guard to SEMANTIC_REGISTRY

Added a hard import-time guard that prevents `SEMANTIC_REGISTRY` from loading
when any less-specific pattern precedes a more-specific one in the same
`activity_` group. A mis-ordered registry silently dispatches to the wrong
use case with no error signal; this makes that impossible to miss.

### Changes

- **`vultron/errors.py`**: Added `RegistryOrderError(VultronError)` with
  docstring referencing SE-03-002 and `notes/semantic-registry.md`.
- **`vultron/semantic_registry/__init__.py`**:
  - Added `_strip_description()` to recursively remove the doc-only
    `description` annotation from pattern dumps before comparison (fixes a
    latent false-negative/false-positive bug in subset comparisons).
  - Added `_elem_matches()` and `_is_subset()` for recursive pattern dump
    comparison.
  - Added `_check_group_order()` and `_validate_registry_order()` which
    groups entries by `activity_` type and raises `RegistryOrderError` on
    any strict-subset violation where the less-specific entry appears first.
  - `_validate_registry_order(SEMANTIC_REGISTRY)` is called at module load
    immediately after `SEMANTIC_REGISTRY` is assembled.
  - Added an ordering-rationale comment block above `SEMANTIC_REGISTRY`
    listing all 9 domain groups and the specific-before-general rule.
- **`test/test_semantic_registry.py`**: Added 4 new tests — valid ordering
  passes, reversed pair raises `RegistryOrderError`, same-specificity passes
  (guard is intentionally narrower than the belt-and-suspenders test), and an
  `importlib.reload` smoke test that exercises the live import-time guard.

### Key design decisions

- The guard raises on strict-subset violations only (less-specific before
  more-specific). Equal-specificity (ambiguous duplicate) pairs are left to
  `test_non_overlapping_activity_patterns()` which serves as belt-and-suspenders.
- `_strip_description()` is recursive — the code review caught that a flat
  `dict.pop("description")` leaves nested descriptions in sub-pattern dumps,
  causing false negatives and false positives for entries like
  `ACCEPT_CASE_MANAGER_ROLE` that carry nested `in_reply_to_` descriptions.

PR: [#761](https://github.com/CERTCC/Vultron/pull/761)

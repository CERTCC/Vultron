---
title: Semantic Registry Design Notes
status: active
description: >
  Design decisions for SEMANTIC_REGISTRY in vultron/semantic_registry/:
  ordering rules, group structure, the import-time order guard, and
  how ActivityPattern definitions in extractor.py relate to the registry.
related_specs:
  - specs/semantic-extraction.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/architecture-hexagonal.md
relevant_packages:
  - vultron/semantic_registry/
  - vultron/wire/as2/extractor.py
  - test/test_semantic_activity_patterns.py
---

# Semantic Registry Design Notes

## Overview

`SEMANTIC_REGISTRY` in `vultron/semantic_registry/` is the single ordered
list that maps every AS2 activity structure to a `MessageSemantics` value,
a `VultronEvent` subclass, and a use-case class. It is iterated by
`find_matching_semantics()`, which returns the **first** match.

`ActivityPattern` objects — one per `MessageSemantics` value — are defined in
`vultron/wire/as2/extractor.py` and imported into the `semantic_registry`
package submodules.

---

## The Ordering Invariant

**More-specific patterns MUST precede more-general ones. `UNKNOWN` must be
last.**

A pattern is *more specific* than another if its dump is a proper superset of
the other's dump (within the same `activity_` group). If a general pattern
appears first, the specific one is never reached — the wrong use case is
invoked with no error signal.

This invariant is captured by spec `SE-03-002`.

### Group ordering within `SEMANTIC_REGISTRY`

Entries are grouped by domain area; within each group, specific patterns come
before general ones:

| # | Group | Example semantics |
|---|---|---|
| 1 | Embargo events | `CREATE_EMBARGO_EVENT`, `INVITE_TO_EMBARGO`, `ACCEPT_INVITE_TO_EMBARGO` |
| 2 | Reports | `CREATE_REPORT`, `SUBMIT_REPORT`, `ACK_REPORT`, `VALIDATE_REPORT`, … |
| 3 | Cases | `CREATE_CASE`, `UPDATE_CASE`, `ENGAGE_CASE`, `DEFER_CASE`, … |
| 4 | Case membership | `INVITE_ACTOR_TO_CASE`, `ACCEPT_INVITE_ACTOR_TO_CASE`, … |
| 5 | Case manager role | `OFFER_CASE_MANAGER_ROLE`, `ACCEPT_CASE_MANAGER_ROLE`, … |
| 6 | Ownership transfer | `OFFER_CASE_OWNERSHIP_TRANSFER`, `ACCEPT_CASE_OWNERSHIP_TRANSFER`, … |
| 7 | Case log entries | `ANNOUNCE_LOG_ENTRY`, `REJECT_LOG_ENTRY` |
| 8 | Vulnerability case announcements | `ANNOUNCE_VULNERABILITY_CASE` |
| 9 | Notes | `CREATE_NOTE`, `ADD_NOTE_TO_CASE`, `REMOVE_NOTE_FROM_CASE` |
| 10 | Participants | `CREATE_CASE_PARTICIPANT`, `ADD_CASE_PARTICIPANT`, … |
| 11 | Fallback sentinels | `UNKNOWN_UNRESOLVABLE_OBJECT`, `UNKNOWN` (must be last) |

When adding a new pattern, place it in the correct group. If it is more
specific than an existing entry in the same `activity_` group, place it
**before** that entry.

---

## Import-Time Order Guard

Because a misplaced pattern fails silently at runtime,
`semantic_registry/__init__.py` calls `_validate_registry_order(SEMANTIC_REGISTRY)`
at module load time. If any less-specific entry precedes a more-specific
one within the same `activity_` group, the validator raises
`RegistryOrderError` (defined in `vultron/errors.py`) immediately on import.

This is a hard guard: a mis-ordered registry **prevents the module from
loading**, making the error impossible to miss.

### Algorithm

The validator uses the same subset logic as
`test_non_overlapping_activity_patterns` in
`test/test_semantic_activity_patterns.py`:

1. Group entries by `activity_` type.
2. For every pair `(A, B)` where A appears before B in the registry:
   - If `dump(B)` is a strict subset of `dump(A)` (B is more specific),
     A should have appeared after B — raise `RegistryOrderError`.
3. Pass if no out-of-order pairs are found.

The test `test_non_overlapping_activity_patterns` is a belt-and-suspenders
check that also catches edge cases the runtime validator might miss (e.g.,
patterns whose `model_dump()` raises). Both should remain.

---

## Common Pitfall: Adding a Pattern Without Running Tests

When adding a new `ActivityPattern` to `extractor.py`:

1. Define the pattern object (named `<TypeName>Pattern`).
2. Add a `SemanticEntry` to `SEMANTIC_REGISTRY` in the correct group
   position (specific before general).
3. Run `test/test_semantic_activity_patterns.py` immediately — the import-
   time guard fires in CI but running the test file locally is faster
   feedback.
4. If the import raises `RegistryOrderError`, move the new entry earlier in
   the registry (before the more-general entry it conflicts with).

The `test_non_overlapping_activity_patterns` test will also catch ordering
errors that the runtime validator might not catch in all edge cases.

---

## File Locations

| File | Role |
|---|---|
| `vultron/wire/as2/extractor.py` | `ActivityPattern` class + all `*Pattern` instances |
| `vultron/semantic_registry/` | `SEMANTIC_REGISTRY`, `find_matching_semantics()`, `_validate_registry_order()` |
| `vultron/errors.py` | `RegistryOrderError(VultronError)` |
| `test/test_semantic_activity_patterns.py` | Pattern ordering + dispatch tests |

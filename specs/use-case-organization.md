# Use-Case Organization Specification

## Overview

Requirements for the physical package layout of `vultron/core/use_cases/`,
registry synchronization, test mirroring, and documentation of the
trigger → received → sync information flow pattern.

**Source**: `plan/IMPLEMENTATION_PLAN.md` REORG-1
**Cross-references**: `specs/code-style.md` CS-12-002,
`specs/handler-protocol.md`

---

## Package Layout

- `UCORG-01-001` (MUST) Use-case classes that process inbound received messages
  MUST reside under `vultron/core/use_cases/received/`
  - Modules in `received/` SHOULD group use cases by protocol domain
    (e.g., `report.py`, `case.py`, `embargo.py`, `participant.py`)
  - UCORG-01-001 implements CS-12-002 (code-style.md)
- `UCORG-01-002` (MUST) Trigger use-case classes that implement actor-initiated
  behaviors MUST reside under `vultron/core/use_cases/triggers/`
  - UCORG-01-002 implements CS-12-002 (code-style.md)
- `UCORG-01-003` The `vultron/core/use_cases/` package root MUST contain
  only `__init__.py` and `use_case_map.py`; use-case implementations MUST
  NOT be placed at the root level

## Registry Synchronization

- `UCORG-02-001` Any relocation or rename of a use-case class MUST update
  `USE_CASE_MAP` in `vultron/core/use_cases/use_case_map.py` in the same
  commit
- `UCORG-02-002` A dispatch coverage test MUST verify that every
  `MessageSemantics` value registered in `USE_CASE_MAP` resolves to a
  callable class and that dispatch succeeds for a representative event
  - The test MUST live in `test/core/use_cases/test_use_case_map.py` or an
    equivalent coverage module

## Test Layout

- `UCORG-03-001` Tests MUST mirror the source layout:
  - `test/core/use_cases/received/` mirrors
    `vultron/core/use_cases/received/`
  - `test/core/use_cases/triggers/` mirrors
    `vultron/core/use_cases/triggers/`
  - UCORG-03-001 refines TB-04-001 (testability.md)

## Information Flow Documentation

- `UCORG-04-001` (SHOULD) The trigger → received → sync information flow pattern
  SHOULD be documented in `notes/` and summarized in a `README.md` under
  `vultron/core/use_cases/`
  - Pattern: local triggers emit outbound activities; received handlers
    process inbound activities from remote actors; sync replicates the
    resulting case event log to all participants

---
source: ISSUE-1808
timestamp: '2026-07-29T20:40:49.748458+00:00'
title: Typed Ports base classes, ADR-0044, BTND-03-009–011, validate_report pilot
type: implementation
---

## Issue #1808 — Adopt py_trees typed Ports: base class, convention, ADR/spec, pilot one subtree

Implementation complete. PR: <https://github.com/CERTCC/Vultron/pull/1827>

### Deliverables

- `DataLayerConditionWithPorts` and `DataLayerActionWithPorts` in `vultron/core/behaviors/helpers.py`
- ADR-0044 (`docs/adr/0044-py-trees-typed-ports-adoption.md`) + ADR index + mkdocs nav
- BTND-03-009 through BTND-03-011 in `specs/behavior-tree-node-design.yaml`
- 4 pilot nodes migrated: `CheckRMStateValid`, `CheckRMStateReceivedOrInvalid`, `EnsureEmbargoExists`, `TransitionRMtoValid`
- 25-test `test/core/behaviors/report/nodes/test_typed_ports.py`
- 6-step migration recipe in `notes/py-trees-ports-adoption.md`

### Key fixes during implementation

- YAML spec entries with inline `{key: value}` maps required `>` folded scalars
- py_trees ports registry collision in tests: inline subclasses across two tests with the same name trigger UserWarning → narrowed with unique class names
- mkdocs nav required explicit ADR entry (enforced by `adr-index-sync` pre-commit hook)
- `except Exception` narrowed to `except NoDataAvailable` for optional trigger_activity_factory port
- `NoDataAvailable` timing corrected: surfaces in `initialise()` (first tick), not `setup()`

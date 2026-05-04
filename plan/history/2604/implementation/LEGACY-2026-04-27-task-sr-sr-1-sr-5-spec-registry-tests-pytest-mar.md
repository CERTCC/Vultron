---
title: "TASK-SR SR.1\u2013SR.5 \u2014 Spec Registry Tests, Pytest Marker,\
  \ Pre-commit Hook"
type: implementation
timestamp: '2026-04-27T00:00:00+00:00'
source: LEGACY-2026-04-27-task-sr-sr-1-sr-5-spec-registry-tests-pytest-mar
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 8074
legacy_heading: "TASK-SR SR.1\u2013SR.5 \u2014 Spec Registry Tests, Pytest\
  \ Marker, Pre-commit Hook"
date_source: git-blame
---

## TASK-SR SR.1–SR.5 — Spec Registry Tests, Pytest Marker, Pre-commit Hook

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:8074`
**Canonical date**: 2026-04-27 (git blame)
**Legacy heading**

```text
TASK-SR SR.1–SR.5 — Spec Registry Tests, Pytest Marker, Pre-commit Hook
```

**Completed**: 2026-04-27

### Summary

Completed SR.1–SR.5 of TASK-SR (spec registry feature). All stub modules in
`vultron/metadata/specs/` were already fully implemented; this stage adds
test coverage, pytest marker integration, and a pre-commit hook.

### Changes

- `vultron/metadata/specs/__init__.py`: Added `UnknownSpecIdWarning(UserWarning)`
  and `warn_unknown_spec_id(spec_id, registry)` helper; updated `__all__`.
- `test/metadata/specs/__init__.py`: New package marker (empty).
- `test/metadata/specs/conftest.py`: Fixtures: `MINIMAL_YAML`, `SECOND_YAML`,
  `spec_dir`, `multi_spec_dir`, `loaded_registry`.
- `test/metadata/specs/test_schema.py` (SR.1.3): 27 tests — `SpecIdStr`
  valid/invalid patterns, `StatementSpec`/`BehavioralSpec` validation,
  `SpecGroup`/`SpecFile`, duplicate-ID error, `load_registry` round-trips,
  `get`/`all_specs`/cross-references.
- `test/metadata/specs/test_lint.py` (SR.2.4): 11 tests — hard errors
  (duplicate IDs, dangling relationship, prefix mismatch → return 1),
  advisory warnings (testable-without-steps, rationale-too-long,
  missing-tags → return 0), `lint_suppress` suppression.
- `test/metadata/specs/test_render.py` (SR.5.3): 14 tests —
  `render_markdown`, `export_json` (filter by priority/kind/scope/tags),
  `render_registry_markdown`.
- `test/metadata/specs/test_spec_marker.py` (SR.3.3): 4 tests —
  `UnknownSpecIdWarning` is `UserWarning` subclass, emits for unknown ID,
  silent for known ID, works with empty registry.
- `test/conftest.py` (SR.3.1, SR.3.2): Added `pytest_configure` (registers
  `spec` marker) and `pytest_collection_modifyitems` (warns for unknown IDs;
  skips silently when no YAML files exist).
- `pyproject.toml`: Added `spec` marker to `markers` list; added
  `"always::vultron.metadata.specs.UnknownSpecIdWarning"` before `"error"`
  in `filterwarnings`.
- `.pre-commit-config.yaml` (SR.4.1): Added `spec-lint` local hook
  (`language: system`, `pass_filenames: false`, fires on `specs/*.yaml`).

### Test results

56 new tests pass; full suite: 1878 passed, 12 skipped, 5633 subtests passed.
mypy and pyright: zero errors.

### Notes

- `pytest_collection_modifyitems` returns early when `registry.files == []`
  (no YAML yet); SR.6 migration will activate validation automatically.
- `filterwarnings` ordering: `"always::UnknownSpecIdWarning"` placed BEFORE
  `"error"` so the specific rule takes precedence (Python prepend semantics).
- `Spec = Union[BehavioralSpec, StatementSpec]` always parses as
  `BehavioralSpec`; tests assert on `spec.steps == []` not `isinstance`.

### Deferred

SR.6 (migration of ~49 `specs/*.md` files) deferred to next build run.

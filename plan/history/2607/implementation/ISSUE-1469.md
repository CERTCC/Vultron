---
source: ISSUE-1469
timestamp: '2026-07-15T19:03:43.802571+00:00'
title: 'fix(render): export_yaml preserves all typed Precondition and SpecGroup.trigger
  fields'
type: implementation
---

## Issue #1469 — fix(render): export_yaml silently drops typed Precondition fields

**Root cause**: `_add_behavioral_spec_fields` in `vultron/metadata/specs/render.py` serialized `Precondition` objects as `{"description": item.description}` only, silently dropping `rm_state`, `em_state`, `role`, `cs_pattern`. Separately, `_group_to_dict` never serialized `SpecGroup.trigger`.

**Fix**:

- Added `_precondition_dict()` helper that emits all typed fields (in field declaration order) before `description`
- Updated `_group_to_dict()` to emit `trigger: {type, value}` when present

**Regression tests added** (3):

- `test_export_yaml_precondition_typed_fields_preserved` — confirms typed fields survive export
- `test_export_yaml_group_trigger_preserved` — confirms trigger survives export
- `test_export_yaml_round_trips_through_schema` — full YAML round-trip reloads cleanly through Pydantic

Fixed in the same commit as #1450 (same branch/PR).

PR: <https://github.com/CERTCC/Vultron/pull/1470>

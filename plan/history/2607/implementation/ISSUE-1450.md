---
source: ISSUE-1450
timestamp: '2026-07-15T18:54:39.928700+00:00'
title: 'spec(schema): enforce Precondition.description required + fix all BehavioralSpec
  YAML items'
type: implementation
---

## Issue #1450 — enforce Precondition.description required + fix all BehavioralSpec YAML items

All four acceptance criteria met:

- AC-1: `Precondition.description` changed from `Optional[str]` to `NonEmptyStr` (required); `Postcondition.description` also upgraded to `NonEmptyStr`; `Precondition` field order updated to `rm_state` → `em_state` → `role` → `cs_pattern` → `description` (matches mad-lib clause order)
- AC-2: 116 description fields added to all precondition blocks across rm-behavior.yaml (39), em-behavior.yaml (43), cs-behavior.yaml (34) using a consistent mad-lib pattern: clauses joined by `"; "` in field declaration order
- AC-3: `uv run spec-dump` exits 0 with no validation errors
- AC-4: `notes/behavioral-conformance-specs.md` updated with description requirement, mad-lib clause templates and separator rule, field declaration order callout

Mad-lib clause templates:

- `rm_state: [X]` → `"Participant is in RM X"`
- `em_state: [X, Y]` → `"EM state is X or Y"`
- `role: [X]` → `"Participant holds the X role"`
- `cs_pattern: "abc..."` → `"CS matches pattern abc..."`

Tests: added `test_precondition_description_required` and `test_precondition_description_only_typed_fields_optional`; updated round-trip test with description field.

DEFER: #1469 created for pre-existing `render.py export_yaml` bug (drops all typed Precondition fields).

PR: <https://github.com/CERTCC/Vultron/pull/1470>

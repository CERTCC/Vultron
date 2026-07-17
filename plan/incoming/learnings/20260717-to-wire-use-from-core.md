---
title: "_to_wire must use wire_cls.from_core(), not model_dump+model_validate"
type: learning
timestamp: 2026-07-17
source: ISSUE-1503
---

When converting a core domain object to a wire type in adapter code,
`wire_cls.from_core(core_obj)` is the correct entry point, NOT
`wire_cls.model_validate(core_obj.model_dump(by_alias=True, serialize_as_any=True))`.

The `model_dump+model_validate` pattern breaks silently when a wire class has
field types that differ from the core class. Concrete example:
`VulnerabilityCase.case_activity` is `list[str]` (URI strings) in core, but
`as_VulnerabilityCase.case_activity` is `list[as_Activity]`. Pydantic raises
`ValidationError` when validating URI strings as `as_Activity` objects.

`from_core` is defined on `VultronAS2Object` (and overridden on specific wire
classes) and handles all field-type differences via `_field_map`, `_strip_core_context`,
and custom conversion logic. It is the canonical core→wire conversion path.

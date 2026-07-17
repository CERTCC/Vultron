---
title: Wire/core type mismatch — EmbargoedCase.model_validate() fails on DataLayer objects
type: learning
timestamp: 2026-07-17
source: ISSUE-1455
---

DataLayer `read()` returns wire objects (`as_VulnerabilityCase`, `as_CaseStatus`). Calling `EmbargoedCase.model_validate(wire_obj)` or `Case.model_validate(wire_obj)` always fails with pydantic `ValidationError` because `as_CaseStatus` is not a valid `CaseStatus` in pydantic's view. AC-1 and AC-5 of #1455 were reverted for this reason.

Before attempting staged-type promotion at any BT node or use case entry point, verify whether the value comes from `resolve_case()` / `DataLayer.read()` (wire) or a core model constructor (core). The `EmbargoedCase`/`Case` validators are only usable on objects that have already been constructed through core model paths.

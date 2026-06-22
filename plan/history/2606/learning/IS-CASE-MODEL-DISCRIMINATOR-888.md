---
source: IS-CASE-MODEL-DISCRIMINATOR-888
timestamp: '2026-06-22T19:32:14.041632+00:00'
title: is_case_model() must not use removed methods as discriminators
type: learning
---

`is_case_model()` in `vultron/core/models/protocols.py` used
`hasattr(obj, "record_event")` as one of its structural checks. Removing
`record_event()` from the wire-layer `VulnerabilityCase` silently broke
this type guard: `find_case_by_report_id()` returned `None` because the
stored wire case no longer matched, causing 440 test failures.

Rule: discriminators in `is_case_model()` (and similar type guards) MUST
use fields/methods declared on the `CaseModel` Protocol itself. The fix
replaced `hasattr(obj, "record_event")` with `hasattr(obj, "case_statuses")`,
which is a declared Protocol member present on both wire and core
`VulnerabilityCase`. Always audit type-guard discriminators when removing
a method from a class matched by one of these guards.

**Promoted**: 2026-06-22 — captured in `specs/code-style.yaml` (CS-20-002) and
`AGENTS.md` pitfalls.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

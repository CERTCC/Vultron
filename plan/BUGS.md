# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYMMDDXX` for bug IDs, where `YYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,
the first bug identified on March 26, 2026 would be `BUG-26032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-26050101 tests are slow

The following tests account for well over a minute of runtime in the test suite.
This is a problem because it slows down development cycles.

```text
test/architecture/test_activity_factory_imports.py
test/metadata/test_append_history.py
test/adapters/driving/fastapi/routers/test_trigger_report.py
```

## BUG-26052601 Factory `cast()` does not coerce at runtime

**Symptom**: `VultronActivityConstructionError: rm_validate_report_activity:
invalid arguments` in all exchange demo tests (24 failures).

**Root cause**: `rm_validate_report_activity`, `rm_invalidate_report_activity`,
and `rm_close_report_activity` in `vultron/wire/as2/factories/report.py` used
`cast(RmSubmitReportActivity, offer)` to satisfy the type-checker.  `cast()`
is a no-op at runtime; Pydantic v2 rejects the plain `as_Offer` when it tries
to assign it to `RmValidateReportActivity.object_: RmSubmitReportActivity`.

**Fix**: Added `isinstance` guard + `RmSubmitReportActivity.model_validate()`
coercion before construction in each of the three factory functions.  Also
added public `parse_submit_report_offer()` factory helper. See commits.

**Status**: Fixed.

## BUG-26052602 `finder_submits_report` loses VulnerabilityReport ID

**Symptom**: `404 Not Found` when verifying stored report in
`TestTriggerLogCommit`, `TestWaitForFinderLogEntry`,
`TestVerifyFinderReplicaState`, `TestRunTwoActorDemo` (5 failures).

**Root cause**: `two_actor_demo.py` called `as_Offer.model_validate(offer_dict)`
on the trigger response.  `as_Offer.object_: as_Object | str | None`, so
`offer.object_` was an `as_Object`, not a `VulnerabilityReport`.  The
`isinstance` fallback created a NEW `VulnerabilityReport` with a fresh UUID,
which was never stored.

**Fix**: Replaced the broken parse + fallback chain with
`parse_submit_report_offer(offer_dict)` from the factory package, which coerces
the dict to `RmSubmitReportActivity` and returns `(report, offer)` with the
correct stable IDs. See commits.

**Status**: Fixed.

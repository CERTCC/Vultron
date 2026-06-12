# Case-Log Invariant Ratchet Workflow

This document describes the ratchet workflow for the CI case-log invariant
harness (`test/ci/test_case_log_invariants.py`), satisfying AC-6 of issue
[#925](https://github.com/CERTCC/Vultron/issues/925).

---

## Overview

The harness parses JSONL case-log replica files produced by the two-actor
demo and asserts a fixed set of canonical-log invariants. All invariants
that are not yet passing are decorated with `pytest.mark.xfail` so the CI
build stays green while fix PRs land one at a time.

Each fix PR ratchets exactly one invariant from "expected failure" to
"permanent regression guard" by removing its `xfail` decorator.

---

## Running the Harness

### In CI (after the demo produces JSONL artifacts)

```bash
uv run pytest -m case_log_invariants -v
```

Or target the file directly:

```bash
uv run pytest test/ci/test_case_log_invariants.py -v
```

### Locally (without demo artifacts)

All tests will **skip** automatically when `devlogs/` is absent — safe
to include in the regular unit-test run.

---

## Invariant List and Status

Per-actor parametrized tests (12–14) show status per actor role.
`✅` = passing today, `⏳` = xfail (fix tracked in linked issue).

| # | Description | case-actor | vendor | finder | Resolving issue |
|---|-------------|-----------|--------|--------|-----------------|
| 1 | Local hash-chain consistency | ✅ | ✅ | ⏳ | #789 |
| 2 | Cross-actor `entryHash` agreement per `logIndex` | ⏳ | ⏳ | ⏳ | #789 |
| 3 | Cross-actor `payloadSnapshot.actor` agreement | ⏳ | ⏳ | ⏳ | #789 |
| 4 | Every recorded entry has non-empty `payloadSnapshot` | ⏳ | ⏳ | ⏳ | #789 |
| 5 | All expected protocol `eventType`s present | ⏳ | ⏳ | ⏳ | #789 |
| 6 | No RM-state oscillation after `CLOSED` | ✅ | ✅ | ✅ | — |
| 7 | Log terminates with all participants `RM=CLOSED` | ⏳ | ⏳ | ⏳ | #789 |
| 8 | Late-joining participants have full pre-join history | ⏳ | ⏳ | ⏳ | #791 |
| 9 | Every `ParticipantStatus` has `emConsentState`+`cvdRole` | ⏳ | ⏳ | ⏳ | #789 |
| 10 | Nested objects inlined (not bare ID strings) | ✅ | ✅ | ✅ | — |
| 11 | `payloadSnapshot.context` uses case URI | ✅ | ✅ | ✅ | — |
| 12 | `logIndex=0` entry is present in actor's log | ✅ | ✅ | ⏳ | #791 |
| 13 | First entry in sorted log has `logIndex=0` | ✅ | ✅ | ⏳ | #791 |
| 14 | No gaps in `logIndex` sequence (0 to max) | ✅ | ✅ | ⏳ | #791 |

---

## Ratchet: Flipping an xfail to Passing

When a fix PR lands that resolves one of the `xfail` invariants:

1. **Identify the test function** — each test's docstring contains its
   AC number (e.g., `AC-4.2`) and a note: "remove the `xfail` decorator
   to make it a permanent regression guard."

2. **Remove the `xfail` decorator** from that test function.

3. **Run the harness** (with demo artifacts in place) to confirm the test
   now passes:

   ```bash
   uv run pytest test/ci/test_case_log_invariants.py -v
   ```

4. **Commit the decorator removal** in the same PR as (or immediately
   after) the fix, citing the issue number.

5. **Update the table above** — change ⏳ xfail to ✅ passing and clear
   the "Resolving issue" column.

---

## Adding a New Invariant

1. Open `test/ci/test_case_log_invariants.py`.

2. Write a new `test_invariant_<N>_<slug>` function following the
   existing pattern.

3. If the invariant is expected to pass today, add no `xfail` decorator.

4. If the invariant will be fixed by a future PR, add:

   ```python
   @pytest.mark.case_log_invariants
   @pytest.mark.xfail(
       strict=False,
       reason="<description>; will pass when #<issue> lands",
   )
   def test_invariant_<N>_<slug>(
       case_log_replicas: dict[str, list[dict]],
   ) -> None:
       """<One-line summary> (AC-4.N).

       When this xfail is unexpectedly promoted to XPASS, remove the
       ``xfail`` decorator to make it a permanent regression guard.
       """
       ...
   ```

5. Add a row to the invariant table above.

6. Run `uv run pytest test/ci/test_case_log_invariants.py -v` (with demo
   artifacts) to confirm the new test appears with the expected
   `XFAIL` status.

---

## CI Behavior (AC-5)

| Scenario | Outcome |
|----------|---------|
| Non-xfailed invariant passes | ✅ green |
| Non-xfailed invariant **fails** | ❌ build fails |
| xfailed invariant fails (expected) | ✅ green (reported as `XFAIL`) |
| xfailed invariant passes unexpectedly | ✅ green but reported as `XPASS` |
| No `devlogs/` present | ✅ green (all tests skipped) |

The `strict=False` on every `xfail` decorator implements this: unexpected
passes (`XPASS`) are visible in the CI report but do not cause a non-zero
exit code.

---

## JSONL Artifact Location

The two-actor demo writes one JSONL file per actor under:

```text
devlogs/<demo_name>/<actor_name>/<case_id_slug>-case-log.jsonl
```

For the standard two-actor run this produces:

```text
devlogs/two-actor/finder/...jsonl
devlogs/two-actor/vendor/...jsonl
devlogs/two-actor/case-actor/...jsonl
```

These files are collected by the `Upload case log JSONL files` step in
`.github/workflows/demo-integration.yml` and are available to the
invariant harness when it runs in the same CI job.

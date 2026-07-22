# Case-Log Invariant Ratchet Workflow

This document describes the ratchet workflow for the CI case-ledger invariant
harness, satisfying AC-6 of issue
[#925](https://github.com/CERTCC/Vultron/issues/925).

The harness is modular (issue [#1592](https://github.com/CERTCC/Vultron/issues/1592)):
universal invariant check functions live in
`test/ci/invariants/common.py`; each scenario has its own test file under
`test/ci/invariants/`.

| Scenario | Test file |
|----------|-----------|
| FV (two-actor) | `test/ci/invariants/test_fv_invariants.py` |
| FVV (three-actor) | `test/ci/invariants/test_fvv_invariants.py` |
| FVCV-extension | `test/ci/invariants/test_fvcv_extension_invariants.py` |

---

## Overview

Each scenario test file parses JSONL case-ledger replica files produced by
the corresponding demo and asserts universal invariants (via `common.py`)
plus scenario-specific checks. All invariants that are not yet passing are
decorated with `pytest.mark.xfail` so the CI build stays green while fix
PRs land one at a time.

Each fix PR ratchets exactly one invariant from "expected failure" to
"permanent regression guard" by removing its `xfail` decorator.

---

## Running the Harness

### In CI (after the demo produces JSONL artifacts)

```bash
uv run pytest -m case_ledger_invariants -v
```

Or target a specific scenario directly:

```bash
uv run pytest test/ci/invariants/test_fv_invariants.py -v
uv run pytest test/ci/invariants/test_fvv_invariants.py -v
uv run pytest test/ci/invariants/test_fvcv_extension_invariants.py -v
```

### Locally (without demo artifacts)

All tests will **skip** automatically when `devlogs/` is absent — safe
to include in the regular unit-test run.

---

## Invariant List and Status

Per-actor parametrized tests (1, 12–14) show status per actor role.
`✅` = passing today, `⏳` = xfail (fix tracked in linked issue).

| # | Description | case-actor | vendor | finder | Resolved by |
|---|-------------|-----------|--------|--------|-------------|
| 1 | Local hash-chain consistency | ✅ | ✅ | ✅ | #789, #791 |
| 2 | Cross-actor `entryHash` agreement per `logIndex` | ✅ | n/a | n/a | #789 |
| 3 | Cross-actor `payloadSnapshot.actor` agreement | ✅ | n/a | n/a | #789 |
| 4 | Every recorded entry has non-empty `payloadSnapshot` | ✅ | n/a | n/a | #789 |
| 5 | All expected protocol `eventType`s present | ✅ | n/a | n/a | #1029, #1030 |
| 6 | No RM-state oscillation after `CLOSED` | ✅ | n/a | n/a | #936 |
| 7 | Log terminates with all participants `RM=CLOSED` | ✅ | n/a | n/a | #789 |
| 8 | Late-joining participants have full pre-join history | ✅ | n/a | n/a | #937 |
| 9 | Every `ParticipantStatus` has `emConsentState`+`cvdRole` | ✅ | n/a | n/a | #936 |
| 10 | Nested objects inlined (not bare ID strings) | ✅ | n/a | n/a | #936 |
| 11 | `payloadSnapshot.context` uses case URI | ✅ | n/a | n/a | #936 |
| 12 | `logIndex=0` entry is present in actor's log | ✅ | ✅ | ✅ | #937 |
| 13 | First entry in sorted log has `logIndex=0` | ✅ | ✅ | ✅ | #937 |
| 14 | No gaps in held `logIndex` range (`min`–`max`) | ✅ | ✅ | ✅ | #937 |
| 15 | All key CS transitions observed (`VFd`, `VFD`, `Pxa`) | ✅ | n/a | n/a | #1020 |

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
   uv run pytest test/ci/invariants/ -v
   ```

4. **Commit the decorator removal** in the same PR as (or immediately
   after) the fix, citing the issue number.

5. **Update the table above** — change ⏳ xfail to ✅ passing and clear
   the "Resolving issue" column.

---

## Adding a New Invariant

### Universal invariant (applies to all scenarios)

1. Add a `check_<name>` function to `test/ci/invariants/common.py`
   following the existing pattern (returns `list[str]` of violations).

2. Add a `test_invariant_<N>_<slug>` function to each scenario test file
   that calls the new check function.

### Scenario-specific invariant

1. Open the appropriate per-scenario file (e.g.,
   `test/ci/invariants/test_fv_invariants.py`).

2. Write a new `test_<scenario>_<slug>` function using helpers from
   `common.py` rather than duplicating logic inline.

3. If the invariant is expected to pass today, add no `xfail` decorator.

4. If the invariant will be fixed by a future PR, add:

   ```python
   @pytest.mark.case_ledger_invariants
   @pytest.mark.xfail(
       strict=False,
       reason="<description>; will pass when #<issue> lands",
   )
   def test_<scenario>_<slug>(
       <fixture>: dict[str, list[dict]],
   ) -> None:
       """<One-line summary>.

       When this xfail is unexpectedly promoted to XPASS, remove the
       ``xfail`` decorator to make it a permanent regression guard.
       """
       ...
   ```

5. Add a row to the invariant table above.

6. Run `uv run pytest test/ci/invariants/ -v` (with demo artifacts) to
   confirm the new test appears with the expected `XFAIL` status.

### Adding a new scenario

1. Create `test/ci/invariants/test_<scenario>_invariants.py`.

2. Define a module-scoped fixture that calls `load_devlogs(demo_name=...)`.

3. Add the universal invariants by importing from `common.py` and calling
   the check helpers.

4. Add scenario-specific invariants below the universal section.

5. Update the scenario table at the top of this document.

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
devlogs/<demo_name>/<actor_name>/<case_id_slug>-case-ledger.jsonl
```

For the standard two-actor run this produces:

```text
devlogs/two-actor/finder/...jsonl
devlogs/two-actor/vendor/...jsonl
devlogs/two-actor/case-actor/...jsonl
```

These files are collected by the `Upload case ledger JSONL files` step in
`.github/workflows/demo-integration.yml` and are available to the
invariant harness when it runs in the same CI job.

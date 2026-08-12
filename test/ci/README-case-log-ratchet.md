# Case-Log Invariant Harness

This document describes the CI case-ledger invariant harness, satisfying AC-6
of issue [#925](https://github.com/CERTCC/Vultron/issues/925).

The harness is modular (issue [#1592](https://github.com/CERTCC/Vultron/issues/1592)):
universal invariant check functions live in
`test/ci/invariants/common.py`; each scenario has its own test file under
`test/ci/invariants/`.

| Scenario | Test file |
|----------|-----------|
| FV | `test/ci/invariants/test_fv_invariants.py` |
| FVV (three-actor) | `test/ci/invariants/test_fvv_invariants.py` |
| FVCV-extension | `test/ci/invariants/test_fvcv_extension_invariants.py` |
| FVCV-handoff | `test/ci/invariants/test_fvcv_handoff_invariants.py` |

---

## Overview

Each scenario test file parses JSONL case-ledger replica files produced by
the corresponding demo and asserts universal invariants (via `common.py`)
plus scenario-specific checks. All invariants are currently passing — there
are no active `xfail` markers.

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
uv run pytest test/ci/invariants/test_fvcv_handoff_invariants.py -v
```

### Locally (without demo artifacts)

All tests will **skip** automatically when `devlogs/` is absent — safe
to include in the regular unit-test run.

---

## Invariant Status

Per-actor parametrized tests (1, 12–14) show status per actor role.

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

## CI Behavior (AC-5)

| Scenario | Outcome |
|----------|---------|
| Invariant passes | ✅ green |
| Invariant **fails** | ❌ build fails |
| No `devlogs/` present | ✅ green (all tests skipped) |

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

   Then add a row to the invariant status table above.

### Adding a new scenario

1. Create `test/ci/invariants/test_<scenario>_invariants.py`.

2. Define a module-scoped fixture that calls `load_devlogs(demo_name=...)`.

3. Add the universal invariants by importing from `common.py` and calling
   the check helpers.

4. Add scenario-specific invariants below the universal section.

5. Update the scenario table at the top of this document.

---

## JSONL Artifact Location

The FV demo writes one JSONL file per actor under:

```text
devlogs/<demo_name>/<actor_name>/<case_id_slug>-case-ledger.jsonl
```

For the standard FV run this produces:

```text
devlogs/fv/finder/...jsonl
devlogs/fv/vendor/...jsonl
devlogs/fv/case-actor/...jsonl
```

These files are collected by the `Upload case ledger JSONL files` step in
`.github/workflows/demo-integration.yml` and are available to the
invariant harness when it runs in the same CI job.

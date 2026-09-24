# Case-Log Invariant Harness

This document describes the CI case-ledger invariant harness, satisfying AC-6
of issue [#925](https://github.com/CERTCC/Vultron/issues/925).

The harness is modular (issue [#1592](https://github.com/CERTCC/Vultron/issues/1592)):
universal invariant check functions live in
`test/ci/invariants/common.py`; each scenario has its own test file under
`test/ci/invariants/`.

Each scenario declares itself in its own demo module by decorating `main()`
with `@scenario(...)` from `vultron/demo/scenario/registry.py`; that registry
is the sole declaration point (ADR-0098, DEMOCI-11-001). Both the table below
and `.github/demo-scenarios.json` are generated from it, and the harness path
in each row is derived from the scenario name by convention rather than stored
(DEMOCI-11-003). Do not hand-edit either — change the decorator and run
`uv run demo-scenarios --write`.

<!-- BEGIN GENERATED SCENARIO TABLE — do not edit; edit the @scenario decorators and run `uv run demo-scenarios --write` -->

| Scenario | Test file | In PR set |
|---|---|---|
| FCCV-extension | `test/ci/invariants/test_fccv_extension_invariants.py` |  |
| FCCV-handoff | `test/ci/invariants/test_fccv_handoff_invariants.py` |  |
| FCV | `test/ci/invariants/test_fcv_invariants.py` |  |
| FCV-reject | `test/ci/invariants/test_fcv_reject_invariants.py` | ✓ |
| FCVCV | `test/ci/invariants/test_fcvcv_invariants.py` | ✓ |
| FV | `test/ci/invariants/test_fv_invariants.py` | ✓ |
| FVCV-extension | `test/ci/invariants/test_fvcv_extension_invariants.py` |  |
| FVCV-handoff | `test/ci/invariants/test_fvcv_handoff_invariants.py` | ✓ |
| FVV | `test/ci/invariants/test_fvv_invariants.py` |  |

<!-- END GENERATED SCENARIO TABLE -->

Scenarios marked *In PR set* run on `pull_request` events (the DEMOCI-06-002
minimum validation set); all of them run on push-to-main and
`workflow_dispatch`.

The other files in `test/ci/invariants/` are not scenario harnesses and need no
demo artifacts: `test_universal_event_types.py` and `test_diagnostic_map_sync.py`
are structural ratchets over the harness constants, the DEMOMA-16-001 spec
statement and the diagnostic map, while `test_common.py`, `test_late_joiner.py`
and `test_causal_edges_negative.py` unit-test the `common.py` check helpers.

---

## Overview

Each scenario test file parses JSONL case-ledger replica files produced by
the corresponding demo and asserts universal invariants (via `common.py`)
plus scenario-specific checks. Some universal invariants carry a live `xfail`
marker; the rest are active, so a failure is a real regression. Which are which
is recorded in one ratcheted place — see
[Invariant Status](#invariant-status) — and deliberately not counted here,
because a count restated in prose is the part that goes stale.

---

## Running the Harness

### In CI (after the demo produces JSONL artifacts)

```bash
uv run pytest -m case_ledger_invariants -v
```

Or target a specific scenario directly, using the harness file the scenario
table above names for it:

```bash
uv run pytest test/ci/invariants/test_fv_invariants.py -v
```

### Locally (without demo artifacts)

Every test in a *scenario harness* **skips** automatically when `devlogs/` is
absent, so the harnesses are safe to include in the regular unit-test run. The
structural ratchets and helper unit tests listed above do not skip — they read
source and docs, not artifacts, and are expected to run and pass everywhere.

One consequence worth knowing: the `_AllSkipGuard` in
`test/ci/invariants/conftest.py` (DEMOCI-10-005) forces a non-zero exit when
*every* collected test skipped, which is how a vacuous green is caught. It
judges the whole session, so it only works because CI invokes one harness file
at a time. Do not "helpfully" widen that CI command to the directory — adding
the non-skipping tests to the session defeats the guard.

---

## Invariant Status

**The per-invariant inventory lives in
[`notes/demo-ci-diagnostics.md`](../../notes/demo-ci-diagnostics.md)
§ "Per-Invariant Diagnostic Map".** Read it there. That table names every
universal invariant by test-function name, its `xfail`-or-active state and the
issue owning each `xfail`, and which of the three diagnostic layers to check
first — and `test/ci/invariants/test_diagnostic_map_sync.py` ratchets it against
`make_universal_invariant_tests()`, so it cannot drift silently.

This section used to carry a second copy of that table, keyed by per-actor
pass/fail. It is deliberately gone rather than resynced (ISSUE-3337). Two
reasons, both worth knowing before adding another one:

- **Two tables on one subject drift apart, and the reader cannot tell which is
  wrong.** This copy still cited #789/#791/#937 long after all three closed,
  omitted the four invariants added since it was written, and carried a row for
  invariant 8, which is not universal at all.
- **Per-actor pass/fail is not derivable from source**, so nothing can ratchet
  it. It records the outcome of one demo run on one day. The CI run is the
  ground truth for pass/fail; a checked-in doc is not.

The rule that follows: a doc may state what the source says — the `xfail`-vs-
active ratchet state and who owns each `xfail` — and must leave today's
pass/fail to CI.

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

2. Add a `test_invariant_<N>_<slug>` closure to
   `make_universal_invariant_tests()` in
   `test/ci/invariants/universal_harness.py`, and register it in that
   function's `result` dict. Do **not** copy the test into the per-scenario
   files — the factory injects it into all of them (ISSUE-2007).

3. Add a row for it to the diagnostic map in
   [`notes/demo-ci-diagnostics.md`](../../notes/demo-ci-diagnostics.md).
   `test/ci/invariants/test_diagnostic_map_sync.py` fails until you do.

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

   Name the owning issue in the `reason` string. For a universal invariant,
   record the same issue number in the diagnostic map's Status column;
   `test_diagnostic_map_sync.py` checks that the two agree.

   Two forms are rejected, because the diagnostic map cannot express either and
   would silently under-report:

   - **`marks=pytest.mark.xfail(...)` on a `pytest.param` entry** in a
     harness's `_CHAIN_ACTORS` or `_XXX_EXPECTED_EVENT_TYPES` list. That xfails
     only *some* cases of a universal invariant, and the map has one Status
     cell per invariant. Put the marker on the invariant in
     `universal_harness.py`, or make the check tolerate that actor.
   - **A conditional `xfail(condition=...)`**, which has no single truthful
     Status cell. Move the condition into the check itself.

   Scenario-local tests are exempt from both — they are not in the map.

### Adding a new scenario

1. Create `test/ci/invariants/test_<scenario>_invariants.py`.

2. Define a module-scoped fixture that calls `load_devlogs(demo_name=...)`.

3. Get the universal invariants by calling `make_universal_invariant_tests()`
   and splatting the result into module globals — **not** by importing
   `check_*` helpers from `common.py` and hand-rolling test functions. Copying
   them by hand is how a harness ends up with an arbitrary subset:

   ```python
   from test.ci.invariants.universal_harness import make_universal_invariant_tests

   globals().update(
       make_universal_invariant_tests(
           replicas_fixture="<scenario>_replicas",
           chain_actors=_CHAIN_ACTORS,
           expected_event_types=_<SCENARIO>_EXPECTED_EVENT_TYPES,
           narrative_path="docs/topics/scenarios/<scenario>.md",
       )
   )
   ```

   Pass `narrative_path`. Omitting it is legal and silently drops invariant 16
   (causal-edge ordering) for this scenario.

4. Add scenario-specific invariants below the universal section — count checks,
   late-joiner checks, and any protocol-path constraint unique to this
   scenario. Import `check_*` helpers from `common.py` for these rather than
   writing the logic inline.

5. Decorate the demo module's `main()` with `@scenario(...)` from
   `vultron/demo/scenario/registry.py`. That decoration is the **only** place
   the scenario is declared: the CI matrix in `.github/demo-scenarios.json`,
   the table at the top of this document and the sub-command table in
   `vultron/demo/scenario/README.md` are all generated from it. Name the
   harness file `test_<scenario>_invariants.py`, where `<scenario>` is the
   decorator's `name` with hyphens replaced by underscores — the registry
   derives the path and does not store it, so a mismatched filename fails
   rather than being silently described (DEMOCI-11-003).

6. Run `uv run demo-scenarios --write` to regenerate the three committed
   artifacts, and commit them. The `demo-scenarios-sync` pre-commit hook fails
   if you forget. `test_all_ci_scenarios_have_a_harness_module` still fails
   until DEMOMA-16 and the `notes/` scenario tables are updated, because those
   are hand-written prose that is checked rather than generated (#3451).

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

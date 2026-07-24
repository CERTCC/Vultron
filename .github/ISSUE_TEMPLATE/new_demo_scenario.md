---
name: "New Demo Scenario"
about: "Track all required update sites when adding a new multi-actor demo scenario"
title: "[Demo] Add <name> scenario"
labels: "enhancement,demo"
---

## Scenario overview

<!-- Briefly describe the scenario: actors involved, CVD workflow demonstrated,
     and which epics or issues this belongs to. -->

**Scenario name** (used in file names and CI): `<scenario-name>`
**Parent epic**: <!-- link to #1093 or a sub-epic -->

---

## Required update checklist

Every new multi-actor demo scenario MUST update all of the following in the
**same PR** (DEMOCI-03-002, DEMOCI-03-004).

### Implementation

- [ ] **Scenario script** — `vultron/demo/scenario/<scenario_name>_demo.py`
  - Module docstring describes actors, protocol flow, and CVD phases covered.
- [ ] **CLI registration** — `vultron/demo/cli.py`
  - Import the scenario module near the top.
  - Add a `@main.command(name="<scenario-name>")` function with URL options
    for each actor container.
- [ ] **Scenario README** — `vultron/demo/scenario/README.md`
  - Add a row to the available-demos table.

### CI integration

- [ ] **`demo-integration.yml`** (`.github/workflows/demo-integration.yml`)
  - Add a matrix entry to the `demo` job:
    ```yaml
    - demo: <scenario-name>
      test_file: test/ci/invariants/test_<scenario_name>_invariants.py
    ```
  - Add the **same** matrix entry to the `invariant-harness` job.
  - Entry MUST include `test_file`; job MUST use
    `--abort-on-container-exit --exit-code-from demo-runner`,
    `timeout-minutes: 15`, and the standard teardown/log-upload steps
    (DEMOCI-03-004, DEMOCI-03-005).
- [ ] **Integration test script** —
  `integration_tests/demo/run_multi_actor_integration_test.sh`
  - Add `<scenario-name>` to the `VALID_SCENARIOS` list (DEMOCI-02-003).

### Invariant harness

- [ ] **Invariant test file** — `test/ci/invariants/test_<scenario_name>_invariants.py`
  - Define `_<SCENARIO_NAME>_EXPECTED_EVENT_TYPES` extending the four
    universal types with any scenario-specific required event types
    (DEMOMA-16-001–16-008).
  - Add `test_<scenario_name>_<event>_at_least_N` functions for events
    that must appear more than once.
  - See `test/ci/invariants/test_fv_invariants.py` for the canonical
    structure.
- [ ] **Spec** — `specs/multi-actor-demo.yaml`
  - Add DEMOMA-16-XXX entries for each scenario-specific required event type
    (DEMOMA-16-008: spec and test MUST change in the same PR).

### Documentation

- [ ] **`docker/README.md`** — add the scenario to the available multi-actor
  scenario list with a brief description.
- [ ] **`notes/demo-future-ideas.md`** — remove or archive the entry for this
  scenario if it was previously listed as a planned future scenario.

---

## Notes

<!-- Any design decisions, actor-to-container mappings, or edge cases
     specific to this scenario. -->

## References

<!-- Links to related issues, ADRs, prior demo PRs (e.g., #1628, #1636),
     and the parent epic. -->

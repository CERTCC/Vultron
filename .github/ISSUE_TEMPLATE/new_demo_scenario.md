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

Every new multi-actor demo scenario MUST be registered in the **same PR** that
adds it (DEMOCI-03-002). The CI matrix, the CLI sub-command and the generated
scenario tables need no other step (ADR-0098, DEMOCI-11). Hand-written prose
that lists scenarios, such as the `notes/` tables and the `mkdocs.yml` nav, is
checked against the registry, so update it by hand (DEMOCI-11-007). See
`vultron/demo/AGENTS.md` § "A Scenario Declares Itself Once".

### Implementation

- [ ] **Scenario script** — `vultron/demo/scenario/<scenario_name>_demo.py`
  - Module docstring describes actors, protocol flow, and CVD phases covered.
  - `@scenario(...)` on `main()`, plus `ROLES` and `CLI_HELP`. These generate
    the `vultron-demo <scenario-name>` sub-command and its options. Do not add
    a `@main.command` block to `vultron/demo/cli.py` (DEMOCI-11-045).
- [ ] **Generated artifacts** — run `uv run demo-scenarios --write` and commit
  the result (`.github/demo-scenarios.json` and the generated scenario tables).
  Never hand-edit a generated file. `uv run demo-scenarios --check` reports any
  hand-written table or list that disagrees with the registry.
- [ ] **Narrative page** — `docs/topics/scenarios/<scenario-name>.md`, the path
  derived from the name (DEMOCI-11-003, DEMOCI-11-046), with its entry in the
  `mkdocs.yml` nav (DEMOCI-11-007).

### CI integration

- [ ] **No workflow edit.** The `demo` and `invariant-harness` job matrices of
  `.github/workflows/demo-integration.yml` are read from
  `.github/demo-scenarios.json`, so the registered scenario runs as its own
  matrix entry (DEMOCI-03-004, DEMOCI-03-006).
- [ ] **Integration test script** —
  `integration_tests/demo/run_multi_actor_integration_test.sh`
  - Add `<scenario-name>` to the `VALID_SCENARIOS` list.

### Invariant harness

- [ ] **Invariant test file** — `test/ci/invariants/test_<scenario_name>_invariants.py`
  - Define `_<SCENARIO_NAME>_EXPECTED_SEMANTIC_TYPES` extending the four
    universal types with any scenario-specific required semantic types
    (DEMOMA-16-001–16-008).
  - Add `test_<scenario_name>_<event>_at_least_N` functions for events
    that must appear more than once.
  - See `test/ci/invariants/test_rv_invariants.py` for the canonical
    structure.
- [ ] **Spec** — `specs/multi-actor-demo.yaml`
  - Add DEMOMA-16-XXX entries for each scenario-specific required semantic type
    (DEMOMA-16-018: spec and test MUST change in the same PR).

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

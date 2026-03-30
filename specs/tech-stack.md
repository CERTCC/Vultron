# Vultron Project Technology Stack Specification

## Overview

This specification defines the normative technology constraints and implementation requirements for the Vultron prototype implementation.

**Source**: Vultron project documentation  
**Note**: Applies to the prototype implementation unless otherwise stated

---

## Runtime and Language

- `IMPL-TS-01-001` The implementation MUST use Python 3.12 or later.
- `IMPL-TS-01-007` MUST Before updating the `requires-python` floor in
  `pyproject.toml`, the full test suite MUST pass on the target Python
  version in CI, and all static type checks (`mypy`, `pyright`) and linters
  MUST pass under the new runtime
  - Any deprecated or removed stdlib features MUST be replaced before the
    floor is raised
  - A runtime version bump of one minor version or more SHOULD be documented
    as an ADR in `docs/adr/`
  - IMPL-TS-01-007 refines IMPL-TS-01-001
- `IMPL-TS-01-002` The backend API MUST be implemented using FastAPI.
- `IMPL-TS-01-003` The backend API MUST expose an OpenAPI specification.
- `IMPL-TS-01-004` The system MUST use Pydantic for data validation and data modeling.
- `IMPL-TS-01-005` The application MUST use Python’s standard logging framework for structured logging.
- `IMPL-TS-01-006` The behavior tree engine MUST be implemented using py_trees.
  - exceptions:
    - The system MAY use custom behavior tree implementations for specific
      use cases like the original protocol simulation in `vultron/bt` and
      the `vultrabot.py` demo.

---

## Persistence and Data

- `IMPL-TS-02-001` The prototype MUST use TinyDB for lightweight local persistence.
- `IMPL-TS-02-002` The system MUST support JSON-based storage for demo and local development use.
- `IMPL-TS-02-003` The system MUST support ISO 8601 date/time parsing and formatting using isodate.
- `IMPL-TS-02-004` The system MUST support graph construction and analysis using networkx.

---

## Interfaces and Tooling

- `IMPL-TS-03-001` Command line interfaces MUST be implemented using `click`.
- `IMPL-TS-03-002` The system MUST support HTTP interactions with external services using requests.
- `IMPL-TS-03-003` The project MUST include automated tests implemented using `pytest`.
- `IMPL-TS-03-004` The project MUST support task automation using `make`.

---

## Documentation and Visualization

- `IMPL-TS-04-001` The project SHOULD generate static documentation using MkDocs.
- `IMPL-TS-04-002` The documentation SHOULD use `mkdocstrings` for API reference generation.
- `IMPL-TS-04-003` The documentation theme SHOULD use Material for MkDocs.
- `IMPL-TS-04-004` The documentation SHOULD support Mermaid diagrams for behavior trees, state machines, and process diagrams.

---

## Containerization and Deployment

- `IMPL-TS-05-001` The system SHOULD support containerization using Docker.
- `IMPL-TS-05-002` Multi-container demo environments SHOULD be orchestrated using `docker-compose`.
- `IMPL-TS-05-003` The project MUST use GitHub Actions for CI/CD.
- `IMPL-TS-05-004` CI workflows MUST include automated testing.
- `IMPL-TS-05-005` CI workflows SHOULD support static site generation and deployment to GitHub Pages.
- `IMPL-TS-05-006` Static documentation SHOULD be hosted via GitHub Pages.
- `IMPL-TS-05-007` Source code MUST be hosted in GitHub using git for version control.

---

## Code Quality Tooling

- `IMPL-TS-07-001` The project MUST use Black for code formatting; Black
  MUST be enforced via pre-commit hooks AND in the CI pipeline.
- `IMPL-TS-07-002` The project MUST use pyright for static type checking;
  pyright MUST run in CI and MUST pass with zero errors on every commit to
  `main` and on every pull request targeting `main`.
- `IMPL-TS-07-003` The project MUST use mypy for static type checking; mypy
  MUST run in CI and MUST pass with zero errors on every commit to `main`
  and on every pull request targeting `main`.
- `IMPL-TS-07-004` The project MUST use flake8 for PEP 8 linting; flake8
  MUST run in CI (without `--exit-zero`) and MUST pass with zero errors on
  every commit to `main` and on every pull request targeting `main`.
- `IMPL-TS-07-005` The CI pipeline MUST run tests (`pytest`), formatting
  (`black --check`), and all three linters (`flake8`, `mypy`, `pyright`) as
  separate parallel jobs. The build job MUST only execute when all parallel
  jobs pass.
  - **Rationale**: Parallel execution surfaces all failures simultaneously,
    reducing fix-cycle time and preserving the known-clean codebase baseline.
- `IMPL-TS-07-006` MUST The pytest configuration in `[tool.pytest.ini_options]`
  MUST include `filterwarnings = ["error"]` so that test-suite warnings are
  treated as errors and cannot accumulate as silent technical debt. Existing
  warnings MUST be resolved before this setting is activated; new warnings
  MUST NOT be introduced after it is active.
  - **Rationale:** Warnings that are silently emitted during the test run are
    a leading indicator of deprecated API usage, missing fixtures, and
    collection hygiene issues. Treating them as errors prevents accumulation
    and enforces immediate remediation.

---

## Optional and Prototype Extensions

- `IMPL-TS-06-001` The system MAY provide interactive demo interfaces using Streamlit.
- `IMPL-TS-06-002` The project MAY use uv for Python environment and dependency management.
- `IMPL-TS-06-003` The system MAY use rdflib and owlready2 for RDF and OWL ontology support.
- `IMPL-TS-06-004` The system MAY use numpy and pandas for data manipulation and analysis.

# Vultron Project Technology Stack Specification

## Overview

This specification defines the normative technology constraints and implementation requirements for the Vultron prototype implementation.

**Source**: Vultron project documentation  
**Note**: Applies to the prototype implementation unless otherwise stated

---

## Runtime and Language (MUST)

- `IMPL-TS-01-001` The implementation MUST use Python 3.12 or later.
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

## Persistence and Data (MUST)

- `IMPL-TS-02-001` The prototype MUST use TinyDB for lightweight local persistence.
- `IMPL-TS-02-002` The system MUST support JSON-based storage for demo and local development use.
- `IMPL-TS-02-003` The system MUST support ISO 8601 date/time parsing and formatting using isodate.
- `IMPL-TS-02-004` The system MUST support graph construction and analysis using networkx.

---

## Interfaces and Tooling (MUST)

- `IMPL-TS-03-001` Command line interfaces MUST be implemented using `click`.
- `IMPL-TS-03-002` The system MUST support HTTP interactions with external services using requests.
- `IMPL-TS-03-003` The project MUST include automated tests implemented using `pytest`.
- `IMPL-TS-03-004` The project MUST support task automation using `make`.

---

## Documentation and Visualization (SHOULD)

- `IMPL-TS-04-001` The project SHOULD generate static documentation using MkDocs.
- `IMPL-TS-04-002` The documentation SHOULD use `mkdocstrings` for API reference generation.
- `IMPL-TS-04-003` The documentation theme SHOULD use Material for MkDocs.
- `IMPL-TS-04-004` The documentation SHOULD support Mermaid diagrams for behavior trees, state machines, and process diagrams.

---

## Containerization and Deployment (SHOULD)

- `IMPL-TS-05-001` The system SHOULD support containerization using Docker.
- `IMPL-TS-05-002` Multi-container demo environments SHOULD be orchestrated using `docker-compose`.
- `IMPL-TS-05-003` The project SHOULD use GitHub Actions for CI/CD.
- `IMPL-TS-05-004` CI workflows SHOULD include automated testing.
- `IMPL-TS-05-005` CI workflows SHOULD support static site generation and deployment to GitHub Pages.
- `IMPL-TS-05-006` Static documentation SHOULD be hosted via GitHub Pages.
- `IMPL-TS-05-007` Source code MUST be hosted in GitHub using git for version control.

---

## Optional and Prototype Extensions (MAY)

- `IMPL-TS-06-001` The system MAY provide interactive demo interfaces using Streamlit.
- `IMPL-TS-06-002` The project MAY use uv for Python environment and dependency management.
- `IMPL-TS-06-003` The system MAY use rdflib and owlready2 for RDF and OWL ontology support.
- `IMPL-TS-06-004` The system MAY use numpy and pandas for data manipulation and analysis.
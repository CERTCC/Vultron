---
applyTo: "**/*.py"
---

# Python Project Structure & Style

### File Length & Refactoring

- **Target Size**: Aim for 150–500 lines of code per file (excluding
  comments/blanks) to ensure manageability and AI context compatibility.
- **Refactor Early**: When a file approaches 1000 lines, identify natural split
  points and decompose it into smaller modules.
- **Clarity Over Conciseness**: Prioritize readable, well-structured code 
  over "clever" or overly compact one-liners. Do not sacrifice clarity to 
  reduce line counts.

### Organization

- **Use Packages**: Organize related modules into directories containing an
  `__init__.py` file to maintain a clean hierarchical structure.
- **Namespace Management**: Use package structures to prevent naming conflicts
  as the project scales.

### Formatting, Linting & Static Analysis

- **Black**: Run `black` on Python sources before committing. The project
  enforces Black formatting via pre-commit hooks.
- **Linting**: Run `flake8` (and optionally `pylint`) against `vultron/` and
  `test/` to catch style and simple correctness issues before opening a PR.
- **Type Checking**: Use `mypy` or `pyright` for static typing checks. Prefer
  explicit types and avoid `Any` unless justified.

### Tests & Test Workflow

- **Mirror Source Layout**: Tests should mirror the production package layout
  (e.g., `test/core/use_cases/` mirrors `vultron/core/use_cases/`).
- **Run Full Test Suite Once**: Follow project policy: run the full test-suite a
  single time as part of validation. Capture the summary output for the PR.
- **Fixtures & Determinism**: Use fixtures for shared setup. Make tests
  deterministic (avoid global mutable state leaking between tests).

### Typing, Validation & Pydantic

- **Pydantic v2**: Use Pydantic v2 BaseModel for structured data. Make
  required fields truly required in subclasses; do not type required fields
  as `X | None` in a subtype.
- **Non-empty Strings**: Prefer shared `NonEmptyString` or `NonEmptyString | None`
  aliases for optional fields that must not be empty when present.
- **Protocol over ABC**: Use `typing.Protocol` to define interfaces (ports).

### Imports & Layering Rules (Hexagonal Architecture)

- **Layer Separation**: Keep core modules free of adapter or framework
  imports. Core code (`vultron/core/`) must not import FastAPI, TinyDB, or
  wire-layer modules. Adapters may depend on all layers.
- **Neutral Modules**: Use small neutral modules (e.g., `types.py`,
  `dispatcher_errors.py`) when shareable types avoid circular imports.
- **Avoid Local Imports**: Prefer module-level imports. If a circular import
  cannot be resolved, document and isolate the local import as a last resort.

### Naming Conventions & Small Style Rules

- **Domain vocabulary**: Use domain names from the project (`vul` for
  vulnerability) rather than ad-hoc abbreviations.
- **Handler & Use-case Names**: Follow project conventions (e.g., handler
  use cases end with `Received`, trigger use cases use `Svc` prefix).
- **Method & Variable Names**: Use descriptive names and avoid single-letter
  names except for local temporaries.

### Error Handling & Logging

- **Raise Domain Errors**: Define and raise domain-specific exceptions that
  inherit from the project base error (`VultronError`) rather than broad
  `Exception` wrappers.
- **No Silent Swallowers**: Do not use bare `except Exception:` to swallow
  errors. Let domain exceptions bubble to a boundary that can translate them.
- **Structured Logging**: Include `activity_id` and `actor_id` in log events
  when available. Use appropriate levels (DEBUG/INFO/WARNING/ERROR).

### Code Review & PR Hygiene

- **Small Focused PRs**: Keep PRs small and self-contained. Group related
  mechanical renames or deletions together when they are low-risk.
- **Format and Lint First**: Run formatting and linters before committing.
- **Tests**: Run relevant tests locally and then the full test-suite once as
  documented by the repository skills before merging.

### Dependencies & Tooling

- **Do not introduce new frameworks** without maintainer approval. Use the
  project's approved tooling (Black, flake8, mypy/pyright, pytest, mkdocs).
- **Dependency Changes**: When adding packages, update `pyproject.toml` and
  include a brief rationale in the PR.

### Documentation

- **Docstrings & Comments**: Document public functions, classes, and ports. 
  Use google-style docstrings. Add comments to explain non-obvious logic or  
  design decisions.
- **Docs Linting**: Do not run Black on markdown. Use `markdownlint-cli2` for
  markdown checks and keep lines under 88 characters where practical.



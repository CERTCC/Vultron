# Testability Specification

## Overview

The Vultron inbox handler must be thoroughly testable at unit, integration, and system levels. Testability enables confidence in correctness, supports refactoring, and documents expected behavior.

**Source**: Software quality requirements, TDD practices

---

## Testing Framework (MUST)

- `TB-01-001` The system MUST use pytest as the testing framework
- `TB-01-002` Test configuration MUST be defined in `pyproject.toml`

## Test Coverage (MUST)

- `TB-02-001` Unit tests MUST achieve 80%+ line coverage
- `TB-02-002` Critical paths MUST achieve 100% line coverage
  - Message validation
  - Semantic extraction
  - Dispatch routing
  - Error handling

## Integration Test Coverage (MUST)

- `TB-03-001` Integration tests MUST cover inbox POST → handler invocation flow
- `TB-03-002` Integration tests MUST cover validation → error response flow
- `TB-03-003` Integration tests MUST verify async processing behavior

## Test Organization (MUST)

- `TB-04-001` Test structure MUST mirror source code structure
  - `test/api/v2/routers/` mirrors `vultron/api/v2/routers/`
  - `test/api/v2/backend/` mirrors `vultron/api/v2/backend/`
- `TB-04-002` Test files MUST use descriptive names starting with `test_`
- `TB-04-003` Unit and integration tests MUST be in separate directories or marked with pytest markers

## Test Data Management (MUST)

- `TB-05-001` The system MUST provide reusable test fixtures
- `TB-05-002` Test data MUST be generated via factories, not hardcoded
- `TB-05-003` Test fixtures MUST be defined in `conftest.py` files
- `TB-05-004` Tests MUST use proper domain objects, not simplified mock data
  - Use full Pydantic models: `VulnerabilityReport(as_id="...", name="...", content="...")`
  - Avoid string IDs or primitives: `object="report-1"` (anti-pattern)
  - Use complete ActivityStreams structures with proper nesting
  - **Rationale**: Tests with string IDs can pass while production code fails; proper objects exercise actual validation and serialization
  - **Verification**: Test data construction uses Pydantic model constructors
- `TB-05-005` Test semantic types MUST match the activity structure being tested
  - Match semantic to structure: `MessageSemantics.CREATE_REPORT` for `Create(VulnerabilityReport)`
  - Don't use `MessageSemantics.UNKNOWN` unless testing unknown activity handling
  - **Rationale**: Handler `@verify_semantics` decorators validate type; mismatched tests bypass actual code paths
  - **Verification**: Each test uses the semantic type that would be extracted from the activity

## Test Isolation (MUST)

- `TB-06-001` Tests MUST be independent and runnable in any order
- `TB-06-002` Tests MUST use test database or mocked database
- `TB-06-003` Test state MUST be reset between tests
- `TB-06-004` Test fixtures MUST clean up created data after test completion
  - **Implementation**: Use pytest teardown fixtures or finalizers
  - **Rationale**: Prevents test database bloat and ensures isolation
  - **Scope**: Applies to integration tests with persistent storage
- `TB-06-005` Behavior Tree tests MUST clear the py_trees blackboard between tests
  - **Implementation**: Add a function-scoped `autouse` fixture named
    `clear_py_trees_blackboard` in `test/behaviors/conftest.py` that calls
    `py_trees.blackboard.Blackboard.storage.clear()` before each test:

    ```python
    # test/behaviors/conftest.py
    import pytest
    import py_trees

    @pytest.fixture(autouse=True, scope="function")
    def clear_py_trees_blackboard() -> None:
        """
        Ensure py_trees blackboard state is cleared before every Behavior Tree test.
        """
        py_trees.blackboard.Blackboard.storage.clear()
    ```
  - **Rationale**: py_trees blackboard is a global singleton; without clearing,
    state from one test leaks into subsequent tests

## Mocking and Stubbing (MUST)

- `TB-07-001` External services MUST be mocked in unit tests
- `TB-07-002` Database access MUST be stubbed in unit tests
- `TB-07-003` Integration tests MAY use real database with test data

## Test Documentation (MUST)

- `TB-08-001` Tests MUST use descriptive names explaining what is tested
- `TB-08-002` Complex tests SHOULD include docstrings
- `TB-08-003` Tests SHOULD serve as usage examples

## Test Maintainability (MUST)

- `TB-09-001` Tests MUST be kept simple and readable
- `TB-09-002` Test duplication SHOULD be avoided via fixtures and helpers
- `TB-09-003` Tests MUST be refactored along with production code

## Verification

### TB-01-001, TB-01-002 Verification

- Code review: pytest used for all tests
- Code review: pytest configuration in `pyproject.toml`

### TB-02-001, TB-02-002 Verification

- CI pipeline: Coverage report shows 80%+ overall
- CI pipeline: Coverage report shows 100% for critical modules
- CI pipeline: Build fails if coverage drops below threshold

### TB-03-001, TB-03-002, TB-03-003 Verification

- Test review: Integration tests exist for each requirement
- Test review: End-to-end flows covered
- Test review: Async behavior verified

### TB-04-001, TB-04-002, TB-04-003 Verification

- Code review: Test structure mirrors source structure
- Code review: All test files named `test_*.py`
- Code review: Unit/integration tests separated

### TB-05-001, TB-05-002, TB-05-003 Verification

- Code review: Fixtures defined in `conftest.py`
- Code review: Test data generated via factories
- Unit test: Fixtures provide expected test data

### TB-06-001, TB-06-002, TB-06-003 Verification

- CI pipeline: Tests run in randomized order
- Unit test: Test database used or database mocked
- Integration test: State reset verified between tests

### TB-07-001, TB-07-002, TB-07-003 Verification

- Code review: External services mocked in unit tests
- Code review: Database mocked in unit tests
- Code review: Integration tests use test database

### TB-08-001, TB-08-002, TB-08-003 Verification

- Code review: Test names are descriptive
- Code review: Complex tests have docstrings
- Code review: Tests demonstrate API usage

### TB-09-001, TB-09-002, TB-09-003 Verification

- Code review: Tests are simple and readable
- Code review: Minimal test duplication
- Git history: Tests updated with production changes

## Related

- Tests: `test/` directory
- Implementation: pytest configuration in `pyproject.toml`
- CI: `.github/workflows/`
- Related Spec: All specifications (tests verify requirements)
- Related Spec: [observability.md](observability.md)

# AGENTS.md — test/

This directory contains all pytest tests for the Vultron project. Test
structure mirrors the source layout under `vultron/`.

See the root `AGENTS.md` for full agent guidance. This file focuses on
rules that apply specifically when running or editing tests.

---

## ⚠️ Running the Test Suite — ONE RUN RULE (MUST)

Run the full test suite **exactly once** per validation cycle using this
exact command:

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

**That single command gives you everything you need:**

- The summary line (e.g., `472 passed, 2 xfailed in 40s`)
- Short tracebacks for any failures

**Do NOT:**

- Re-run pytest a second time to grep for counts (`grep -E "passed|failed"`)
- Change the tail length (`tail -3`, `tail -15`)
- Add the `-q` flag — it suppresses the summary line in some configurations
- Run with different flags to get "just the counts" — the tail already shows
  them

**Do NOT run sequences like these** (each line is a separate pytest
invocation — this wastes time and violates the one-run rule):

```bash
# ❌ WRONG — multiple runs
uv run pytest -q --tb=short 2>&1 | tail -15
uv run pytest -q --tb=short 2>&1 | grep -E "passed|failed|error"
uv run pytest -q --tb=short 2>&1 | tail -3
```

```bash
# ✅ CORRECT — one run, read the tail
uv run pytest --tb=short 2>&1 | tail -5
```

---

## Running a Specific Test File

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

Use `-v` for verbose output when debugging a single file or module.

---

## Test Layout

- `test/` mirrors `vultron/` — e.g., `test/api/v2/backend/` mirrors
  `vultron/api/v2/backend/`
- Shared fixtures live in `conftest.py` files at each directory level
- Test files are named `test_*.py`

## Testing Expectations

### Test Organization (MUST)

- Test structure mirrors source layout (e.g., `test/adapters/driving/fastapi/`
  mirrors `vultron/adapters/driving/fastapi/`,
  `test/core/use_cases/` mirrors `vultron/core/use_cases/`)
- Test files named `test_*.py`
- Fixtures in `conftest.py` at appropriate directory levels
- Use pytest markers to distinguish unit vs integration tests

### Coverage Requirements (MUST)

Per `specs/testability.yaml`:

- 80%+ line coverage overall
- 100% coverage for critical paths:
  - Message validation
  - Semantic extraction  
  - Dispatch routing
  - Error handling

### Testing Patterns (SHOULD)

- Use `monkeypatch` fixture for dependency injection
- Mock external dependencies in unit tests
- Use real SQLite backend with test data in integration tests
- Verify logs using `caplog` fixture
- Test both success and error paths
- New behavior MUST include tests
- Tests SHOULD validate observable behavior, not implementation details
- Avoid brittle mocks when real components are cheap to instantiate
- One test per workflow is preferred over fragmented stateful tests

### Test Data Quality (MUST)

Per `specs/testability.yaml` TB-05-004 and TB-05-005:

**Domain Objects Over Primitives**:

- ✅ Use full Pydantic models: `VulnerabilityReport(name="TEST-001",
  content="...")`
- ❌ Avoid string IDs or primitives: `object="report-1"`

**Semantic Type Accuracy**:

- ✅ Match semantic to structure: `MessageSemantics.CREATE_REPORT` for
  `Create(VulnerabilityReport)`
- ❌ Avoid generic types in specific tests: `MessageSemantics.UNKNOWN` (unless
  testing unknown handling)

**Complete Activity Structure**:

- ✅ Full URIs: `actor="https://example.org/alice"`
- ❌ Incomplete references: `actor="alice"`

**Rationale**: Poor test data quality masks real bugs. Tests with string IDs
can pass even when handlers expect full objects. Tests with mismatched semantics
don't exercise the actual code paths.

```python
# ❌ Anti-pattern
activity = as_Create(actor="alice", object="report-1")
event = CreateReportReceivedEvent(semantic_type=MessageSemantics.UNKNOWN, ...)

# ✅ Best practice
report = VulnerabilityReport(name="TEST-001", content="...")
activity = as_Create(actor="https://example.org/alice", object=report)
event = CreateReportReceivedEvent(semantic_type=MessageSemantics.CREATE_REPORT, ...)
```

### Handler Testing (MUST)

When implementing handler business logic, tests MUST verify:

- Correct semantic type validation at dispatch time via `USE_CASE_MAP` key lookup
- Payload access via `request` parameter on the use-case class
- State transitions persisted correctly
- Response activities generated (when implemented)
- Error conditions handled appropriately
- Idempotency (same input → same result)

See `specs/handler-protocol.yaml` verification section for complete requirements.

If a change touches the datalayer, include repository-level tests that verify
behavior across backends (in-memory / tinydb) where reasonable.

---

## Parallelism and Single-Agent Testing

- Agents may use parallel subagents for complex tasks, but the testing step must
  only ever use a single agent instance to ensure consistency.

---

### Pytest `filterwarnings = ["error"]` Does Not Catch All Warnings

`pyproject.toml` sets `filterwarnings = ["error"]`, which converts Python
`warnings.warn()` calls into test errors. This prevents silent accumulation
of deprecation and misuse warnings.

**Scope caveat**: This policy applies only to `warnings.warn()` calls
captured by pytest's warning machinery. It does **not** catch
`"Exception ignored in:"` messages printed by the Python interpreter at
process teardown (e.g., `ResourceWarning: unclosed file ...`). Those arise
from finalizers (`__del__`) running after pytest exits and are invisible to
`filterwarnings`.

**Rule for agents**: After running the test suite, also scan the output for
`ResourceWarning` or `"Exception ignored in:"` messages. These signal
unclosed resources and are still bugs even if they do not cause test
failures. File them in `plan/BUGS.md` if not already tracked and fix them
by explicitly closing resources in fixtures.

---

### Pytest Helper Enums Must Not Use `Test*` Names

**Symptom**: `PytestCollectionWarning` emitted for helper enum classes in test
modules: "cannot collect 'TestXxx' because it has a custom `__init__`".

**Cause**: pytest's class collection heuristics treat any class named `Test*`
as a candidate test class, even when it is just a helper enum inheriting from
`Enum`/`IntEnum`.

**Fix**: Name helper enums in `test/` with neutral names: `MockEnum`,
`ExampleState`, `FixtureEnum`, etc. — never `TestEnum` or `Test*`. The
regression test in `test/test_pytest_collection_hygiene.py` enforces this.

---

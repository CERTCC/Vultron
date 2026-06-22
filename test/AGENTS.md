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

### Per-Test Timeout Guardrail

Every test has a **5-second default timeout** enforced by `pytest-timeout`
(configured in `pyproject.toml`). A test that runs longer than 5 seconds
fails immediately with a `Timeout` error.

**When a test trips the timeout, fix the test first:**

- Mock slow dependencies (real HTTP calls, filesystem scans, long sleeps)
- Avoid `time.sleep()` in tests; use `monkeypatch` or fake timers instead
- Restructure integration tests to avoid unnecessary sequential waits

`@pytest.mark.timeout(N)` exists as a **last resort** for tests that
genuinely cannot be made faster — for example, a test that exercises a
real sleep-based timeout or a live-network behavior. Any override **MUST**
include a comment explaining why the default is insufficient:

```python
@pytest.mark.timeout(90)  # exercises the 60-second embargo expiry timer
def test_embargo_expiry_fires():
    ...
```

Do **not** use `@pytest.mark.timeout(N)` as a quick fix for a test that is
just slow. Slow tests are a signal of a structural problem; fix the root
cause instead.

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

### `SUBFAILED` in `unittest.TestCase` Subtests Does Not Fail pytest

`test/bt/test_vultrabot.py::MyTestCase::test_main` uses `unittest` subtests
(`with self.subTest(...)`). When run as part of the full suite, the subtest
may show `SUBFAILED` in pytest output due to py_trees blackboard global-state
ordering, but **the pytest exit code remains 0**.

This is a known limitation: `unittest` subtest failures report as `SUBFAILED`
in verbose pytest output but do not cause pytest to exit non-zero. The test
summary line may still show "passed", masking the subtest failure.

**Rule**: The ONE RUN RULE above remains the only required full-suite
validation command. Do **not** change that command or add `-v` to the full
suite run. If you are specifically investigating
`test/bt/test_vultrabot.py::MyTestCase::test_main`, you may run that targeted
test or file separately with `-v` and treat any `SUBFAILED` line as a real
failure even if pytest exits 0.

**Root cause here**: py_trees `Blackboard.storage` is process-global. Test
ordering in the full suite can leave state from a prior test that affects
`test_vultrabot`. Clear `py_trees.blackboard.Blackboard.storage` in fixtures
that use behavior trees.

---

## Demo Integration Test Isolation

Each actor in a demo integration test MUST use a **distinct `DataLayer`
instance** — sharing one bypasses the outbox → inbox delivery path.
Integration tests MUST be marked `@pytest.mark.integration`.

Full rules, code examples, and polling-helper patching guidance:
[`vultron/adapters/driven/AGENTS.md`](../vultron/adapters/driven/AGENTS.md)
§ "Co-located actor isolation" and § "Reentrancy Guard".

If you touch any file under `vultron/demo/` or `test/demo/`, run the
full suite before committing:

```bash
uv run pytest -m "" --tb=short 2>&1 | tail -5
```

When a Demo Integration CI run fails, load
[`notes/demo-ci-diagnostics.md`](../notes/demo-ci-diagnostics.md) for the
3-layer diagnostic model, per-invariant diagnostic map, local Docker run
workflow, and CI artifact interpretation guide.

---

## SYNC Replication Test Patterns

### Happy-Path Replication Test Harness

(SYNC-901, 2026-06-11)

For SYNC happy-path replication integration coverage, the most stable test
seam is **two isolated FastAPI apps** created with `create_isolated_actor_app`
plus a shared `_TestASGIRouter` wired as each app's emitter fallback and as
the module-level default emitter:

- Each app has its own actor-scoped `DataLayer` — satisfying per-actor isolation
- `_TestASGIRouter` routes `Announce(CaseLedgerEntry)` deliveries between apps
  synchronously within the test process — no real HTTP, no retry delays
- This setup exercises the full outbox → ASGI delivery → inbox processing
  pipeline with realistic actor boundaries

Use `post_actor_inbox` (the FastAPI test client) for inbound activities.

### Predecessor-Mismatch Test Seam

(SYNC-902, 2026-06-11)

For predecessor-mismatch coverage, do **not** inject `Announce(CaseLedgerEntry)`
through `post_actor_inbox`. Nested-object persistence in the inbox path can
cause `CheckLogEntryAlreadyStored` to short-circuit before hash validation
runs, masking the mismatch.

The stable test seam for mismatch assertions is:

1. Call `handle_inbox_item(dl, activity)` directly with a typed activity object
2. Then drive normal outbox-based replay from the CaseActor

This bypasses the short-circuit and ensures hash validation is exercised.

---

## Module-Split Test Layout Rules

(NODES-SPLIT-883, 2026-06-11)

When converting a behavior area from a flat `nodes.py` to a `nodes/` subpackage:

- **Preserve import paths**: Add explicit re-exports in `nodes/__init__.py` for
  all names previously importable from `nodes.py`. Callers that do
  `from ...nodes import Foo` must continue to work without modification.
- **Mirror in tests**: Move node-level tests from the flat test file into
  `test/.../nodes/` with per-submodule test files (e.g., `test_conditions.py`,
  `test_participant.py`). Keep tree-composition tests in the parent workflow
  test module.
- **Conftest inheritance**: pytest's upward conftest search means the parent
  `conftest.py` fixtures are automatically available to the new subdirectory.
  Only copy vocabulary-registration side-effect imports (if any) into each new
  subdirectory `conftest.py`.
- **Delete old flat file**: Do not leave both `nodes.py` and `nodes/__init__.py`
  present — pytest will collect both and produce duplicate test IDs.

This pattern applies equally to use-case subpackage splits
(`triggers/`, `received/`, etc.).

---

## Hash-Chain Invariant Assertions

(CASE-LOG-925, 2026-06-12)

When asserting hash-chain invariants in SYNC tests, **always assert field
presence before comparing field values**:

```python
# ❌ Wrong — "" == "" is a false positive if fields are missing
assert entry_a["entry_hash"] == entry_b["prev_log_hash"]

# ✅ Correct — assert presence first, then compare
assert entry_a.get("entry_hash"), "entryHash must be non-empty"
assert entry_b.get("prev_log_hash"), "prevLogHash must be non-empty"
assert entry_a["entry_hash"] == entry_b["prev_log_hash"]
```

An empty string `""` compares equal to another `""`, masking serializer
or schema-migration bugs that produce empty hash fields. The presence
assertion catches this class of bug before the comparison.

---

## Pytest Mark Consistency — pyproject.toml and Workflow YAML

(RENAME-934, 2026-06-12; see `specs/testability.yaml` TB-11-001)

When renaming or adding a pytest mark, update **all three locations** in the
same changeset:

1. **`pyproject.toml`** `[tool.pytest.ini_options] markers` list
2. **`.github/workflows/`** — any YAML file that references the mark by name
   (e.g., `-m "old_mark_name"` in a `pytest` invocation)
3. **Test source files** — all `@pytest.mark.old_name` usages

A mark renamed in test files but not in a workflow YAML causes `pytest` to
collect **0 tests** and exit with code 5 (no tests collected). CI treats this
as a failure, but the error message ("no tests ran") looks like an environment
issue rather than a naming mismatch.

**Verification checklist after a mark rename**:

```bash
# Confirm old name is gone from workflows
grep -r "old_mark_name" .github/workflows/  # should produce no output

# Confirm new name is registered
grep "new_mark_name" pyproject.toml

# Confirm pytest collects tests
uv run pytest -m "new_mark_name" --collect-only 2>&1 | tail -5
```

---

## Genesis-Hash Path Must Be Tested with a Stored Case

(CLP-08-995, 2026-06-18)

`is_ledger_fresh_for_case` skips the genesis-hash check when the effective
genesis hash is `""` (no stored case or empty hash). This means positive
freshness tests that do **not** save a `VulnerabilityCase` to the DataLayer
always bypass the genesis-hash validation path — they pass even if
`_get_case_genesis_hash` is completely broken.

**Rule**: For every positive freshness test that is meant to exercise
CLP-08-004, save the `VulnerabilityCase` to the DataLayer first:

```python
dl.save(_make_case())  # ensures genesis hash is available for validation
result = is_ledger_fresh_for_case(dl, case_id, ...)
assert result is True
```

Tests that intentionally test the "no case stored → trivially fresh" path
should be clearly labeled as such and must NOT be used as the sole coverage
for the genesis-hash check path.

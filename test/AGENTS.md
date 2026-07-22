# AGENTS.md — test/

This directory contains all pytest tests for the Vultron project. Test
structure mirrors the source layout under `vultron/`.

See the root `AGENTS.md` for full agent guidance. This file focuses on
rules that apply specifically when running or editing tests.

---

## ⚠️ Running the Test Suite — ONE RUN RULE (MUST)

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

Run **exactly once**. Do NOT re-run to grep counts, change tail length, or add
`-q` (suppresses summary line). One run, read the tail.

---

## Running a Specific Test File

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

## Test Layout and Expectations

- `test/` mirrors `vultron/`; test files named `test_*.py`; fixtures in
  `conftest.py` at each level.
- 80%+ line coverage overall; 100% for message validation, semantic extraction,
  dispatch routing, error handling. See `specs/testability.yaml`.
- Use `monkeypatch` for DI; real SQLite for integration tests; verify logs with
  `caplog`; test success and error paths.
- Use full Pydantic models in tests (not string IDs/primitives). Match semantic
  types to structure (TB-05-004, TB-05-005). Use full URIs for actor/object fields.
- Handler tests MUST verify: semantic dispatch, state transitions, outbox
  activities, error conditions, idempotency. See `specs/handler-protocol.yaml`.
- Testing step MUST use a single agent instance.

---

### Per-Test Timeout Guardrail

Default 5-second timeout (`pytest-timeout`, `pyproject.toml`). When a test
trips it: mock slow deps, avoid `time.sleep()`, restructure integration tests.
`@pytest.mark.timeout(N)` is a last resort and MUST have a comment explaining
why. Do not use it to paper over slow tests.

---

### Pytest `filterwarnings = ["error"]` Does Not Catch All Warnings

`filterwarnings = ["error"]` converts `warnings.warn()` to errors, but does NOT
catch `ResourceWarning` / `"Exception ignored in:"` at process teardown. After
running the suite, scan for these — they're still bugs. File in `plan/BUGS.md`
if not tracked; fix by explicitly closing resources in fixtures.

---

### Pytest Helper Enums Must Not Use `Test*` Names

Pytest treats `Test*` classes as test candidates even when they're helper enums.
Use neutral names: `MockEnum`, `ExampleState`, `FixtureEnum`. Enforced by
`test/test_pytest_collection_hygiene.py`.

---

### `SUBFAILED` in `unittest.TestCase` Subtests Does Not Fail pytest

`test/bt/test_vultrabot.py::MyTestCase::test_main` may show `SUBFAILED` due to
py_trees `Blackboard.storage` global-state ordering, but pytest exits 0.
When investigating that test, run it targeted with `-v` and treat `SUBFAILED`
as real. Clear `py_trees.blackboard.Blackboard.storage` in BT-using fixtures.

---

## Demo Integration Test Isolation

Each actor MUST use a **distinct `DataLayer` instance**; mark tests
`@pytest.mark.integration`. See
[`vultron/adapters/driven/AGENTS.md`](../vultron/adapters/driven/AGENTS.md)
§ "Co-located actor isolation" and § "Reentrancy Guard".

If `vultron/demo/` or `test/demo/` touched, run the full suite:
`uv run pytest -m "" --tb=short 2>&1 | tail -5`.

CI failures: see [`notes/demo-ci-diagnostics.md`](../notes/demo-ci-diagnostics.md).

---

## SYNC Replication Test Patterns

### Happy-Path (SYNC-901)

Use two isolated `create_isolated_actor_app` instances + shared `_TestASGIRouter`
as emitter fallback. Each app has its own actor-scoped `DataLayer`. Use
`post_actor_inbox` for inbound activities.

### Predecessor-Mismatch (SYNC-902)

Do NOT inject via `post_actor_inbox` — `CheckLogEntryAlreadyStored` can
short-circuit before hash validation. Use:

1. `handle_inbox_item(dl, activity)` directly
2. Then drive outbox-based replay from the CaseActor

---

## Module-Split Test Layout Rules (NODES-SPLIT-883)

When splitting `nodes.py` → `nodes/` subpackage:

- Re-export all public names from `nodes/__init__.py`.
- Mirror in tests: move to `test/.../nodes/` with per-submodule files; keep
  tree-composition tests in parent.
- Parent `conftest.py` fixtures are auto-available; only copy vocabulary
  side-effect imports into new `conftest.py`.
- Delete old flat file — never have both `nodes.py` and `nodes/__init__.py`.

Applies equally to `triggers/`, `received/`, etc.

---

## Hash-Chain Invariant Assertions (CASE-LOG-925)

Assert field presence before comparing values:

```python
assert entry_a.get("entry_hash"), "entryHash must be non-empty"
assert entry_b.get("prev_log_hash"), "prevLogHash must be non-empty"
assert entry_a["entry_hash"] == entry_b["prev_log_hash"]
```

`"" == ""` is a false positive masking serializer/schema bugs.

---

## Pytest Mark Consistency (RENAME-934; TB-11-001)

When renaming a mark, update **all three** in the same changeset:

1. `pyproject.toml` markers list
2. `.github/workflows/` YAML files
3. Test source files

A mismatch → pytest collects 0 tests (exit code 5). Verify:

```bash
grep -r "old_mark_name" .github/workflows/  # no output
grep "new_mark_name" pyproject.toml
uv run pytest -m "new_mark_name" --collect-only 2>&1 | tail -5
```

---

## BT Factory Determinism (BT-FACTORY-DETERMINISM)

When a tree builder's default `CallOutBackendFactory` is probabilistic
(`AlmostAlwaysSucceed`, `WeightedBehavior`), SUCCESS-asserting integration
tests MUST pass an explicit deterministic factory:

```python
def _always_succeed_factory(name: str) -> py_trees.behaviour.Behaviour:
    class _AlwaysSucceed(py_trees.behaviour.Behaviour):
        def update(self):
            return py_trees.common.Status.SUCCESS
    return _AlwaysSucceed(name)
```

Structure tests and FAILURE-path tests are unaffected.
See `notes/bt-pitfalls.md` § "Integration Tests Must Use Deterministic
Factories When BT Default Is Probabilistic".

---

## MagicMock Requires `spec=` When Code Uses `isinstance()` Guards

When migrating from duck-typing guards (TypeGuard helpers using `getattr`) to
`isinstance()` checks, bare `MagicMock()` instances break silently: the
`isinstance` check returns `False` and the test exercises the wrong branch.

**Fix:** use `MagicMock(spec=ConcreteClass)` so
`isinstance(mock, ConcreteClass)` returns `True`. This applies to every test
that creates a mock case, participant, or ledger entry AND passes it through
code that uses `isinstance(x, VulnerabilityCase)` etc.

**Symptom:** test passes but verifies the wrong code path (e.g., "case not
found" instead of the intended `ValueError` branch).

<!-- Source: ISSUE-1504 -->

---

## BT Contract Tests: Inherit Production Node Class (Not Just the Mixin)

When writing behavior-contract tests for probabilistic call-out-point nodes
(e.g., `DevelopExploit(OftenSucceed)`, `PurchaseExploit(RarelySucceed)`), the
deterministic wrapper MUST subclass the **production node** plus `AlwaysSucceed`
as a secondary base — not a fresh class that only inherits from the abstract
mixin and `AlwaysSucceed`:

```python
# ✅ CORRECT — inherits output_keys, annotations, etc. from DevelopExploit
class _DeterministicDevelopExploit(DevelopExploit, AlwaysSucceed):
    pass

# ❌ WRONG — declares its own output_keys; won't catch regressions in DevelopExploit
class _Wrapper(ComposerCallOutPoint, AlwaysSucceed):
    output_keys = {"developed_exploit_artifact": str}  # duplicated, not inherited
```

The wrong form would pass even if `DevelopExploit.output_keys` was emptied or
renamed. Inherit from the production class so any regression there is caught.

<!-- Source: ISSUE-1565 -->

---

## Full-Tree Tick Tests: Stub Only the Probabilistic Nodes, Not the Node Under Test

When ticking a collapsed FUZZ-08x tree to SUCCESS to verify one call-out
point's contract, check each leaf's fuzzer base type:

- **Leave the node under test at its default factory** — otherwise the test
  proves nothing about that node's contract.
- **Inject deterministic stubs for every other probabilistic call-out point**
  in the tick path (e.g., `AlmostAlwaysSucceed` at 0.90 makes the full-tree
  tick flaky).

The existing `_marker_factory` helper in test files returns an unconditional-SUCCESS
stub. Add an `isinstance` guard (e.g., `assert isinstance(tree.children[0], PrioritizePublicationIntents)`)
so a future refactor that accidentally stubs the node under test fails loudly.

The blackboard storage key carries a **leading slash** (`/publication_intent_decision`);
assert against `py_trees.blackboard.Blackboard.storage` and rely on the
`autouse clear_blackboard` fixture to keep the assertion non-vacuous.

<!-- Source: ISSUE-1594 -->

---

## Genesis-Hash Path Must Be Tested with a Stored Case (CLP-08-995)

`is_ledger_fresh_for_case` skips genesis-hash check when no case is stored
(effective hash = `""`). CLP-08-004 tests MUST save the case first:

```python
dl.save(_make_case())  # ensures genesis hash available
result = is_ledger_fresh_for_case(dl, case_id, ...)
assert result is True
```

"No case stored → trivially fresh" tests must be clearly labeled and MUST NOT
be the sole coverage for the genesis-hash path.

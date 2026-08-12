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

Timeouts are **two-tier** (`pytest-timeout`):

| Tier | Ceiling | Set in |
|---|---|---|
| Unit (default) | 5s | `timeout = 5`, `pyproject.toml` |
| `@pytest.mark.integration` | 60s | `INTEGRATION_TIMEOUT_SECONDS`, `test/conftest.py` |

`test/conftest.py::apply_integration_timeout` widens the ceiling for
integration-marked tests at collection time. An explicit
`@pytest.mark.timeout(N)` on a test always wins over the tier default.

**Why two tiers** (#2270): `timeout_method = "thread"` kills the *whole pytest
process*, not the one slow test. Several integration tests do 3.5-4.3s of
honest work, so the 5s ceiling tripped nondeterministically and aborted the
session with **no summary line** — a red integration run carried no information
about the branch. The unit suite keeps 5s, where it is a genuinely useful hang
detector.

When a **unit** test trips 5s: mock slow deps, avoid `time.sleep()`, or move it
behind the `integration` marker if it really does exercise the full stack.
`@pytest.mark.timeout(N)` is a last resort and MUST have a comment explaining
why. Do not use it to paper over slow tests.

A timeout ceiling is a diagnostic tool, not a correctness invariant — if a tier
is firing on honest work rather than catching hangs, change the tier rather
than contorting the tests around it.

---

### `monkeypatch.undo()` MUST Precede `reload_config()` in Fixture Teardown

`vultron/config/app.py` keeps a process-global `_config_cache`.
`reload_config()` clears it and re-reads the environment. Pytest undoes
`monkeypatch` env changes **after** the requesting fixture's teardown body
runs, so this order pins the patched value into the cache for the rest of the
session:

```python
# WRONG — re-caches the still-patched env
yield
reload_config()

# RIGHT — undo first, then reload from the clean env
yield
monkeypatch.undo()
reload_config()
```

Any fixture that both patches a `VULTRON_*` env var and calls
`reload_config()` in teardown is affected, not just `test/demo/`. Clearing the
cache without reloading (`_cfg_module._config_cache = None`, as in
`test/adapters/driven/test_get_datalayer.py`) is an equally valid fix.

`test/demo/conftest.py` has an autouse guard that detects and repairs such
leaks, and records them on `config_leak_ledger` so
`test_config_leak_guard.py::TestNoFixtureLeakedConfig` fails rather than
silently masking the regression. That guard is **function-scoped only** — a
module-, class-, or session-scoped fixture pollutes the cache before the guard
snapshots it, so higher-scoped fixtures must get the order right themselves.
Nothing outside `test/demo/` is guarded at all.

Source: #2086 / PR #2126.

---

### A Test That Needs `VULTRON_*` Config MUST Set It Itself

The flip side of the rule above: fixing a leak removes config that downstream
tests may have been silently borrowing. `test_create_tree.py` and
`nodes/test_communication.py` both run `ResolveCaseActorUrlsNode` (via
`CreateCaseActorNode` / `CreateCaseBT`), which returns FAILURE when
`case_actor_service_url` is None (CP-08-002/003) — yet neither module set it.
They passed only because another module leaked the value into the process-global
cache first, and failed in isolation or in a subset run (#1897).

Each module that depends on a `VULTRON_*` setting needs its own autouse fixture
setting it, using the `monkeypatch.undo()`-then-`reload_config()` teardown order
above. Verify with a targeted run, not just the full suite — a module that only
passes in a full-suite run is order-dependent, not passing.

Source: #1897 / PR #2126.

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

## `test/demo/` Tests Are Auto-Marked `integration` by a Directory Hook

`test/demo/conftest.py` has a `pytest_collection_modifyitems` hook that
unconditionally adds `pytest.mark.integration` to **every** test collected from
`test/demo/`, regardless of whether the test actually starts a FastAPI
`TestClient`. Because the default `pyproject.toml` `addopts` is
`-m 'not integration'`, a pure-unit test placed in `test/demo/` will be
**silently deselected** by a bare `uv run pytest test/demo/test_something.py` —
the run reports "N deselected" and 0 passed, which looks like a collection error
but is not.

**To run or confirm tests under `test/demo/`, always pass `-m ""`:**

```bash
uv run pytest test/demo/test_something.py -m ""
```

This is the same reason `AGENTS.md` requires the full suite
(`uv run pytest -m ""`) whenever `vultron/demo/` or `test/demo/` is touched.

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

Use two isolated `create_isolated_actor_app` instances + shared
`_TestClientRouter` as emitter fallback. The router POSTs cross-actor
deliveries to each target app's `TestClient` inbox (the only sanctioned
in-process transport per ADR-0042 / OX-12-003 — no hand-rolled
`httpx.ASGITransport`). Each app has its own actor-scoped `DataLayer`. Use
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

## Invariant Harness Failures Are Independent of Demo Failures (DEMOCI-04)

The case-ledger invariant harness (`test/ci/invariants/`) runs as a **separate
CI job** from the demo run. When adding or modifying a scenario test file:

- Do NOT add the invariant harness step back into the demo job — the two must
  stay in separate jobs so each gets its own PR status check.
- When a demo run and its invariants both fail, **always check the invariant
  job separately** — invariant failures can point to a different root cause
  than the demo failure.

**Per-scenario expected-event-types**: each `_XXX_EXPECTED_EVENT_TYPES` list
must be comprehensive for its scenario (see `notes/demo-ci-invariants.md` and
DEMOMA-16-001 through DEMOMA-16-008). When adding a new scenario phase that
produces a new `event_type`, update both the spec requirement and the test
constant in the same PR.

<!-- Source: CONCERN-1649, PR-1590 -->

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

# AGENTS.md — test/

This directory contains all pytest tests for the Vultron project. Test
structure mirrors the source layout under `vultron/`.

See the root `AGENTS.md` for project-wide guidance. This file holds the rules you
need on *every* run; the longer pitfall write-ups live in
[`notes/testing-pitfalls.md`](../notes/testing-pitfalls.md).

---

## ⚠️ Running the Test Suite — ONE RUN RULE (MUST)

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

Run **exactly once**. Do NOT re-run to grep counts, change tail length, or add
`-q` (suppresses summary line). One run, read the tail.

**Absence of a summary line means the run was killed, not that it passed** — the
pipeline returns `tail`'s exit code. See
[`notes/testing-pitfalls.md`](../notes/testing-pitfalls.md) § "A Killed `pytest`
Run Reports Exit 0 Under `tail -5`" for the file-redirect form to use when
diagnosing.

## Running a Specific Test File

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

If `vultron/demo/` or `test/demo/` was touched, run the full suite:
`uv run pytest -m "" --tb=short 2>&1 | tail -5`.

---

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
- When splitting `nodes.py` → `nodes/`, mirror the split in the test layout
  (NODES-SPLIT-883) — see
  [`notes/testing-pitfalls.md`](../notes/testing-pitfalls.md) § "Test Layout and
  Markers".

---

## Timeouts Are Two-Tier

| Tier | Ceiling | Set in |
|---|---|---|
| Unit (default) | 30s | `timeout = 30`, `pyproject.toml` |
| `@pytest.mark.integration` | 60s | `INTEGRATION_TIMEOUT_SECONDS`, `test/conftest.py` |

`timeout_method = "thread"` kills the *whole pytest process*, so a trip produces
no summary line at all. An explicit `@pytest.mark.timeout(N)` wins over the tier
default, is a last resort, and MUST carry a comment explaining why. Why these
numbers, and why a too-tight ceiling reads as flakiness:
[`notes/testing-pitfalls.md`](../notes/testing-pitfalls.md) § "Per-Test Timeout
Guardrail".

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

---

## Demo Integration Test Isolation

Each actor MUST use a **distinct `DataLayer` instance**; mark tests
`@pytest.mark.integration`. See
[`vultron/adapters/driven/AGENTS.md`](../vultron/adapters/driven/AGENTS.md)
§ "Co-located actor isolation" and § "Reentrancy Guard".

An `actor_id` *is* a store name, and a BT's store follows its executing actor —
both hazards, and the `@pytest.mark.executes_as` declaration that resolves the
second, are in
[`notes/datalayer-design.md`](../notes/datalayer-design.md) § "One Actor Id Is One
Database".

CI failures: see
[`notes/demo-ci-diagnostics.md`](../notes/demo-ci-diagnostics.md). The invariant
harness runs as a separate job from the demo run and must be read separately:
[`notes/demo-ci-invariants.md`](../notes/demo-ci-invariants.md).

---

## Pytest Collection Hygiene

### `filterwarnings = ["error"]` Does Not Catch All Warnings

It converts `warnings.warn()` to errors, but does NOT catch `ResourceWarning` /
`"Exception ignored in:"` at process teardown. After running the suite, scan for
these — they're still bugs. Fix by explicitly closing resources in fixtures.

### Pytest Helper Enums Must Not Use `Test*` Names

Pytest treats `Test*` classes as test candidates even when they're helper enums.
Use neutral names: `MockEnum`, `ExampleState`, `FixtureEnum`. Enforced by
`test/test_pytest_collection_hygiene.py`.

### Tests Verifying a Protocol-Kind Requirement MUST Carry `@pytest.mark.spec`

(SR-05-004, ISSUE-2117)

Protocol-kind requirements are conformance-critical. Without a marker the CI
uncovered-count ratchet (SR-05-005,
`test/architecture/test_spec_coverage_ratchet.py`) cannot enforce coverage and
the requirement becomes unverifiable. Add `@pytest.mark.spec("<ID>")` to every
test that exercises a `kind: protocol` spec entry, and run `spec-coverage` to
find protocol IDs with no markers yet. The strict-`xfail` pattern for a spec
whose implementation does not exist yet is in
[`notes/spec-authoring-rules.md`](../notes/spec-authoring-rules.md).

### Renaming a Mark Touches Three Files

`pyproject.toml`, `.github/workflows/`, and the test sources — all in the same
changeset, or pytest collects 0 tests (exit code 5). Verification commands:
[`notes/testing-pitfalls.md`](../notes/testing-pitfalls.md) § "Pytest Mark
Consistency".

---

## Config in Fixtures

`vultron/config/app.py` keeps a process-global `_config_cache`. Prefer
`config_override()`; where you cannot, `monkeypatch.undo()` MUST precede
`reload_config()` in teardown, or the patched value is pinned into the cache for
the rest of the session. A module that depends on a `VULTRON_*` setting MUST set
it itself rather than borrowing another module's leak. Both rules, the
autouse leak guard and its function-scope-only limitation:
[`notes/configuration.md`](../notes/configuration.md) § "Testing Pattern".

---

## Pitfall Index

Full write-ups in [`notes/testing-pitfalls.md`](../notes/testing-pitfalls.md):

- **Vacuous assertions** — broadcast guards need a third participant; hash-chain
  comparisons need presence checks before equality (`"" == ""` passes);
  `MagicMock` needs `spec=` wherever code uses `isinstance()`; the genesis-hash
  path needs a stored case (CLP-08-995); `call_args.args` over `call_args[0]`.
- **A test that "falls back to" a value for *malformed* input is asserting a
  bug** — absent input and unreadable input are different.
- **Process-global state** — the `py_trees` blackboard *and* its class registry
  (define test BT subclasses at module level); `SUBFAILED` in `unittest` subtests
  does not fail pytest; `caplog.set_level()` in a fixture captures other
  fixtures' setup.
- **BT test patterns** — pass a deterministic factory when the default is
  probabilistic; contract-test wrappers inherit the *production* node class; stub
  every probabilistic node *except* the one under test;
  `ResolveCaseManagerNode` needs a CASE_MANAGER participant in the fixture.
- **Fixtures that silently miss deliveries** — the outbox `BackgroundTasks`
  emitter has two resolution paths, patch both; a `_TestClientRouter` WARNING for
  an unregistered host is a config-leak signal; `rm -rf devlogs/` before running
  the invariant harness locally.
- **Coverage shape** — one test per distinct lookup path when consolidating
  helpers; trigger use cases need per-use-case tests
  ([`notes/triggers-test-coverage.md`](../notes/triggers-test-coverage.md)).
- **SYNC replication test setup** —
  [`notes/sync-ledger-replication.md`](../notes/sync-ledger-replication.md)
  § "SYNC Replication Test Patterns".

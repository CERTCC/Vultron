# AGENTS.md — test/

This directory contains all pytest tests for the Vultron project. Test
structure mirrors the source layout under `vultron/`.

See the root `AGENTS.md` for project-wide guidance. This file holds the rules you
need on *every* run; the longer pitfall write-ups live in
[`notes/testing-pitfalls.md`](../notes/testing-pitfalls.md).

---

## ⚠️ Running the Test Gate — ONE RUN RULE (MUST)

```bash
logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"
gate=$(PYTHONPATH= uv run targeted-tests --base origin/main --pytest); rc=$?
[ "$rc" -eq 0 ] && { eval "$gate" > "$logs-gate.log" 2>&1; rc=$?; tail -20 "$logs-gate.log"; }; echo "exit: $rc"; (exit $rc)
```

Run **exactly once**; never re-run for counts, a longer tail, or `-q`. `-n auto`
in the printed command is sized to the slot's cgroup, not `nproc`.

**No local gate runs the whole suite** (PAD-18-003, PAD-18-008, PAD-18-015).
`targeted-tests` prints the files; CI runs both suites on every push and the
required `CI gate` refuses the merge until that run passes
([run-tests](../.agents/skills/run-tests/SKILL.md) § "The Targeted Gate").

**Read `exit:` before the tail — it is the verdict; the tail is only detail.**
Never pipe the run into `tail` or `tee`: a pipeline exits with its last stage's
status, so a killed run reports 0 under a passing-looking tail
([pitfalls](../notes/testing-pitfalls.md) § "A Killed `pytest` Run Reports Exit
0 Under `tail -5`").

## Running a Specific Test File

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

A change under `vultron/demo/` or `test/demo/` needs no full local run: that
exception is retired, because `demo-integration.yml` runs those tests and the
required `CI gate` judges it (PAD-18-008).

---

## Test Layout and Expectations

- `test/` mirrors `vultron/`; test files named `test_*.py`; fixtures in
  `conftest.py` at each level.
- 80%+ line coverage overall; 100% for message validation, semantic
  extraction, dispatch routing, error handling (`specs/testability.yaml`).
- Use `monkeypatch` for DI; real SQLite for integration tests; verify logs with
  `caplog`; test success and error paths.
- Use full Pydantic models in tests (not string IDs/primitives). Match semantic
  types to structure (TB-05-004/005). Full URIs for actor/object fields.
- Handler tests MUST verify: semantic dispatch, state transitions, outbox
  activities, error conditions, idempotency (`specs/handler-protocol.yaml`).
- Testing step MUST use a single agent instance.
- When splitting `nodes.py` → `nodes/`, mirror the split in the test layout
  (NODES-SPLIT-883) — see [pitfalls](../notes/testing-pitfalls.md) § "Test
  Layout and Markers".

---

## Timeouts Are Two-Tier

| Tier | Ceiling | Set in |
|---|---|---|
| Unit (default) | 30s | `timeout = 30`, `pyproject.toml` |
| `@pytest.mark.integration` | 120s | `INTEGRATION_TIMEOUT_SECONDS`, `test/conftest.py` |

`timeout_method = "signal"`: a trip fails that one test and the session goes on.
An explicit `@pytest.mark.timeout(N)` wins over the tier default, is a last
resort, and MUST carry a comment saying why. Why these numbers, and why the
method matters more: [pitfalls](../notes/testing-pitfalls.md) § "Per-Test
Timeout Guardrail".

---

## `test/demo/` Tests Are Auto-Marked `integration` by a Directory Hook

`test/demo/conftest.py` marks **every** test there `integration`, and `addopts`
is `-m 'not integration'`, so a bare run of one demo file silently deselects it
("N deselected", 0 passed) — which reads like a collection error. Always `-m ""`:

```bash
uv run pytest test/demo/test_something.py -m ""
```

---

## Demo Integration Test Isolation

Each actor MUST use a **distinct `DataLayer` instance**; mark tests
`@pytest.mark.integration`. See
[`driven/AGENTS.md`](../vultron/adapters/driven/AGENTS.md) § "Co-located actor
isolation" and § "Reentrancy Guard".

An `actor_id` *is* a store name and a BT's store follows its executing actor —
both hazards, plus the `@pytest.mark.executes_as` fix for the second:
[datalayer-design](../notes/datalayer-design.md) § "One Actor Id Is One
Database".

CI failures: [demo-ci-diagnostics](../notes/demo-ci-diagnostics.md). The
invariant harness is a separate job from the demo run, read separately:
[demo-ci-invariants](../notes/demo-ci-invariants.md).

---

## Pytest Collection Hygiene

### `filterwarnings = ["error"]` Does Not Catch All Warnings

It converts `warnings.warn()` to errors, but does NOT catch `ResourceWarning` /
`"Exception ignored in:"` at process teardown. After a run, scan for these —
they're still bugs. Fix by closing resources explicitly in fixtures.

### Pytest Helper Enums Must Not Use `Test*` Names

Pytest treats `Test*` classes as test candidates even when they are helper
enums. Use `MockEnum`, `ExampleState`, `FixtureEnum`; enforced by
`test/test_pytest_collection_hygiene.py`.

### Tests Verifying a Protocol- or Foundation-Kind Requirement MUST Carry `@pytest.mark.spec`

(SR-05-004, ISSUE-2117, ISSUE-4528)

Without a marker the PR-only coverage guard (SR-05-005,
`test/architecture/test_spec_coverage_ratchet.py`) cannot enforce coverage, so
the conformance-critical requirement becomes unverifiable. Add
`@pytest.mark.spec("<ID>")` to every test exercising a `kind: protocol` or
`kind: foundation` entry; `spec-coverage` lists the unmarked and the
strict-`xfail`-only IDs. Strict-`xfail` pattern, and the `docs-site --write` a
marker change needs (DF-12-020):
[spec-authoring-rules](../notes/spec-authoring-rules.md).

### Renaming a Mark Touches Three Files

`pyproject.toml`, `.github/workflows/`, and the test sources — all in the same
changeset, or pytest collects 0 tests (exit code 5). Verification commands:
[pitfalls](../notes/testing-pitfalls.md) § "Pytest Mark Consistency".

---

## Config in Fixtures

`vultron/config/app.py` caches `get_config()` process-wide. Prefer
`config_override()`; where you cannot, `monkeypatch.undo()` MUST precede
`reload_config()` in teardown, or the patched value is pinned into the cache for
the rest of the session. A module that depends on a `VULTRON_*` setting MUST set
it itself rather than borrowing another module's leak. Both rules, the
autouse leak guard and its function-scope-only limitation:
[`notes/configuration.md`](../notes/configuration.md) § "Testing Pattern".

---

## Pitfall Index

Full write-ups in [testing-pitfalls](../notes/testing-pitfalls.md):

- **An exemption listed *before* `"error"` is a no-op** (SR-05-015): later wins.
  Verify in a `pytester` sub-session (SR-05-016); `pytest.warns` misses it.
- **Vacuous assertions** — broadcast guards need a third participant; hash-chain
  comparisons need presence checks before equality (`"" == ""` passes);
  `MagicMock` needs `spec=` wherever code uses `isinstance()`; the genesis-hash
  path needs a stored case (CLP-08-004); and "falls back to" a value for
  *malformed* input asserts a bug — absent and unreadable input differ.
- **Drive a guard through its production entry point** — a direct call covers
  nothing and still reads as covered (`test_guards_run_in_production.py`, #3156).
- **A FAILURE test must prove the harness can produce its named reason** — the
  scenario always injects a datalayer and a trigger-activity adapter, so
  "failure when X absent" is unreachable for either; assert the reason
  (`assert_failure(result, reason=...)`), not just the status.
- **Process-global state** — reset only in root `test/conftest.py` (blackboard,
  per-actor registries; no per-directory copy, #3996); define test BT subclasses
  at module level; test-local `CoreObject`/`CoreRecord` subclasses pollute
  `CORE_VOCABULARY`/`CORE_TYPE_MAP` (use `isolated_core_registries`); `SUBFAILED`
  in `unittest` subtests does not fail pytest; `caplog.set_level()` in a fixture
  captures other fixtures' setup.
- **BT test patterns** — pass a deterministic factory when the default is random;
  contract-test wrappers inherit the *production* node class; stub every probabilistic
  node *except* the one under test; `ResolveCaseManagerNode` needs a CASE_MANAGER
  participant in the fixture.
- **Fixtures that mislead** — the outbox `BackgroundTasks` emitter has two resolution
  paths, patch both; an `InProcessRouter` WARNING for an unregistered host is a
  config-leak signal; `rm -rf devlogs/` before the invariant harness; a
  CSB-18-001-impossible status fixture is guarded only under
  `test/core/behaviors/status/`; ask `impossible_state_reasons()` elsewhere.
- **Coverage shape** — one test per distinct lookup path when consolidating
  helpers; trigger use cases need per-use-case tests
  ([triggers-test-coverage](../notes/triggers-test-coverage.md)).
- **The timeout *method* sets what a trip costs; the ceiling only sets how often** —
  `thread` killed the session or xdist worker, `signal` fails one test (#3603); a dead
  worker fails the run, and gate exit 124 means it hung (#4809).
- **A marker sweep misses a directory hook** — grepping `pytestmark` calls
  `test/demo/` non-compliant though its hook marks it 100%; probe it (#3604).
- **SYNC replication test setup** — `notes/sync-ledger-replication.md` § "SYNC
  Replication Test Patterns". A `LedgerNetwork` is rebuilt from its ledger at
  teardown; direct CASE_MANAGER setup writes call `bypass_ledger()`
  ([case-ledger-authority](../notes/case-ledger-authority.md)).

---
title: Testing Pitfalls and Patterns
status: active
description: >
  Full write-ups for pytest pitfalls in this repo: reading a killed run, the
  two-tier timeout guardrail, fixture and blackboard isolation, py_trees test
  patterns, assertion-quality traps (vacuous asserts, "falls back to" tests,
  bare MagicMock), and test layout rules for module splits. `test/AGENTS.md`
  keeps the short index and the rules you need on every run.
related_specs:
  - specs/testability.yaml
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/flaky-tests.md
  - notes/configuration.md
  - notes/bt-pitfalls.md
  - notes/datalayer-design.md
  - notes/triggers-test-coverage.md
  - notes/demo-ci-invariants.md
relevant_packages:
  - pytest
  - py_trees
---

# Testing Pitfalls and Patterns

Canonical write-ups for the testing pitfalls that were previously inlined in
the root `AGENTS.md` and `test/AGENTS.md`. Both of those files keep short
pointers into the sections below.

---

## Reading Test Output

### A Killed `pytest` Run Reports Exit 0 Under `tail -5`

When `pytest-timeout` kills a test that exceeds the budget, it dumps a stack
trace and exits non-zero, but the `uv run pytest ... 2>&1 | tail -5` pipeline
returns `tail`'s exit code (0) and shows dump frames where the `N passed`
summary line would be. **Absence of a summary line from `tail -5` is the
signal.** Redirect to a file and check pytest's own exit code:

```bash
uv run pytest --tb=short > /tmp/unit.log 2>&1; echo $?
```

The spec-lint test (`test_real_specs_lint_no_hard_errors`) is particularly
load-sensitive at ~3s against the 5s budget.

Source: ISSUE-2232

### Per-Test Timeout Guardrail

Timeouts are **two-tier** (`pytest-timeout`):

| Tier | Ceiling | Set in |
|---|---|---|
| Unit (default) | 30s | `timeout = 30`, `pyproject.toml` |
| `@pytest.mark.integration` | 60s | `INTEGRATION_TIMEOUT_SECONDS`, `test/conftest.py` |

`test/conftest.py::apply_integration_timeout` widens the ceiling for
integration-marked tests at collection time. An explicit
`@pytest.mark.timeout(N)` on a test always wins over the tier default.

**Why these numbers** (#2270): `timeout_method = "thread"` kills the *whole
pytest process*, not the one slow test, so a trip produces **no summary line**.
A too-tight ceiling therefore does not surface a slow test — it converts the run
into an uninformative abort. Both tiers used to be 5s, which was thin enough
that honest work tripped it under load:

- integration tests doing 3.5-4.3s of real HTTP work, and
- AST-walking architecture ratchets at ~3.4s in isolation.

Four separate sessions re-diagnosed the result as flakiness (ISSUE-1925,
ISSUE-1988, ISSUE-2086, ISSUE-2237) before the ceiling itself was fixed. Raising
it costs nothing on a genuine hang — that test was never going to finish — and
the suite stays fast because total runtime is bounded by the tests, not by this
ceiling.

Both tiers are sized from measurement: the slowest unit test is ~3.1s idle and
the slowest integration test ~4.3s. The headroom is deliberately large because
contention (a CI runner, or a background graphify rebuild) inflates these well
beyond their idle cost — an intermediate unit value of 20s was tried and still
tripped once under exactly that.

When a test trips its tier: mock slow deps, avoid `time.sleep()`, or move it
behind the `integration` marker if it really does exercise the full stack.
`@pytest.mark.timeout(N)` is a last resort and MUST have a comment explaining
why. Do not use it to paper over slow tests.

A timeout ceiling is a diagnostic tool, not a correctness invariant — if a tier
is firing on honest work rather than catching hangs, change the tier rather
than contorting the tests around it. Do not add a row to
[notes/flaky-tests.md](flaky-tests.md) for a test that is merely near its
ceiling.

### `caplog` Captures Fixture-Setup-Phase Records

`caplog.set_level()` set in a fixture captures log records emitted during other
fixtures' setup, not just the test body. Set it inside the test function to
scope capture to the test body only, and call `caplog.clear()` at the start of
the assertion block if setup noise accumulates.

Source: ISSUE-2086

---

## Fixture and Store Isolation

### Delete `devlogs/` Before Validating a Branch If the Integration Suite Ran

`test/demo/test_fv_demo.py` runs `run_fv_demo()` in-process and writes real
ledger files into repo-root `devlogs/fv/` (the default path). A subsequent
`uv run pytest test/ci/invariants/` then reads those local files instead of
skipping, and a second run accumulates two chains whose `prevLogHash` values
mismatch. `devlogs/` is gitignored so `git status` shows nothing. Fix:
`rm -rf devlogs/` after running the integration suite and before running the
invariant harness locally. Bug #2274.

Source: ISSUE-2266

### `_TestClientRouter` WARNING for Unregistered Hosts Is a Bug Signal

`_TestClientRouter.emit` in `test/demo/conftest.py` drops deliveries when no
client is registered for the recipient's base URL. Drops to hosts in
`_KNOWN_FICTIONAL_HOSTS` (e.g. `vultron.example`) log at `DEBUG` — those are
intentionally unreachable. Drops to any *other* unregistered host (e.g. a
`.test` host) log at `WARNING` — that is almost always a config leak or fixture
bug. A WARNING in the demo-test output means a `Create(CaseProposal)` or similar
activity was misaddressed; look for a stale-config leak upstream. See
[notes/configuration.md](configuration.md) § "_TestClientRouter WARNING".

Source: CONCERN-2323

### Outbox `BackgroundTasks` Emitter Has Two Resolution Paths — Patch Both

`POST /actors/{id}/outbox/` schedules `outbox_handler` with no emitter argument
and resolves it via `get_default_emitter()` → patch with
`configure_default_emitter(router)`. `POST /actors/{id}/inbox/` schedules
`outbox_handler` with `emitter=getattr(request.app.state, "emitter", None)` and
bypasses `get_default_emitter()` when `app.state.emitter` is set. A test fixture
that patches only one path will miss deliveries from the other. Patch both:
`configure_default_emitter(router)` **and** `api_app.state.emitter = router`.

Source: ISSUE-1780

### Config Overrides in Fixtures

Prefer `config_override()` over `monkeypatch` + `reload_config()`, and if you
cannot, get the teardown order right. Both rules, with the leak-guard caveats,
are in [notes/configuration.md](configuration.md) § "Testing Pattern".

### Store Scoping

An `actor_id` *is* a store name, and a BT's store follows its executing actor.
Both hazards (and why one of them is silent) are in
[notes/datalayer-design.md](datalayer-design.md) § "One Actor Id Is One
Database".

---

## py_trees and BT Tests

### `py_trees` Blackboard Is Process-Global — Clear Between Test BT Runs

`py_trees.blackboard.Blackboard.storage` is a module-level singleton.
Constructing a fresh `BtNode` tree per test does **not** clear it; keys set by a
previous `execute_with_setup` remain visible to the next run. Either use a scoped
namespace per run or clear the blackboard explicitly between executions. In
production, BT-17-003 already requires domain-specific output keys to be reset on
every tick; tests must also prevent cross-test contamination.

Source: ISSUE-2232

### `SUBFAILED` in `unittest.TestCase` Subtests Does Not Fail pytest

`test/bt/test_vultrabot.py::MyTestCase::test_main` may show `SUBFAILED` due to
py_trees `Blackboard.storage` global-state ordering, but pytest exits 0. When
investigating that test, run it targeted with `-v` and treat `SUBFAILED` as real.
Clear `py_trees.blackboard.Blackboard.storage` in BT-using fixtures.

### `py_trees` BT Subclasses in Tests MUST Be Defined at Module Level

py_trees maintains a global class registry keyed by class name. A BT subclass
defined inside a test function is registered globally; if two test functions
define local classes with the same name (e.g. `class MyBT`), the second
registration clobbers the first. Trees built from the first definition then
silently resolve to the wrong class. Define all test-only BT subclasses at module
level, prefixed with `_` to mark them as non-public:
`class _MyBT(py_trees.behaviours.Behaviour): ...`. Never define them inside test
functions or fixtures. See also [notes/bt-pitfalls.md](bt-pitfalls.md).

Source: CONCERN-2321

### BT Factory Determinism

When a tree builder's default `CallOutBackendFactory` is probabilistic
(`AlmostAlwaysSucceed`, `WeightedBehavior`), SUCCESS-asserting integration tests
MUST pass an explicit deterministic factory:

```python
def _always_succeed_factory(name: str) -> py_trees.behaviour.Behaviour:
    class _AlwaysSucceed(py_trees.behaviour.Behaviour):
        def update(self):
            return py_trees.common.Status.SUCCESS
    return _AlwaysSucceed(name)
```

Structure tests and FAILURE-path tests are unaffected.

### BT Contract Tests: Inherit Production Node Class (Not Just the Mixin)

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

Source: ISSUE-1565

### Full-Tree Tick Tests: Stub Only the Probabilistic Nodes, Not the Node Under Test

When ticking a collapsed FUZZ-08x tree to SUCCESS to verify one call-out point's
contract, check each leaf's fuzzer base type:

- **Leave the node under test at its default factory** — otherwise the test
  proves nothing about that node's contract.
- **Inject deterministic stubs for every other probabilistic call-out point** in
  the tick path (e.g., `AlmostAlwaysSucceed` at 0.90 makes the full-tree tick
  flaky).

The existing `_marker_factory` helper in test files returns an
unconditional-SUCCESS stub. Add an `isinstance` guard (e.g.,
`assert isinstance(tree.children[0], PrioritizePublicationIntents)`) so a future
refactor that accidentally stubs the node under test fails loudly.

The blackboard storage key carries a **leading slash**
(`/publication_intent_decision`); assert against
`py_trees.blackboard.Blackboard.storage` and rely on the `autouse
clear_blackboard` fixture to keep the assertion non-vacuous.

Source: ISSUE-1594

### `ResolveCaseManagerNode` Requires a CASE_MANAGER Participant in Fixtures

Set `case_participants` and `actor_participant_index` directly in the
constructor; pass `TriggerActivityAdapter(dl)` to every use case in chained
integration tests.

---

## Assertion Quality

### A Test That Says "Falls Back To" for Malformed Input Is Asserting a Bug

A test whose docstring says "falls back to X" or "defaults to X" for *malformed*
(not absent) input is asserting the ARCH-15 violation as intended behavior.
Absent input and unreadable input are different: `RM.START` is the right answer
when no statuses exist; it is never the right answer when a status exists but
cannot be read. A test that locks in the fallback turns the regression suite
against the fix. When writing a test for a defensive fallback, distinguish "not
present" from "present but invalid" and assert a raise/`FAILURE` for the latter.

Sources: ISSUE-2232, ISSUE-2264

### A FAILURE Test Must Prove the Harness Can Produce Its Named Reason

`BTTestScenario` injects some collaborators unconditionally, so several
"failure when X is absent" conditions **cannot be reached through it**:

| Named condition | Why unreachable |
|---|---|
| datalayer absent | `BTBridge.setup_tree` always assigns `blackboard.datalayer` |
| trigger factory unavailable | `BTTestScenario.__init__` always wires `trigger_activity=TriggerActivityAdapter(dl)` |

Three tests named one of these and passed anyway — each was actually dying on an
unrelated missing blackboard port. `assert_failure` only checked
`status == FAILURE`, which both causes satisfy, so the name and the behavior
drifted apart with nothing to catch it.

**Pattern:** when asserting FAILURE, assert the *reason* too:

```python
bt_scenario.assert_failure(result, reason="case 'https://…/case-001' not found")
```

`reason` is a substring of `result.feedback_message`. Supply it whenever the node
has more than one FAILURE path — a bare `assert_failure(result)` on a node ticked
with no domain context verifies only "it did not hang". Use
`assert_failure_reason(tree, "<substring>")` only when the leaf's reason does not
survive into the result: it inspects the *tree*, so it sees neither the status nor
the crash classification and MUST NOT be the sole assertion after a run.

`assert_failure` rejects a failure that came from an escaped exception unless the
test passes `allow_internal=True` (see `BTExecutionResult.internal_error`). Use
that flag **only** when the crash path is the subject of the test; reaching for it
to quiet an unexplained failure re-creates the problem it detects. Because it
switches the classification guard off, it is accepted **only together with
`reason`** and it also enforces `result.internal_error is True` — a test that
opts out of the automatic check has to name what it expects and must be testing
a genuine crash path, not a protocol FAILURE whose message happens to match:

```python
bt_scenario.assert_failure(
    result, reason="Input port 'activity_ids'", allow_internal=True
)
```

The guard is not exhaustive — a crash swallowed by a node's own `except Exception`,
or one inside a subtree run through a nested `BTBridge`, still arrives as an
ordinary FAILURE. Why that is structural, and why the nested-bridge idiom
guarantees it, is in [notes/bt-pitfalls.md](bt-pitfalls.md) § "…And That Idiom Is
Why `internal_error` Cannot See a Nested Crash".

**Corollary:** if the condition is genuinely unreachable, the coverage does not
exist. Rename the test to what it verifies and record the real gap rather than
leaving a name that implies coverage — BT-14-001's factory-unavailable branch was
uncovered for exactly this reason.

Source: CONCERN-3019

### Case-Actor Broadcast Guard Tests Need a Third Participant

Include at least one non-sender peer, or the assertion is vacuous.

### Happy-Path DL Seed Must Include `origin` Activities for `dl.read()` Calls

Assert `len(outbox) >= N` with the expected count, not just `>= 1`. See
[notes/datalayer-design.md](datalayer-design.md).

### `MagicMock` Requires `spec=` When Code Uses `isinstance()` Guards

When migrating from duck-typing guards (TypeGuard helpers using `getattr`) to
`isinstance()` checks, bare `MagicMock()` instances break silently: the
`isinstance` check returns `False` and the test exercises the wrong branch.

**Fix:** use `MagicMock(spec=ConcreteClass)` so
`isinstance(mock, ConcreteClass)` returns `True`. This applies to every test that
creates a mock case, participant, or ledger entry AND passes it through code that
uses `isinstance(x, VulnerabilityCase)` etc.

**Symptom:** test passes but verifies the wrong code path (e.g., "case not found"
instead of the intended `ValueError` branch).

Source: ISSUE-1504

### DataLayer Scope Tests: Use `call_args.args`, Not `call_args[0]`

The named attribute raises `AttributeError` clearly; the index returns an empty
tuple silently.

### Hash-Chain Invariant Assertions (CASE-LOG-925)

Assert field presence before comparing values:

```python
assert entry_a.get("entry_hash"), "entryHash must be non-empty"
assert entry_b.get("prev_log_hash"), "prevLogHash must be non-empty"
assert entry_a["entry_hash"] == entry_b["prev_log_hash"]
```

`"" == ""` is a false positive masking serializer/schema bugs.

### Genesis-Hash Path Must Be Tested with a Stored Case (CLP-08-995)

`is_ledger_fresh_for_case` skips the genesis-hash check when no case is stored
(effective hash = `""`). CLP-08-004 tests MUST save the case first:

```python
dl.save(_make_case())  # ensures genesis hash available
result = is_ledger_fresh_for_case(dl, case_id, ...)
assert result is True
```

"No case stored → trivially fresh" tests must be clearly labeled and MUST NOT be
the sole coverage for the genesis-hash path.

### Dual-Path Consolidation Test Gap

(ISSUE-1378, 2026-07-14)

When consolidating two helpers with different lookup paths into one unified
function, the new test suite MUST exercise each distinct path in isolation.

In ISSUE-1378, `_resolve_case_manager_id` was consolidated from two helpers: a
primary `actor_participant_index` path and a fallback `case_participants` path.
All 6 initial tests only populated `case_participants`, leaving the primary index
path entirely untested.

**Pattern**: For a helper with N distinct lookup paths, write at least one test
per path where that path is the *sole* source of truth — all other paths are left
empty or unpopulated. "One test exercises both paths" means neither path is
verified independently.

---

## Test Layout and Markers

### Module-Split Test Layout Rules (NODES-SPLIT-883)

When splitting `nodes.py` → `nodes/` subpackage:

- Re-export all public names from `nodes/__init__.py`.
- Mirror in tests: move to `test/.../nodes/` with per-submodule files; keep
  tree-composition tests in parent.
- Parent `conftest.py` fixtures are auto-available; only copy vocabulary
  side-effect imports into new `conftest.py`.
- Delete the old flat file — never have both `nodes.py` and `nodes/__init__.py`.

Applies equally to `triggers/`, `received/`, etc.

### Pytest Mark Consistency (RENAME-934; TB-11-001)

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

### Trigger Use Cases Need Per-Use-Case Tests

Incidental coverage via `test_trignotify.py` is insufficient. See
[notes/triggers-test-coverage.md](triggers-test-coverage.md).

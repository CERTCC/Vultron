---
title: Testing Pitfalls and Patterns
status: active
description: >
  Full write-ups for pytest pitfalls in this repo: reading a killed run, the
  two-tier timeout guardrail and why the timeout *method* matters more than the
  ceiling, measuring effective markers rather than declarations,
  `filterwarnings` precedence, fixture and blackboard isolation, py_trees test
  patterns, CoreObject subclass isolation, assertion-quality traps (vacuous
  asserts, "falls back to" tests, bare MagicMock), and test layout rules for
  module splits, why a two-sided count pin races concurrent PRs (keep a
  per-item record instead), why `nproc` overstates a worktree slot's CPUs for
  `-n auto`, why order-dependent tests need an `xdist_group`, and how outbox
  retry backoff hides inside a passing demo.
  `test/AGENTS.md` keeps the short index and the rules you need on every run.
related_specs:
  - specs/testability.yaml
  - specs/behavior-tree-integration.yaml
  - specs/spec-registry.yaml
  - specs/meta-specifications.yaml
  - specs/handler-protocol.yaml
  - specs/outbox.yaml
related_notes:
  - notes/flaky-tests.md
  - notes/configuration.md
  - notes/bt-pitfalls.md
  - notes/bt-integration.md
  - notes/datalayer-design.md
  - notes/triggers-test-coverage.md
  - notes/demo-ci-invariants.md
  - notes/wire-artifact-immutability.md
  - notes/spec-authoring-rules.md
  - notes/architecture-ratchet-corpus.md
  - notes/outbox-delivery-reliability.md
relevant_packages:
  - pytest
  - pytest-xdist
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
signal.** Any pipeline does this — a pipeline's status is its *last* stage's, so
`| tail`, `| tee … | tail`, `| head`, and `| wc` all mask it equally. Never end a
gate command with a pipe. Redirect, capture `$?` immediately, then re-raise it:

```bash
uv run pytest --tb=short > /tmp/unit.log 2>&1; rc=$?; tail -5 /tmp/unit.log; echo "exit: $rc"; (exit $rc)
```

Three details carry the weight, and dropping any one of them re-opens the hole:

- **`rc=$?` directly after the redirected command.** Any command in between —
  including the `tail` — overwrites `$?`.
- **`echo` last, after the `tail`.** Otherwise the exit code scrolls above the
  five tail lines, which is exactly where nobody looks.
- **`(exit $rc)` at the end.** Without it the *statement* still exits 0, because
  its status is that of the last command. `echo "exit: $?"` alone makes the code
  visible to a reader but leaves it invisible to `&&`, to `set -e`, to a CI
  `run:` step, and to anything consuming a skill's `commands:` frontmatter.

Read the `exit:` line before the tail: it is authoritative. If the redirect
cannot be opened (read-only `/tmp`, exhausted disk, `noclobber`), the command
never runs and `tail` prints the *previous* run's passing summary.

The spec-lint test (`test_real_specs_lint_no_hard_errors`) is particularly
load-sensitive at ~3s against the 5s budget.

The canonical command lives in
[`.agents/skills/run-tests/SKILL.md`](../.agents/skills/run-tests/SKILL.md) §
Constraints, and `test/metadata/test_instruction_command_hygiene.py` fails the
suite if a masking form reappears in an instruction file.

Source: ISSUE-2232, #3518

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

Session after session re-diagnosed the result as flakiness before the ceiling
itself was fixed; the write-ups are under `plan/history/*/learning/` (grep
`timeout_method`). Raising it costs nothing on a genuine hang — that test was
never going to finish — and the suite stays fast because total runtime is
bounded by the tests, not by this ceiling.

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

#### Raising the Ceiling Lowers the Frequency of Signal Loss, Never the Severity

`timeout_method = "thread"` arrived in #528 alongside the ceiling itself, with
no stated reason for the method — and the tier table above, like most write-ups
since, tunes *ceilings* around it. That is the wrong dial. A ceiling governs how
often a trip happens; the method governs what a trip costs, and under `"thread"`
a trip costs the whole session: the process dies where it stands, so the tests
after the hang never run and the failures already recorded are never named.

The cost is not theoretical — #3576 lost the names of four unrelated failures
that way. **And the method has been named before without being acted on, which
is the sharper lesson.** `plan/history/2608/learning/ISSUE-2086-thread-timeout.md`
and `ISSUE-2235-pytest-5s.md` both proposed `timeout_method = "signal"` so a slow
test "fails alone instead of voiding the suite", and `ISSUE-2270.md` already
recorded the GIL limitation noted below. Every time, the ceiling moved instead.
So the trap is not that nobody spotted the dial; it is that a ceiling change is
always the smaller diff, and the diagnosis got re-filed as flakiness (ISSUE-1925,
ISSUE-1988, ISSUE-2237, and the timeout observed during ISSUE-2762 that put #3041
on this trail). A two-line probe settles which dial matters, because the
difference is visible in the summary rather than in argument:

| `--timeout-method` | Hanging test | Rest of session | Summary line |
|---|---|---|---|
| `thread` | kills the process | never runs | none |
| `signal` | fails, named, alone | runs to completion | names every failure |

`signal` (POSIX-only, `SIGALRM` in the main thread) is what restores the
signal. It is not free: the alarm raises at an arbitrary point, so an interrupt
landing while a test holds the module-level blackboard `RLock` is a deadlock
mode `"thread"` does not have, and a hang inside a C call that never releases
the GIL is unreachable by a signal. Both are bounded by a job-level
`timeout-minutes` on the pytest job, which the `thread` method's self-kill has
been quietly standing in for. Tracked in #3603.

Source: #528, #2270, #3041, #3576

#### A Marker Sweep That Counts Declarations Misses a Directory Hook

Tests under `test/demo/` are marked `integration` by a path-based
`pytest_collection_modifyitems` hook in `test/demo/conftest.py`, not by a
`pytestmark` line in each module. A sweep that greps for the declaration
therefore reports near-total non-compliance for a directory that is in fact
100% compliant — which is how #3041 came to assert that 59 of 63 demo modules
inherit the unit tier, three weeks after both the hook and the 60s tier had
landed. It also proposed adding the marker to all 59, which would have been a
no-op duplicating the hook's job per module.

The mechanism itself is documented in
[`test/AGENTS.md`](../test/AGENTS.md) § "`test/demo/` Tests Are Auto-Marked
`integration` by a Directory Hook" — it was already written down when #3041
asserted the opposite, so the miss was in the measurement, not the docs.

**Ask what the collected items actually carry, not what the files declare.** A
`trylast` plugin reading `item.get_closest_marker(...)` answers it in one run
and leaves no repo change behind:

```bash
cat > probe_plugin.py <<'PY'
import pytest


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items):
    for item in items:
        integration = item.get_closest_marker("integration") is not None
        timeout = item.get_closest_marker("timeout")
        print(
            f"{item.nodeid}\tintegration={integration}\t"
            f"timeout={timeout.args[0] if timeout else None}"
        )
PY
uv run pytest test/demo -m "" --collect-only -q -s -p probe_plugin
rm probe_plugin.py
```

`trylast` is the load-bearing part: it puts the probe after both the root and
the directory hook, so it reports the resolved marker rather than an intermediate
state. On 2026-09-24 it reported 1276 collected items, every one
`integration=True` — 1274 at the 60s tier plus two deliberate per-test overrides
(180s, 10s) — and none at the 30s unit ceiling.

The same distinction applies to the assertion that guards the tier, though less
starkly than it first appears. `test/test_integration_timeout_tier.py` does
reach past stubs: `TestResolvedTimeoutsUnderRealPytest` runs a `pytester`
sub-session and asks `pytest-timeout` what it actually resolved per item, which
is what catches a root-hook-vs-`pytest-timeout` ordering regression. But that
sub-session builds its own conftest and three synthetic tests, and the rest of
the file asserts against hand-built `FakeItem`s — so nothing in it exercises the
`test/demo/` directory hook. If the root and demo
`pytest_collection_modifyitems` hooks ever reorder relative to each other, demo
tests can drop to the unit tier with no test failing. Tracked in #3604.

Source: #3041, #3576

### A `filterwarnings` Exemption Placed Before `"error"` Is a No-Op

pytest applies ini `filterwarnings` entries in list order through
`warnings.filterwarnings()`, and that function **inserts at index 0**. So the
list reads in *increasing* order of precedence: the **last** entry wins. An
`always::`/`ignore::` exemption listed *before* `"error"` never applies, and the
warning it was meant to surface non-blockingly raises instead.

```toml
filterwarnings = [
    "error",                       # must come FIRST
    "always::pkg.AdvisoryWarning", # exemptions AFTER it
]
```

Verify with `warnings.filters` — index 0 is highest precedence:

```bash
uv run python -c "import warnings; print(warnings.filters[:6])"  # inside a session
```

**Why this keeps recurring.** The rule is the opposite of how the list reads, and
the original write-up recorded it backwards ("placed BEFORE `error` so the
specific rule takes precedence (Python prepend semantics)"). Consequences:

- `always::UnknownSpecIdWarning` sat before `"error"` from the spec-marker gate's
  introduction, so SR-05-002's normative "non-blocking" guarantee **never held** —
  an unknown spec ID aborted collection rather than warning.
- #2329 measured the correct rule and named the latent bug, but the finding sat in
  an issue body rather than here, so #3331 and PR #3336 both reproduced it for a
  second warning class before it was caught in review.

**A position assertion cannot catch this.** `pytest.warns` and
`warnings.catch_warnings` both replace the ini filters, so no in-session test can
observe the escalation — which is why a test asserting the *index* passed while
the behaviour was broken. Assert the behaviour in a `pytester` sub-session fed the
project's real filter list
(`test/metadata/specs/test_spec_marker_gate.py::TestWarningIsNotEscalated`).

Normative: SR-05-007. Sources: #2329, #3336.

### `caplog` Captures Fixture-Setup-Phase Records

`caplog.set_level()` set in a fixture captures log records emitted during other
fixtures' setup, not just the test body. Set it inside the test function to
scope capture to the test body only, and call `caplog.clear()` at the start of
the assertion block if setup noise accumulates.

Source: ISSUE-2086

### `nproc` Lies Inside a Worktree Slot

`start-dev.sh` starts each slot with `--cpus 2 --memory 6g`, but `nproc`,
`os.cpu_count()` and xdist's stock `-n auto` all report every host core. On a
12-core host, `-n 10` in a slot ran the full suite in 12m51s at 1.8 cores busy,
and five workers were OOM-killed — xdist reports each as a failure of whatever
test the worker held, so the failures name innocent tests. `-n 2` ran the same
suite green in 9m56s.

`test/conftest.py` therefore implements `pytest_xdist_auto_num_workers` from
the cgroup files (`test/support/xdist_workers.py`): the CPU quota, the
scheduler affinity, and the memory limit at 1.5 GiB per worker.
`PYTEST_XDIST_AUTO_NUM_WORKERS` still overrides it. When a worker "crashed"
before any assertion failed, read `/sys/fs/cgroup/memory.events` — a non-zero
`oom_kill` means the test it names is not the cause.

### Order-Dependent Tests Need an `xdist_group`

Under `-n`, xdist's default `--dist load` hands tests to whichever worker is
free, so two tests of one module can land in different processes. A test that
reads state an earlier test left behind then runs without it: the ordered pairs
in `test/test_process_global_isolation.py` failed CI this way on their first
parallel run. `addopts` sets `--dist loadgroup`, which distributes like `load`
but keeps every test sharing an `xdist_group` mark on one worker, in collection
order. Mark an order-dependent module with
`pytestmark = pytest.mark.xdist_group("<name>")`; the mark does nothing without
`loadgroup`, and `loadgroup` does nothing without `-n`.

### A Retry Loop With Real Backoff Hides Inside a Passing Demo

A demo test that takes 25 seconds with no sleep of its own is usually waiting on
the outbox's in-pass backoff (1s, 2s, 4s per failure). The scenarios built on
`setup_initialized_case` queued a `Create(VulnerabilityCase)` addressed to no
one; delivery refused it, and the outbox retried it on backoff twelve times per
case before dead-lettering it — about 24 seconds per test, every test still
green. Profile a slow demo with a wall-clock, all-threads profiler (`yappi`):
`cProfile` sees only the main thread, which is idle in `epoll` waiting on the
TestClient portal while the app's thread sleeps. The fixes: a refused sealed
body is dead-lettered on its first refusal (OX-13-013), and
`_no_outbox_row_is_dead_lettered` in `test/demo/conftest.py` fails any demo test
that dead-letters a row.

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

### `py_trees` Blackboard Is Process-Global — Cleared Once, at the Test Root

`py_trees.blackboard.Blackboard.storage` is a module-level singleton.
Constructing a fresh `BtNode` tree per test does **not** clear it.
`BTBridge.execute_with_setup` restores only the keys on its `managed_keys` list,
so any other key a node writes outlives the run and is visible to the next one.
In production, BT-17-003 requires a node to write `None` to its output keys on a
no-op path; tests must also prevent cross-test contamination (TB-06-005).

The autouse `clear_py_trees_blackboard` fixture in the root `test/conftest.py`
clears the storage before **and** after every test in the suite. Do not add a
per-directory or per-file copy: a copy covers only its own directory, and the
gap between copies is where #3996 lived. The same root conftest resets the
other per-actor registries (`_reset_buffers()` for the ledger gap buffer, the
pending-assertion stores, the actor stores). A new process-global registry gets
its reset there too.

**#3996 diagnosis.** The received embargo Reject/Invite tests failed in some
orders. The issue blamed the per-actor store cache, but the stores were already
disposed after every test. The real cause was a stale `/participant` key: the
since-deleted `OptionalLookupParticipantNode` wrote it only when it *found* a
participant (a BT-17-003 breach), and the use-case tests outside
`test/core/behaviors/` had no clearing fixture, so a later test transitioned
the previous test's participant. Ratchet: the ordered pairs in
`test/test_process_global_isolation.py`. The second test of each pair fails
loudly if the first did not run.

Source: ISSUE-2232, ISSUE-3996

### `SUBFAILED` in `unittest.TestCase` Subtests Does Not Fail pytest

`test/bt/test_vultrabot.py::MyTestCase::test_main` may show `SUBFAILED` due to
py_trees `Blackboard.storage` global-state ordering, but pytest exits 0. When
investigating that test, run it targeted with `-v` and treat `SUBFAILED` as real.
The root `clear_py_trees_blackboard` fixture clears the storage between tests.

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

### CoreObject and CoreRecord Subclasses in Tests: Use `isolated_core_registries`

`CoreObject.__init_subclass__` and `CoreRecord.__init_subclass__` register every
concrete subclass in `CORE_VOCABULARY` and `CORE_TYPE_MAP` at class-definition
time.
These are module-level dicts — pollution is visible to every test that runs
in the same process after the class is first defined.

There is also a second, irrecoverable side-effect: the class permanently joins
Python's `CoreObject.__subclasses__()` graph.
Unlike the dicts, that graph cannot be restored by any fixture.
Architecture ratchets that walk `__subclasses__()` (e.g.
`test_every_core_object_forbids_extra_with_no_exemption_list`) will see the
test-local class for the rest of the session, but because `CoreObject`
subclasses inherit `extra="forbid"` those ratchets still pass.
The dict pollution is the actionable risk.

**Rule**: any test that defines a local `CoreObject` or `CoreRecord` subclass
MUST request the `isolated_core_registries` fixture.
It snapshots and restores both `CORE_VOCABULARY` and `CORE_TYPE_MAP`:

```python
def test_something(isolated_core_registries):
    class _Probe(CoreObject):
        type_: Literal["_Probe"] = "_Probe"
    ...
```

The fixture lives in the root `test/conftest.py`, so it is available to every
test in the suite — such subclasses appear under `test/core/`, `test/adapters/`
and `test/architecture/` alike. The snapshot/restore itself is
`test.support.core_vocab.restore_core_registries()`, a context manager the
fixture wraps, so the restore is tested directly rather than by test ordering.
Do not hand-roll a `dict(CORE_VOCABULARY)` snapshot or a `CORE_TYPE_MAP.pop()`
in a test body: those restore one map and miss the other (#3789, fixed
by #3801).

This mirrors the py_trees rule (see `### py_trees BT Subclasses in Tests MUST
Be Defined at Module Level` above): both patterns protect process-global
registries from test-local class definitions.
The key difference is that py_trees requires module-level definitions; the
CoreObject rule allows function-local definitions as long as the fixture is
present, because the dict registries can be fully restored.

Source: CONCERN-3789

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
`py_trees.blackboard.Blackboard.storage` and rely on the root autouse
`clear_py_trees_blackboard` fixture to keep the assertion non-vacuous.

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

### Deciding whether a permissive fallback is load-bearing

Moved to [notes/domain-validation.md](domain-validation.md) § "Broad `except
Exception` Is a Masking Smell" (subsection "When you cannot tell whether a
fallback is load-bearing") — the defensive/validation-boundary home for the
normative rule (CS-23-001). Use the instrument-and-count method there before
removing or trusting a bare `except`, `or <default>`, or failed-lookup fallback.

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

### A Wrong Base Class Silently Skips the Branch the Test Names

A fixture built on the wrong base class can report a function as covered while
never executing the line that matters — worse than missing coverage, which at
least reads as a known gap. A `test_json2md` passed continuously while the
function was 100% broken for every real input, because its fixture was
`class Foo(as_Base)`: the code is guarded by `hasattr(obj, "published")`, but
`published`/`updated` live on `as_Object`, one level down, so the guard evaluated
`False`, the body never ran, and the test asserted nothing went wrong.

**Pattern:** when a function branches on `hasattr`, `isinstance`,
`in model_fields`, or any other capability probe, the fixture MUST be a type that
*takes* the branch. Prefer a real domain type over a minimal stand-in subclass
(here `as_VulnerabilityReport`, not a local `Foo(as_Base)`). When a stand-in is
genuinely needed, assert the precondition explicitly so the fixture cannot
silently drift out of the branch:

```python
report = _frozen_report()
self.assertIsNotNone(report.published)
self.assertTrue(type(report).model_config.get("frozen"))
```

`as_Base` and `as_Object` differ in both field set *and* mutability (ADR-0017),
so picking the wrong one changes what the test can possibly detect — see
[notes/wire-artifact-immutability.md](wire-artifact-immutability.md).

Source: ISSUE-2904

### A Received-Side Test Only Sees Bugs Its Fixture Shape Can Reach

Three fixture/assertion traps that let a sender-side field silently vanish before
core code could read it (the sending and receiving halves were tested separately
and each was right about its own side):

- **A "so that receivers can…" clause in a spec is a claim about the *receiving*
  side.** It is not satisfied by the sender setting the field. Assert it by
  reading the field back out of the *extracted event* (`request.activity`), not
  out of the wire object the sender built.
- **Fixture shape decides which bug a test can see.** A received-side fixture in
  the *simple* shape (`actor=vendor_id`) cannot detect a defect that only appears
  in the *delegated* shape (`actor=case_actor_id, attributed_to=vendor_id`), even
  when its assertion names the right field — because in the simple shape
  `request.actor_id` happens to equal the value being checked. For anything under
  CM-24, seed `actor=case_actor_id` with a *distinct* `attributed_to`; if the two
  are the same actor, the test proves nothing about which one the code read.
- **Field-by-field copy functions rot silently.** A builder like
  `_build_activity_snapshot` that enumerates fields by hand omits every field
  added to the source type since it was written, and nothing fails. When a
  received-side read comes up empty, suspect the extraction/snapshot copy before
  the sender.

Source: ISSUE-2789

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
uv run pytest -m "new_mark_name" --collect-only > /tmp/collect.log 2>&1; rc=$?; tail -5 /tmp/collect.log; echo "exit: $rc"; (exit $rc)
```

### Trigger Use Cases Need Per-Use-Case Tests

Incidental coverage via `test_trignotify.py` is insufficient. See
[notes/triggers-test-coverage.md](triggers-test-coverage.md).

---

## Ratchets

### A Two-Sided Count Pin Races Every Concurrent PR

A ratchet that asserts `live_count == PINNED` fails in both directions: above
the pin means new debt, below means a fix that forgot to lower the pin. That
is correct on the PR that sets the pin and wrong on every other PR in flight.
If a sibling PR moves the count by one (verifying a requirement, adding a
marker), each PR is green on its own base and the merge is red on `main`, and
then on every branch rooted at it, through no change of their own. Each
affected session then does a clean-base proof, finds the cause, and applies the
same one-line fix. That fix collides on the next sync. Two PRs that make the
*identical* edit to the pin merge cleanly, to the wrong number.

MS-10-006's `VERIFICATION_CEILINGS` table was this shape. It turned `main`
red twice: #3974/#3975 pinned project at 1004 while a sibling lowered it to
1003, and #4031 repeated it with the MS-12 kind gates. Nor is a one-sided pin
the fix, because it collects silent slack instead (#3959).

**Keep a per-item record instead of a shared number.** Mark each item that is
still in debt (`verification_debt: '#N'` on the requirement itself) and check
each item on its own. Then two PRs conflict only when they edit the same item,
and git reports that as a real conflict. The count is still printed, computed
from the markers, so progress stays visible without being committed. Hold back
growth with a one-way, PR-only diff guard (#4200), not a pinned total. Where a
committed baseline is unavoidable, make it a named set (`KNOWN_VIOLATIONS`,
ARCH-18), never a bare number. A set entry names what it exempts, and a
concurrent PR that removes a different entry merges cleanly to the right
answer.

## Delete an Ephemeral Migration Check When the Migration Lands

A test written to prove a migration is complete (every call site moved, no
caller of the old name left, old and new outputs equal) is scaffolding. Once the
migration has landed, the check guards a transition that is over, so it keeps
costing runtime and review attention while protecting nothing a durable test does
not. Delete it in the PR that finishes the migration (#4190). If part of it
states an invariant that must keep holding, promote that part to a durable test
under its own spec ID (an architecture ratchet with a named known-violations set
is the usual shape; see § Ratchets) and delete the rest.

## A Test Timeout Is Acceptable Verification of a Time-Limit MUST

When a requirement is a time limit ("MUST complete within N seconds", "MUST NOT
block longer than N"), a test that fails by timing out *is* its verification.
Do not add a stopwatch assertion beside the timeout; it measures the same thing
with more noise. HP-07-002 stands on this reading. The timeout *method* still
matters (see the two-tier timeout guardrail above): a timeout that cannot
interrupt the blocked call verifies nothing.

Source: ISSUE-4190, ISSUE-4195

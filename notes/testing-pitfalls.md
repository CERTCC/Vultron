---
title: Testing Pitfalls and Patterns
status: active
kind: guidance
description: >
  Full write-ups for pytest pitfalls in this repo: reading a killed run, a dead
  xdist worker hanging the run, the two-tier timeout guardrail and why the
  timeout *method* matters more than the ceiling, reading `configfile:` before
  concluding a ceiling is inert, profiling a near-ceiling test
  before re-tiering it, sizing the integration tier from measured load, the
  ledger-rebuild teardown error a timeout trip leaves behind, proving off-loop
  work without a wall-clock window, an in-process pass that hides what each node
  holds on its own,
  measuring effective markers rather than declarations,
  `filterwarnings` precedence, `nproc` in a worktree slot, `xdist_group` for
  order-dependent tests, retry backoff hiding in a passing demo, fixture and
  blackboard isolation, why a status fixture may not encode a state the CS
  invariants forbid and where the guard for that reaches,
  py_trees test patterns, CoreObject subclass isolation,
  assertion-quality traps (vacuous asserts, "falls back to" tests, bare
  MagicMock), driving a guard through its production entry point rather than by
  direct call, the three future-date idioms a sweep must tell apart before
  replacing a literal, why turning nesting into sequence moves the skip nobody
  tests,
  why no test may assert over the whole collection now that CI runs the suite
  as partitioned sessions,
  test layout rules for module splits, why a two-sided count pin
  races concurrent PRs (keep a per-item record and a PR-only growth guard
  instead), why a schema change that the merge base fails breaks every growth
  guard, when to delete a migration check, why a child Python process
  must get its environment from `child_env()`, why a test that spawns children
  sizes its fan-out from the cgroup rather than the host's cores, and why a
  harness that fails for the environment — a filesystem that refuses the
  fixture, a bash the construct needs — hides real failures.
  `test/AGENTS.md` keeps the short index and the rules you need on every run.
related_specs:
  - specs/testability.yaml
  - specs/behavior-tree-integration.yaml
  - specs/spec-registry.yaml
  - specs/meta-specifications.yaml
  - specs/handler-protocol.yaml
  - specs/outbox.yaml
  - specs/case-ledger-processing.yaml
  - specs/cs-behavior.yaml
related_notes:
  - notes/flaky-tests.md
  - notes/configuration.md
  - notes/bt-pitfalls.md
  - notes/bt-integration.md
  - notes/datalayer-design.md
  - notes/domain-validation.md
  - notes/triggers-test-coverage.md
  - notes/demo-ci-invariants.md
  - notes/demo-scenario-tree.md
  - notes/wire-artifact-immutability.md
  - notes/spec-authoring-rules.md
  - notes/architecture-ratchet-corpus.md
  - notes/outbox-delivery-reliability.md
  - notes/sync-ledger-replication.md
  - notes/devcontainer-tooling.md
  - notes/ci-workflow-authoring.md
relevant_packages:
  - pytest
  - pytest-xdist
  - py_trees
---

# Testing Pitfalls and Patterns

`test/AGENTS.md` keeps short pointers into the sections below.

## Reading Test Output

### A Killed `pytest` Run Reports Exit 0 Under `tail -5`

When a run is killed (the gate's `timeout` ceiling, an OOM kill) it exits
non-zero, but the `uv run pytest ... 2>&1 | tail -5` pipeline returns `tail`'s
exit code (0) and shows the last output where the `N passed` summary would be.
Any pipeline masks the status the same way (`| tee`, `| head`, `| wc`), because a
pipeline exits with its last stage's status. Never end a gate command with a
pipe. Redirect, capture `$?` at once, then re-raise it:

```bash
timeout -k 30 1800 uv run pytest --tb=short > /tmp/unit.log 2>&1; rc=$?; tail -5 /tmp/unit.log; echo "exit: $rc"; (exit $rc)
```

- **`rc=$?` directly after the redirected command**: anything in between,
  including `tail`, overwrites `$?`.
- **`echo` after the `tail`**, so the exit code is not scrolled above the tail.
- **`(exit $rc)` last**, so `&&`, `set -e` and a CI `run:` step see the failure,
  not just a reader.

Read the `exit:` line first: it is authoritative. If the redirect cannot be
opened, the command never runs and `tail` prints the *previous* run's summary.
The canonical command is in
[`.agents/skills/run-tests/SKILL.md`](../.agents/skills/run-tests/SKILL.md), and
`test/metadata/test_instruction_command_hygiene.py` fails the suite if a masking
form appears in an instruction file (#3518).

### A Dead xdist Worker Hung the Run

Symptom: the log stops advancing near the end, an earlier line reads
`[gwN] node down: Not properly terminated`, and `/proc` shows the dead worker as a
zombie (`Z`) beside an idle replacement. Under `--dist loadgroup`, xdist's
`remove_node` puts the dead worker's *whole* workload back in the queue, finished
work units too. The replacement is handed a unit with nothing left to run, sends
no report, and the controller waits forever (#4809). The default `load` scheduler
does not do this, but the repo needs `loadgroup` (§ "Order-Dependent Tests Need an
`xdist_group`").

`addopts` sets `--max-worker-restart=0`, so a dead worker now fails the run at once
with `worker 'gwN' crashed while running <test>`;
`test/test_xdist_worker_crash.py` pins it. Two things killed workers: OOM kills,
and the old `thread` timeout method (§ "Per-Test Timeout Guardrail"). Every local
gate command also runs under `timeout -k 30 1800` (`GATE_CEILING` in
`vultron/metadata/planning/targeted_tests/selection.py`), so any hang still left
ends with exit 124. The run-tests skill's table tells the three outcomes apart.

### Per-Test Timeout Guardrail

Timeouts are **two-tier** (`pytest-timeout`):

| Tier | Ceiling | Set in |
|---|---|---|
| Unit (default) | 30s | `timeout = 30`, `pyproject.toml` |
| `@pytest.mark.integration` | 120s | `INTEGRATION_TIMEOUT_SECONDS`, `test/conftest.py` |

`apply_integration_timeout` in `test/conftest.py` widens the ceiling for
integration-marked tests at collection time; an explicit
`@pytest.mark.timeout(N)` always wins. The root hook is `trylast`, so it runs
after directory hooks that add the `integration` marker.

`timeout_method = "signal"` makes a trip fail that one test, named
`Failed: Timeout (>Ns)`; the rest of the session runs and the summary names every
failure (#3603). A ceiling is a hang detector, not a performance budget: it is
sized well above the slowest honest test (#2270) because contention on CI runners
and loaded dev boxes inflates honest multi-second tests far past their idle cost.

When a test trips its tier: mock slow dependencies, avoid `time.sleep()`, or mark
it `integration` if it exercises the full stack. `@pytest.mark.timeout(N)` is a
last resort and MUST carry a comment saying why. If a tier fires on honest work
rather than hangs, change the tier, and do not add a
[flaky-tests.md](flaky-tests.md) row for a test that is merely near its ceiling.

Profile a near-ceiling test before you move it to another tier. Its cost is often
work repeated per call rather than honest work: a check that parses the whole spec
corpus once per sub-check, or an adapter that re-reads the whole outbox on every
send. Removing the repeat also speeds up every other test on that path
(#5341, #4906). Also look for a second test that runs the same expensive fixture
only to inspect what the first test's run already recorded (#5227).

Size the integration tier from the slowest test's quiet cost times the load
stretch it meets, not from the typical test. The exchange demos are CPU-bound
(wall time equals CPU time), so host load stretches them in proportion (#5188).
`test/test_integration_timeout_tier.py` records the measured inputs and pins
their product as the tier's floor.

Before concluding a ceiling does not fire, read the `rootdir:`/`configfile:`
lines in the pytest header. A ceiling lives in `pyproject.toml`, so a control
test placed outside the repo gets no `configfile` at all and sleeps past it
untouched — which looks exactly like an inert ceiling and is really an unread
config (#5597). Run the control from inside the tree, and under both `-n 0` and
`-n auto`, because a worker is its own process and the `signal` method has to
reach that worker's main thread. `TestTheUnitCeilingIsLive` in
`test/test_integration_timeout_tier.py` pins both, by asking `pytest_timeout`
what it resolved for the running test rather than trusting the ini.

A demo test that trips its timeout also fails at teardown with a ledger-rebuild
error (`… rebuilt from its ledger differs …`, or a case naming a `log_index`
past its chain's end). The trip stopped the demo between a ledger commit and the
case update that follows it, and the rebuild check in
`test/demo/_helpers.py` runs on the half-finished case. Diagnose the timeout;
the rebuild error is its consequence, not a second defect (#5188).

#### A Timeout Trip With No Assertion In Its Traceback Is Someone Else's Memory

Two heavy local runs together exhaust the container's memory, and the suite is
the one that reports it: its markdown-rendering and AST-scanning tests trip
`pytest-timeout` and show as failures, while the command that took the memory
exits with no output at all. A trip with no assertion in its traceback, in a
test that does not touch the diff, is the signature. Re-run that test alone
before believing it (#3156). Every heavy local check takes a per-host slot
([devcontainer-tooling](devcontainer-tooling.md) § "Run Every Heavy Local
Check Through the Per-Host Lock"), which caps how many share the host but does
not stop one agent starting two at once, so still run them in turn.

#### A Count of Events in a Wall-Clock Window Is Not a Concurrency Proof

Do not prove that work runs off the event loop by counting loop ticks in a fixed
window. CPU contention from other xdist workers starves the loop, and the test
fails with nothing wrong. Park the work on an event that only a coroutine on the
loop can set: the work then finishes released only if the loop ran while it
waited. Load can delay that release but cannot fake it (#4913).

#### The Timeout Method Sets What a Trip Costs

A ceiling sets how often a trip happens; the method sets what it costs. Change the
method's cost first, because a ceiling change is always the smaller diff and so
keeps being chosen instead.

| `--timeout-method` | Hanging test | Rest of session | Summary line |
|---|---|---|---|
| `thread` | kills the process (under `-n`, the worker) | never runs | none |
| `signal` | fails, named, alone | runs to completion | names every failure |

`signal` is POSIX-only (`SIGALRM`, main thread). Its feared cost, an alarm that
leaves the blackboard `_BT_GLOBAL_LOCK` held, does not occur: every acquire in
`vultron/` is a `with` block, which releases on the raised `Failed`, and a blocked
acquire is interrupted by the signal. `test/test_integration_timeout_tier.py`
checks both paths. A hang the signal cannot reach, such as a C call that never
releases the GIL, is bounded by the CI job's `timeout-minutes` and the local
gate's `timeout` ceiling.

#### A Marker Sweep That Counts Declarations Misses a Directory Hook

Tests under `test/demo/` are marked `integration` by a
`pytest_collection_modifyitems` hook in `test/demo/conftest.py`, not by a
`pytestmark` line per module, so grepping for declarations reports a compliant
directory as non-compliant (#3041). Ask what the collected items carry. A
`trylast` probe plugin reports the resolved markers and leaves no repo change:

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

`trylast` is what makes it report the resolved state, after both the root and the
directory hook. `test/test_integration_timeout_tier.py` checks the tier with
`FakeItem`s and a synthetic `pytester` session, and
`TestDemoItemsResolveToTheIntegrationTier` asks the same probe question of the
real `test/demo/` collection, so a hook reorder fails a test (#3604).

### A `filterwarnings` Exemption Placed Before `"error"` Is a No-Op

pytest applies ini `filterwarnings` entries in order through
`warnings.filterwarnings()`, which **inserts at index 0**, so the **last** entry
wins. An `always::`/`ignore::` exemption listed before `"error"` never applies,
and the warning raises instead:

```toml
filterwarnings = [
    "error",                       # must come FIRST
    "always::pkg.AdvisoryWarning", # exemptions AFTER it
]
```

A test asserting the list position cannot catch this, because `pytest.warns` and
`warnings.catch_warnings` replace the ini filters. Assert the behaviour in a
`pytester` sub-session fed the project's real filter list, as
`test/metadata/specs/test_spec_marker_gate.py::TestWarningIsNotEscalated` does
(SR-05-016).

### `caplog` Captures Fixture-Setup-Phase Records

`caplog.set_level()` in a fixture also captures records other fixtures emit
during setup. Set it inside the test function, and call `caplog.clear()` before
the assertion block if setup noise accumulates.

### `nproc` Lies Inside a Worktree Slot

`start-dev.sh` caps each slot's CPUs and memory (`SLOT_CPUS`, `SLOT_MEMORY`),
but `nproc`, `os.cpu_count()` and xdist's stock `-n auto` report every host
core. Too many workers run slower and get OOM-killed, and xdist reports each
kill as a failure of whatever innocent test the worker held. `test/conftest.py` implements
`pytest_xdist_auto_num_workers` from the cgroup limits
(`test/support/xdist_workers.py`); `PYTEST_XDIST_AUTO_NUM_WORKERS` overrides it.
When a worker "crashed" before any assertion failed, read
`/sys/fs/cgroup/memory.events`: a non-zero `oom_kill` means the named test is not
the cause.

### Order-Dependent Tests Need an `xdist_group`

Under `-n`, two tests of one module can land on different workers, so a test that
reads state an earlier test left behind runs without it. `addopts` sets
`--dist loadgroup`, which keeps every test sharing an `xdist_group` mark on one
worker in collection order. Mark a module that *asserts* an order with
`pytestmark = pytest.mark.xdist_group("<name>")`, as
`test/test_process_global_isolation.py` does. A test that merely *depends* on an
order is a leak to fix: put the reset in root `test/conftest.py` (TB-06-003), with
an ordered pair in `test_process_global_isolation.py`.

### A Retry Loop With Real Backoff Hides Inside a Passing Demo

A demo test that takes many seconds with no sleep of its own is usually waiting
on the outbox's in-pass backoff (1s, 2s, 4s per failure) for a row that will
never deliver. Profile it with a wall-clock, all-threads profiler (`yappi`):
`cProfile` sees only the main thread, idle in `epoll` on the TestClient portal. A
refused sealed body is dead-lettered on its first refusal (OX-13-013), and
`_no_outbox_row_is_dead_lettered` in `test/demo/conftest.py` fails any demo test
that dead-letters a row.

## Fixture and Store Isolation

### A Status Fixture May Not Encode a State the CS Invariants Forbid

A participant status pairing a pre-acceptance RM state with the VFD F bit —
`rm=VALID` with `vf=VF`, say — is a state CSB-18-001 says cannot exist, and a
test standing on one passes for a reason other than the behaviour it names.
When the matching invariant is finally enforced every such test breaks at once,
so a real enforcement improvement reads as a regression (#2906, #3046). The
same holds for `d=D` against a pre-acceptance RM, and for `Vf` with `d=D`, the
`*fD*` compound CSB-17-001 rules out.

`test/core/behaviors/status/conftest.py` installs an autouse guard that calls
`composite_state_violations` on every participant record a test in that package
writes to a store, and the shared `current_status()` and `seed_case()` builders
in `test/support/rm_declaration.py` check the fixture they build. **Outside
`test/core/behaviors/status/` there is no guard**: a status fixture under
`sync/`, `report/` or `test/core/use_cases/` is the author's to get right. Ask
`impossible_state_reasons()` (`test/support/participant_status.py`) before
seeding one.

Two properties of the guard's design are worth keeping if it moves:

- It keys on the evaluator and on the DataLayer write, never on a fixture
  builder's name, so a renamed or hand-rolled builder cannot slip past
  (#5535). `save_many` takes a list and `UpdateObject` writes a
  `StorableRecord` whose statuses are plain dicts, so both shapes are walked.
- A BT node's `except Exception`, or the bridge's own handler, turns the
  guard's raise into `Status.FAILURE` or an `internal_error` result, so the
  raise alone does not report a tree write. Each violation is recorded as well,
  and the installing fixture fails the test on a non-empty record.

The inbound status under judgement is deliberately *not* checked: several
received-side tests exist to show an impossible one refused.

### Delete `devlogs/` Before Running the Invariant Harness Locally

`test/demo/test_rv_demo.py` runs the demo in-process and writes real ledger files
into the gitignored repo-root `devlogs/`. `test/ci/invariants/` then reads them
instead of skipping, and a second run accumulates two chains whose `prevLogHash`
values mismatch. `rm -rf devlogs/` after the integration suite and before the
invariant harness (#2274).

### `InProcessRouter` WARNING for Unregistered Hosts Is a Bug Signal

`InProcessRouter` in `vultron/demo/in_process.py` drops deliveries to a base URL with
no registered client. Drops to `_KNOWN_FICTIONAL_HOSTS` (e.g. `vultron.example`)
log at `DEBUG`; drops to any other host log at `WARNING`, which almost always
means a misaddressed activity from a stale-config leak upstream. See
[notes/configuration.md](configuration.md) § "Testing Pattern".

### Patch Both Outbox Emitter Paths

The inbox and outbox routes schedule `outbox_handler` with
`emitter=request.app.state.emitter` when that is set, and `outbox_handler` falls
back to `get_default_emitter()` when it is not. A fixture that patches only one
path misses deliveries from the other: set `configure_default_emitter(router)`
**and** `api_app.state.emitter = router`, as `test/demo/conftest.py` does.

### Config Overrides in Fixtures

Prefer `config_override()` over `monkeypatch` + `reload_config()`, and if you
cannot, get the teardown order right. Both rules are in
[notes/configuration.md](configuration.md) § "Testing Pattern".

### A Child Python Process Gets Its Environment From `child_env()`

A test that runs `sys.executable` on code importing `vultron` MUST pass
`env=child_env()` (`test/support/child_env.py`). pytest puts the repository
root first only on its own `sys.path`; a child inherits just `PYTHONPATH`, and
in a worktree that can name another checkout. A script child's `sys.path[0]` is
the script's directory, so the other checkout's `vultron` wins and a module it
lacks fails to import (#5456). A devcontainer built before #5571 exports
`PYTHONPATH=/app` ([devcontainer-tooling](devcontainer-tooling.md) § "The Image
Exports No `PYTHONPATH`; Rebuild if `$PYTHONPATH` Is `/app`").

### A Test That Spawns Children Sizes Them From The Cgroup, Not The Host

A test that runs several child processes at once MUST take its fan-out from
`child_process_budget()` (`test/support/xdist_workers.py`), not from
`os.cpu_count()`. The budget is the memory one xdist worker is given
(`WORKER_MEMORY_BYTES / CHILD_MEMORY_BYTES`), capped by `worker_count()` — the
same cgroup reading `-n auto` is sized from (§ "`nproc` in a Worktree Slot").
Sizing from the core count puts as many children in the container as the *host*
has cores however little of it the slot allows, beside workers already sized to
the slot; the OOM killer then takes a worker, which xdist reports as a crash of
whatever test that worker happened to hold (#5184).

A per-test `xdist_group` is not the lever here: it co-locates tests on one
worker, it does not stop the other workers spending the container at the same
time. When the symptom is a wall-clock trip rather than a crash, look for a
*serial* bottleneck inside the test before widening its ceiling — one
brand-new interpreter at a time cost `test_every_module_imports_fresh.py` 88 of
its 110 seconds, and batching that route under the same bound took the whole
test to 47s.

### A Harness That Fails For The Environment Hides Real Failures

A gate that is red for a reason the diff cannot cause trains a contributor to
read past red, so the next real failure is read past too. Two shapes of it:

- **A fixture the filesystem refuses.** Attempt the write and `pytest.skip` on
  `OSError`; do not skip on `sys.platform`. APFS rejects a file name that is
  not valid UTF-8, so `test_changed_files_keeps_a_non_utf8_name` errored in
  setup on macOS (#5449). The property under test belongs to the filesystem, so
  the refusal is the condition: a Linux host on a UTF-8-enforcing mount skips
  for the same reason, and a filesystem that later accepts the name is still
  covered. Exercise the skip arm with a refusal every host raises (a missing
  parent directory), or CI never runs it.
- **A shell construct the host's bash lacks.** macOS ships bash 3.2, so a
  bash 4 builtin exits 127 there while passing on the Linux runners —
  `ensure-issue-type.sh` used `mapfile` and failed three `test/ci/` tests
  (#5698). `test/ci/test_shell_script_portability.py` scans every tracked
  `*.sh` for the constructs that have bitten;
  [ci-workflow-authoring](ci-workflow-authoring.md) § "A Script Runs On The
  Host's bash, Which May Be 3.2" carries the portable spellings.

### Store Scoping

An `actor_id` *is* a store name, and a BT's store follows its executing actor. See
[notes/datalayer-design.md](datalayer-design.md) § "One Actor Id Is One
Database".

## py_trees and BT Tests

### `py_trees` Blackboard Is Process-Global — Cleared Once, at the Test Root

`py_trees.blackboard.Blackboard.storage` is a module-level singleton; a fresh tree
per test does not clear it, and `BTBridge.execute_with_setup` restores only its
`managed_keys`. The autouse `clear_py_trees_blackboard` fixture in root
`test/conftest.py` clears it before and after every test (TB-06-005). Do not add a
per-directory copy: the gap between copies is where order-dependent failures live
(#3996). The same root conftest resets the other process-global registries (the
pending-assertion and actor stores); a new registry gets its reset there too,
with an ordered pair in
`test/test_process_global_isolation.py`.

### `SUBFAILED` in `unittest.TestCase` Subtests Does Not Fail pytest

`test/bt/test_vultrabot.py::MyTestCase::test_main` can show `SUBFAILED` while
pytest exits 0. When investigating it, run it targeted with `-v` and treat
`SUBFAILED` as real.

### `py_trees` BT Subclasses in Tests MUST Be Defined at Module Level

A BT subclass defined inside a test function is keyed by class name, so two
functions defining `class MyBT` clobber each other and trees silently resolve to
the wrong class. Define test-only BT subclasses at module level with a `_`
prefix (CONCERN-2321). See also [notes/bt-pitfalls.md](bt-pitfalls.md).

### CoreObject and CoreRecord Subclasses in Tests: Use `isolated_core_registries`

`CoreObject.__init_subclass__` and `CoreRecord.__init_subclass__` register every
concrete subclass in the module-level `CORE_VOCABULARY` and `CORE_TYPE_MAP` at
class-definition time, so a test-local subclass pollutes every later test in the
process. Any test that defines one MUST request the root `isolated_core_registries`
fixture, which snapshots and restores both maps through
`test.support.core_vocab.restore_core_registries()`:

```python
def test_something(isolated_core_registries):
    class _Probe(CoreObject):
        type_: Literal["_Probe"] = "_Probe"
    ...
```

Do not hand-roll a `dict(CORE_VOCABULARY)` snapshot or a `CORE_TYPE_MAP.pop()`:
each restores one map and misses the other (#3789). The class still joins
`CoreObject.__subclasses__()` for the session, which no fixture can undo;
ratchets that walk it still pass because subclasses inherit `extra="forbid"`.

### BT Factory Determinism

When a tree builder's default `CallOutBackendFactory` is probabilistic
(`AlmostAlwaysSucceed`, `WeightedBehavior`), SUCCESS-asserting integration tests
MUST pass an explicit deterministic factory (one returning an
always-`SUCCESS` behaviour). Structure tests and FAILURE-path tests are
unaffected.

### BT Contract Tests: Inherit the Production Node Class

A deterministic wrapper for a probabilistic call-out node MUST subclass the
**production node** plus `AlwaysSucceed`, not the abstract mixin plus
`AlwaysSucceed`; otherwise it redeclares `output_keys` and cannot catch a
regression in the real node:

```python
class _DeterministicDevelopExploit(DevelopExploit, AlwaysSucceed):
    pass
```

### Full-Tree Tick Tests: Stub Only the Probabilistic Nodes, Not the Node Under Test

When ticking a collapsed tree to SUCCESS to check one call-out point, leave the
node under test at its default factory and inject deterministic stubs (such as
the `_marker_factory` helpers) for every *other* probabilistic node. Add an
`isinstance` guard (`assert isinstance(tree.children[0],
PrioritizePublicationIntents)`) so a refactor that stubs the node under test
fails loudly. Blackboard storage keys carry a leading slash
(`/publication_intent_decision`).

### `ResolveCaseManagerNode` Requires a CASE_MANAGER Participant in Fixtures

Set `case_participants` and `actor_participant_index` directly in the
constructor, and pass `TriggerActivityAdapter(dl)` to every use case in chained
integration tests.

## Assertion Quality

### Turning Nesting Into Sequence Moves the Skip Nobody Tests

A block whose nesting carried the behaviour — a `demo_gate`, a `try`/`finally`,
a context manager, a BT composite — decided what got **skipped** on failure.
Split it into two sequential pieces and that decision moves to the caller that
now sequences them, which is a place neither piece's test reaches. Two passing
per-piece tests then leave the one behaviour the split changed unchecked.

Both witnesses so far are in the demo story runner (#5534). Splitting the
case-invite chain so a branch point could sit between the invite and the answer
put the step mark between them unnested, so a failed invite trigger died at the
mark instead of skipping the answer. Moving `rcvcv`'s roster `demo_gate` into
the shared opening, where the invite is a *different* fragment, turned the gate
into a `demo_check`: a timeout recorded a failure and the invite went ahead
anyway, where before it skipped the whole invite and admit chain.

**How to apply.** When a diff turns nesting into sequence, name the guarantee
the nesting gave — what did it skip, and on whose failure? — and write one test
that exercises that guarantee *through the new caller*. The per-piece tests
stay; they are not the ones at risk. In a flat sequence the guarantee needs a
carrier: #5534's answer is a `StoryProp` the gate keeps and the dependent
reads, so a failed gate leaves the artifact absent and the runner stops the
story (`notes/demo-scenario-tree.md` § "Composition"). ADR-0135's "compose,
never chain" rule for BT helpers is the same shape seen from the design side.

### Drive a Guard Through Its Production Entry Point, Not by Direct Call

A unit test that calls a private guard directly says nothing about whether the
production path reaches it, so the guard can be dead while the test is green.
That is worse than no coverage: the spec-coverage ratchet counts the
requirement as covered, so nothing anywhere reports a problem (#3156). Write at
least one case that reaches the guard through the node or use case that runs it;
`test/core/behaviors/sync/nodes/test_chain_timestamp_guard.py` is the shape.

The production half is structural and checked.
`test/architecture/test_guards_run_in_production.py` fails on a private guard
nothing under `vultron/` references, and on a parameter whose presence opens a
refusal that no call site supplies. A caller alone is not enough: the witness
had one, and it never passed the argument the check needed.

### A Future Date Is Three Idioms — Decide Which One Before Replacing It

A test that names a future date is asking one of three questions, and a sweep
that swaps the literals without sorting them turns an assertion green for the
wrong reason. `FAR_FUTURE` from `test/support/future_dates.py` answers only the
first — "some date plausibly ahead, expected to be accepted". An absolute
`datetime(2099, ...)` usually means "implausibly far ahead, expected to be
**refused**", and substituting a relative value can land it inside the very
tolerance under test; a pinned instant means the value *is* the assertion. That
module's docstring holds the rule, the witnesses, and why `FAR_FUTURE`
truncates its microseconds (#2879).

### A Test That Says "Falls Back To" for Malformed Input Is Asserting a Bug

A test whose docstring says "falls back to X" for *malformed* (not absent) input
asserts the ARCH-15 violation as intended behavior. `RM.START` is right when no
status exists, never when a status exists but cannot be read. Distinguish "not
present" from "present but invalid" and assert a raise or `FAILURE` for the
latter. Before removing or trusting a fallback, use the method in
[notes/domain-validation.md](domain-validation.md) § "When you cannot tell
whether a fallback is load-bearing" (CS-23-002).

### A FAILURE Test Must Prove the Harness Can Produce Its Named Reason

`BTTestScenario` always injects a datalayer (`BTBridge.setup_tree` assigns
`blackboard.datalayer`) and `trigger_activity=TriggerActivityAdapter(dl)`, so
"failure when the datalayer / trigger factory is absent" cannot be reached
through it. A bare `status == FAILURE` assertion passes for any cause, so the
test name and the behavior drift apart (CONCERN-3019). Assert the reason:

```python
bt_scenario.assert_failure(result, reason="case 'https://…/case-001' not found")
```

`reason` is a substring of `result.feedback_message`; supply it whenever the node
has more than one FAILURE path. `assert_failure_reason(tree, "<substring>")`
inspects the tree, not the result, so it MUST NOT be the sole assertion after a
run. `assert_failure` rejects a failure from an escaped exception unless
`allow_internal=True`, which is accepted only with `reason`, requires
`result.internal_error is True`, and is for tests whose subject *is* the crash
path. The guard does not see a crash swallowed by a node's `except Exception` or
one inside a nested `BTBridge`; see [notes/bt-pitfalls.md](bt-pitfalls.md) §
"…And That Idiom Is Why `internal_error` Cannot See a Nested Crash". If the
condition is genuinely unreachable, the coverage does not exist: rename the test
to what it verifies.

### Case-Actor Broadcast Guard Tests Need a Third Participant

Include at least one non-sender peer, or the assertion is vacuous.

### Happy-Path DL Seed Must Include `origin` Activities for `dl.read()` Calls

Seed every object the use case reads, `origin` activities included, or the happy
path fails before it reaches the code under test. Then assert `len(outbox) >= N`
with the expected count, not just `>= 1`. See
[datalayer-design.md](datalayer-design.md) § "Happy-Path DL Seeds Must Include
Everything a Use Case Reads".

### `MagicMock` Requires `spec=` When Code Uses `isinstance()` Guards

A bare `MagicMock()` fails every `isinstance()` check, so the test silently
exercises the wrong branch (e.g. "case not found" instead of the intended
`ValueError`). Use `MagicMock(spec=ConcreteClass)` for any mock case, participant
or ledger entry that passes through an `isinstance` guard.

### DataLayer Scope Tests: Use `call_args.args`, Not `call_args[0]`

The named attribute raises `AttributeError` clearly; the index returns an empty
tuple silently.

### Hash-Chain Assertions: Check Presence Before Equality

Assert `entry_hash` and `prev_log_hash` are non-empty before comparing them:
`"" == ""` passes and masks serializer or schema bugs.

### Test the Genesis-Hash Path With a Stored Case

`is_ledger_fresh_for_case` skips the genesis-hash check when no case is stored, so
CLP-08-004 tests MUST `dl.save()` the case first. A "no case stored → trivially
fresh" test must say so and MUST NOT be the sole coverage of that path.

### One Test per Lookup Path When Consolidating Helpers

When two helpers with different lookup paths merge into one, write at least one
test per path in which that path is the *sole* source of truth and the others
are empty (ISSUE-1378). A test that populates both verifies neither.

### A Wrong Base Class Silently Skips the Branch the Test Names

When a function branches on `hasattr`, `isinstance`, `in model_fields` or another
capability probe, the fixture MUST be a type that *takes* the branch. Prefer a
real domain type over a minimal stand-in; a stand-in on `as_Base` lacks the
`published`/`updated` fields and the mutability of `as_Object` (ADR-0017), so a
`hasattr` guard skips the body and the test asserts nothing (ISSUE-2904). When a
stand-in is needed, assert the precondition (`assertIsNotNone(report.published)`)
so it cannot drift out of the branch. See
[notes/wire-artifact-immutability.md](wire-artifact-immutability.md).

### A Received-Side Test Only Sees Bugs Its Fixture Shape Can Reach

- **"So that receivers can…" in a spec is a claim about the receiving side.**
  Assert it by reading the field from the extracted event (`request.activity`),
  not from the wire object the sender built.
- **Fixture shape decides which bug a test can see.** For anything under CM-24,
  seed `actor=case_actor_id` with a *distinct* `attributed_to`; in the simple
  shape `request.actor_id` equals the checked value and proves nothing
  (ISSUE-2789).
- **Field-by-field copy functions rot silently.** A builder such as
  `_build_activity_snapshot` omits every field added since it was written. When a
  received-side read comes up empty, suspect the copy before the sender.

### An In-Process Pass Is Not Evidence for What Each Node Holds on Its Own

- **Rule.** When a change touches what an outbound payload carries, or what a
  CASE_MANAGER path reads about *another* actor, reproduce it in a topology whose
  participant node starts empty and is bootstrapped only by delivered activities
  (`test/demo/conftest.py` supports this; `test_pcr_bootstrap.py` does it for a
  two-node Announce). A green in-process suite does not count as coverage.
- **Why.** In-process topologies share what Docker keeps apart. They seed the case,
  its participants and its embargo into every node's store before one protocol
  step runs, so a receiver never depends on what the wire carried. Every node also
  reads one process-global `get_config()`, so a CaseActor that reads its own
  configuration for another actor's facts gets the right answer. Only the Docker
  demos bootstrap from delivered activities, with one configuration per container.
- **Symptom.** The suite is green, and the Docker demo fails with a "missing
  object" error on the receiving side (`no VulnerabilityCase for report`, `Invalid
  RM transition START → …`, `no routable recipients`) or a role error from a
  configuration read (`CVDRole.VENDOR required for VF state`). The sealed-body ratchet
  (`test_sealed_body_audit.py`) covers the trigger port only, not the receive-side
  projections. Witnesses: PR #3923 (payloads), #1876 / PR #4539 (configuration);
  the per-node configuration fix is tracked in #4541.

## Test Layout and Markers

### A Test MUST Not Assert Over the Whole Collection

CI runs the suite as four partitioned pytest sessions, one per matrix part of
`python-app.yml`'s `test` job, so no session sees every test (TB-11-002). A
test that reads `request.session.items`, pins a collected-test count, or
compares against a full-collection snapshot passes locally under one `pytest`
and is vacuous or red in CI, where its session holds one slice. Ask the
question of the **filesystem** instead — walk `test/` and parse, as
`test/test_pytest_collection_hygiene.py` does — or probe a collection in a
subprocess you launch with the paths you mean, as
`test/test_integration_timeout_tier.py` does for `test/demo`.

### Module-Split Test Layout Rules (NODES-SPLIT-883)

When splitting `nodes.py` → `nodes/` subpackage:

- Re-export all public names from `nodes/__init__.py`.
- Mirror in tests: move to `test/.../nodes/` with per-submodule files; keep
  tree-composition tests in parent.
- Parent `conftest.py` fixtures are auto-available; only copy vocabulary
  side-effect imports into new `conftest.py`.
- Delete the old flat file — never have both `nodes.py` and `nodes/__init__.py`.

Applies equally to `triggers/`, `received/`, etc.

### Pytest Mark Consistency (TB-11-001)

When renaming a mark, update **all three** in the same changeset, or pytest
collects 0 tests (exit code 5):

1. `pyproject.toml` markers list
2. `.github/workflows/` YAML files
3. Test source files

Verify:

```bash
grep -r "old_mark_name" .github/workflows/  # no output
grep "new_mark_name" pyproject.toml
timeout -k 30 1800 uv run pytest -m "new_mark_name" --collect-only > /tmp/collect.log 2>&1; rc=$?; tail -5 /tmp/collect.log; echo "exit: $rc"; (exit $rc)
```

### Trigger Use Cases Need Per-Use-Case Tests

Incidental coverage via `test_trignotify.py` is insufficient. See
[notes/triggers-test-coverage.md](triggers-test-coverage.md).

## Ratchets

### A Two-Sided Count Pin Races Every Concurrent PR

A ratchet asserting `live_count == PINNED` is right on the PR that sets the pin
and wrong on every other PR in flight. When a sibling PR moves the count, each PR
is green on its own base and the merge is red on `main` and on every branch rooted
at it; two PRs making the identical edit to the pin merge cleanly to the wrong
number (#3984). A one-sided pin is no fix: it collects silent slack (#3959).

**Keep a per-item record instead of a shared number.** Mark each item still in
debt (`verification_debt: '#N'` on the requirement) and check each item on its
own, so two PRs conflict only when they edit the same item. Print the count,
computed from the markers, without committing it. Where a committed baseline is
unavoidable, make it a named set (`KNOWN_VIOLATIONS`, ARCH-18), never a bare
number.

### Hold Back Growth With a PR-Only Guard, Not a Pinned Total

`added_since_base` in `vultron/metadata/specs/growth_guard/compare.py` runs a per-item
extractor (repository root → set of item IDs in debt) on the merge base with
`origin/main` and on the working tree, and returns only the items the branch
added, so a sibling PR cannot turn this one red. `test_spec_coverage_ratchet.py`
(SR-05-005), `test_spec_kind_ratchet.py` (MS-12-007),
`test_spec_statement_guard.py` (MS-03-007) and `test_verification_debt_guard.py`
(MS-10-016) use it. A debt class already at zero needs no guard: assert the set
is empty (MS-12-008).

Every guard reads the merge base with this branch's loaders, so a branch that
tightens the spec schema fails all of them with `BaseExtractionError` unless the
base already satisfies the new rule. Land the data fix on `main` first, then the
schema change (#5437 before #5285).

When adding one, keep three properties:

- **The base side is materialized from git** (`git archive` of only the paths the
  extractor reads), so the same extractor runs on both trees. A caller may pass
  the head set from an in-memory corpus (TB-13-001), but only through the
  extractor's own logic (e.g. `test_sources=`); a head set built another way
  reports phantom additions.
- **No base means skip, never pass.** Without a base the guard returns a
  `skipped` reason and the test calls `pytest.skip(reason)`. CI jobs running a
  guard check out with `fetch-depth: 0`, and under `GITHUB_ACTIONS=true` a missing
  base raises instead.
- **An unreadable base fails.** If the branch's loaders cannot read the base, the
  guard raises `BaseExtractionError` naming the merge base; give the loader a path
  that also accepts the old form.
- **Cost follows the change, not the tree.** A guard runs on every PR under the
  unit timeout, and reading two whole trees tripped it under load (#4904). An
  extractor whose items depend on one file at a time reads only the changed files
  (`compare_changed_with_base`); a cross-file one keeps `compare_with_base`, which
  skips the base read when nothing under its paths changed.

## Delete an Ephemeral Migration Check When the Migration Lands

A test written to prove a migration complete (every call site moved, no caller of
the old name left) guards a transition that is over once it lands. Delete it in
the PR that finishes the migration (#4190). If part of it states a lasting
invariant, promote that part to a durable test under its own spec ID (usually an
architecture ratchet with a named known-violations set; see § Ratchets).

## A Test Timeout Is Acceptable Verification of a Time-Limit MUST

When a requirement is a time limit ("MUST complete within N seconds"), a test
that fails by timing out *is* its verification; a stopwatch assertion beside it
measures the same thing with more noise (HP-07-002). The timeout *method* still
matters: a timeout that cannot interrupt the blocked call verifies nothing.

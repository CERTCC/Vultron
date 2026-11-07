---
stakeholder_type: [project-contributor]
---

# How to run maintainer tests

Use this guide when you need CI-aligned test execution from a maintainer
workflow.

## The automated gate is not this page

No automated local gate runs the whole unit or integration suite (PAD-18-003, PAD-18-008, PAD-18-015).
Every pipeline gate — a pull request's first push, a fix commit, a conflict merge — runs the test files `targeted-tests` derives from the diff:

```bash
logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"
git fetch -q origin main || { echo "fetch failed — stop and report"; exit 1; }; gate=$(PYTHONPATH= uv run targeted-tests --base origin/main --pytest); rc=$?
[ "$rc" -eq 0 ] && { eval "$gate" > "$logs-gate.log" 2>&1; rc=$?; tail -20 "$logs-gate.log"; }; echo "exit: $rc"; (exit $rc)
```

CI runs both suites on every push, and the required `CI gate` check refuses the merge until that run passes.
The commands below are for a human who wants the whole suite anyway — a long bisect, a local reproduction of a CI failure, a first-day check that the checkout works.
None of them is a step a pull request waits on.

## Whole-suite command (by hand)

Run:

```bash
uv run pytest -n auto --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)
```

This runs the unit suite by hand.
`-n auto` runs the tests on parallel `pytest-xdist` workers, one per CPU the container may use.
The worker count comes from the container's CPU and memory limits, not from `nproc`, so a worktree slot gets one worker per CPU it is capped at (`SLOT_CPUS`), memory permitting.
Set `PYTEST_XDIST_AUTO_NUM_WORKERS` to choose a different count.

Each slot container sizes its workers from its own limits and cannot see the other slots on the same host.
When several slots run the suite at once, start it through the per-host heavy-check lock:

```bash
uv run python .agents/skills/shared/run-heavy.py uv run pytest -n auto --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)
```

The wrapper waits until one of the host's heavy-check slots is free, then runs the command and exits with its status.
While it waits, it writes one line that names the runs holding the slots.
`start-dev.sh` sets the number of slots from the Docker VM's CPUs, and `HEAVY_SLOTS` overrides it.
Outside a slot container the wrapper says so and runs the command without a slot.

If a worker process dies, for example when the container runs out of memory, the run stops at once and reports `worker 'gwN' crashed while running <test>`.
The named test is the one the worker was running, which is not always the cause.
A test that starts child processes of its own adds to the same memory pressure.
Such a test sizes how many it runs at once from the container's limits too, never from the host's core count.
A test that runs past its per-test timeout fails on its own with `Failed: Timeout`, and the rest of the run goes on.

## Run a focused file while iterating

If you need faster feedback during implementation, run:

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

Replace the test path with your target file.

## Include integration tests

To mirror CI's run by hand, add the marker:

```bash
uv run pytest -m "" -n auto --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)
```

A change under `vultron/demo/` or `test/demo/` used to require this before a pull request's first push.
That exception is retired: `demo-integration.yml` runs those tests and the required `CI gate` judges it (PAD-18-008).
The targeted gate covers them through their importers like any other path, and its `-m ""` keeps a selected integration test in (PAD-18-011).

## Troubleshooting

- If pytest selection is surprising, check markers in test files and rerun with
  explicit `-m` as needed.
- If local output differs from CI, rerun with the integration-inclusive command
  above.

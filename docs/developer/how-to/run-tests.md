---
stakeholder_type: [project-contributor]
---

# How to run maintainer tests

Use this guide when you need CI-aligned test execution from a maintainer
workflow.

## Default command (maintainer baseline)

Run:

```bash
uv run pytest -n auto --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)
```

This is the default local maintainer command.
`-n auto` runs the tests on parallel `pytest-xdist` workers, one per CPU the container may use.
The worker count comes from the container's CPU and memory limits, not from `nproc`, so a two-CPU worktree slot gets two workers.
Set `PYTEST_XDIST_AUTO_NUM_WORKERS` to choose a different count.

## Run a focused file while iterating

If you need faster feedback during implementation, run:

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

Replace the test path with your target file.

## Include integration tests when required

If you touched any file under `vultron/demo/` or `test/demo/`, run:

```bash
uv run pytest -m "" -n auto --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)
```

Use this to mirror CI behavior for demo/integration-sensitive changes.

## Troubleshooting

- If pytest selection is surprising, check markers in test files and rerun with
  explicit `-m` as needed.
- If local output differs from CI, rerun with the integration-inclusive command
  above.

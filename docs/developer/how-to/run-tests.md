---
stakeholder_type: [project-contributor]
---

# How to run maintainer tests

Use this guide when you need CI-aligned test execution from a maintainer
workflow.

## Default command (maintainer baseline)

Run:

```bash
uv run pytest --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)
```

This is the default local maintainer command.

## Run a focused file while iterating

If you need faster feedback during implementation, run:

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

Replace the test path with your target file.

## Include integration tests when required

If you touched any file under `vultron/demo/` or `test/demo/`, run:

```bash
uv run pytest -m "" --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)
```

Use this to mirror CI behavior for demo/integration-sensitive changes.

## Troubleshooting

- If pytest selection is surprising, check markers in test files and rerun with
  explicit `-m` as needed.
- If local output differs from CI, rerun with the integration-inclusive command
  above.

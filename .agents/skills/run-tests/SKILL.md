---
id: "run-tests"
title: "Run canonical test-suite and capture summary"
description: "Run the repository's canonical pytest command and capture the final summary lines used by CI and automation."
author: "CERTCC / Vultron"
tags:
  - testing
  - ci
shell: "zsh"
commands:
  - "uv run pytest --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo \"exit: $rc\"; (exit $rc)"
inputs:
  - name: repo_root
    description: "Repository root"
    default: "."
outputs:
  - name: pytest_summary
    description: "The last 5 lines of pytest output (summary and short failure traces)"
  - name: exit_code
    description: "pytest's own exit status, printed as `exit: N` and returned as the command's status"
---

# Skill: Run Tests

| Suite | Command |
|---|---|
| Unit (default) | `uv run pytest --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)` |
| Integration | `uv run pytest -m integration --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)` |
| All | `uv run pytest -m "" --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)` |

The shape is always the same: **redirect, capture `$?` immediately, tail the log,
print the code last, then re-raise it.** `rc=$?` must come directly after the
redirected command — any other command in between overwrites `$?`. The trailing
`(exit $rc)` is what makes the whole statement carry pytest's status, so the
command is safe to chain or to use as a gate.

## Pre-PR Validation (build and create-pr)

Run **both** suites before opening a PR:

```bash
uv run pytest --tb=short > /tmp/pytest-unit.log 2>&1; rc=$?; tail -5 /tmp/pytest-unit.log; echo "exit: $rc"; (exit $rc)
uv run pytest -m integration --tb=short > /tmp/pytest-integration.log 2>&1; rc=$?; tail -5 /tmp/pytest-integration.log; echo "exit: $rc"; (exit $rc)
```

The first command covers the unit suite (integration tests excluded by
`addopts = "-m 'not integration'"`). The second explicitly runs the
integration suite. Both must pass; a branch that only breaks integration
tests must not reach a non-draft PR.

## Constraints

- Run exactly once per validation cycle; do not use `-q` or change output formatting.
- Do not change `tail -5` in the commands above. Other skills that tail a longer
  window (`pr-execute` uses `-20` and `-40`) may do so, but must keep the rest of
  the shape intact.
- **Never end a validation command with a pipe.** A pipeline exits with its
  *last* stage's status, so `… | tail`, `… | tee … | tail`, `… | head`, and
  `… | wc` all report 0 no matter how pytest exited — a `pytest-timeout` kill
  reads as success. This applies to every gate command (`pytest`, `mkdocs
  build --strict`, `flake8`, `mypy`, `pyright`, `markdownlint`), not just
  pytest, and to the bare `2>&1 | tail -5` form as much as to `tee | tail`.
  Redirect, capture `$?`, then re-raise it:

  ```bash
  <gate command> > /tmp/x.log 2>&1; rc=$?; tail -5 /tmp/x.log; echo "exit: $rc"; (exit $rc)
  ```

- **The `exit:` line is authoritative, not the tail.** Read it first. If the
  redirect itself fails (read-only `/tmp`, exhausted disk, `noclobber`), the
  command never runs and `tail` prints the *previous* run's summary — a
  passing-looking tail above a non-zero `exit:`. Trust the code.
- `filterwarnings = ["error"]` in `pyproject.toml` — warnings are test errors; fix root cause, do not suppress.
- Integration tests are excluded from the default interactive run; always run `-m integration` explicitly in pre-PR validation.
- Treat all failures as branch-owned by default; clean-base proof is required before classifying as pre-existing.
- **Never re-run the test suite to get more output.** Full pytest output is written to `/tmp/last-test-run.log` (or `/tmp/pytest-unit.log` / `/tmp/pytest-integration.log` when both suites run). Read or grep those files instead.

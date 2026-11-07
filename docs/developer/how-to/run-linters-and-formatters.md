---
stakeholder_type: [project-contributor]
---

# How to run formatters and linters

Use this guide to run the same formatting and linting flow maintainers expect before commit.

ruff formats and lints Python.
It reads its scope from `[tool.ruff]` in `pyproject.toml`, so neither command takes a path argument.

## Fix and format Python code first

Run:

```bash
uv run ruff check --fix
uv run ruff format
```

`--fix` applies only the safe autofixes: import sorting, unused imports and similar mechanical rewrites.

## Run the lint check next

Run:

```bash
uv run ruff check
```

A finding the fixer could not resolve needs a hand fix.
Do not add a `# noqa` to make it pass: a suppression needs a stated reason, and the ruleset is governed by `notes/lint-tooling.md`.

## Run the type checker

Run:

```bash
uv run mypy
```

Run it after formatting, never before.
The formatter can wrap a line that ends in a `# type: ignore` or `# pyright: ignore`, which leaves the pragma on a different line from the code it suppressed.

pyright is the second type checker, and CI's `Lint (pyright)` job is where the project runs it: it costs about two minutes and enough memory to disturb a parallel test run, so no local gate runs it (PAD-18-027).
Read its findings off that job.
You may still run `uv run pyright` by hand when you are chasing a type error mypy does not report.

## Lint markdown separately

Run:

```bash
./mdlint.sh
```

`ruff format` skips markdown by configuration.

## Troubleshooting

- If a type check reports an unused `# type: ignore` next to a new error on the line above, the formatter moved the pragma; put it back on the flagged line.
- If type checks fail unexpectedly, confirm your virtual environment is synced with `uv sync --dev`.

# How to run formatters and linters

Use this guide to run the same formatting and linting flow maintainers expect
before commit.

## Format Python code first

Run:

```bash
uv run black vultron/ test/
```

## Run flake8 next

Run:

```bash
uv run flake8 vultron/ test/
```

## Run the full lint set

Run:

```bash
uv run mypy
uv run pyright
```

## Lint markdown separately

Run:

```bash
./mdlint.sh
```

Do not use Black for markdown files.

## Troubleshooting

- If `black` reformats files, rerun the relevant linters after formatting.
- If type checks fail unexpectedly, confirm your virtual environment is synced
  with `uv sync --dev`.

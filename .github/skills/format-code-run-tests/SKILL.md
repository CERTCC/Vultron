# Skill: Format code & run tests

Purpose

Describe how to run Black and the canonical project test command for Vultron.

Commands (run in zsh, from repository root)

Format code (pre-commit enforces Black):

```bash
uv run black vultron/ test/
```

Run the full test-suite — EXACTLY this command, EXACTLY ONCE per validation cycle:

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

Notes

- Read the last 5 lines for the summary and any short failure tracebacks.
- Do NOT re-run pytest to grep counts, do not use -q, and do not change the tail window (e.g., tail -3 or tail -15).
- Run Black after editing any Python files and before staging for commit.
- Do NOT run Black on markdown files (use markdownlint-cli2 for those).

Running a specific test file:

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

Rationale

These commands are the canonical, repo-authoritative steps recorded in AGENTS.md for formatting and validating changes before committing.
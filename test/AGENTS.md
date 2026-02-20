# AGENTS.md — test/

This directory contains all pytest tests for the Vultron project. Test
structure mirrors the source layout under `vultron/`.

See the root `AGENTS.md` for full agent guidance. This file focuses on
rules that apply specifically when running or editing tests.

---

## ⚠️ Running the Test Suite — ONE RUN RULE (MUST)

Run the full test suite **exactly once** per validation cycle using this
exact command:

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

**That single command gives you everything you need:**

- The summary line (e.g., `472 passed, 2 xfailed in 40s`)
- Short tracebacks for any failures

**Do NOT:**

- Re-run pytest a second time to grep for counts (`grep -E "passed|failed"`)
- Change the tail length (`tail -3`, `tail -15`)
- Add the `-q` flag — it suppresses the summary line in some configurations
- Run with different flags to get "just the counts" — the tail already shows
  them

**Do NOT run sequences like these** (each line is a separate pytest
invocation — this wastes time and violates the one-run rule):

```bash
# ❌ WRONG — multiple runs
uv run pytest -q --tb=short 2>&1 | tail -15
uv run pytest -q --tb=short 2>&1 | grep -E "passed|failed|error"
uv run pytest -q --tb=short 2>&1 | tail -3
```

```bash
# ✅ CORRECT — one run, read the tail
uv run pytest --tb=short 2>&1 | tail -5
```

---

## Running a Specific Test File

```bash
uv run pytest test/test_semantic_activity_patterns.py -v
```

Use `-v` for verbose output when debugging a single file or module.

---

## Test Layout

- `test/` mirrors `vultron/` — e.g., `test/api/v2/backend/` mirrors
  `vultron/api/v2/backend/`
- Shared fixtures live in `conftest.py` files at each directory level
- Test files are named `test_*.py`

---

## Expected Baseline

The 2 `xfailed` tests in `test/api/test_reporting_workflow.py` use
deprecated `_old_handlers` with import issues and are **intentionally
skipped**. They do NOT indicate regressions.

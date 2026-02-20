# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## FIXED: Agents running test suite multiple times

**Status**: Fixed 2026-02-20

Agents were running the entire test suite multiple times with slightly
different commands to extract different pieces of information (counts,
summary line, failure tracebacks).

**Fix applied**:

1. Strengthened the warning in root `AGENTS.md` Agent Quickstart section:
   added a `⚠️` callout block listing the exact anti-patterns to avoid.
2. Created `test/AGENTS.md` with a prominent one-run rule that agents will
   discover when navigating to or working in the `test/` directory.

The correct single command is:

```bash
uv run pytest --tb=short 2>&1 | tail -5
```


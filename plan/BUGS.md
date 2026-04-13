# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYYYMMDDXX` for bug IDs, where `YYYYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-2026041001 Tests are slow ✅ FIXED

The test suite has slowed down significantly (>15m, target is 1 minute),
which is affecting development velocity. Run the suite to investigate which
tests are taking the longest and identify bottlenecks. Consider whether any
of the slowest tests can be optimized, isolated, or refactored to improve
overall test suite performance without sacrificing coverage or reliability.
Isolating slow integration tests is an option, but the primary goal is to
optimize the test suite as a whole while maintaining confidence in the codebase.

**Root cause**: TinyDB's `JSONStorage` re-reads and re-writes the entire JSON
file on every operation. `mydb.json` grew across hundreds of tests, compounding
the penalty to >15 minutes.

**Fix**: `pytest_configure` hook in `test/conftest.py` patches
`TinyDbDataLayer.__init__` to always use `MemoryStorage`. Demo tests marked
`@pytest.mark.integration` and excluded from the default run via
`addopts = "-m 'not integration'"`. An autouse fixture in
`test/adapters/driven/conftest.py` re-applies the patch after any test that
calls `importlib.reload()`.

**Result**: default run 13s; demo/integration run 6s (was 15m48s).

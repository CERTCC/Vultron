---
title: "uv run pytest full suite times out at 120s with no summary line"
type: learning
timestamp: "2026-08-03T00:00:00Z"
source: ISSUE-1925
signal: tooling-issue
---

Running `uv run pytest --tb=short` (all tests) consistently times out at 120
seconds and produces a truncated output file ending mid-traceback — no
`passed/failed` summary line is emitted.

The last visible traceback is from `yaml/parser.py` inside the spec-dump test
infrastructure, suggesting a long-running YAML parse or a blocking `spec-dump`
invocation is on the hot path. The background task reports exit code 0, so the
suite is not failing — it's just never finishing within 2 minutes.

**Impact on validation**: Cannot confirm the full-suite green baseline from
within this environment. Scoped runs (`test/demo/`, `test/ci/invariants/`)
complete in under 6 seconds and show 0 failures.

**Workaround used**: Run scoped suites that exclude `test/architecture/` and
`test/integration/` — these complete in ~6s.

**Suggested fix**: Profile the spec-dump or YAML-heavy test path to identify
the bottleneck; consider marking slow tests with `@pytest.mark.slow` and
adding a `--ignore` default to the local pytest config so `uv run pytest`
runs fast by default.

**Promoted**: 2026-08-17 — captured in docs/reference/codebase/TESTING.md (pytest-timeout cluster — prior session update).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.

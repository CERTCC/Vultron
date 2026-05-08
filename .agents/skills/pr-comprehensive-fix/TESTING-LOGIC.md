# Testing Logic and File Detection

## Detecting Integration Test Need

The skill automatically analyzes which files changed in the PR to decide
whether integration tests should be run.

### Files That Trigger Integration Tests

Run **full test suite (unit + integration)** if PR modifies:

1. `demo/` — any demo script or orchestration file
2. `integration_tests/` — any integration test
3. `adapters/` — driving or driven adapters
4. `vultron/core/behaviors/` — behavior tree logic
5. `vultron/core/use_cases/` — use-case implementations
6. `vultron/wire/as2/extractor.py` — semantic extraction (core to message handling)

### Detection Implementation

```python
changed_files = gh pr diff --name-only
needs_integration = any(
  f.startswith("demo/") or
  f.startswith("integration_tests/") or
  f.startswith("adapters/") or
  f.startswith("vultron/core/behaviors/") or
  f.startswith("vultron/core/use_cases/") or
  f == "vultron/wire/as2/extractor.py"
  for f in changed_files
)
```

## Test Suite Execution

### Unit Tests Only (default)

**Command**: `uv run pytest --tb=short 2>&1 | tail -5`

**When**: Changes are localized (single module, no core/demo/adapter impact)

**Expected output**: Summary of passed/failed tests

### Full Suite (unit + integration)

**Commands**:

1. `uv run pytest --tb=short 2>&1 | tail -5` (all unit tests)
2. `uv run pytest integration_tests/ -v` (integration test suite)

**When**: Demo, adapters, behavior trees, or use-cases modified

**Expected output**: Full test summary from both suites

## Interpreting Test Results

### All Tests Pass ✅

- Proceed to Step 4: Resolve comments individually
- CI will pass on merge

### Unit Tests Fail ❌

**Symptoms**: Test errors, assertion failures, import errors

**Likely cause**: Code changes broke tests

**Action**:

1. Display failure output
2. Ask if you want to rerun `/pr fix ci` to fix test errors
3. If yes, rerun tests
4. If still failing after 2 attempts, stop and ask for human intervention

### Integration Tests Fail ❌

**Symptoms**: Demo startup failures, protocol errors, CI job timeout

**Likely cause**: Demo or adapter changes broke the integration workflow

**Action**:

1. Display failure output (first 50 lines + last 20 for context)
2. **Stop** — do not auto-retry
3. Report the issue and suggest manual debugging
4. Integration test failures usually indicate architectural issues

**Why not auto-retry**: Integration tests are slow and often fail due to:

- Missing environment setup
- Timing issues in demo orchestration
- Architectural breaking changes
- Infrastructure problems (docker, network)

These need human judgment to diagnose.

## Handling Partial Fixes

If `/pr fix feedback` or `/pr fix ci` reports partial success (fixed some,
not all):

1. Display what was fixed vs. what remains
2. Ask:
   - Continue to testing (proceed with partial fixes)?
   - Stop and iterate manually?
   - Abort entirely?

**Best practice**: Test the partial fixes to see if they unblock other issues.

## When Test Results Suggest Stopping

The skill will **stop and report** rather than auto-loop if:

- Integration test failure with unclear root cause
- 2+ consecutive test failures after `/pr fix ci` attempts
- Test output suggests missing context (env vars, setup, infrastructure)
- Error suggests architectural issue (breaking change to core logic)

In these cases, the skill reports the state and recommends manual investigation
or discussion with reviewers.

## Future Enhancement: Integrate with `build` Skill

The same file-change detection should be used in the `build` skill to run
integration tests before creating a PR. This would prevent PR creation with
predictable test failures.

### Proposed `build` Enhancement

```text
When creating a PR, if changed files match integration test triggers,
run full test suite (unit + integration) before opening the PR.
This catches demo/adapter issues early.
```

This prevents the scenario where a PR is created but immediately fails CI.

# Comprehensive PR Fix: Reference

This skill uses a **structured, checkpoint-based workflow** to ensure PR fixes
don't miss problems. The workflow is organized into 4 steps, each with
decision points and verification checkpoints.

## Workflow Overview

| Step | Focus | Decision Point |
|------|-------|---|
| 1 | **Inventory** problems (comments + CI) | Run integration tests? (based on file changes) |
| 2 | **Fix code** systematically | Approve fixes before testing? |
| 3 | **Test** intelligently (unit ± integration) | Rerun fixes if tests fail? |
| 4 | **Resolve** comments individually | Verify all addressed? |

## For Each Use Case

- **PR with feedback + CI failures** → Follow all 4 steps
- **Feedback only** → Steps 1,2 (skip fix CI), then 3,4
- **CI failures only** → Steps 1,3,4 (skip fix feedback)

## Key Decisions Made During Inventory

The skill automatically detects which files changed and decides:

- **Integration tests needed?** (See [TESTING-LOGIC.md](TESTING-LOGIC.md))

## During Code Fix Phase

The skill uses existing subskills:

1. **`/pr fix feedback`** — Address review comments
2. **`/pr fix ci`** — Fix CI failures

## During Test Phase

The skill runs either:

- **Unit tests only** (typical case)
- **Unit + integration** (demo/adapter changes detected)

See [TESTING-LOGIC.md](TESTING-LOGIC.md) for decision criteria.

## During Resolution Phase

The skill marks comments resolved **individually** with explanations:

- ✅ Fully addressed
- ⚠️ Partially addressed (explain why)
- ❌ Cannot address (ask for clarification)

See [RESOLUTION-GUIDE.md](RESOLUTION-GUIDE.md) for strategies and examples.

## When Things Go Wrong

- **Stuck PR** (multiple fix attempts, no progress) → Stop and report
- **Integration test failure** (unclear cause) → Stop, don't auto-loop
- **Partial fix success** → Ask if you want to continue or iterate manually
- **Comment is architectural** → Reply, don't mark resolved

See [TESTING-LOGIC.md](TESTING-LOGIC.md) for handling test failures.

## Future Enhancement

The same file-change detection logic should be integrated into the `build`
skill to run integration tests before creating a PR. This prevents PR
creation with integration test failures.

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

The skill reads which files changed, and `targeted-tests` derives the gate
from them. There is no integration-tests-or-not decision to make: an
integration-bearing path is gated by its importers like any other
(PAD-18-003, ADR-0143). See [TESTING-LOGIC.md](TESTING-LOGIC.md).

## During Code Fix Phase

The skill uses existing subskills:

1. **`/pr fix feedback`** — Address review comments
2. **`/pr fix ci`** — Fix CI failures

## During Test Phase

The skill runs one gate: the targeted set `targeted-tests` derives from the
diff, with the integration marker enabled so integration-marked tests among
the selected files still run (PAD-18-011). No diff escalates it to the whole
suite (PAD-18-003); CI's required full run covers the reach beyond it.

See [TESTING-LOGIC.md](TESTING-LOGIC.md) for the command.

## During Resolution Phase

The skill marks comments resolved **individually** with explanations:

- ✅ Fully addressed
- ⚠️ Partially addressed (explain why)
- ❌ Cannot address (ask for clarification)

See [RESOLUTION-GUIDE.md](RESOLUTION-GUIDE.md) for strategies and examples.

## When Things Go Wrong

- **Stuck PR** (multiple fix attempts, no progress) → Stop and report
- **Integration test failure** (unclear cause) → Treat as PR-owned until
  disproven; do not label unrelated without evidence
- **Partial fix success** → Ask if you want to continue or iterate manually
- **Comment is architectural** → Reply, don't mark resolved

See [TESTING-LOGIC.md](TESTING-LOGIC.md) for handling test failures.

## Where the gate runs before a PR exists

`create-pr` Phase 3 runs the same targeted gate on a branch's first push
(PAD-18-001), and `build` runs no suite of its own (PAD-18-017). Nothing
local runs the whole suite before the push (PAD-18-008).

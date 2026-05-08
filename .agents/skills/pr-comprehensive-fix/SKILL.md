---
name: pr-comprehensive-fix
description: >
  Complete PR fix workflow that addresses review comments, CI failures, and test issues
  holistically. Inventory all problems first, fix code batch, run full test suite intelligently
  (integration tests for demo/adapter changes), and mark comments resolved individually.
  Use when a PR has multiple problems (review feedback + CI failures) and you want to ensure
  nothing gets missed.
---

# Comprehensive PR Fix Workflow

## Purpose

When a PR has accumulated review comments AND CI failures, the typical fix-all
patterns can get incomplete: they address feedback but miss CI problems, or
forget to mark comments as resolved, or skip integration tests for demo changes.

This skill provides a **structured, checkpoint-based workflow** that:

1. **Inventories** all problems (unresolved comments + CI failures)
2. **Fixes** code systematically (feedback + CI issues)
3. **Tests** intelligently (unit + integration if demo/adapter changes)
4. **Verifies** CI passes
5. **Resolves** comments individually with explanations

## Quick Start

```bash
# Fix all issues on the current PR systematically
/pr comprehensive-fix

# Answer prompts:
# - Review inventory of problems
# - Approve each fix phase
# - Verify final state
```

## Workflow: Step by Step

### Step 1: Inventory All Problems

1. Fetch all unresolved review comments from the PR
2. Parse CI failure logs from the most recent workflow run
3. Display inventory with categorization:
   - **Feedback issues** (from review comments)
   - **CI issues** (from workflow failures)
   - **Context** (which files changed, what's at risk)

**Decision Point**: Do CI failures suggest this PR needs integration tests?

- If changed files touch `demo/`, `integration_tests/`, or `adapters/`: YES
- Otherwise: unit tests only

Proceed? (yes/no)

### Step 2: Batch-Fix Code

If proceeding, invoke sub-skills in order:

1. **`/pr fix feedback`** — Address all unresolved review comments
2. **`/pr fix ci`** — Fix all CI failures

**Checkpoint**: Code fixed locally. Stop and let user review if needed.

### Step 3: Re-Run Full Test Suite

Based on Step 1 decision point:

- **Unit only**: `uv run pytest --tb=short 2>&1 | tail -5`
- **Full (unit + integration)**: Run both unit and integration test suites

If tests fail:

- Parse failure output
- Offer to re-run `/pr fix ci` if compilation/test errors
- Stop and report if human judgment needed

Proceed to resolve comments? (yes/no)

### Step 4: Mark Comments Resolved Individually

For each unresolved comment:

1. Check if the code change addresses it
2. If YES: resolve the comment with a note like "Addressed in latest commit: [summary]"
3. If NO or PARTIAL: add a comment explaining why it couldn't be fully addressed, and ask for clarification

**Final verification**: All comments resolved, CI green, tests passing?

## Workflows

### Full comprehensive fix

```text
1. Inventory → approve
2. Fix feedback (subskill) → review
3. Fix CI (subskill) → review
4. Run full tests → check results
5. Resolve comments individually → verify all addressed
```

### When feedback + CI failures both exist

The workflow doesn't rerun tests after feedback-only (to avoid duplication),
because Step 3 runs the full suite once both feedback and CI fixes are applied.

### When only one type of problem exists

Still follow the full workflow to ensure nothing is missed:

- Feedback-only PR: Skip fix CI, still run full tests, still mark comments
- CI-only PR: Skip fix feedback, still run full tests, verify any comments

## Advanced Features

See [REFERENCE.md](REFERENCE.md) for:

- How file-change detection works (demo/* detection)
- Integration test vs unit-only decision criteria
- Handling partial/unaddressable feedback
- Fallback strategies for complex failures

## Next Steps

1. Run the skill on a problem PR
2. Follow the checkpoint prompts carefully
3. Review code changes before allowing test runs
4. Verify each comment resolution before marking done

---

**Tip**: If CI failures are cryptic or suggest architectural issues, the skill
will stop and ask for human judgment rather than loop endlessly on fixes.

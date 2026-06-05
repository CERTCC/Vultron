# How to fix your first bug

Use this guide when you've encountered a bug in Vultron and want to fix it
following the test-first discipline.

## Overview

Vultron provides a `bugfix` skill that gates implementation on **shared
understanding**. You and the maintainers agree on what the bug is and why
before any code changes happen. This guide walks you through the workflow.

**When to use the bugfix skill**: Whenever you encounter reproducible misbehavior
in the running system (tests, demo, protocol handling).

**When NOT to use it**: For speculative refactoring, optimization, or features
(use the `build` skill instead).

## The workflow at a glance

1. **Identify** — Find or create an issue, claim it
2. **Clarify** — Answer mandatory questions until understanding is shared
3. **Test-first** — Write a failing test that reproduces the bug
4. **Implement** — Fix the bug with minimal scope
5. **Validate** — Run linting, formatting, and full tests
6. **Finalize** — Archive progress, open PR

Most of these steps are handled by the `bugfix` skill; this guide focuses on
the decisions *you* make at each step.

## Get started

Invoke the bugfix skill:

```bash
copilot bugfix
```

If you have an issue number in mind, give it to the skill. Otherwise, the skill
will list open bugs for you to pick from, or let you create a new one.

## Phase 1: Identify (the skill does this)

The skill will:

- Fetch the issue and read its description
- Summarize the bug (title, symptoms, likely files)
- Claim the issue so others know you're working on it

Skim the summary to confirm you're fixing the right bug. If it doesn't match
what you expected, tell the skill to pick a different one.

## Phase 2: Clarify (mandatory — answer the skill's questions)

**Do not skip this phase.** The skill will ask you:

1. **Is this the right bug?** Confirm the issue title and description match
   what you're seeing.

2. **How do you reproduce it?** Describe the steps (e.g., "Run scenario M6
   and watch for timeout" or "Load a case with 50 participants and create
   an embargo update").

3. **What's the expected behavior?** What should happen instead?

4. **What's the scope?** Are we fixing just one file, or are there related
   areas?

5. **Is this isolated, or a symptom?** Does fixing this file address the root,
   or might there be deeper issues? If deeper issues exist, the skill will
   file them as separate bugs and narrow the scope for this one.

**Do not proceed to writing code until every answer is confirmed.**

## Deciding where the bug is

Bugs live in different layers. Your decision tree:

### Is it a parsing or serialization issue?

**Symptoms**: Malformed AS2 input causes crashes, or valid input produces
wrong output format.

**Layer**: Wire layer (`vultron/wire/as2/`).

**Test pattern**: Create an AS2 activity JSON or dict with edge-case values
(missing fields, wrong types, boundary values). Invoke the extractor or parser;
verify it fails cleanly or produces the correct domain object.

**Example stub**:

```python
def test_malformed_activity_missing_actor():
    """Verify parser rejects activity without actor."""
    malformed = {
        "type": "Accept",
        "object": {"type": "Offer", "id": "..."},
        # "actor" field intentionally missing
    }
    with pytest.raises(ValidationError):
        VultronActivity.model_validate(malformed)
```

### Is it a state machine or use-case logic issue?

**Symptoms**: Wrong state transition, incorrect condition checked, or expected
side-effect didn't happen.

**Layer**: Core layer (`vultron/core/`).

**Test pattern**: Create the relevant domain objects (Case, Embargo, Report),
trigger the use-case or behavior-tree, and verify the resulting state or
database record.

**Example stub**:

```python
def test_embargo_lifecycle_owner_transitions():
    """Verify embargo owner can only transition from ACTIVE to REVISE."""
    embargo = Embargo(...)
    embargo_bt = create_embargo_bt(embargo, ...)
    # Set blackboard with embargo_id, trigger_actor (owner)
    assert embargo_bt.tick_once() == py_trees.common.Status.SUCCESS
    # Verify embargo moved to REVISE
    updated = dl.load(Embargo, embargo.id)
    assert updated.state == EmbargoStatus.REVISE
```

### Is it a database or data layer issue?

**Symptoms**: Data doesn't persist, wrong data is returned, or constraint
violations occur.

**Layer**: Adapters (`vultron/adapters/driven/`).

**Test pattern**: Call the DataLayer methods directly with test objects; verify
the database state before and after.

**Example stub**:

```python
def test_datalay_save_case_with_valid_attachments(dl):
    """Verify case with attachments persists correctly."""
    case = VulnerabilityCase(...)
    dl.save(case)
    loaded = dl.load(VulnerabilityCase, case.id)
    assert loaded.vul_title == case.vul_title
    assert len(loaded.attachments) == len(case.attachments)
```

### Is it an HTTP or API routing issue?

**Symptoms**: POST to inbox returns wrong status, wrong handler gets invoked,
or response format is incorrect.

**Layer**: Adapters (`vultron/adapters/driving/fastapi/`).

**Test pattern**: Use FastAPI's test client to POST to the endpoint; verify
the response and any side-effects (database changes, background tasks
submitted).

**Example stub**:

```python
def test_inbox_post_accept_activity():
    """Verify POST /inbox accepts Accept activity and returns 202."""
    app = create_app()
    client = TestClient(app)
    activity = {...}
    response = client.post("/inbox", json=activity)
    assert response.status_code == 202
```

### Is it a multi-layer integration issue?

**Symptoms**: Works in isolation but fails in end-to-end scenarios (demo,
integration tests).

**Layer**: Multiple layers; use integration tests.

**Test pattern**: Mark the test with `@pytest.mark.integration`. Instantiate
a real app with test data; trigger a workflow; verify the result.

**Run the test**:

```bash
uv run pytest -m "" --tb=short 2>&1 | tail -5
```

The `-m ""` flag includes integration tests (CI runs both).

## Write your failing test first

Do **not** implement the fix before the test exists.

1. Create a test file in the `test/` directory mirroring the source layout.
2. Write a test that reproduces the bug. It should **fail** before you fix it.
3. Run the test to confirm it fails:

   ```bash
   uv run pytest test/path/to/test_file.py::test_your_bug -v
   ```

4. Only once the test fails, implement the fix.

**Why test-first?**

- Confirms you understand the bug (if your test doesn't fail with the current
  code, you may have misunderstood)
- Ensures your fix works (the test passes after the fix)
- Prevents regressions (the test catches it if the bug comes back later)

## Implement the fix

Once the test fails and you've clarified scope with the skill:

1. Modify **only** the code needed to make the test pass.
2. Follow all Vultron conventions (see `AGENTS.md` § Naming Conventions and
   [`vultron/core/AGENTS.md`](../../development/code-organization.md) for
   layer-specific rules).
3. Do not pursue incidental bugs you discover — file them separately and focus
   on this one.

## Before you open a PR

Run these checks **in order**:

### 1. Format your code

```bash
uv run black vultron/ test/
```

### 2. Run linters

```bash
uv run flake8 vultron/ test/
uv run mypy
uv run pyright
```

If any checks fail, fix them and reformat.

### 3. Run tests

Run the **default unit test command**:

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

If you touched any files under `vultron/demo/` or `test/demo/`, run the
full suite including integration tests:

```bash
uv run pytest -m "" --tb=short 2>&1 | tail -5
```

Read the tail output. All tests should pass.

### 4. (Optional) Format markdown if you updated docs

```bash
./mdlint.sh
```

## Troubleshooting

### Test hangs indefinitely

**Likely cause**: Async code not properly awaited or event loop not resolved.

**Solution**:

- Ensure all `async` functions are awaited in tests
- Check for `pytest-asyncio` markers if using async fixtures
- Use `pytest` `-v` flag to see which test is hanging, then inspect it

### Test fails with "blackboard key not found" or random failures

**Likely cause**: Behavior tree blackboard is shared between tests (global
state).

**Solution**: Clear the blackboard in your test's `conftest.py`:

```python
@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
```

### Data layer test fails with "constraint violation"

**Likely cause**: Test is reusing an ID or violating a unique constraint.

**Solution**:

- Use unique IDs per test (e.g., UUIDs, or `test_case_id_<test_name>`)
- Check for leftover data in the test database; use a fresh SQLite instance
  per test

### Test passes locally but fails in CI

**Likely cause**: CI runs integration tests; your bug is in a demo or
multi-layer scenario.

**Solution**: Run the full suite locally before pushing:

```bash
uv run pytest -m "" --tb=short 2>&1 | tail -5
```

If tests still pass locally, check for timing or environment differences
(CI uses Python 3.13; your local may be 3.12).

## Finalizing (the skill does this)

Once all tests pass, the bugfix skill will:

1. Archive a history entry recording the bug and fix
2. Ask you to open a PR
3. Suggest commit message and PR title

Follow the skill's guidance. Your PR is now ready for review.

## Next steps

- Monitor your PR for review feedback
- If changes are requested, make them on the same branch
- Once merged, the fix is live in the next release

See also:

- [`test/AGENTS.md`](../../../../test/AGENTS.md) — Testing expectations and patterns
- [`AGENTS.md`](../../../AGENTS.md) § Common Pitfalls — Reference for tricky
  scenarios (BT state, async, integration)
- [How to run tests](run-tests.md) — Test execution details
- [How to run linters and formatters](run-linters-and-formatters.md) — Full
  linting workflow

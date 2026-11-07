# Testing Logic and File Detection

## Test Gate Execution

### One Gate, Always Targeted

The gate is the test files `targeted-tests` derives from the diff, plus
`test/architecture/` and `test/metadata/` (PAD-18-002). No scope escalates it
to the whole suite (PAD-18-003), and no local gate runs one (PAD-18-008,
PAD-18-015): CI runs both suites on every push, and GitHub's required
`CI gate` refuses the merge until that run passes.

**Command**:

```bash
logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"
gate=$(PYTHONPATH= uv run targeted-tests --base origin/<base> --pytest); rc=$?
[ "$rc" -eq 0 ] && { eval "$gate" > "$logs-gate.log" 2>&1; rc=$?; tail -20 "$logs-gate.log"; }; echo "exit: $rc"; (exit $rc)
```

**When**: every fix commit, and the conflict-merge case with
`--paths <conflicted files>` instead of `--base` (PAD-18-015).

**Expected output**: the selected files' pass/fail summary. Paths reported on
stderr as `no test maps to` or `no targeted set bounds` are CI's; that is
expected, not an error.

Full pytest output is written to `"$logs-gate.log"`. **Never re-run the gate
to get more output** — grep or read that file instead.

## Interpreting Test Results

### All Tests Pass ✅

- Proceed to Step 4: Resolve comments individually
- CI will pass on merge

### Unit Tests Fail ❌

**Symptoms**: Test errors, assertion failures, import errors

**Default assumption**: Current PR changes caused the failure until disproven.

**Action**:

1. Display failure output
2. Fix branch-owned issues directly and rerun relevant validations
3. Classify as pre-existing only after:
   - clean-base proof on `main` (or equivalent documented evidence), and
   - at least one causality check against the current PR diff
4. If pre-existing is proven, create/update a Bug issue with evidence via
   `create-issue`, wiring structured blockers, and post a handoff comment
5. If evidence is incomplete, keep treating as PR-owned and continue debugging

### Integration Tests Fail ❌

**Symptoms**: Demo startup failures, protocol errors, CI job timeout

**Default assumption**: Current PR changes caused the failure until disproven.

**Action**:

1. Display failure output (first 50 lines + last 20 for context)
2. Perform targeted causality checks against the PR diff
3. Allow "unrelated/pre-existing" only with clean-base + causality evidence
4. If pre-existing is proven, create/update a Bug issue with evidence via
   `create-issue`, wiring blockers, and add a handoff comment
5. Stop only after recording blocked/unblocked status with linked evidence

**Why caution is needed**: Integration tests are slow and can fail due to:

- Missing environment setup
- Timing issues in demo orchestration
- Architectural breaking changes
- Infrastructure problems (docker, network)

These still require evidence-based triage before any unrelated classification.

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

The skill may **stop and report** after evidence capture if:

- Integration test failure with unclear root cause after causality checks
- 2+ consecutive test failures after `/pr fix ci` attempts
- Test output suggests missing context (env vars, setup, infrastructure)
- Error suggests architectural issue (breaking change to core logic)

In these cases, the skill reports the state with linked Bug issue evidence,
structured blockers, and explicit blocked/unblocked status.

## No Full-Suite Escalation

The file-change detection this section used to describe — demo, adapters,
behavior trees, use cases, the extractor — decided nothing by the time
ADR-0143 landed, and decides nothing now: those paths are gated by their
importers like any other (PAD-18-012). `pr-triage` still records
`needs_integration_tests`, but only as information for a reader; no gate
reads it (`pr-execute/REFERENCE.md`).

`build` runs no suite of its own either, and never will: it hands off to
`create-pr`, whose first-push gate is the linters plus the targeted set
(PAD-18-001, PAD-18-008, PAD-18-017).

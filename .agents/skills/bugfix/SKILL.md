---
name: bugfix
description: >
  Fix a bug using investigate-first discipline. The agent does all its
  homework before talking to the user — reproduces the symptom, forms a
  root-cause hypothesis, scans peer files, and drafts a fix plan. The user
  gets one structured briefing and confirms before any code is written.
---

# Skill: Bugfix

No code is written until the agent has completed its own investigation and
the user has confirmed the plan. The reporter is not omniscient — treat the
issue as a symptom description and determine the facts independently before
presenting findings.

See [REFERENCE.md](REFERENCE.md) for the sibling-scan pattern, escalation
pattern, and archive format.

## Phase 0 — Sync

Move the worktree HEAD to `origin/main` before loading any context. Do **not**
use `git checkout main` — that branch may be checked out in another worktree.

```bash
git fetch origin main && git reset --hard origin/main
```

If this fails, stop and investigate before proceeding.

## Phase 1 — Identify and Claim

1. If the user specified a GitHub issue number, skip to step 3.
2. Query open Bug-type issues and present via `ask_user`. Include a
   **"Create a new bug"** option at the end:

   ```bash
   gh issue list --repo CERTCC/Vultron --limit 200 \
     --json number,title,issueType \
     --jq '.[] | select(.issueType.name == "Bug") | "#\(.number): \(.title)"'
   ```

   If the user selects **"Create a new bug"**: ask for a description,
   synthesize a title, and create the issue:

   ```bash
   BUG_TYPE_ID=$(bash .agents/skills/shared/board-id.sh issue-type Bug)
   ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
     --title "${BUG_TITLE}" \
     --body "${BUG_BODY}" \
     --issue-type-id "${BUG_TYPE_ID}")
   ```

   Immediately after creation, route the new issue onto the epic forest:
   invoke `calve-epics` Mode 1 on `${ISSUE_NUMBER}`. If `calve-epics` reports
   no matching epic, present an `AskUserQuestion` with the top 5 closest open
   epics plus "Specify other epic number". **A parent epic is required** —
   do not proceed to Phase 2 until the issue is wired to a parent.

3. Invoke `orient-agent` to load baseline context.
4. Fetch the issue body and comments.

4.5. **Pre-claim defect verification** — before claiming, verify the
     described defect still exists on `origin/main` HEAD:

     Search for the specific symptom, anti-pattern, or code path described
     in the issue body (grep, `git log -S "<key term>" -- <file>`, or
     graphify query). If the defect cannot be reproduced on `origin/main`,
     it may have been fixed by a prior PR that lacked a `Closes #N` footer.

     If the defect is absent from `origin/main`:

     1. Post a reference comment identifying any PR that likely fixed it:

        ```bash
        gh issue comment <N> --repo CERTCC/Vultron --body "$(cat <<'EOF'
        The described defect is not present on `origin/main`. It appears to
        have been fixed by #<PR> without a `Closes #N` footer. Closing.
        EOF
        )"
        ```

     2. Close the issue:

        ```bash
        gh issue close <N> --repo CERTCC/Vultron
        ```

     3. **Stop.** Do not claim, branch, or investigate further.

     If the defect is confirmed present, proceed to step 5 and claim.

5. Claim the issue:

   ```bash
   bash .agents/skills/shared/claim-issue.sh <N> bug <slug>
   ```

   Abort immediately if this exits non-zero.

## Phase 2 — Investigate (no user questions)

Before presenting anything to the user, complete the full investigation.
The reporter is not omniscient — treat the issue as a symptom description
and determine the facts independently.

### 2a — Verify the symptom exists

Search `vultron/`, `test/`, and `.claude/skills/` for the reported behavior.
Locate the specific file and line where it manifests.

**Prior-fix check**: run `git log -S "<key term>" -- <file>` on `origin/main`
to confirm the bug has not already been fixed by a prior PR that lacked a
`Closes #N` footer. If it is already fixed, post a reference comment and
close the issue. Do not proceed.

### 2b — Identify the root cause

Trace the code path that produces the symptom. Form a specific hypothesis
with file:line evidence — not "looks like X" but "Y at `path/to/file.py:42`
is called with Z, which causes W because...".

### 2c — Verify the hypothesis

Confirm the root cause accounts for the symptom (not just correlated). Ask:
"If I fix this, does the symptom disappear? Could the same symptom arise
from a different path?"

### 2d — Sibling scan (MANDATORY)

Search for the same structural pattern in:

- Peer files in the same directory or module
- Sibling demo scenarios (same naming convention, e.g., `fvcv_*`, `fccv_*`)
- Other actors or handlers that implement the same protocol step

Document each hit with file:line and whether it exhibits the same bug. Do
not skip this step even if the issue body says the bug is isolated. See
[REFERENCE.md](REFERENCE.md) § "Sibling Scan Pattern".

### 2e — Fix options

Identify 1–2 concrete approaches to fix the root cause. For each, note the
key tradeoff (e.g., minimal-invasive vs. root-cause-correct; fix-in-place
vs. file-sibling-issues).

### 2f — Test strategy

Identify the specific failing test that will prove the bug exists. Name it:
"I'll add `test_<what>_<when>_<expected>` in `test/<path>.py`."

### 2g — Deepen context

Invoke `deepen-context` with focus hints derived from the investigation
(e.g., `"BT node write boundary"`, `"EM state transition"`).

## Phase 3 — Present Findings (BLOCKING)

Present a single structured briefing via `ask_user`. Include every item
from Phase 2 with concrete evidence:

```text
Reproduced at: <file:line>
Root cause:    <specific hypothesis with evidence>
Sibling hits:  <list of file:line instances, or "none found">
Proposed fix:  <approach>
Alternative:   <if any>
Test strategy: <specific test name and location>
```

Ask: **"Proceed with this plan, redirect, or narrow scope?"**

- **Confirms**: proceed to Phase 4.
- **Redirects** to a different area: update understanding and return to
  Phase 2 for the redirected scope.
- **Narrows scope**: note which sibling hits will be filed as new Bug issues
  rather than fixed in this PR.

**Do not begin implementation until the user confirms the plan.**

## Phase 4 — Implement

Once the plan is confirmed:

0. **Compose-before-create gate (blocking)**: before writing any new code,
   load `.agents/skills/shared/compose-before-create.md` and apply the
   per-subsystem search patterns for every subsystem the fix touches (use
   cases, wire handlers, adapters, demo helpers). If an existing artifact
   covers the requirement, compose or subclass it — do not re-implement.

1. **Write a failing test first** — confirm it fails before fixing.

   **Regression test exception**: if test infrastructure cost is genuinely
   disproportionate, skip the test but create a follow-up Bug issue explaining
   why. Do not silently omit the test.

2. **Fix the root cause** — not just the symptom. If the root cause is
   provably out of scope, fix the symptom and create a Bug issue for the
   root cause before closing this one.

3. **Handle sibling hits**:
   - Hits small enough to fix in the same PR: fix them.
   - Hits out of scope: file each as a new Bug-type issue via the
     `manage-github-issue` helper. Reference each in the PR description
     (`Also filed: #NNN`). See [REFERENCE.md](REFERENCE.md) § "Escalation".

4. **Iterate**: run `format-code`, `run-linters`, `run-tests`; refine until
   all relevant tests pass. Apply branch-ownership and pre-existing-failure
   rules from `completeness-doctrine.md`.

5. **Finalize**:
   - Invoke `check-docs-sync` to identify any `docs/` updates required by
     the fix (PD-03-007). Apply small updates inline; file a `type:Concern`
     issue for large updates. Do not block the PR on large updates.
   - Invoke `archive-history`:

     ```text
     TYPE    = implementation
     SOURCE  = ISSUE-<N>
     TITLE   = <short bug title>
     BODY    = issue number, symptoms, root cause, fix summary, PR link
     ```

   - Run the **upward-reflection checklist** per
     `.agents/skills/shared/upward-reflection.md`. Record triggered signals
     as learning files.
   - Compute diff size: ≤50 → `size:S`; 51–300 → `size:M`; 301+ → `size:L`.
     Update the `size:` label.
   - Invoke `create-pr`:

     ```text
     type:         implementation
     title:        fix: <short title>
     body:         <per pr-body-guide.md implementation template>
     labels:       size:<X>
     issue_number: <N>
     ```

   - Invoke `commit` if any learning files were created in
     `plan/incoming/learnings/` outside the PR branch.

## Constraints

- Implementation is blocked until the user confirms the Phase 3 plan.
- Follow test-first discipline; never fix before the failing test exists.
- **If the session is interrupted**: invoke `bugfix-handoff` immediately.
  Do not attempt further resolution.

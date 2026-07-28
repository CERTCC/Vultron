---
name: bugfix
description: >
  Fix a bug using test-first development. Gates implementation on confirmed
  shared understanding with the user — no code is written until both the agent
  and the user agree on what bug is being fixed and why. Use when the user
  asks to fix a bug.
---

# Skill: Bugfix

No implementation work begins until both the agent and the user agree on what
bug is being fixed and why.

## Phase 1 — Identify the Bug

1. Invoke `orient-agent` to load baseline context.
2. If the user specified a GitHub issue number, skip to step 4.
3. Query open Bug-type issues and present them via `ask_user`. Include a
   **"Create a new bug"** option at the end:

   ```bash
   gh issue list --repo CERTCC/Vultron --limit 200 \
     --json number,title,issueType \
     --jq '.[] | select(.issueType.name == "Bug") | "#\(.number): \(.title)"'
   ```

   If the user selects **"Create a new bug"**: ask for a description
   (freeform), synthesize a title, and create the issue:

   ```bash
   ISSUE_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
     --title "${BUG_TITLE}" \
     --body "${BUG_BODY}" \
     --issue-type-id "IT_kwDOAjf0s84AcFLq")
   ```

4. Fetch the issue body and comments. Use the content as bug context
   throughout Phases 2–3.
5. Summarize for the user: issue number/title, observed vs. expected
   behaviour, likely file(s)/component(s) involved.
6. **Claim the issue**:

   ```bash
   bash .agents/skills/shared/claim-issue.sh <N> bug <slug>
   ```

   Abort immediately if this exits non-zero.

## Phase 2 — Clarify (BLOCKING)

Before writing any code or tests, use `ask_user` to verify shared
understanding. Ask **one question at a time**. Do **not** skip this phase.

Mandatory questions (stop early if the user signals sufficient clarity):

1. **Confirm the selected bug**: "I'm planning to work on [bug title]. Is that
   the right bug to address right now, or would you prefer a different one?"

2. **Confirm reproduction scenario**: "My understanding of the bug is
   [description]. Does that match what you're seeing?"

3. **Confirm expected behaviour**: "The fix should make [expected behaviour]
   happen. Is that correct?" — Probe for edge-cases if any are unclear.

4. **Confirm scope**: "Do you want this fix scoped to [identified
   files/component], or are there other areas that should change?"

5. **Open questions**: Continue asking until all assumptions are resolved.

**Do not proceed to Phase 2b until every point is explicitly confirmed.**

## Phase 2b — Root Cause Depth (BLOCKING)

Ask one targeted question before locking in scope:

> "My working theory for the root cause is [code path / invariant / data
> flow]. Does this look like an isolated defect, or might it be a symptom of
> a deeper issue in [module / design pattern]?"

- **Isolated defect**: proceed to Phase 3.
- **Deeper issue**: ask which related concerns this fix should address, then
  file each remaining concern as a new Bug-type issue:

  ```bash
  .agents/skills/manage-github-issue/manage_github_issue.sh \
    --title "<short bug title>" \
    --body "## Symptoms
  <one sentence>

  ## Root cause (hypothesis)
  <what was observed during analysis of #N>

  ## Components involved
  - \`path/to/module.py\`" \
    --issue-type-id "IT_kwDOAjf0s84AcFLq"
  ```

  Confirm the narrowed scope before proceeding.

See `specs/bugfix-workflow.yaml` BFW-02-001–BFW-02-004 for question
templates and escalation patterns.

**Do not proceed to Phase 3 until Phase 2b scope is confirmed.**

## Phase 3 — Implement

See `.claude/skills/shared/completeness-doctrine.md` for the project standard
on what "done" means — loaded by `orient-agent` in Phase 1.

Once shared understanding is confirmed, invoke `deepen-context` with
focus hints from Phase 2 (e.g., `"wire layer"`, `"BT integration"`), then:

1. **Verify Before Changes** — Search `vultron/` and `test/` to confirm the
   bug exists as understood. Do not assume; confirm via code search.

2. **Reproduce with a Failing Test** — Add or modify a test that fails due to
   the bug. Confirm the test fails before implementing the fix. A bug fix
   without a regression test is not a bug fix.

   **Regression test exception**: if test infrastructure cost is genuinely
   disproportionate (requires long-running infrastructure or complex setup far
   exceeding the fix's scope), skip the test but create a follow-up GitHub Bug
   issue explaining the specific reason. Do not silently omit the test.

3. **Fix the Root Cause** — Fix what actually caused the bug, not just the
   symptom. If the root cause is provably out of scope, fix the symptom anyway
   but create a Bug issue for the root cause before closing this one. Never
   ship a symptom-only fix without documenting the underlying cause.

4. **Iterate** — Run `format-code`, `run-linters`, `run-tests`; refine until
   all relevant tests pass. Apply branch-ownership and pre-existing-failure
   rules from `completeness-doctrine.md` § "Finding Severity". If pre-existing
   is proven, create/update a Bug issue with evidence, wire structured blockers
   via `manage-github-issue`, and add a handoff comment with pickup context.

5. **Finalize**:
   - Invoke `archive-history`:

     ```text
     TYPE    = implementation
     SOURCE  = ISSUE-<N>
     TITLE   = <short bug title>
     BODY    = issue number, symptoms, root cause, fix summary, PR link
     ```

   - Run the **upward-reflection checklist** per
     `.agents/skills/shared/upward-reflection.md`. Record each triggered signal
     as a learning file.
   - Compute diff size: ≤50 → `size:S`; 51–300 → `size:M`; 301+ → `size:L`.
     Update the `size:` label.
   - Invoke the `create-pr` skill to push and open the PR:

     ```text
     type:         implementation
     title:        fix: <short title>
     body:         <composed per pr-body-guide.md implementation template>
     labels:       size:<X>
     issue_number: <N>
     ```

     `create-pr` performs the rebase on `origin/main`, validates, pushes, and
     returns the PR URL. Use the returned URL in the `archive-history` call.

   - Invoke `commit` if any learning files were created in `plan/incoming/learnings/`
     outside the PR branch.

## Constraints

- Implementation is blocked until **both** Phase 2 and Phase 2b produce
  confirmed shared understanding. Non-negotiable.
- Follow test-first discipline; never fix before the failing test exists.
- **If the session is interrupted**: invoke `bugfix-handoff` immediately.
  Do not attempt further resolution.

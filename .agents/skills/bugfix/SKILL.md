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

1. Invoke the `study-project-docs` skill to load all specs and project context.
2. If the user specified a GitHub issue number, skip to step 4.
3. Query GitHub for open Bug-type issues and present them to the user as a
   multiple-choice list using `ask_user`. Include a **"Create a new bug"**
   option at the end.

   ```bash
   gh issue list --repo CERTCC/Vultron \
     --json number,title,issueType \
     --jq '.[] | select(.issueType.name == "Bug") | "#\(.number): \(.title)"'
   ```

   Build a `choices` array from the results (e.g. `["#42: Wrong state after
   accept", "#51: Demo crashes on empty case", "Create a new bug"]`). Wait for
   the user's selection before continuing.

   If the user selects **"Create a new bug"**: ask the user to describe the bug
   in freeform text (using `ask_user`). Synthesize a short, descriptive title,
   then create a GitHub Bug-type issue:

   ```bash
   REPO_NODE_ID="R_kgDOIn77fA"
   BUG_TYPE_ID="IT_kwDOAjf0s84AcFLq"

   TITLE_JSON=$(printf '%s' "${BUG_TITLE}" \
     | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
   BODY_JSON=$(printf '%s' "${BUG_BODY}" \
     | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

   ISSUE_NUMBER=$(gh api graphql -f query="
   mutation {
     createIssue(input: {
       repositoryId: \"${REPO_NODE_ID}\"
       title: ${TITLE_JSON}
       body: ${BODY_JSON}
       issueTypeId: \"${BUG_TYPE_ID}\"
     }) {
       issue { number }
     }
   }" --jq '.data.createIssue.issue.number')
   echo "Created bug issue #${ISSUE_NUMBER}"
   ```

4. Fetch the selected issue body and comments using
   `github-mcp-server-issue_read` (`method: get` then `method: get_comments`).
   Use the combined content as bug context throughout Phases 2–3.
5. Summarise the selected bug for the user:
   - Issue number / title
   - One-sentence description of the observed vs. expected behaviour
   - The file(s) / component(s) most likely involved
6. **Claim the issue**:
   - Create a branch: `git switch -c bug/<issue-number>-<slug>`
   - If the branch already exists, abort — the bug is already claimed.
   - Assign the issue to the triggering user:
     `gh issue edit <N> --add-assignee @me --repo CERTCC/Vultron`
   - Post a claim comment:
     `gh issue comment <N> --repo CERTCC/Vultron --body "Claimed by <agent-session> on branch bug/<N>-<slug>"`

## Phase 2 — Clarify (BLOCKING)

Before writing any code or tests, use the `ask_user` tool to verify shared
understanding with the user. Ask **one question at a time**. Continue asking
until every open question is resolved. Do **not** skip this phase even if the
bug description looks unambiguous.

Mandatory questions (ask each one in turn; stop early if the user signals
sufficient clarity):

1. **Confirm the selected bug**: "I'm planning to work on [bug title]. Is that
   the right bug to address right now, or would you prefer a different one?"

2. **Confirm reproduction scenario**: "My understanding of the bug is
   [description]. Does that match what you're seeing?" — If no, ask the user
   to describe it in their own words and update your understanding accordingly.

3. **Confirm expected behaviour**: "The fix should make [expected behaviour]
   happen. Is that correct?" — Probe for edge-cases if any are unclear.

4. **Confirm scope**: "Do you want this fix scoped to [identified
   files/component], or are there other areas that should change?" — Ask about
   related tests, docs, or migration concerns.

5. **Open questions**: If any assumption is still unclear after the four
   questions above, continue asking until it is resolved.

**Do not proceed to Phase 2b until the user has explicitly confirmed or
corrected each point.** If the user provides a correction, restate your updated
understanding and ask them to confirm before moving on.

## Phase 2b — Root Cause Depth (BLOCKING)

After Phase 2 alignment is confirmed, check whether the user has already
indicated a broader underlying issue. If not, ask one more targeted question
before locking in scope:

> "My working theory for the root cause is [specific code path / invariant /
> data flow you identified]. Does this look like an isolated defect, or might
> it be a symptom of a deeper issue in [module / design pattern]?"

- If the user says **isolated defect**: proceed to Phase 3.
- If the user says **deeper issue**: ask which of the related concerns this
  fix should address, then file each remaining concern as a new Bug-type
  GitHub issue via the `manage-github-issue` skill:

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

See `specs/bugfix-workflow.yaml` BFW-02-001 through BFW-02-004 and
`notes/bugfix-workflow.md` for question templates and escalation patterns.

**Do not proceed to Phase 3 until Phase 2b scope is confirmed.**

## Phase 3 — Implement

Once shared understanding is confirmed:

1. **Verify Before Changes** — Search `vultron/` and `test/` to confirm the
   bug exists as understood. Do not assume; confirm via code search.

2. **Reproduce with a Failing Test** — Add or modify a test that fails due to
   the bug. Confirm the test fails before implementing the fix.

3. **Implement the Fix** — Modify only the code required to resolve the bug.
   Follow all project conventions (formatting, linting, layer rules).

4. **Iterate** — Invoke `format-code`, then `run-linters`, then `run-tests`;
   refine until all relevant tests pass. Any incidental bugs discovered should
   be filed as Bug-type GitHub issues via `manage-github-issue`; do not pursue
   them now.

5. **Finalize**
   - Archive a completion summary (issue number, symptoms, root cause, fix)
     using `uv run append-history implementation` (see
     `notes/bugfix-workflow.md` for the template).
   - Capture observations, constraints, and open questions in
     `plan/BUILD_LEARNINGS.md`.
   - Compute the actual diff size (total lines added + removed):
     ≤50 lines → `size:S`; 51–300 lines → `size:M`; 301+ lines → `size:L`.
     Update the `size:` label on the issue to match.
   - Push the branch and open a PR:

     ```bash
     git push -u origin bug/<issue-number>-<slug>
     gh pr create --repo CERTCC/Vultron \
       --title "fix: <short title>" \
       --body "Fixes #<N>

     <summary of changes>" \
       --label "size:<X>"
     ```

     "Fixes #N" causes GitHub to close the issue automatically on merge.
   - Reference any new bugs filed during Phase 2b analysis in the PR body
     (e.g., `Also filed: #NNN`).
   - Invoke the `commit` skill if any local files (BUILD_LEARNINGS.md) were
     updated outside the PR branch.

## Constraints

- **Implementation is blocked** until Phase 2 AND Phase 2b both produce
  confirmed shared understanding. This is non-negotiable.
- Follow test-first discipline; never fix before the failing test exists.
- Do not work on implementation-plan tasks while bugs remain.
- Do not pursue incidental bugs discovered during implementation; file them as
  Bug-type GitHub issues via `manage-github-issue` instead.
- When Phase 2b surfaces additional issues, file each as a new Bug-type GitHub
  issue and implement only the confirmed-scope fix in the current run.
- Invoke `format-code`, `run-linters`, and `run-tests` before committing
  (see those skills for exact commands).
- Each run operates in a fresh context; do not carry forward assumptions from
  previous sessions.

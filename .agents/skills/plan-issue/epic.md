# Plan Issue — Epic path

## Phase A — Validate the Epic

Before decomposing, research the Epic against the current codebase and
present a validation brief — do not ask the user to answer these questions;
answer them yourself first, then confirm.

Research and present findings on:

1. **Currency** — What has changed since this Epic was written? Adjacent
   Epics, merged PRs, new specs that affect scope or approach.
2. **Codebase audit** — Which of this Epic's ACs (if any) have been
   partially or fully addressed already? Search `vultron/` and `test/`.
3. **AC gaps** — ACs that should be added or rewritten in light of current
   understanding.
4. **Hierarchy** — Does the Epic still belong under its current parent, or
   has the project structure shifted?
5. **Title/body gaps** — Proposed edits to the Epic title or body if the
   validated understanding differs from what is written.

Present all findings as a brief, ask for confirmation or correction, and
apply any agreed Epic title/body edits before proceeding to Phase B:

```bash
gh issue edit "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --title "<updated title>" \
  --body "<updated body>"
```

## Phase B — Decompose into Tasks

After validating the Epic, propose a decomposition. Present a draft task
breakdown — boundaries, sequencing, AC coverage — and ask "does this look
right, or should we adjust?" rather than asking each question in sequence.

The decomposition should cover:

1. **Decomposition boundaries** — What is one Task vs. two? Avoid both
   over-splitting (trivial Tasks) and under-splitting (Tasks too large to
   implement in a single PR).
2. **Sequencing constraints** — Which Tasks must precede others? This determines
   `blocked-by` relationships.
3. **AC inheritance** — Which of the Epic's ACs map to which Tasks? Every AC
   must be covered by at least one Task.

Signal when the decomposition is stable: "I think we're almost there —
here's the full task breakdown. Got more?" rather than declaring done
unilaterally.

## Docs Output (optional)

- `specs/<topic>.yaml` — Add or amend requirements if Phase A revealed gaps
- `notes/<topic>.md` — Add design decisions or implementation guidance if needed
- ADR in `docs/adr/` if ADR determination recommended one

Docs updates are optional. Skip if Phase A found no gaps.

## Implementation Issues

Create one Task sub-issue per decomposition cluster from Phase B. Wire each as:

- `--blocked-by <N>` for any sequencing constraints
- `--issue-type-id "$(bash .agents/skills/shared/board-id.sh issue-type Task)"`
  (Task type)

```bash
TASK_TYPE_ID=$(bash .agents/skills/shared/board-id.sh issue-type Task)
TASK_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<task title from Phase B>" \
  --body "## Summary
<description>

## Acceptance Criteria
- [ ] AC-1: <from Phase B>

## Reference
Epic: #${ISSUE_NUMBER}" \
  --label "size:<S|M|L>" \
  --issue-type-id "${TASK_TYPE_ID}" \
  --parent "${ISSUE_NUMBER}" \
  [--blocked-by "<prerequisite task number>"])
bash .agents/skills/shared/add-to-project.sh "${TASK_NUMBER}"
```

## Completion

Remove `needs-decomposition` label and post a summary comment:

```bash
gh issue edit "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --remove-label "needs-decomposition"

gh issue comment "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --body "✅ Decomposed into Tasks: $(echo "${TASK_NUMBERS[@]}" | sed 's/ /, #/g; s/^/#/').

$([ -n "${PR_URL}" ] && echo "Docs PR: ${PR_URL}")"
```

**Do NOT archive or close the Epic.** It remains open until all sub-issues
are complete.

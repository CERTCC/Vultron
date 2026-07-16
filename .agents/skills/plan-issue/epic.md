# Plan Issue — Epic path

## Phase A — Validate the Epic

Before decomposing, validate the Epic against current understanding. Cover:

1. **Currency check** — What do we know now that wasn't known when this Epic
   was written? Has adjacent work (e.g., related Epics, merged PRs, new specs)
   changed what this Epic should cover or how it should be scoped?
2. **Codebase audit** — Have any of this Epic's ACs been partially or fully
   addressed already? Search `vultron/` and `test/` before answering.
3. **AC refinement** — Should any ACs be dropped, rewritten, or added in light
   of current understanding?
4. **Hierarchy check** — Does the Epic still belong under its current parent, or
   has the project structure shifted?
5. **Description/title gaps** — Should the Epic title or body be updated to
   reflect the validated understanding? Draft proposed edits if so.

Apply any agreed Epic title/body edits before proceeding to Phase B:

```bash
gh issue edit "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --title "<updated title>" \
  --body "<updated body>"
```

## Phase B — Decompose into Tasks

After validating the Epic, decompose it. Cover:

1. **Decomposition boundaries** — What is one Task vs. two? Avoid both
   over-splitting (trivial Tasks) and under-splitting (Tasks too large to
   implement in a single PR).
2. **Sequencing constraints** — Which Tasks must precede others? This determines
   `blocked-by` relationships.
3. **AC inheritance** — Which of the Epic's ACs map to which Tasks? Every AC
   must be covered by at least one Task.

## Docs Output (optional)

- `specs/<topic>.yaml` — Add or amend requirements if Phase A revealed gaps
- `notes/<topic>.md` — Add design decisions or implementation guidance if needed
- ADR in `docs/adr/` if ADR determination recommended one

Docs updates are optional. Skip if Phase A found no gaps.

## Implementation Issues

Create one Task sub-issue per decomposition cluster from Phase B. Wire each as:

- `--blocked-by <N>` for any sequencing constraints
- `--issue-type-id IT_kwDOAjf0s84AcFLo` (Task type)

```bash
TASK_NUMBER=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<task title from Phase B>" \
  --body "## Summary
<description>

## Acceptance Criteria
- [ ] AC-1: <from Phase B>

## Reference
Epic: #${ISSUE_NUMBER}" \
  --label "size:<S|M|L>" \
  --issue-type-id "IT_kwDOAjf0s84AcFLo" \
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

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
   validated understanding differs from what is written. A new title is a
   done-state claim with no ADR number or spec ID, and the body keeps its
   `Theme:` and `Design idea:` lines, each with its own job (`notes/epic-themes.md`
   § "Epic Titles and Bodies", PAD-02-030 to PAD-02-038).
6. **Governing specs** — The spec topics or groups the Epic as a whole must
   satisfy (from the Spec manifest). Add or refresh a `Governing specs:`
   line in the Epic body; its Tasks narrow it to specific IDs.

Present all findings as a brief, ask for confirmation or correction, and
apply any agreed Epic title/body edits before proceeding to Phase B. Run the
create-time gate on the edited title and body first, and fix every breach it
prints; `gh issue edit` applies no check of its own:

```bash
PYTHONPATH= uv run theme-gate --epic --title "<updated title>" \
  --label "<the Epic's theme label(s), comma-separated>" \
  --body-file - < body.md \
  && gh issue edit "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
    --title "<updated title>" \
    --body-file body.md
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

Docs updates are optional. Skip if Phase A found no gaps. These are planning
docs; name each reader-facing `docs/` page a Task will change in that Task's
ACs instead (`SKILL.md` Phase 8).

## Implementation Issues

Create one Task sub-issue per decomposition cluster from Phase B, each through
**`create-issue`** with type `Task`, reason `planned`, `size:` from the AC
count, `blocked-by` any prerequisite Task for sequencing, and this Epic as the
**suggested parent**. Every Task body carries a `Governing specs:` line (see
`SKILL.md` Phase 8). Keep the `<docs/ page> describes` AC only when a
reader-facing `docs/` page is known to be affected; delete it otherwise.

```text
## Summary
<description>

Governing specs: <spec/group IDs this Task must satisfy>, or "none — <reason>"

## Acceptance Criteria
- [ ] AC-1: <from Phase B>
- [ ] AC-N: <docs/ page> describes <changed behavior>

## Reference
Epic: #<ISSUE_NUMBER>
```

`create-issue` judges each Task's theme from its own content. A Task whose
theme this Epic does not carry goes to a same-theme Epic instead, and the
script refuses it here (PAD-02-017). Tell the user when that happens: a Task
outside the Epic's theme usually means the decomposition has crossed the
Epic's grain.

## Completion

Post a summary comment. Leave the `needs-planning` label alone: the
`epic-needs-planning` workflow removes it once the Epic has children and none
is an open, unblocked Concern or Idea, and a manual removal would be reverted.

```bash
gh issue comment "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --body "✅ Decomposed into Tasks: $(echo "${TASK_NUMBERS[@]}" | sed 's/ /, #/g; s/^/#/').

$([ -n "${PR_URL}" ] && echo "Docs PR: ${PR_URL}")"
```

**Do NOT archive or close the Epic.** It remains open until all sub-issues
are complete.
